"""Versioned historical evidence contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

HISTORICAL_SCHEMA_VERSION = "1.0"
PLAYER_HISTORY_SCHEMA_VERSION = "2.0"
HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION = "1.0"
PREDICTION_MODEL_VERSION = "1.0"
DATABASE_MIGRATION_VERSION = 5
IMPORTER_VERSION = "1.2"


class Availability(str, Enum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    ESTIMATED = "estimated"
    CALCULATED = "calculated"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "provider_not_supported"


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_record_id: str
    retrieved_at: str
    observed_at: str
    season: int | None
    week: int | None
    availability: Availability
    confidence: int
    calculation_method: str
    derived: bool = False


@dataclass(frozen=True)
class HistorySignal:
    signal: str
    status: str
    strength: int
    evidence: tuple[str, ...]
    confidence: int
    date_range: str
    model_version: str = PLAYER_HISTORY_SCHEMA_VERSION


@dataclass(frozen=True)
class ImportSummary:
    run_id: str
    league_id: str
    seasons: tuple[int, ...]
    status: str
    records_written: int
    records_unchanged: int
    errors: tuple[str, ...]
    started_at: str
    completed_at: str | None
    workbook_status: str
    checkpoint: str | None


@dataclass(frozen=True)
class HistoricalAssetEvent:
    event_id: str
    asset_id: str
    asset_type: str
    event_type: str
    event_status: str
    season: int
    week: int | None
    occurred_at: str | None
    observed_at: str
    source_league_id: str
    parent_id: str | None
    from_franchise_id: str | None
    to_franchise_id: str | None
    original_franchise_id: str | None
    source_provider: str
    source_record_id: str
    provenance: tuple[str, ...]
    completeness: str
    missing_reasons: tuple[str, ...]
    schema_version: str = HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION
    importer_version: str = IMPORTER_VERSION


@dataclass(frozen=True)
class OwnershipInterval:
    asset_id: str
    franchise_id: str
    acquisition_event_id: str
    acquired_at: str | None
    disposition_event_id: str | None
    disposed_at: str | None
    duration_days: int | None
    season: int
    season_end_owner: bool
    source_event_ids: tuple[str, ...]
    reconciliation_status: str
    schema_version: str = HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION


@dataclass(frozen=True)
class PlayerSeasonSummary:
    player_id: str
    season: int
    scoring_settings_version: str
    games_observed: int
    starts: int
    bench_appearances: int
    fantasy_points: float | None
    points_per_game: float | None
    overall_rank: int | None
    positional_rank: int | None
    starter_points: float | None
    end_of_season_franchise_id: str | None
    franchise_ids: tuple[str, ...]
    completeness_percentage: float
    missing_weeks: tuple[int, ...]
    source_record_ids: tuple[str, ...]
    status: str
    calculation_version: str = PLAYER_HISTORY_SCHEMA_VERSION


JsonObject = dict[str, Any]
