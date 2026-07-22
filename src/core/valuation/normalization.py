"""Provider-aware conversion to the canonical 0-1000 comparison scale."""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp
from typing import Iterable

from src.core.valuation.config import CANONICAL_MAX, DEFAULT_CONFIG, NORMALIZATION_VERSION, ValuationConfig
from src.core.valuation.models import NormalizedValuation


def _freshness(updated_at: str | None, config: ValuationConfig) -> tuple[str, int]:
    if not updated_at:
        return "unknown", 70
    try:
        observed = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        observed = observed if observed.tzinfo else observed.replace(tzinfo=timezone.utc)
        hours = max(0.0, (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds() / 3600)
    except ValueError:
        return "unknown", 60
    factor = exp(-hours / max(config.freshness_half_life_hours, 1))
    return ("fresh" if hours <= 48 else "aging" if hours <= 336 else "stale"), round(100 * factor)


def normalize_value(
    provider: str,
    raw_value: float,
    *,
    distribution: Iterable[float] = (),
    updated_at: str | None = None,
    source_season: str | None = None,
    provider_confidence: int = 70,
    config: ValuationConfig = DEFAULT_CONFIG,
) -> NormalizedValuation:
    scale = config.provider_scales.get(provider)
    if scale is None:
        return NormalizedValuation(provider, float(raw_value), 0, 0, 0, updated_at, source_season, 0, "unknown", NORMALIZATION_VERSION, "unsupported_provider")
    raw = max(scale.minimum, min(scale.maximum, float(raw_value)))
    ratio = (raw - scale.minimum) / max(scale.maximum - scale.minimum, 1)
    population = sorted(float(item) for item in distribution if item is not None and scale.minimum <= float(item) <= scale.maximum)
    if len(population) >= 10:
        below = sum(item < raw for item in population)
        equal = sum(item == raw for item in population)
        percentile = (below + equal * 0.5) / len(population)
        canonical = round(CANONICAL_MAX * (ratio * 0.70 + percentile * 0.30))
        method = "provider_range_70_percentile_30"
    else:
        canonical = round(CANONICAL_MAX * ratio)
        method = "provider_range_linear"
    freshness, freshness_confidence = _freshness(updated_at, config)
    confidence = round(min(100, max(0, provider_confidence)) * scale.reliability * freshness_confidence / 100)
    return NormalizedValuation(provider, float(raw_value), scale.minimum, scale.maximum, max(0, min(CANONICAL_MAX, canonical)), updated_at, source_season, confidence, freshness, NORMALIZATION_VERSION, method)


def normalize_internal(value: float) -> int:
    """Convert a legacy DTOS 0-100 score without treating it as provider market data."""
    return max(0, min(CANONICAL_MAX, round(float(value) * 10)))


def normalize_pick(value: float, round_number: int, config: ValuationConfig = DEFAULT_CONFIG) -> int:
    base = normalize_internal(value)
    return max(0, min(CANONICAL_MAX, round(base * config.rookie_pick_adjustments.get(round_number, 0.70))))
