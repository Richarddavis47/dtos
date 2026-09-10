"""Provider-aware conversion to the canonical 0-1000 comparison scale."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable

from src.core.freshness import assess_freshness

from src.core.valuation.config import CANONICAL_MAX, DEFAULT_CONFIG, NORMALIZATION_VERSION, ValuationConfig
from src.core.valuation.models import NormalizedValuation
from src.core.valuation.source_time import market_times


def prepare_distribution(
    provider: str,
    distribution: Iterable[float],
    config: ValuationConfig = DEFAULT_CONFIG,
) -> tuple[float, ...]:
    """Prepare provider values once for repeated percentile lookups."""
    scale = config.provider_scales.get(provider)
    if scale is None:
        return ()
    return tuple(
        sorted(
            float(item)
            for item in distribution
            if item is not None
            and scale.minimum <= float(item) <= scale.maximum
        )
    )


def _freshness(updated_at: str | None, provider: str) -> tuple[str, int]:
    if not updated_at:
        return "unknown", 70
    try:
        observed = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        observed = observed if observed.tzinfo else observed.replace(tzinfo=timezone.utc)
        hours = max(0.0, (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds() / 3600)
    except ValueError:
        return "unknown", 60
    family = {
        "FantasyCalc": "fantasycalc_observed_market",
        "DynastyProcess": "fantasypros_derived_market",
        "KTC": "ktc_crowd_market",
        "DTOS": "dtos_intrinsic",
        "DTOS Pick": "dtos_intrinsic",
    }.get(provider)
    assessment = assess_freshness(hours, family)
    # Preserve the existing normalized-value freshness vocabulary for consumers.
    label = {"Very Stale": "stale", "Immutable": "fresh"}.get(
        assessment.tier, assessment.tier.lower(),
    )
    return label, assessment.semantic_weight


def normalize_value(
    provider: str,
    raw_value: float,
    *,
    distribution: Iterable[float] = (),
    prepared_distribution: tuple[float, ...] | None = None,
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
    population = (
        prepared_distribution
        if prepared_distribution is not None
        else prepare_distribution(provider, distribution, config)
    )
    if len(population) >= 10:
        below = bisect_left(population, raw)
        equal = bisect_right(population, raw) - below
        percentile = (below + equal * 0.5) / len(population)
        canonical = round(CANONICAL_MAX * (ratio * 0.70 + percentile * 0.30))
        method = "provider_range_70_percentile_30"
    else:
        canonical = round(CANONICAL_MAX * ratio)
        method = "provider_range_linear"
    freshness, freshness_confidence = _freshness(updated_at, provider)
    confidence = round(min(100, max(0, provider_confidence)) * scale.reliability * freshness_confidence / 100)
    return NormalizedValuation(provider, float(raw_value), scale.minimum, scale.maximum, max(0, min(CANONICAL_MAX, canonical)), updated_at, source_season, confidence, freshness, NORMALIZATION_VERSION, method)


def normalize_internal(value: float) -> int:
    """Convert a legacy DTOS 0-100 score without treating it as provider market data."""
    return max(0, min(CANONICAL_MAX, round(float(value) * 10)))


def prepare_market_normalization(market_data: dict[str, Any]) -> None:
    """Pin comparison values before league relevance discards provider rows.

    Existing cached rows retain only their normalized scalar and reference
    identity, not a second population array. No provider or durable store reads.
    Freshness/confidence are still evaluated at consumption time.
    """
    for provider, rows in (market_data.get("providers") or {}).items():
        if provider not in {"FantasyCalc", "DynastyProcess"} or not isinstance(rows, dict):
            continue
        population = prepare_distribution(provider, (
            row.get("value") for row in rows.values() if isinstance(row, dict)
        ))
        generation = hashlib.sha256(json.dumps(
            [NORMALIZATION_VERSION, provider, population], separators=(",", ":")
        ).encode()).hexdigest()
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            row.pop("normalization_reference", None)
            if row.get("value") is None:
                continue
            normalized = normalize_value(provider, float(row["value"]), prepared_distribution=population)
            row["normalization_reference"] = {
                "provider": provider, "raw_value": normalized.raw_value,
                "normalized_value": normalized.normalized_value,
                "version": NORMALIZATION_VERSION, "method": normalized.method,
                "generation": generation, "population_size": len(population),
            }


def normalize_cached_value(provider: str, row: dict[str, Any], **kwargs: Any) -> NormalizedValuation:
    """Use a matching pre-filter reference; stale/raw-changed references fail closed."""
    clocks = market_times(row, kwargs.get('updated_at'))
    kwargs['updated_at'] = clocks['source_updated_at']
    normalized = normalize_value(provider, float(row["value"]), **kwargs)
    # Keep knowledge separate from the source time used to assess freshness.
    normalized = replace(normalized, updated_at=clocks['retrieved_at'])
    reference = row.get("normalization_reference") or {}
    value = reference.get("normalized_value")
    if (reference.get("provider") == provider
            and reference.get("raw_value") == normalized.raw_value
            and reference.get("version") == NORMALIZATION_VERSION
            and reference.get("generation")
            and reference.get("method") in {"provider_range_linear", "provider_range_70_percentile_30"}
            and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= CANONICAL_MAX):
        return replace(normalized, normalized_value=value, method=reference["method"])
    return normalized


def normalize_pick(value: float, round_number: int, config: ValuationConfig = DEFAULT_CONFIG) -> int:
    base = normalize_internal(value)
    return max(0, min(CANONICAL_MAX, round(base * config.rookie_pick_adjustments.get(round_number, 0.70))))
