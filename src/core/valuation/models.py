"""Public contracts for calibrated player, pick, consensus, and package values."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CalibrationStatus(str, Enum):
    CALIBRATED = "calibrated"
    PARTIALLY_CALIBRATED = "partially_calibrated"
    UNCALIBRATED = "uncalibrated"
    INSUFFICIENT_DATA = "insufficient_data"
    STALE = "stale"


@dataclass(frozen=True)
class NormalizedValuation:
    provider: str
    raw_value: float
    raw_min: float
    raw_max: float
    normalized_value: int
    updated_at: str | None
    source_season: str | None
    confidence_score: int
    freshness: str
    normalization_version: str
    method: str
    # Numeric normalization alone does not prove cross-provider compatibility.
    compatibility_key: str | None = None


@dataclass(frozen=True)
class ConsensusProvider:
    provider: str
    raw_value: float
    normalized_value: int
    weight: float
    freshness: str


@dataclass(frozen=True)
class CanonicalConsensus:
    market_consensus: int | None
    providers_used: tuple[ConsensusProvider, ...]
    provider_spread: int | None
    confidence_score: int
    calibration_status: CalibrationStatus
    warning: str | None

    @property
    def evidence_state(self) -> str:
        if self.market_consensus is None:
            return "MARKET UNAVAILABLE"
        return "MULTI-PROVIDER CONSENSUS" if len(self.providers_used) > 1 else "SINGLE-PROVIDER MARKET"


@dataclass(frozen=True)
class PlayerIntelligenceCard:
    player_id: str
    market_value: int | None
    dtos_intrinsic_value: int | None
    win_now_value: int | None
    rebuild_value: int | None
    future_value: int | None
    trade_value: int | None
    age_score: int | None
    production_score: int | None
    situation_score: int | None
    risk_score: int | None
    liquidity_score: int | None
    confidence_score: int
    calibration_status: CalibrationStatus
    provider_evidence: tuple[ConsensusProvider, ...]
    recommendation: str
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True)
class PackageValue:
    raw_total: int
    adjusted_value: int
    adjustment: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TradeGuardrailResult:
    recommendation_status: str
    reason_code: str | None
    message: str
    offered_value: int
    requested_value: int
    confidence_score: int


@dataclass(frozen=True)
class PlayerMarketFact:
    """Global evidence facts; no manager strategy, ownership or roster fit."""
    player_id: str
    value: int | None
    generation: str
    generated_at: str | None
    source_updated_at: str | None
    retrieved_at: str | None
    freshness: str
    availability: str
    unavailability_reason: str | None
    confidence: int
    evidence_coverage: tuple[str, ...]
    providers_used: tuple[ConsensusProvider, ...]
    calibration_status: str
    agreement: int | None
    warning: str | None
    fallback: bool
    source_times: tuple[dict, ...]

    def to_dict(self) -> dict:
        """JSON-native facts for durable canonical snapshots and API consumers."""
        from dataclasses import asdict
        row = asdict(self)
        for key in ('evidence_coverage', 'providers_used', 'source_times'):
            row[key] = list(row[key])
        return row
