"""Bounded retained semantic-contract reads for lifecycle validation."""
from __future__ import annotations

from typing import Any


def retained_semantic_contract(
    cache: Any, data: dict[str, Any], state: dict[str, Any], store: Any,
    league_id: str,
) -> dict[str, Any]:
    """Read worker-prepared identities without rebuilding semantic inputs."""
    health = cache.health()
    cache_health = health.get("cache") or {}
    prepared = dict(
        (cache_health.get("semantic_preparation") or {}).get(
            "semantic_identities"
        ) or {}
    )
    return {
        "semantic_generation": cache_health.get("requested_generation"),
        "semantic_identities": {
            name: value for name, value in prepared.items()
            if name.endswith("_digest") and name != "database_identity_digest"
        },
        "raw_identities": {
            "last_sync": state.get("last_sync"),
            "brain_generated_at": (
                (data.get("valuation_intelligence") or {}).get("generated_at")
            ),
            "historical_cache_generation": store.semantic_generations(
                league_id,
            ).get("provider_cache"),
        },
        "artifact_compatibility": cache_health.get("artifact_compatibility"),
    }
