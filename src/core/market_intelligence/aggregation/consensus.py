"""Canonical market consensus calculated only from normalized provider values."""
from __future__ import annotations

from src.core.market_intelligence.models import MarketConsensus, ProviderQuote
from src.core.valuation import NormalizedValuation, build_canonical_consensus


def build_consensus(asset_id: str, quotes: tuple[ProviderQuote, ...], expected: tuple[str, ...]) -> MarketConsensus:
    available = tuple(item for item in quotes if item.available and item.value is not None and (item.normalized_value is not None or 0 <= item.value <= 1000))
    missing = tuple(name for name in expected if name not in {item.provider for item in available})
    if not available:
        return MarketConsensus(asset_id, None, 0, None, 0, quotes, missing, None, "insufficient_data", (), "Experimental — market calibration has insufficient data.")
    normalized = tuple(
        NormalizedValuation(item.provider, float(item.value), *(item.raw_scale or (0, 1000)), int(item.normalized_value if item.normalized_value is not None else item.value), item.observed_at, None, item.confidence, item.freshness, item.normalization_version or "legacy-canonical", item.normalization_method or "legacy_canonical_passthrough")
        for item in available
    )
    canonical = build_canonical_consensus(normalized, len(expected))
    agreement = max(0, 100 - round((canonical.provider_spread or 0) / 4))
    updated = max((item.observed_at for item in available if item.observed_at), default=None)
    return MarketConsensus(asset_id, canonical.market_consensus, agreement, float(canonical.provider_spread or 0), canonical.confidence_score, quotes, missing, updated, canonical.calibration_status.value, tuple((item.provider, item.weight) for item in canonical.providers_used), canonical.warning)
