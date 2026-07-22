"""Stable, immutable player-value and projection contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DataStatus(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    FALLBACK = "fallback"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ValueMetric:
    value: float | None
    source: str
    status: DataStatus
    confidence: int
    updated_at: str | None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Projection:
    projected_points: float | None
    floor: float | None
    median: float | None
    ceiling: float | None
    confidence: int
    matchup_adjustment: float
    role_adjustment: float
    injury_adjustment: float
    expected_opportunity: str
    usage_share: float | None
    source: str
    status: DataStatus
    updated_at: str | None
    effective_week: int | None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductionWindow:
    label: str
    fantasy_points: float | None
    opportunities: float | None
    targets: float | None
    carries: float | None
    receptions: float | None
    touchdowns: float | None


@dataclass(frozen=True)
class ProductionContext:
    windows: tuple[ProductionWindow, ...]
    volatility: float | None
    consistency: int | None
    trend: str
    source: str
    status: DataStatus
    updated_at: str | None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class LineupValue:
    role: str
    projected_starter: bool
    flex_utility: bool
    superflex_utility: bool
    replacement_points: float
    points_above_replacement: float
    points_above_current_starter: float
    marginal_value: int
    scarcity: int


@dataclass(frozen=True)
class PositionalContext:
    overall_rank: int
    dynasty_rank: int
    weekly_rank: int
    tier: str
    scarcity: int
    replacement_gap: float
    league_supply: int
    elite_advantage: bool


@dataclass(frozen=True)
class PlayerValueProfile:
    player_id: str
    name: str
    position: str
    nfl_team: str
    age: float | None
    portrait_url: str | None
    image_status: str
    fallback_initials: str
    dtos_dynasty: ValueMetric
    market_consensus: ValueMetric
    market_range: tuple[float, float] | None
    contender: ValueMetric
    rebuilder: ValueMetric
    redraft: ValueMetric
    positional_value: ValueMetric
    replacement_adjusted: ValueMetric
    trade_liquidity: ValueMetric
    market_trend: str
    value_gap: float | None
    market_posture: str
    projection: Projection
    production: ProductionContext
    lineup: LineupValue
    positional: PositionalContext
    recommendation: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
