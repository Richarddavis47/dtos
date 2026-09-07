"""Lossless player-level projection history; observation envelopes stay intact.

Only publication metadata is separated. All other fields, including missing
values, evidence timestamps and unknown future fields, participate in identity.
No unique historical evidence is expired by this representation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import zlib

FORMAT = "projection-players-v1"
OBSERVATION = frozenset({"generated_at", "projection_snapshot_id"})
SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_player_states (
 state_id TEXT PRIMARY KEY, payload BLOB NOT NULL
);
"""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def encode(connection: sqlite3.Connection, snapshot: dict) -> str:
    envelope = {key: value for key, value in snapshot.items() if key != "players"}
    references = {}
    # Scoring-derived evidence is never shared across private league scope.
    scope = {key: snapshot.get(key) for key in (
        "league_id", "scoring_profile_id", "schema_version", "model_version",
        "contract_version", "semantic_policy_version",
    )}
    for player_id, player in snapshot["players"].items():
        state = {key: value for key, value in player.items() if key not in OBSERVATION}
        raw = canonical({"scope": scope, "player_id": player_id, "state": state}).encode()
        identity = hashlib.sha256(raw).hexdigest()
        connection.execute("INSERT OR IGNORE INTO projection_player_states VALUES (?,?)", (identity, zlib.compress(raw)))
        stored = connection.execute("SELECT payload FROM projection_player_states WHERE state_id=?", (identity,)).fetchone()[0]
        if zlib.decompress(stored) != raw:
            raise ValueError("Projection state collision or corruption")
        references[player_id] = [identity, {key: player[key] for key in OBSERVATION if key in player}]
    body = canonical({"envelope": envelope, "players": references}).encode()
    return canonical({"$storage": FORMAT, "data": base64.b64encode(zlib.compress(body)).decode("ascii")})


def decode(connection: sqlite3.Connection, value: str) -> dict:
    payload = json.loads(value)
    if payload.get("$storage") != FORMAT:
        return payload
    body = json.loads(zlib.decompress(base64.b64decode(payload["data"], validate=True)))
    snapshot = body["envelope"]
    players = {}
    scope = {key: snapshot.get(key) for key in (
        "league_id", "scoring_profile_id", "schema_version", "model_version",
        "contract_version", "semantic_policy_version",
    )}
    for player_id, (identity, observation) in body["players"].items():
        row = connection.execute("SELECT payload FROM projection_player_states WHERE state_id=?", (identity,)).fetchone()
        if row is None:
            raise ValueError("Missing projection player state")
        raw = zlib.decompress(row[0])
        state = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != identity or state["scope"] != scope
                or state["player_id"] != player_id or set(observation) - OBSERVATION):
            raise ValueError("Invalid projection player state")
        players[player_id] = {**state["state"], **observation}
    return {**snapshot, "players": players}
