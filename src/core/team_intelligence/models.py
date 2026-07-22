"""Reusable league-relative team grading contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompetitiveWindow(str, Enum):
    ELITE_CONTENDER = "Elite Contender"
    CONTENDER = "Contender"
    PLAYOFF_TEAM = "Playoff Team"
    RETOOLING = "Re-tooling"
    REBUILDING = "Rebuilding"
    FULL_REBUILD = "Full Rebuild"


@dataclass(frozen=True)
class RelativeGrade:
    category: str
    score: int
    grade: str
    percentile: int
    rank: int
    league_size: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TeamIntelligenceCard:
    roster_id: int
    overall: RelativeGrade
    current_contending: RelativeGrade
    dynasty: RelativeGrade
    starting_lineup: RelativeGrade
    depth: RelativeGrade
    positions: dict[str, RelativeGrade]
    draft_capital: RelativeGrade
    youth: RelativeGrade
    future_outlook: RelativeGrade
    roster_flexibility: RelativeGrade
    asset_liquidity: RelativeGrade
    current_window: CompetitiveWindow
    current_strength: int
    future_strength: int
    risk_score: int
    confidence: int
    explanation: tuple[str, ...]
    preseason: bool
    projected_finish: int
    projected_wins: float
    playoff_odds: int
    championship_odds: int


@dataclass(frozen=True)
class LeagueTeamSummary:
    league_strength: int
    average_age: float | None
    average_team_grade: float
    contenders: int
    rebuilders: int
    strongest_position_group: str
    weakest_position_group: str
    parity_score: int
    championship_favorite: int | None
    biggest_risers: str
    biggest_fallers: str
    most_draft_capital: int | None
    least_draft_capital: int | None
    most_flexible_roster: int | None
    oldest_team: int | None
    youngest_team: int | None
    season_label: str
