"""Season-specific deterministic fantasy scoring."""
from __future__ import annotations

from typing import Any


def calculate_fantasy_points(
    raw_stats: dict[str, Any] | None, scoring_settings: dict[str, Any],
) -> dict[str, Any]:
    if raw_stats is None:
        return {
            "fantasy_points": None, "availability": "unavailable",
            "reason": "Raw statistical components were not supplied.",
            "components": {},
        }
    components: dict[str, float] = {}
    for category, multiplier in scoring_settings.items():
        if category not in raw_stats or raw_stats[category] is None:
            continue
        try:
            components[category] = float(raw_stats[category]) * float(multiplier)
        except (TypeError, ValueError):
            continue
    return {
        "fantasy_points": round(sum(components.values()), 2),
        "availability": "calculated",
        "reason": None,
        "components": components,
    }


def normalize_usage(value: Any, *, provider_supported: bool, estimated: bool = False) -> dict[str, Any]:
    if not provider_supported:
        return {"value": None, "availability": "provider_not_supported", "confidence": 0}
    if value is None:
        return {"value": None, "availability": "unavailable", "confidence": 0}
    return {
        "value": float(value),
        "availability": "estimated" if estimated else "observed",
        "confidence": 55 if estimated else 90,
    }
