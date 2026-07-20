"""Contextual deterministic team recommendation engine."""
from __future__ import annotations

from src.core.decision_engine.models.decision import TeamWindow
from src.core.decision_engine.models.evaluation import Evaluation
from src.core.decision_engine.models.recommendation import Recommendation, RecommendationCategory, RecommendationPriority
from src.core.decision_engine.models.team_profile import TeamProfile
from src.core.decision_engine.recommendations.confidence_calculator import calculate_confidence
from src.core.decision_engine.recommendations.reasoning_builder import build_reasoning, supporting_metrics


def build_recommendations(
    profile: TeamProfile,
    current: Evaluation,
    future: Evaluation,
    depth: Evaluation,
    assets: Evaluation,
    positions: dict[str, Evaluation],
    window: TeamWindow,
) -> tuple[Recommendation, ...]:
    recommendations: list[Recommendation] = []
    if window in {TeamWindow.CHAMPIONSHIP, TeamWindow.PLAYOFF}:
        recommendations.append(
            Recommendation(
                "Protect the active competitive window",
                "Prioritize moves that preserve current lineup strength while checking their future-asset cost.",
                RecommendationPriority.HIGH if window is TeamWindow.CHAMPIONSHIP else RecommendationPriority.MEDIUM,
                calculate_confidence(current, future),
                RecommendationCategory.COMPETE,
                build_reasoning(f"The team is classified in the {window.value}", current, future),
                supporting_metrics(current, future),
                {"engine": "trade-intelligence", "window": window.value},
            )
        )
    elif window is TeamWindow.REBUILD:
        recommendations.append(
            Recommendation(
                "Preserve rebuild flexibility",
                "Avoid treating short-term roster coverage as more valuable than future optionality without a documented reason.",
                RecommendationPriority.HIGH,
                calculate_confidence(current, future, assets),
                RecommendationCategory.REBUILD,
                build_reasoning("The team is classified in the Rebuild Window", current, future, assets),
                supporting_metrics(current, future, assets),
                {"engine": "trade-intelligence", "window": window.value},
            )
        )
    elif window is TeamWindow.ASCENSION:
        recommendations.append(
            Recommendation(
                "Hold the ascending core unless value is clear",
                "Preserve future strength while monitoring opportunities to improve the current outlook.",
                RecommendationPriority.MEDIUM,
                calculate_confidence(current, future),
                RecommendationCategory.HOLD,
                build_reasoning("Future outlook currently exceeds current outlook", current, future),
                supporting_metrics(current, future),
                {"engine": "player-intelligence", "window": window.value},
            )
        )
    weakest_position, weakest = min(positions.items(), key=lambda item: (item[1].score, item[0]))
    if weakest.score < 70:
        recommendations.append(
            Recommendation(
                f"Review {weakest_position} depth options",
                f"Audit internal, waiver, and trade options for {weakest_position} without assuming an available player is an upgrade.",
                RecommendationPriority.HIGH if weakest.score < 50 else RecommendationPriority.MEDIUM,
                calculate_confidence(weakest, depth, adjustment=5),
                RecommendationCategory.WAIVER if weakest.score < 50 else RecommendationCategory.MONITOR,
                build_reasoning(f"{weakest_position} is the lowest-rated core position room", weakest, depth),
                supporting_metrics(weakest, depth),
                {"engine": "player-intelligence", "position": weakest_position, "active_front_office_id": profile.active_front_office_id},
            )
        )
    if assets.score < 60:
        recommendations.append(
            Recommendation(
                "Protect asset flexibility",
                "Review draft capital and positional balance before committing additional future assets.",
                RecommendationPriority.MEDIUM,
                calculate_confidence(assets, future),
                RecommendationCategory.MONITOR,
                build_reasoning("Asset Health is below the foundation threshold", assets, future),
                supporting_metrics(assets, future),
                {"engine": "draft-intelligence", "active_front_office_id": profile.active_front_office_id},
            )
        )
    if not recommendations:
        recommendations.append(
            Recommendation(
                "Monitor context before acting",
                "No decision horizon currently crosses a deterministic action threshold; review new data before making a reactive move.",
                RecommendationPriority.LOW,
                calculate_confidence(current, future, depth, assets),
                RecommendationCategory.MONITOR,
                build_reasoning("No action threshold is currently crossed", current, future, depth, assets),
                supporting_metrics(current, future, depth, assets),
                {"engine": "recommendation-engine", "active_front_office_id": profile.active_front_office_id},
            )
        )
    order = {RecommendationPriority.HIGH: 0, RecommendationPriority.MEDIUM: 1, RecommendationPriority.LOW: 2}
    return tuple(sorted(recommendations, key=lambda item: (order[item.priority], -item.confidence.value, item.title)))
