"""Contextual team input profile."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PositionRoom:
    position: str
    total_players: int
    starters: int
    injured: int
    average_age: float | None


@dataclass(frozen=True)
class TeamProfile:
    roster_id: int
    owner_name: str
    team_name: str
    league_id: str
    active_front_office_id: int
    league_settings: dict[str, Any]
    strategy: str
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    max_points: float
    league_points_for: tuple[float, ...]
    league_max_points: tuple[float, ...]
    roster_size: int
    known_ages: tuple[float, ...]
    starter_ages: tuple[float, ...]
    young_player_count: int
    veteran_player_count: int
    draft_pick_count: int
    first_round_pick_count: int
    position_rooms: dict[str, PositionRoom]
    market_context: dict[str, Any]
    players: tuple[dict[str, Any], ...]
    picks: tuple[dict[str, Any], ...]
