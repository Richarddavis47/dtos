"""Consensus calculation that only accepts canonical normalized values."""
from __future__ import annotations

from statistics import pstdev

from src.core.valuation.models import CalibrationStatus, CanonicalConsensus, ConsensusProvider, NormalizedValuation


def build_canonical_consensus(values: tuple[NormalizedValuation, ...], expected_providers: int = 2) -> CanonicalConsensus:
    usable = tuple(item for item in values if item.method != "unsupported_provider")
    if not usable:
        return CanonicalConsensus(None, (), None, 0, CalibrationStatus.INSUFFICIENT_DATA, "Experimental — market calibration has insufficient data.")
    raw_weights = [max(0.05, item.confidence_score / 100) for item in usable]
    total_weight = sum(raw_weights)
    providers = tuple(ConsensusProvider(item.provider, item.raw_value, item.normalized_value, round(weight / total_weight, 4), item.freshness) for item, weight in zip(usable, raw_weights, strict=True))
    consensus = round(sum(item.normalized_value * provider.weight for item, provider in zip(usable, providers, strict=True)))
    spread = round(pstdev(item.normalized_value for item in usable)) if len(usable) > 1 else 0
    agreement = max(0, 100 - round(spread / 4))
    coverage = min(1, len(usable) / max(expected_providers, 1))
    base = sum(item.confidence_score for item in usable) / len(usable)
    confidence = max(0, min(100, round(base * .55 + agreement * .25 + coverage * 100 * .20)))
    stale = all(item.freshness == "stale" for item in usable)
    status = CalibrationStatus.STALE if stale else CalibrationStatus.CALIBRATED if len(usable) >= expected_providers and confidence >= 70 else CalibrationStatus.PARTIALLY_CALIBRATED
    warning = None if status is CalibrationStatus.CALIBRATED else "Experimental — market calibration incomplete."
    return CanonicalConsensus(consensus, providers, spread, confidence, status, warning)
