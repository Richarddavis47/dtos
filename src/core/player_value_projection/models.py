"""Stable, immutable player-value and projection contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    projection_snapshot_id: str | None = None
    rest_of_season_points: float | None = None
    rest_of_season_games: int | None = None
    season_projected_points: float | None = None
    agreement: int | None = None
    freshness: str = "unavailable"


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
    actual_starter: bool
    flex_utility: bool
    superflex_utility: bool
    replacement_points: float | None
    points_above_replacement: float | None
    points_above_current_starter: float | None
    marginal_value: int | None
    scarcity: int | None


@dataclass(frozen=True)
class PositionalContext:
    overall_rank: int | None
    dynasty_rank: int | None
    weekly_rank: int | None
    tier: str
    scarcity: int | None
    replacement_gap: float | None
    league_supply: int
    elite_advantage: bool | None
    rank_scope: str = "roster"
    scoped_ranks: dict[str, Any] = field(default_factory=dict)


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
    intelligence_card: Any = None
