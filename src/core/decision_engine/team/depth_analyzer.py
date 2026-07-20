"""Position-level depth and injury-exposure evaluation."""
from __future__ import annotations

from statistics import mean

from src.core.decision_engine.league.positional_scarcity import positional_scarcity
from src.core.decision_engine.models.evaluation import Evaluation, EvaluationFactor, EvaluationHorizon
from src.core.decision_engine.models.team_profile import TeamProfile
from src.core.decision_engine.team.scoring import clamp, grade

TARGETS = {"QB": (3, 1), "RB": (7, 2), "WR": (9, 3), "TE": (4, 1)}


def evaluate_position_depth(profile: TeamProfile, position: str) -> Evaluation:
    room = profile.position_rooms[position]
    total_target, starter_target = TARGETS[position]
    roster_score = min(room.total_players / total_target, 1) * 55
    starter_score = min(room.starters / starter_target, 1) * 35
    injury_penalty = min(room.injured / max(1, room.total_players), 1) * 20
    scarcity, scarcity_detail = positional_scarcity(profile.market_context, position)
    score = roster_score + starter_score + 10 - injury_penalty
    value = clamp(score)
    confidence = 90 if room.total_players else 80
    return Evaluation(
        EvaluationHorizon.DEPTH,
        value,
        grade(value),
        confidence,
        f"{position} depth measures coverage and injury exposure, not player quality.",
        (
            EvaluationFactor("Room coverage", f"{room.total_players}/{total_target}", roster_score, "55-point coverage component.", "Sleeper roster"),
            EvaluationFactor("Starter coverage", f"{room.starters}/{starter_target}", starter_score, "35-point starter component.", "Sleeper lineup"),
            EvaluationFactor("Injury exposure", f"{room.injured} flagged", -injury_penalty, "Up to a 20-point exposure penalty.", "Sleeper injury status"),
            EvaluationFactor("League scarcity context", f"{scarcity}/100 scarcity", 10.0, scarcity_detail, "League rostered position supply"),
        ),
        ("Player quality, replacement availability, and weekly projections are future inputs.",),
    )


def evaluate_depth(profile: TeamProfile) -> tuple[Evaluation, dict[str, Evaluation]]:
    positions = {position: evaluate_position_depth(profile, position) for position in TARGETS}
    score = mean(item.score for item in positions.values())
    value = clamp(score)
    return (
        Evaluation(
            EvaluationHorizon.DEPTH,
            value,
            grade(value),
            round(mean(item.confidence for item in positions.values())),
            "Core position rooms are evaluated independently and then summarized for navigation and recommendations.",
            tuple(
                EvaluationFactor(position, f"{evaluation.score}/100", evaluation.score / 4, "Equal-weight position contribution.", "Position depth evaluator")
                for position, evaluation in positions.items()
            ),
            ("The depth summary is not an overall team score and does not combine current or future outlooks.",),
        ),
        positions,
    )
