"""Draft-pick intelligence contract."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.asset_intelligence.models.asset_evaluation import AssetEvaluation
from src.core.asset_intelligence.models.player_report import AssetRecommendation, RiskReport


@dataclass(frozen=True)
class PickReport:
    season: int
    round: int
    original_owner: str
    current_owner_id: int | None
    dynasty_value: AssetEvaluation
    market_value: AssetEvaluation
    risk: RiskReport
    expected_range: str
    time_horizon: str
    recommendation: AssetRecommendation
    limitations: tuple[str, ...]
