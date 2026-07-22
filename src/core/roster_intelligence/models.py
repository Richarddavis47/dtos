"""Immutable, presentation-neutral Roster Intelligence contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeDimension:
    name: str
    score: int
    grade: str
    reasoning: str


@dataclass(frozen=True)
class PlayerCard:
    player_id: str
    tier: str
    overall_grade: str
    overall_score: int
    age_curve: str
    market_trend: str
    market_value: int | None
    dynasty_value: int
    contender_value: int
    rebuilder_value: int
    trade_liquidity: int
    scarcity: int
    risk: str
    weekly_ceiling: int
    weekly_floor: int
    production_outlook: str
    future_outlook: str
    recommended_action: str


@dataclass(frozen=True)
class PositionRoomReport:
    position: str
    overall: GradeDimension
    dimensions: tuple[GradeDimension, ...]
    league_rank: int
    league_size: int
    advantage: str | None
    reasoning: tuple[str, ...]


@dataclass(frozen=True)
class RosterReport:
    identity: str
    identity_reasoning: str
    rooms: dict[str, PositionRoomReport]
    players: dict[str, PlayerCard]
    metrics: dict[str, object]
    strongest_position: str
    weakest_position: str
    positional_advantages: tuple[str, ...]
    limitations: tuple[str, ...]
    league_rooms: dict[int, dict[str, int]]
    league_players: dict[int, dict[str, PlayerCard]]
    league_metrics: dict[int, dict[str, float]]
