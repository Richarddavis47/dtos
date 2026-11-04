"""One availability vocabulary for canonical facts, distinct from evidence quality."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from src.core.freshness import assess_freshness

from .global_evidence import utc


class Availability(StrEnum):
    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    NOT_CONNECTED = "not_connected"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AvailabilityAssessment:
    state: Availability
    reason: str
    freshness: str


def assess_availability(*, connected: bool, applicable: bool, value_present: bool,
                        checked_at: str | None, as_of: str, evidence_family: str,
                        sample_count: int | None = None, required_sample: int = 1,
                        completed_period: bool = False, live: bool = False) -> AvailabilityAssessment:
    """Provider failure, absent evidence and observed zero are different states.

    ``value_present`` must come from ``value is not None``, never its truthiness.
    Completed facts do not expire solely because the calendar advances.
    """
    if not applicable:
        return AvailabilityAssessment(Availability.NOT_APPLICABLE, "not_applicable", "not_applicable")
    if not connected:
        return AvailabilityAssessment(Availability.NOT_CONNECTED, "provider_not_connected", "unavailable")
    if sample_count is not None and sample_count < required_sample:
        return AvailabilityAssessment(Availability.INSUFFICIENT_SAMPLE, "insufficient_sample", "unavailable")
    if not value_present:
        return AvailabilityAssessment(Availability.UNAVAILABLE, "evidence_not_available", "unavailable")
    boundary = datetime.fromisoformat(utc(as_of))
    checked = datetime.fromisoformat(utc(checked_at)) if checked_at else None
    if checked is not None and checked > boundary:
        return AvailabilityAssessment(Availability.UNAVAILABLE, "observation_after_as_of", "unavailable")
    age = (boundary - checked).total_seconds() / 3600 if checked else None
    freshness = assess_freshness(age, "historical" if completed_period else evidence_family).tier
    if freshness in {"Stale", "Very Stale", "Unavailable"}:
        return AvailabilityAssessment(Availability.STALE, "retained_evidence_not_current", freshness)
    return AvailabilityAssessment(Availability.LIVE if live else Availability.CACHED, "evidence_available", freshness)
