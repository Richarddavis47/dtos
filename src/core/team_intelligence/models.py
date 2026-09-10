"""Reusable league-relative team grading contracts."""
from __future__ import annotations

from dataclasses import dataclass
from src.core.competitive_window import (
    CompetitiveWindowClassification,
    CompetitiveWindowContract,
)


@dataclass(frozen=True)
class RelativeGrade:
    category: str
    score: int | None
    grade: str
    percentile: int | None
    rank: int | None
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
    competitive_window: CompetitiveWindowContract
    current_strength: int | None
    future_strength: int | None
    risk_score: int | None
    confidence: int
    explanation: tuple[str, ...]
    preseason: bool
    projected_finish: int | None
    projected_wins: float | None
    playoff_odds: int | None
    championship_odds: int | None
    market_asset_strength: RelativeGrade
    production_quality: RelativeGrade
    league_id: str
    generation: str

    @property
    def current_window(self) -> CompetitiveWindowClassification:
        """Backward-compatible presentation alias for the canonical contract."""
        return self.competitive_window.classification


@dataclass(frozen=True)
class LeagueTeamSummary:
    league_strength: int | None
    average_age: float | None
    average_team_grade: float | None
    contenders: int
    rebuilders: int
    strongest_position_group: str
    weakest_position_group: str
    parity_score: int | None
    championship_favorite: int | None
    biggest_risers: str
    biggest_fallers: str
    most_draft_capital: int | None
    least_draft_capital: int | None
    most_flexible_roster: int | None
    oldest_team: int | None
    youngest_team: int | None
    season_label: str
