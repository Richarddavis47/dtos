"""Canonical derived contracts for historical transaction intelligence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


HISTORICAL_TRANSACTION_SCHEMA_VERSION = "historical-transaction-intelligence-1"
HISTORICAL_TRANSACTION_METHOD_VERSION = "historical-trade-process-outcome-1"


class ProcessClassification(StrEnum):
    STRONG = "strong_process"
    SOUND = "sound_process"
    DEFENSIBLE = "defensible_optional"
    QUESTIONABLE = "questionable_process"
    POOR = "poor_process"
    INSUFFICIENT = "insufficient_evidence"
    BLOCKED = "evaluation_blocked_invalid_historical_state"


class OutcomeClassification(StrEnum):
    STRONG_POSITIVE = "strong_positive_outcome"
    POSITIVE = "positive_outcome"
    MIXED = "mixed_neutral"
    NEGATIVE = "negative_outcome"
    STRONG_NEGATIVE = "strong_negative_outcome"
    NOT_MATURE = "outcome_not_yet_mature"
    INSUFFICIENT = "insufficient_evidence"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class HistoricalDecisionDimension:
    name: str
    assessment: str
    explanation: str
    evidence_available: bool = True


@dataclass(frozen=True)
class HistoricalProcessEvaluation:
    classification: ProcessClassification
    confidence: ConfidenceLevel
    dimensions: tuple[HistoricalDecisionDimension, ...]
    explanation: tuple[str, ...]
    known_outgoing_value: float
    known_incoming_value: float
    market_coverage_ratio: float
    missing_asset_ids: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalOutcomeEvaluation:
    classification: OutcomeClassification
    confidence: ConfidenceLevel
    maturity: str
    as_of: str
    dimensions: tuple[HistoricalDecisionDimension, ...]
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalTradeSideEvaluation:
    franchise_id: str
    pre_state_id: str
    post_state_id: str
    later_state_id: str | None
    process: HistoricalProcessEvaluation
    outcome: HistoricalOutcomeEvaluation


@dataclass(frozen=True)
class HistoricalTradeEvaluation:
    evaluation_id: str
    league_id: str
    event_id: str
    occurred_at: str
    season: int
    sides: tuple[HistoricalTradeSideEvaluation, ...]
    evidence_references: tuple[str, ...]
    history_generation: str
    market_generation: str
    as_of: str
    schema_version: str = HISTORICAL_TRANSACTION_SCHEMA_VERSION
    method_version: str = HISTORICAL_TRANSACTION_METHOD_VERSION

    def private_contract(self) -> dict[str, Any]:
        """Return the authenticated league-scoped structured evaluation."""
        return asdict(self)


@dataclass(frozen=True)
class HistoricalBacklogMetrics:
    league_id: str
    trades_discovered: int
    trades_evaluated: int
    reused: int
    insufficient_evidence: int
    invalid_state_blocked: int
    process_confidence: Mapping[str, int]
    outcome_maturity: Mapping[str, int]
    provider_calls: int
    raw_history_scans: int
    cursor: int = 0
    next_cursor: int | None = None
    completed: bool = True
    method_version: str = HISTORICAL_TRANSACTION_METHOD_VERSION
