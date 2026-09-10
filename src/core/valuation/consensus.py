"""Consensus calculation that only accepts canonical normalized values."""
from __future__ import annotations

from statistics import pstdev
from math import isfinite

from src.core.valuation.models import CalibrationStatus, CanonicalConsensus, ConsensusProvider, NormalizedValuation


def build_canonical_consensus(values: tuple[NormalizedValuation, ...], expected_providers: int = 2) -> CanonicalConsensus:
    from src.core.provider_network.registry import evidence_family
    # A zero-confidence observation cannot gain weight/confidence merely because
    # it is present (or agrees with itself). Keep it as raw evidence upstream.
    grouped = {}
    for item in values:
        if (item.method == 'unsupported_provider' or item.provider.casefold() in {'dtos', 'dtos pick'}
            or not all(isfinite(value) for value in (item.normalized_value, item.confidence_score, item.raw_value))
            or not 0 < item.confidence_score <= 100 or not 0 <= item.normalized_value <= 1000):
            continue
        grouped.setdefault(item.provider.strip().casefold(), []).append(item)
    # Repeated copies are one observation, not independent corroboration. An
    # unresolved conflict within one provider is excluded, never last-row-wins.
    unique = tuple(rows[0] for _, rows in sorted(grouped.items()) if all(row == rows[0] for row in rows))
    families = {}
    for item in unique:
        families.setdefault(evidence_family(item.provider), []).append(item)
    # Mirrored evidence is one vote. Conflicting representations of the same
    # underlying source require resolution, not extra consensus confidence.
    usable = tuple(rows[0] for _, rows in sorted(families.items())
                   if all(row.normalized_value == rows[0].normalized_value for row in rows))
    if not usable:
        return CanonicalConsensus(None, (), None, 0, CalibrationStatus.INSUFFICIENT_DATA, "Experimental — market calibration has insufficient data.")
    if len(usable) > 1 and (any(not item.compatibility_key for item in usable)
                            or len({item.compatibility_key for item in usable}) != 1):
        return CanonicalConsensus(None, (), None, 0, CalibrationStatus.INSUFFICIENT_DATA,
            "Separate provider evidence available; cross-provider format compatibility is unproven.")
    raw_weights = [item.confidence_score / 100 for item in usable]
    total_weight = sum(raw_weights)
    providers = tuple(ConsensusProvider(item.provider, item.raw_value, item.normalized_value, round(weight / total_weight, 4), item.freshness) for item, weight in zip(usable, raw_weights, strict=True))
    consensus = round(sum(item.normalized_value * weight / total_weight for item, weight in zip(usable, raw_weights, strict=True)))
    spread = round(pstdev(item.normalized_value for item in usable)) if len(usable) > 1 else None
    agreement = max(0, 100 - round(spread / 4)) if spread is not None else None
    base = sum(item.confidence_score for item in usable) / len(usable)
    # Missing corroboration is not observed disagreement. Single-source
    # confidence retains its evidence support without a provider-count penalty.
    confidence = max(0, min(100, round(base if agreement is None else base * .75 + agreement * .25)))
    stale = all(item.freshness == "stale" for item in usable)
    status = CalibrationStatus.STALE if stale else CalibrationStatus.CALIBRATED if confidence >= 70 else CalibrationStatus.PARTIALLY_CALIBRATED
    warning = "Market source evidence is stale." if stale else None
    return CanonicalConsensus(consensus, providers, spread, confidence, status, warning)
