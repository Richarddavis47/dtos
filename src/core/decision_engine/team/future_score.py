"""Future Outlook evaluator."""
from __future__ import annotations

from src.core.decision_engine.assets.pick_evaluator import evaluate_pick_assets
from src.core.decision_engine.assets.player_evaluator import evaluate_player_assets
from src.core.decision_engine.models.evaluation import Evaluation, EvaluationFactor, EvaluationHorizon
from src.core.decision_engine.models.team_profile import TeamProfile
from src.core.decision_engine.team.scoring import clamp, grade


def evaluate_future_outlook(profile: TeamProfile) -> Evaluation:
    player_score, player_factors, player_limits = evaluate_player_assets(profile)
    pick_score, pick_factors, pick_limits = evaluate_pick_assets(profile)
    score = player_score * 0.55 + pick_score * 0.45
    factors = tuple(
        EvaluationFactor(factor.name, factor.value, factor.contribution * 0.55, factor.explanation, factor.source)
        for factor in player_factors
    ) + tuple(
        EvaluationFactor(factor.name, factor.value, factor.contribution * 0.45, factor.explanation, factor.source)
        for factor in pick_factors
    )
    known_share = len(profile.known_ages) / max(1, profile.roster_size)
    confidence = 65 + round(known_share * 20)
    value = clamp(score)
    return Evaluation(
        EvaluationHorizon.FUTURE,
        value,
        grade(value),
        confidence,
        "Age structure and draft flexibility form the v1 future outlook; current wins do not affect it.",
        factors,
        tuple(dict.fromkeys((*player_limits, *pick_limits))),
    )
