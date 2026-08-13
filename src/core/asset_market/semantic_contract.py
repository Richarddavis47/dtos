"""Shared deterministic Asset Market semantic identity contract."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

PROTOCOL_VERSION = "dtos-market-semantic-v1"

_TRANSIENT_FIELDS = frozenset({
    "generated_at", "generation_timestamp", "last_sync", "last_updated",
    "observed_at", "provider_refresh_timestamp", "retrieved_at",
    "sleeper_sync_timestamp", "updated_at", "valuation_timestamp",
    "data_age", "freshness", "last_changed", "sleeper_data_age_hours",
})

_OBSERVATIONAL_FIELDS = frozenset({
    "generated_at", "updated_at", "retrieved_at", "observed_at",
    "freshness_recorded_at", "last_checked_at", "last_attempt",
    "last_success", "last_refresh", "request_id", "latency_ms",
    "cache_hits", "restore_count", "external_requests",
    "freshness_age_hours", "age_hours", "generation_timestamp",
    "hours_until_threshold",
})


def semantic_value(value: Any) -> Any:
    """Normalize market content while excluding transient observation fields."""
    if isinstance(value, dict):
        return {
            str(key): semantic_value(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) not in _TRANSIENT_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [semantic_value(child) for child in value]
    if isinstance(value, set):
        return sorted(semantic_value(child) for child in value)
    return value


def canonical_semantic_value(value: Any) -> Any:
    """Normalize Brain semantics without process or observation metadata."""
    if isinstance(value, dict):
        return {
            key: canonical_semantic_value(item)
            for key, item in sorted(value.items())
            if key not in _OBSERVATIONAL_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [canonical_semantic_value(item) for item in value]
    if isinstance(value, float):
        return round(value, 8)
    return value


def digest(value: Any) -> str:
    encoded = json.dumps(
        semantic_value(value), separators=(",", ":"), sort_keys=True,
        default=lambda item: getattr(item, "value", str(item)),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def semantic_record(
    asset: dict[str, Any], brain_asset: dict[str, Any] | None,
    summary: dict[str, Any], sequence: int,
) -> dict[str, Any]:
    """Return only the ordered fields consumed by the four canonical digests."""
    identity = asset.get("identity") or {}
    return {
        "sequence": sequence,
        "universe": {
            "asset_id": asset["asset_id"],
            "asset_type": asset["asset_type"],
            "identity": {
                key: value for key, value in identity.items()
                if key not in {"current_owner", "free_agent"}
            },
        },
        "semantic_output": {
            "asset_id": asset["asset_id"],
            "summary": {
                key: value for key, value in summary.items()
                if key not in {"availability", "provider_count"}
            },
            "brain": brain_asset,
            "valuation_layers": asset.get("valuation_layers") or {},
            "comparison": asset.get("comparison") or {},
        },
        "ownership": {
            "asset_id": asset["asset_id"],
            "owner": identity.get("current_owner"),
            "availability": summary["availability"],
        },
        "provider_evidence": {
            "asset_id": asset["asset_id"],
            "providers": asset.get("providers") or [],
        },
    }


@dataclass
class SemanticAccumulator:
    """Incrementally compute the unchanged four-digest identity contract."""

    universe: Any = field(default_factory=hashlib.sha256)
    output: Any = field(default_factory=hashlib.sha256)
    ownership: Any = field(default_factory=hashlib.sha256)
    providers: Any = field(default_factory=hashlib.sha256)
    asset_count: int = 0

    def update(self, record: dict[str, Any]) -> None:
        if record.get("sequence") != self.asset_count:
            raise ValueError("Semantic records are not in canonical sequence order.")
        self.universe.update(digest(record["universe"]).encode())
        self.output.update(digest(canonical_semantic_value(
            record["semantic_output"],
        )).encode())
        self.ownership.update(digest(record["ownership"]).encode())
        self.providers.update(digest(canonical_semantic_value(
            record["provider_evidence"],
        )).encode())
        self.asset_count += 1

    def result(self, valuation_schema: Any) -> dict[str, Any]:
        return {
            "asset_universe_digest": self.universe.hexdigest(),
            "brain_semantic_output_digest": self.output.hexdigest(),
            "ownership_dependency_digest": self.ownership.hexdigest(),
            "provider_evidence_digest": self.providers.hexdigest(),
            "asset_count": self.asset_count,
            "valuation_schema": valuation_schema,
        }


def reference_identities(
    records: Iterable[dict[str, Any]], valuation_schema: Any,
) -> dict[str, Any]:
    accumulator = SemanticAccumulator()
    for record in records:
        accumulator.update(record)
    return accumulator.result(valuation_schema)
