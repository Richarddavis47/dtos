"""Public, immutable Market Intelligence contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ValueGapLabel(str, Enum):
    UNDERVALUED = "Undervalued"
    OVERVALUED = "Overvalued"
    FAIR = "Fairly Valued"
    UNCERTAIN = "High Uncertainty"


@dataclass(frozen=True)
class ProviderQuote:
    provider: str
    asset_id: str
    value: float | None
    confidence: int
    observed_at: str | None
    source: str
    available: bool
    detail: str
    latency_ms: float = 0.0
    cached: bool = False
    retrieval_mode: str = "unavailable"
    retrieved_at: str | None = None
    cache_age_seconds: float | None = None
    freshness: str = "unavailable"
    confidence_impact: int = 0
    normalized_value: int | None = None
    raw_scale: tuple[float, float] | None = None
    normalization_version: str | None = None
    normalization_method: str | None = None


@dataclass(frozen=True)
class MarketEvidence:
    factor: str
    observed_value: str
    impact: float
    explanation: str
    source: str
    available: bool = True


@dataclass(frozen=True)
class MarketConsensus:
    asset_id: str
    value: int | None
    agreement: int
    dispersion: float | None
    confidence: int
    quotes: tuple[ProviderQuote, ...]
    missing_providers: tuple[str, ...]
    updated_at: str | None
    calibration_status: str = "uncalibrated"
    provider_weights: tuple[tuple[str, float], ...] = ()
    warning: str | None = None


@dataclass(frozen=True)
class MarketTrend:
    direction: str
    momentum: float
    volatility: float
    confidence_drift: float
    periods: dict[str, float | None]


@dataclass(frozen=True)
class ValueGap:
    intrinsic_value: int
    market_value: int | None
    difference: int | None
    percentage: float | None
    label: ValueGapLabel
    confidence: int


@dataclass(frozen=True)
class AssetMarketReport:
    asset_id: str
    label: str
    consensus: MarketConsensus
    value_gap: ValueGap
    trend: MarketTrend
    opportunity: str
    evidence: tuple[MarketEvidence, ...]


@dataclass(frozen=True)
class TradeMarketImpact:
    active_roster_id: int
    partner_roster_id: int
    market_gain_loss: int | None
    current_consensus: str
    expected_movement: str
    potential_arbitrage: str
    evidence: tuple[MarketEvidence, ...]


@dataclass(frozen=True)
class MarketIntelligenceReport:
    assets: dict[str, AssetMarketReport]
    opportunities: tuple[AssetMarketReport, ...]
    trade_impacts: tuple[TradeMarketImpact, ...]
    evidence: tuple[MarketEvidence, ...]
    provider_health: dict[str, dict[str, object]]
    generated_at: str
    offline: bool
