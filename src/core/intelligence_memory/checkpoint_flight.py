"""Bounded, read-only checkpoint evidence reuse within one preparation flight.

Only public checkpoint projections are memoized, never league assessments or
date-selected values. The canonical evaluator still applies each event/as_of,
franchise, league and method boundary independently. No cache survives a flight.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from typing import Any, Iterator

from .store import SCHEMA_VERSION, IntelligenceCheckpointStore

READ_CONTRACT = "global-checkpoint-projection-flight-v1"


class CheckpointGenerationChanged(RuntimeError):
    """Discard the preparation result instead of publishing mixed evidence."""


class CheckpointReadFlight:
    def __init__(
        self, store: IntelligenceCheckpointStore, connection: sqlite3.Connection,
        *, max_serialized_bytes: int = 8 * 1024 * 1024, max_entries: int = 1024,
    ):
        self.store = store
        self.connection = connection
        self.max_serialized_bytes = max_serialized_bytes
        self.max_entries = max_entries
        self.cache: OrderedDict[tuple[str, int], tuple[list[Any], int]] = OrderedDict()
        self.retained_bytes = 0
        self.storage_reads = 0
        self.cache_hits = 0
        self.closed = False
        # Stream the generation, not the database, into memory. Include both
        # observation fields and the reference/knowledge evidence the projection
        # actually reads. Ordering is explicit for cross-process determinism.
        digest = hashlib.sha256(f"{READ_CONTRACT}|{SCHEMA_VERSION}".encode())
        for query in (
            "SELECT * FROM global_market_observations ORDER BY observation_id",
            "SELECT r.observation_id,r.trigger_type,c.knowledge_state "
            "FROM market_observation_references r JOIN intelligence_checkpoints c "
            "ON c.checkpoint_id=r.checkpoint_id "
            "ORDER BY r.observation_id,r.trigger_type,c.knowledge_state",
        ):
            for row in connection.execute(query):
                digest.update(json.dumps(tuple(row), separators=(",", ":")).encode())
                digest.update(b"\n")
        self.generation = digest.hexdigest()

    def global_market_checkpoints(self, *, asset_id: str, limit: int = 500) -> list[Any]:
        if self.closed:
            raise RuntimeError("Checkpoint preparation flight is closed.")
        key = (str(asset_id), max(1, min(int(limit), 500)))
        if key in self.cache:
            self.cache_hits += 1
            self.cache.move_to_end(key)
            return deepcopy(self.cache[key][0])
        rows = self.store._global_market_checkpoints(
            self.connection, asset_id=key[0], limit=key[1],
        )
        self.storage_reads += 1
        size = len(json.dumps([asdict(row) for row in rows], default=str).encode())
        if size <= self.max_serialized_bytes and self.max_entries > 0:
            while self.cache and (
                self.retained_bytes + size > self.max_serialized_bytes
                or len(self.cache) >= self.max_entries
            ):
                _, (_, removed) = self.cache.popitem(last=False)
                self.retained_bytes -= removed
            self.cache[key] = (deepcopy(rows), size)
            self.retained_bytes += size
        return rows

    def metrics(self) -> dict[str, Any]:
        return {
            "generation": self.generation, "read_contract": READ_CONTRACT,
            "storage_reads": self.storage_reads, "cache_hits": self.cache_hits,
            "retained_serialized_bytes": self.retained_bytes,
            "retained_assets": len(self.cache),
        }


@contextmanager
def checkpoint_read_flight(store: IntelligenceCheckpointStore) -> Iterator[CheckpointReadFlight]:
    # No WAL setup/write transaction per asset, and no accidental empty database.
    connection = sqlite3.connect(store.path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    flight = None
    try:
        connection.execute("PRAGMA query_only=ON")
        before = connection.execute("PRAGMA data_version").fetchone()[0]
        connection.execute("BEGIN")
        flight = CheckpointReadFlight(store, connection)
        yield flight
        connection.rollback()
        # data_version is used only on this SAME open connection as a concurrent
        # write fence, never as a portable generation identity. Conservatively
        # reject even an unrelated checkpoint write while the flight was active.
        if connection.execute("PRAGMA data_version").fetchone()[0] != before:
            raise CheckpointGenerationChanged("Checkpoint evidence advanced during FOIS preparation.")
    finally:
        if flight is not None:
            flight.closed = True
            flight.cache.clear()
            flight.retained_bytes = 0
        connection.close()
