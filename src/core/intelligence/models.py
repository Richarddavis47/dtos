"""Unified orchestration result contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.intelligence.context import IntelligenceContext
from src.core.intelligence.recommendations import UnifiedRecommendation


@dataclass(frozen=True)
class IntelligenceResult:
    context: IntelligenceContext
    decision: Any
    decisions: dict[int, Any]
    player_portfolio: Any
    pick_portfolio: Any
    player_reports: dict[str, Any]
    front_office_model: Any
    trades: tuple[Any, ...]
    market: Any
    player_values: dict[str, Any]
    roster: Any
    recommendation: UnifiedRecommendation
    timings_ms: dict[str, float]
    cache_hit: bool
