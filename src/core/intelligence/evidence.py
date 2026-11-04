"""Cross-engine evidence normalization and aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class UnifiedEvidence:
    source: str
    factor: str
    observed_value: str
    explanation: str
    impact: float
    supports: bool


def normalize_evidence(source: str, items: Iterable[Any]) -> tuple[UnifiedEvidence, ...]:
    return tuple(
        UnifiedEvidence(source, str(getattr(item, "factor", "Evidence")), str(getattr(item, "observed_value", "Available")), str(getattr(item, "explanation", item)), float(getattr(item, "impact", 0)), float(getattr(item, "impact", 0)) >= 0)
        for item in items
    )


def aggregate_evidence(groups: Iterable[tuple[UnifiedEvidence, ...]]) -> tuple[UnifiedEvidence, ...]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for group in groups:
        for item in group:
            key = (item.source, item.factor, item.observed_value)
            if key not in seen:
                seen.add(key)
                result.append(item)
    return tuple(result)
