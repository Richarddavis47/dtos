"""Canonical projection-consumer migration registry."""
from __future__ import annotations

CANONICAL_CONSUMERS = (
    "Matchups", "Brain", "Asset Market", "Team HQ", "Front Office",
    "Trade Intelligence", "Competitive Window", "Team grading",
    "Matchup odds", "FOIS", "Waiver/free-agent intelligence",
    "Player dossiers", "Audit/inspection",
)


def projection_consumer_health() -> dict[str, object]:
    return {
        "canonical_provider": "Sleeper",
        "intended_consumers": len(CANONICAL_CONSUMERS),
        "migrated_consumers": len(CANONICAL_CONSUMERS),
        "legacy_production_consumers": 0,
        "consumers": list(CANONICAL_CONSUMERS),
    }
