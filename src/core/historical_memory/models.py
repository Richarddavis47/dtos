"""Versioned historical evidence contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

HISTORICAL_SCHEMA_VERSION = "1.0"
PLAYER_HISTORY_SCHEMA_VERSION = "1.0"
PREDICTION_MODEL_VERSION = "1.0"
DATABASE_MIGRATION_VERSION = 1


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


JsonObject = dict[str, Any]
