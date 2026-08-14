"""Compact, permanent DTOS intelligence-memory contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

CHECKPOINT_SCHEMA_VERSION = "1.0"
NORMALIZATION_VERSION = "1.0"


class ProvenanceType(str, Enum):
    """Quality of the historical evidence supporting a checkpoint."""

    LIVE_CAPTURED = "live_captured"
    HISTORICAL_SOURCE_BACKFILL = "historical_source_backfill"
    RECONSTRUCTED = "reconstructed"
    UNAVAILABLE = "unavailable"

    @property
    def definitive_process_evidence(self) -> bool:
        return self in {
            ProvenanceType.LIVE_CAPTURED,
            ProvenanceType.HISTORICAL_SOURCE_BACKFILL,
        }


class CheckpointTrigger(str, Enum):
    TRADE_EXECUTION = "trade_execution"
    WAIVER_ADD = "waiver_add"
    DROP = "drop"
    FANTASY_DRAFT_PICK = "fantasy_draft_pick"
    NFL_DRAFT_PRE = "nfl_draft_pre"
    NFL_DRAFT_SELECTION = "nfl_draft_selection"
    NFL_DRAFT_TEAMMATE_IMPACT = "nfl_draft_teammate_impact"
    NFL_TRADE = "nfl_trade"
    FREE_AGENCY = "free_agency"
    MAJOR_INJURY = "major_injury"
    INJURY_RETURN = "injury_return"
    SUSPENSION = "suspension"
    RETIREMENT = "retirement"
    SEASON_START = "season_start"
    MIDSEASON = "midseason"
    REGULAR_SEASON_END = "regular_season_end"
    FANTASY_SEASON_END = "fantasy_season_end"


class EvidenceCompleteness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SourceObservation:
    provider: str
    raw_value: float | int | None
    observed_at: str | None
    source_identity: str | None
    temporal_distance_seconds: int | None
    normalization_version: str = NORMALIZATION_VERSION
    normalized_value: float | int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntelligenceCheckpoint:
    checkpoint_id: str
    asset_id: str
    asset_type: str
    timestamp: str
    season: int
    trigger_type: CheckpointTrigger
    provenance_type: ProvenanceType
    league_id: str | None = None
    scoring_profile_id: str | None = None
    week: int | None = None
    dtos_value: float | int | None = None
    intrinsic_value: float | int | None = None
    contender_value: float | int | None = None
    rebuilder_value: float | int | None = None
    market_value: float | int | None = None
    confidence: int = 0
    evidence_completeness: EvidenceCompleteness = EvidenceCompleteness.UNAVAILABLE
    model_version: str = "unknown"
    normalization_version: str = NORMALIZATION_VERSION
    brain_identity: str | None = None
    related_event_id: str | None = None
    observations: tuple[SourceObservation, ...] = ()
    knowledge_state: str | None = None
    schema_version: str = CHECKPOINT_SCHEMA_VERSION

    def public(self) -> dict[str, Any]:
        result = asdict(self)
        result["trigger_type"] = self.trigger_type.value
        result["provenance_type"] = self.provenance_type.value
        result["evidence_completeness"] = self.evidence_completeness.value
        return result


@dataclass(frozen=True)
class PickLineage:
    lineage_id: str
    generic_pick_id: str
    season: int
    round: int
    original_roster_id: str
    exact_slot: str | None = None
    selected_player_id: str | None = None
    slot_known_at: str | None = None
    selected_at: str | None = None


@dataclass(frozen=True)
class HistoricalTradeAssessment:
    status: EvidenceCompleteness
    process_grade_eligible: bool
    valued_assets: int
    unavailable_assets: int
    side_totals: dict[str, float | None]
    evidence_checkpoint_ids: tuple[str, ...]
