"""Central, league-neutral configuration for canonical DTOS valuations."""
from __future__ import annotations

from dataclasses import dataclass, field


VALUATION_SCHEMA_VERSION = "1.0"
NORMALIZATION_VERSION = "1.0"
CANONICAL_MIN = 0
CANONICAL_MAX = 1000


@dataclass(frozen=True)
class ProviderScale:
    minimum: float
    maximum: float
    reliability: float


@dataclass(frozen=True)
class ValuationConfig:
    provider_scales: dict[str, ProviderScale] = field(default_factory=lambda: {
        "FantasyCalc": ProviderScale(0, 12_000, 0.90),
        "DynastyProcess": ProviderScale(0, 10_000, 0.82),
        "DTOS": ProviderScale(0, 100, 0.75),
        "DTOS Pick": ProviderScale(0, 100, 0.72),
    })
    freshness_half_life_hours: float = 168
    minimum_confidence: int = 55
    market_floor_tolerance: float = 0.72
    consolidation_penalty: float = 0.08
    low_value_threshold: int = 300
    elite_asset_threshold: int = 750
    premium_asset_threshold: int = 600
    superflex_qb_premium: float = 1.12
    rookie_pick_adjustments: dict[int, float] = field(default_factory=lambda: {1: 1.08, 2: 1.0, 3: 0.88, 4: 0.78})


DEFAULT_CONFIG = ValuationConfig()
