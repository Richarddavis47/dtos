"""Bounded, private-by-default semantic restart evidence; never a public artifact.

Callers supply the exact canonical inputs, not an already summarized digest.
Private leaf values and dictionary identifiers are fingerprinted; structural
paths remain comparable. No raw account or league payload is retained.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import tempfile
from typing import Any

MAX_LEAVES = 500_000
MAX_BYTES = 64 * 1024 * 1024
REQUIRED = frozenset({
    "account_identity", "league_identity", "synchronization_generation",
    "market_generation", "brain_generation", "brain_semantic_digest",
    "provider_evidence_digest", "projection_snapshot_id", "projection_digest",
    "asset_universe_digest", "ownership_digest", "calibration",
    "artifact_compatibility", "provider_confidence", "source_timestamps",
    "semantic_records", "market_rows",
})
FORBIDDEN = frozenset({
    "password", "token", "cookie", "cookies", "authorization",
    "headers", "credentials", "secret", "csrf_token", "session_token",
})
PUBLIC_CONFIDENCE_FIELDS = frozenset({
    "raw_value", "normalized_value", "source_confidence", "confidence",
    "reliability", "freshness_weight",
})
PUBLIC_STATE_FIELDS = frozenset({
    "source_timestamp", "last_successful_refresh", "updated_at", "tier",
    "freshness", "semantic_weight", "next_tier", "next_threshold_hours",
    "policy_version", "normalization_version", "minimum", "maximum",
})
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def snapshot(inputs: dict[str, Any]) -> dict[str, Any]:
    if set(inputs) != REQUIRED:
        raise ValueError("Restart evidence requires the complete exact input contract")
    node_count = 0
    key_hashes: dict[str, str] = {}

    def walk(value: Any, path: str) -> dict[str, Any]:
        nonlocal node_count
        node_count += 1
        if node_count > MAX_LEAVES:
            raise ValueError("Restart evidence exceeds its leaf budget")
        if isinstance(value, dict):
            if any(FORBIDDEN.intersection(str(key).casefold().replace("-", "_").split("_"))
                   for key in value):
                raise ValueError("Credential-bearing input is forbidden")
            node = {"kind": "object", "children": {}}
            for key in sorted(value):
                # Hash nested keys too: roster names and IDs can be object keys.
                public = (path.startswith(("$.provider_confidence/", "$.source_timestamps/"))
                          and key in PUBLIC_CONFIDENCE_FIELDS | PUBLIC_STATE_FIELDS)
                full_hash = fingerprint(key)
                short_hash = full_hash[:16]
                if short_hash in key_hashes and key_hashes[short_hash] != full_hash:
                    raise ValueError("Restart evidence key fingerprint collision")
                key_hashes[short_hash] = full_hash
                suffix = key if public else "key:" + short_hash
                node["children"][suffix] = walk(value[key], path + "/" + suffix)
        elif isinstance(value, list):
            node = {"kind": "array", "children": [
                walk(item, f"{path}/{index}") for index, item in enumerate(value)
            ]}
        elif value is None or isinstance(value, (str, bool, int, float)):
            node = {"kind": type(value).__name__, "sha256": fingerprint(value)}
            if (path.startswith("$.provider_confidence/")
                    and path.rsplit("/", 1)[-1] in PUBLIC_CONFIDENCE_FIELDS
                    and isinstance(value, (int, float)) and not isinstance(value, bool)):
                node["value"] = value
            field = path.rsplit("/", 1)[-1]
            if path.startswith(("$.provider_confidence/", "$.source_timestamps/")):
                if (field in PUBLIC_STATE_FIELDS and isinstance(value, (int, float))
                        and not isinstance(value, bool)):
                    node["value"] = value
                elif isinstance(value, str) and (
                    field in {"source_timestamp", "last_successful_refresh", "updated_at"}
                    and _TIMESTAMP.fullmatch(value)
                    or field in {"tier", "freshness", "next_tier"}
                    and value.lower() in {"fresh", "aging", "stale", "very stale", "immutable", "unavailable", "unknown"}
                ):
                    node["value"] = value
        else:
            raise ValueError("Non-JSON canonical input")
        return node

    tree = {key: walk(inputs[key], "$." + key) for key in sorted(inputs)}
    result = {"schema": "dtos-restart-evidence-v2", "key_hashes": key_hashes,
              "tree": tree, "node_count": node_count}
    if len(json.dumps(result).encode()) > MAX_BYTES:
        raise ValueError("Restart evidence exceeds its byte budget")
    return result


def differences(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    if before.get("schema") != after.get("schema") or before.get("schema") != "dtos-restart-evidence-v2":
        raise ValueError("Incompatible restart evidence schemas")
    left, right = before["tree"], after["tree"]
    before_keys, after_keys = before.get("key_hashes", {}), after.get("key_hashes", {})
    if any(before_keys[key] != after_keys[key] for key in before_keys.keys() & after_keys.keys()):
        raise ValueError("Restart evidence key fingerprint collision")
    changes = []

    def descriptor(node):
        if node is None:
            return None
        if "children" in node:
            return {"kind": node["kind"], "size": len(node["children"])}
        return node

    def children(node):
        value = (node or {}).get("children", {})
        return {str(index): item for index, item in enumerate(value)} if isinstance(value, list) else value

    def visit(a, b, path):
        old, new = descriptor(a), descriptor(b)
        if old != new:
            changes.append({"path": path, "before": old, "after": new})
        a_children, b_children = children(a), children(b)
        for key in sorted(a_children.keys() | b_children.keys()):
            visit(a_children.get(key), b_children.get(key), path + "/" + key)

    for key in sorted(left.keys() | right.keys()):
        visit(left.get(key), right.get(key), "$." + key)
    return sorted(changes, key=lambda item: item["path"])


def record_at(evidence: dict[str, Any], path: str) -> dict[str, Any]:
    """Inspect one recorded structural path without flattening the entire capture."""
    root, *parts = path.removeprefix("$.").split("/")
    node = evidence["tree"][root]
    for part in parts:
        node = node["children"][int(part) if node["kind"] == "array" else part]
    return node


def persist(path: Path, evidence: dict[str, Any]) -> None:
    """Publish before assertions; atomically preserve the last complete snapshot."""
    encoded = json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError("Restart evidence exceeds its byte budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".restart-", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
