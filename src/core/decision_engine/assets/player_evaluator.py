"""Decision Engine adapter for Asset Intelligence player portfolios."""
from __future__ import annotations

from src.core.asset_intelligence.models import AssetContext
from src.core.asset_intelligence.portfolio import evaluate_player_portfolio
from src.core.decision_engine.models.evaluation import EvaluationFactor
from src.core.decision_engine.models.team_profile import TeamProfile


def evaluate_player_assets(profile: TeamProfile) -> tuple[float, tuple[EvaluationFactor, ...], tuple[str, ...]]:
    context = AssetContext(
        profile.league_id,
        profile.active_front_office_id,
        profile.league_settings,
        team_strategy=profile.strategy,
        position_depth={position: room.total_players for position, room in profile.position_rooms.items()},
    )
    result = evaluate_player_portfolio(profile.players, context)
    factors = tuple(
        EvaluationFactor(item.factor, item.observed_value, item.impact, item.explanation, item.source)
        for item in result.evidence
    )
    return float(result.score), factors, result.limitations
