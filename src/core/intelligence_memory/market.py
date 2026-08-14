"""Historical market evidence selection, separate from current Market Value."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .confidence import temporal_confidence
from .models import EvidenceCompleteness, ProvenanceType, SourceObservation

APPROVED_HISTORICAL_PROVIDERS = frozenset({"dynastyprocess"})
SCHEMA_SUPPORTED_PROVIDERS = frozenset({"dynastyprocess", "fantasycalc"})


@dataclass(frozen=True)
class HistoricalMarketSelection:
    provenance: ProvenanceType
    completeness: EvidenceCompleteness
    value: float | None
    confidence: int
    observations: tuple[SourceObservation, ...]
    consensus: bool
    reason: str


def select_historical_market(
    observations: Iterable[SourceObservation],
    event_at: str,
    *, approved_providers: frozenset[str] = APPROVED_HISTORICAL_PROVIDERS,
    intervening_material_event: bool = False,
) -> HistoricalMarketSelection:
    """Select only legitimate observations at or before the decision time."""
    event = datetime.fromisoformat(event_at)
    eligible = []
    for observation in observations:
        if observation.provider.casefold() not in approved_providers:
            continue
        if not observation.observed_at or observation.normalized_value is None:
            continue
        observed = datetime.fromisoformat(observation.observed_at)
        if observed > event:
            continue
        eligible.append(observation)
    if not eligible:
        return HistoricalMarketSelection(
            ProvenanceType.UNAVAILABLE, EvidenceCompleteness.UNAVAILABLE,
            None, 0, (), False, "no_legitimate_pre_event_observation",
        )
    # Newest legitimate observation per provider; never silently use future knowledge.
    per_provider: dict[str, SourceObservation] = {}
    for observation in sorted(eligible, key=lambda row: str(row.observed_at)):
        per_provider[observation.provider.casefold()] = observation
    selected = tuple(per_provider.values())
    scores = [temporal_confidence(
        row.observed_at, event_at,
        intervening_material_event=intervening_material_event,
    )[0] for row in selected]
    value = sum(float(row.normalized_value) for row in selected) / len(selected)
    consensus = len(selected) > 1
    return HistoricalMarketSelection(
        ProvenanceType.HISTORICAL_SOURCE_BACKFILL,
        EvidenceCompleteness.COMPLETE if consensus else EvidenceCompleteness.PARTIAL,
        value, min(scores), selected, consensus,
        "historical_consensus" if consensus else "single_source_historical_evidence",
    )


def current_market_value(
    value: float | int | None, *, fresh: bool, provider_available: bool,
) -> tuple[float | int | None, str]:
    if value is None or not fresh or not provider_available:
        return None, "current_market_unavailable"
    return value, "current_market_fresh"
