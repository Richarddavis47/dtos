"""Canonical, rebuildable Step 7 Market Trend contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

TREND_SCHEMA_VERSION = "market-trend-1"
TREND_METHOD_VERSION = "sparse-event-market-trend-1"
COMPACT_TREND_FIELDS = (
    "asset_id",
    "direction",
    "magnitude",
    "magnitude_band",
    "horizon",
    "confidence",
    "checkpoint_count",
    "as_of",
    "schema_version",
    "method_version",
)


class TrendDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    VOLATILE = "volatile"
    INSUFFICIENT = "insufficient_evidence"


@dataclass(frozen=True)
class TrendCheckpoint:
    observation_id: str
    observed_at: str
    value: float
    confidence: int
    reason_codes: tuple[str, ...] = ()
    provider_count: int = 0
    related_asset_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LeagueLiquidity:
    league_id: str
    transaction_count: int
    recent_transaction_count: int
    ownership_turnover_count: int
    distinct_franchises: int
    last_transaction_at: str | None
    confidence: str
    availability: str


@dataclass(frozen=True)
class MarketTrend:
    asset_id: str
    current_value: float | None
    as_of: str
    direction: TrendDirection
    magnitude: float | None
    magnitude_band: str
    horizon: str | None
    confidence: str
    confidence_score: int
    evidence_coverage: str
    checkpoint_count: int
    latest_checkpoint_age_days: int | None
    observed_high: float | None
    observed_low: float | None
    volatility: float | None
    volatility_band: str
    milestones: dict[str, dict[str, Any]] = field(default_factory=dict)
    event_context: tuple[dict[str, Any], ...] = ()
    checkpoints: tuple[TrendCheckpoint, ...] = ()
    league_liquidity: LeagueLiquidity | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = TREND_SCHEMA_VERSION
    method_version: str = TREND_METHOD_VERSION

    def public(self, *, compact: bool = False) -> dict[str, Any]:
        result = asdict(self)
        result["direction"] = self.direction.value
        if compact:
            return {key: result[key] for key in COMPACT_TREND_FIELDS}
        return result
