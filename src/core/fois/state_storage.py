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
from . import state_delta

FORMAT = "fois-state-v1"
DELTA_FORMAT = "fois-delta-v1"
MAX_DELTA_DEPTH = 16
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


def encode(connection: sqlite3.Connection, payload: dict[str, Any], *, base_payload=None) -> str:
    identity, body, observation = split(payload)
    raw = body.encode()
    envelope = canonical({"$storage": FORMAT, "state_id": identity, "observation": observation})
    if connection.execute('SELECT 1 FROM fois_semantic_states WHERE state_id=?', (identity,)).fetchone():
        if decode(connection, envelope) != payload:
            raise ValueError('FOIS state identity collision or corruption')
        return envelope
    stored, storage_format = zlib.compress(raw), FORMAT
    scope = ('league_id', 'score_key', 'tenure_id', 'model_version')
    if base_payload and all(base_payload.get(k) == payload.get(k) for k in scope):
        base_id, base_body, _ = split(base_payload)
        if base_id != identity:
            encode(connection, base_payload)
            base_row = connection.execute('SELECT format,payload FROM fois_semantic_states WHERE state_id=?', (base_id,)).fetchone()
            depth = json.loads(zlib.decompress(base_row[1]))['depth'] if base_row[0] == DELTA_FORMAT else 0
            if depth < MAX_DELTA_DEPTH:
                delta = zlib.compress(canonical({'base': base_id, 'depth': depth + 1,
                    'changes': state_delta.changes(json.loads(base_body), json.loads(body))}).encode())
                if len(delta) + 128 < len(stored):
                    stored, storage_format = delta, DELTA_FORMAT
    connection.execute(
        "INSERT OR IGNORE INTO fois_semantic_states VALUES (?,?,?,?,?)",
        (identity, storage_format, stored, len(raw), str(payload.get('league_id') or '')),
    )
    # Verify collisions/corruption before allowing a reference to replace data.
    if decode(connection, envelope) != payload:
        raise ValueError("FOIS state identity collision or corruption")
    return envelope


def _state(connection, identity, seen):
    if identity in seen or len(seen) > MAX_DELTA_DEPTH:
        raise ValueError('Invalid FOIS delta dependency chain')
    row = connection.execute('SELECT format,payload,decoded_bytes,league_id FROM fois_semantic_states WHERE state_id=?', (identity,)).fetchone()
    if row is None or row[0] not in (FORMAT, DELTA_FORMAT):
        raise ValueError('Missing FOIS semantic state')
    raw = zlib.decompress(row[1])
    if row[0] == DELTA_FORMAT:
        delta = json.loads(raw)
        if not 1 <= delta['depth'] <= MAX_DELTA_DEPTH:
            raise ValueError('Invalid FOIS delta depth')
        base = _state(connection, delta['base'], seen | {identity})
        state = state_delta.apply(base, delta['changes'])
        if any(base.get(k) != state.get(k) for k in ('league_id', 'score_key', 'tenure_id', 'model_version')):
            raise ValueError('FOIS delta scope mismatch')
        raw = canonical(state).encode()
    if len(raw) != row[2] or hashlib.sha256(FORMAT.encode() + b'\n' + raw).hexdigest() != identity:
        raise ValueError('Corrupt FOIS semantic state')
    state = json.loads(raw)
    if str(state.get('league_id') or '') != row[3]:
        raise ValueError('FOIS state league mismatch')
    return state


def decode(connection: sqlite3.Connection, value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if payload.get("$storage") != FORMAT:
        return payload
    state = _state(connection, payload['state_id'], set())
    observation = payload["observation"]
    if not isinstance(observation, dict) or set(observation) - OBSERVATION_FIELDS:
        raise ValueError("Invalid FOIS observation metadata")
    return {**state, **observation}


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
