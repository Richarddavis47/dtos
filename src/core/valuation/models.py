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


@dataclass(frozen=True)
class PlayerIntelligenceCard:
    player_id: str
    market_value: int | None
    dtos_intrinsic_value: int
    win_now_value: int
    rebuild_value: int
    future_value: int
    trade_value: int
    age_score: int
    production_score: int
    situation_score: int
    risk_score: int
    liquidity_score: int
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
