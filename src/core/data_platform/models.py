"""Stable contracts for external data, provenance, health, and refresh state."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"


class LicensingTier(str, Enum):
    PUBLIC_API = "Public API"
    API_KEY = "User API Key Required"
    COMMERCIAL = "Licensed Commercial Data"
    PARTNER = "Partner Integration"
    UNSUPPORTED = "Unsupported"


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    category: str
    version: str
    licensing_tier: LicensingTier
    enabled: bool
    supports_live_refresh: bool
    supports_scheduled_refresh: bool
    refresh_seconds_in_season: int
    refresh_seconds_offseason: int


@dataclass(frozen=True)
class DataQuality:
    status: str
    issues: tuple[str, ...]
    score: int


@dataclass(frozen=True)
class DataEnvelope:
    key: str
    category: str
    value: Any
    source: str
    provider: str
    timestamp: str
    freshness: str
    confidence: int
    cache_state: str
    retrieval_mode: str
    quality: DataQuality
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    status: ProviderStatus
    last_refresh: str | None
    last_success: str | None
    last_failure: str | None
    next_refresh: str | None
    cache_status: str
    freshness: str
    latency_ms: float
    confidence: int
    rate_limits: str
    licensing_tier: LicensingTier
    failure_reason: str | None


@dataclass(frozen=True)
class ConsensusResult:
    key: str
    value: float | None
    confidence: int
    variance: float | None
    agreement: int
    bullish_sources: tuple[str, ...]
    bearish_sources: tuple[str, ...]
    missing_providers: tuple[str, ...]
    sources: tuple[DataEnvelope, ...]


@dataclass(frozen=True)
class TrendResult:
    key: str
    absolute_change: float | None
    percentage_change: float | None
    momentum: float
    volatility: float
    direction: str
    periods: dict[str, float | None]


@dataclass(frozen=True)
class RefreshResult:
    provider: str
    category: str
    status: str
    refreshed_at: str
    records: int
    detail: str
