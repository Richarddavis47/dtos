"""Read-only comparison between provider cache and legacy Historical Memory."""
from __future__ import annotations

from typing import Any


PROVIDER_RECONSTRUCTIBLE_CATEGORIES = (
    "league", "users", "rosters", "matchups", "transactions", "drafts",
    "draft_picks", "traded_picks", "winners_bracket", "losers_bracket",
)


def compare_provider_to_legacy(
    provider_facts: dict[str, Any], legacy_counts: dict[str, int],
) -> dict[str, Any]:
    """Compare sources without filling either side from the other."""
    rows = []
    for category in PROVIDER_RECONSTRUCTIBLE_CATEGORIES:
        value = provider_facts.get(category)
        provider_count = (
            sum(len(item or ()) for item in value.values()) if isinstance(value, dict)
            else len(value or ()) if isinstance(value, (list, tuple))
            else 1 if value is not None else 0
        )
        legacy_count = int(legacy_counts.get(category, 0))
        rows.append({
            "category": category,
            "provider_available": value is not None,
            "provider_count": provider_count,
            "legacy_count": legacy_count,
            "equivalent_count": provider_count == legacy_count,
            "fallback_used": False,
        })
    available = sum(row["provider_available"] for row in rows)
    return {
        "status": "complete" if available == len(rows) else "partial",
        "coverage_percent": round(100 * available / len(rows)),
        "historical_memory_fallback": False,
        "categories": rows,
    }
