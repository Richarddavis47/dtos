"""Robust consensus calculation that limits outlier influence."""
from __future__ import annotations

from statistics import median, pstdev

from src.core.market_intelligence.models import MarketConsensus, ProviderQuote


def build_consensus(asset_id: str, quotes: tuple[ProviderQuote, ...], expected: tuple[str, ...]) -> MarketConsensus:
    available = tuple(item for item in quotes if item.available and item.value is not None)
    missing = tuple(name for name in expected if name not in {item.provider for item in available})
    if not available:
        return MarketConsensus(asset_id, None, 0, None, 0, quotes, missing, None)
    center = median(item.value for item in available if item.value is not None)
    deviations = [abs(float(item.value) - center) for item in available if item.value is not None]
    scale = median(deviations) or max(center * 0.10, 1)
    weighted = []
    weights = []
    for item in available:
        distance = abs(float(item.value) - center)
        outlier_weight = 1 / (1 + distance / scale)
        weight = max(0.05, item.confidence / 100) * outlier_weight
        weighted.append(float(item.value) * weight)
        weights.append(weight)
    value = round(sum(weighted) / sum(weights))
    dispersion = round(pstdev(float(item.value) for item in available), 2) if len(available) > 1 else 0.0
    normalized = dispersion / max(abs(value), 1)
    agreement = max(0, min(100, round(100 - normalized * 180)))
    coverage = len(available) / max(len(expected), 1)
    provider_confidence = sum(item.confidence for item in available) / len(available)
    confidence = max(0, min(100, round(provider_confidence * 0.45 + agreement * 0.35 + coverage * 100 * 0.20)))
    updated = max((item.observed_at for item in available if item.observed_at), default=None)
    return MarketConsensus(asset_id, value, agreement, dispersion, confidence, quotes, missing, updated)
