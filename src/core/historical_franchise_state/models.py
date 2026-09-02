"""Presentation-neutral contracts for historical franchise state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Mapping


HISTORICAL_FRANCHISE_STATE_SCHEMA_VERSION = "historical-franchise-state-1"
HISTORICAL_FRANCHISE_STATE_METHOD_VERSION = "reverse-event-reconstruction-1"


class BoundaryMode(StrEnum):
    BEFORE = "before"
    AT_OR_BEFORE = "at_or_before"


class ReconstructionAvailability(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


class CoverageDimension(StrEnum):
    SETTINGS = "settings"
    OWNERSHIP = "ownership"
    PICKS = "picks"
    MARKET = "market"
    LINEUP = "lineup"
    PRODUCTION = "production"
    STANDINGS = "standings"
    AGE = "age"
    COMPETITIVE_WINDOW = "competitive_window"


@dataclass(frozen=True)
class HistoricalBoundary:
    season: int
    occurred_at: str | None = None
    week: int | None = None
    event_id: str | None = None
    mode: BoundaryMode = BoundaryMode.AT_OR_BEFORE

    def __post_init__(self) -> None:
        if not self.occurred_at and self.week is None and not self.event_id:
            raise ValueError("A historical boundary requires time, week, or event identity.")


@dataclass(frozen=True)
class EvidenceCoverage:
    availability: ReconstructionAvailability
    confidence: int
    reason_codes: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalAssetState:
    asset_id: str
    asset_type: str
    position: str | None = None
    market_value: float | None = None
    market_checkpoint_id: str | None = None
    market_observed_at: str | None = None
    market_confidence: int | None = None
    season_to_date_points: float | None = None
    age_as_of: float | None = None


@dataclass(frozen=True)
class HistoricalLineupState:
    actual_starters: tuple[str, ...] = ()
    optimal_starters: tuple[str, ...] = ()
    actual_points: float | None = None
    optimal_points: float | None = None
    evidence_week: int | None = None


@dataclass(frozen=True)
class HistoricalRecordState:
    wins: int
    losses: int
    ties: int
    points_for: float
    rank: int | None
    games_observed: int


@dataclass(frozen=True)
class HistoricalWindowState:
    classification: str | None
    confidence: int
    championship_score: int | None = None
    playoff_score: int | None = None
    rebuild_score: int | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalFranchiseState:
    state_id: str
    league_id: str
    franchise_id: str
    boundary: HistoricalBoundary
    history_generation: str
    market_generation: str
    availability: ReconstructionAvailability
    confidence: int
    league_settings: Mapping[str, Any]
    scoring_settings: Mapping[str, Any]
    roster_positions: tuple[str, ...]
    players: tuple[HistoricalAssetState, ...]
    draft_picks: tuple[HistoricalAssetState, ...]
    lineup: HistoricalLineupState
    record: HistoricalRecordState
    competitive_window: HistoricalWindowState
    roster_market_value: float | None
    known_market_value: float
    market_coverage_ratio: float
    position_counts: Mapping[str, int]
    coverage: Mapping[str, EvidenceCoverage]
    warnings: tuple[str, ...]
    evidence_references: tuple[str, ...]
    events_applied: int
    trace: tuple[Mapping[str, Any], ...] = field(default=(), compare=False)
    schema_version: str = HISTORICAL_FRANCHISE_STATE_SCHEMA_VERSION
    method_version: str = HISTORICAL_FRANCHISE_STATE_METHOD_VERSION

    def public_contract(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["boundary"]["mode"] = self.boundary.mode.value
        payload["availability"] = self.availability.value
        for row in payload["coverage"].values():
            row["availability"] = row["availability"].value
        return payload


@dataclass(frozen=True)
class StateDifference:
    before_state_id: str
    after_state_id: str
    players_added: tuple[str, ...]
    players_removed: tuple[str, ...]
    picks_added: tuple[str, ...]
    picks_removed: tuple[str, ...]
    known_market_value_delta: float | None
    changed_dimensions: tuple[str, ...]
