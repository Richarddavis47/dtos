"""Current Championship Outlook evaluator."""
from __future__ import annotations

from src.core.decision_engine.models.evaluation import Evaluation, EvaluationFactor, EvaluationHorizon
from src.core.decision_engine.models.team_profile import TeamProfile
from src.core.decision_engine.team.scoring import clamp, grade, relative_score


def evaluate_current_outlook(profile: TeamProfile) -> Evaluation:
    games = profile.wins + profile.losses + profile.ties
    record_score = ((profile.wins + profile.ties * 0.5) / games * 100) if games else 50.0
    points_score = relative_score(profile.points_for, profile.league_points_for)
    max_points_score = relative_score(profile.max_points, profile.league_max_points)
    score = record_score * 0.35 + points_score * 0.35 + max_points_score * 0.30
    limitations = [
        "Weekly projections and elite-player values are not available in Decision Engine v1.",
        "Injury impact is represented as exposure, not a projected points penalty.",
    ]
    confidence = 82
    if not games:
        limitations.append("No completed games are available; record uses a neutral baseline.")
        confidence -= 12
    if len(set(profile.league_points_for)) <= 1:
        limitations.append("League points-for data is flat; the relative points signal is neutral.")
        confidence -= 8
    value = clamp(score)
    return Evaluation(
        EvaluationHorizon.CURRENT,
        value,
        grade(value),
        confidence,
        "Current results, scoring output, and lineup ceiling are evaluated independently from future assets.",
        (
            EvaluationFactor("Record", f"{profile.wins}-{profile.losses}-{profile.ties}", record_score * 0.35, "35% current-outlook weight.", "Sleeper roster record"),
            EvaluationFactor("Points For", f"{profile.points_for:.2f}", points_score * 0.35, "35% league-relative current-outlook weight.", "Sleeper points for"),
            EvaluationFactor("Max PF", f"{profile.max_points:.2f}", max_points_score * 0.30, "30% league-relative lineup-ceiling weight.", "Sleeper potential points"),
        ),
        tuple(limitations),
    )
