"""Lossless FOIS state/observation separation; no historical evidence pruning.

Only the two top-level publication fields are observation metadata. Nested
timestamps (trade time, evidence as-of, tenure) remain semantic, as do all
unknown/future fields. Scope and model identity are inside the hashed payload.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from typing import Any

FORMAT = "fois-state-v1"
OBSERVATION_FIELDS = frozenset({"generated_at", "brain_snapshot_id"})
SCHEMA = """
CREATE TABLE IF NOT EXISTS fois_semantic_states (
 state_id TEXT PRIMARY KEY,
 format TEXT NOT NULL,
 payload BLOB NOT NULL,
 decoded_bytes INTEGER NOT NULL,
 league_id TEXT NOT NULL
);
"""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def split(payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(payload, dict) or "score_key" not in payload:
        raise ValueError("Invalid FOIS state payload")
    state = {key: value for key, value in payload.items() if key not in OBSERVATION_FIELDS}
    observation = {key: payload[key] for key in OBSERVATION_FIELDS if key in payload}
    body = canonical(state)
    identity = hashlib.sha256((FORMAT + "\n" + body).encode()).hexdigest()
    return identity, body, observation


def encode(connection: sqlite3.Connection, payload: dict[str, Any]) -> str:
    identity, body, observation = split(payload)
    raw = body.encode()
    connection.execute(
        "INSERT OR IGNORE INTO fois_semantic_states VALUES (?,?,?,?,?)",
        (identity, FORMAT, zlib.compress(raw), len(raw), str(payload.get('league_id') or '')),
    )
    # Verify collisions/corruption before allowing a reference to replace data.
    row = connection.execute(
        "SELECT payload FROM fois_semantic_states WHERE state_id=?", (identity,),
    ).fetchone()
    if zlib.decompress(row[0]) != raw:
        raise ValueError("FOIS state identity collision or corruption")
    return canonical({"$storage": FORMAT, "state_id": identity, "observation": observation})


def decode(connection: sqlite3.Connection, value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if payload.get("$storage") != FORMAT:
        return payload
    row = connection.execute(
        "SELECT format,payload,decoded_bytes FROM fois_semantic_states WHERE state_id=?",
        (payload["state_id"],),
    ).fetchone()
    if row is None or row[0] != FORMAT:
        raise ValueError("Missing FOIS semantic state")
    raw = zlib.decompress(row[1])
    if len(raw) != row[2] or hashlib.sha256(FORMAT.encode() + b"\n" + raw).hexdigest() != payload["state_id"]:
        raise ValueError("Corrupt FOIS semantic state")
    observation = payload["observation"]
    if not isinstance(observation, dict) or set(observation) - OBSERVATION_FIELDS:
        raise ValueError("Invalid FOIS observation metadata")
    return {**json.loads(raw), **observation}


def classify(connection: sqlite3.Connection) -> dict[str, int]:
    """Streaming read-only admission evidence; stores hashes, never full history."""
    identities: set[str] = set()
    count = original = unique_bytes = observation_bytes = 0
    for (value,) in connection.execute("SELECT payload FROM fois_snapshot_history ORDER BY snapshot_id"):
        payload = decode(connection, value)
        identity, body, observation = split(payload)
        count += 1
        original += len(canonical(payload).encode())
        observation_bytes += len(canonical({"$storage": FORMAT, "state_id": identity, "observation": observation}).encode())
        if identity not in identities:
            identities.add(identity)
            unique_bytes += len(zlib.compress(body.encode()))
    return {
        "observations": count, "semantic_states": len(identities),
        "duplicate_observations": count - len(identities),
        "original_payload_bytes": original, "compressed_state_bytes": unique_bytes,
        "observation_bytes": observation_bytes,
        "estimated_payload_savings": original - unique_bytes - observation_bytes,
    }
