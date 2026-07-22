"""Deterministic external-data quality checks."""
from __future__ import annotations

from collections import Counter
from typing import Any

from src.core.data_platform.models import DataQuality


def assess_quality(value: Any, *, stale: bool = False, duplicate_keys: tuple[str, ...] = ()) -> DataQuality:
    issues: list[str] = []
    if value is None:
        issues.append("Missing value")
    if isinstance(value, (int, float)) and (value < 0 or value > 1_000_000):
        issues.append("Impossible value")
    if stale:
        issues.append("Stale snapshot")
    if duplicate_keys:
        duplicates = tuple(key for key, count in Counter(duplicate_keys).items() if count > 1)
        if duplicates:
            issues.append(f"Duplicate records: {', '.join(duplicates)}")
    score = max(0, 100 - 30 * len(issues))
    return DataQuality("good" if not issues else "blocked" if value is None else "warning", tuple(issues), score)


def consensus_quality(values: tuple[float, ...]) -> DataQuality:
    if not values:
        return assess_quality(None)
    center = sorted(values)[len(values) // 2]
    outliers = tuple(str(value) for value in values if abs(value - center) > max(abs(center) * 0.5, 100))
    issues = ("Provider disagreement or outlier detected",) if outliers else ()
    return DataQuality("warning" if issues else "good", issues, 75 if issues else 100)
