"""Tiny DTOS-owned lifecycle and semantic metadata store."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator
from uuid import uuid4
from datetime import datetime, timezone

from config import METADATA_DATABASE_FILE


class MinimalMetadataStore:
    schema_version = 1

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(
              namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(namespace,key)
            );
            CREATE TABLE IF NOT EXISTS lifecycle_audit(
              id INTEGER PRIMARY KEY, category TEXT NOT NULL, identity TEXT NOT NULL,
              payload TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(category,identity)
            );
            """)
            connection.execute(
                "INSERT OR IGNORE INTO metadata(namespace,key,value) VALUES('system','database_uuid',?)",
                (json.dumps(uuid4().hex),),
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = sqlite3.connect(self.path)
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE namespace=? AND key=?",
                (namespace, key),
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            # The first unpublished v1.10.23 implementation stored its UUID as
            # plain text. Accept and atomically normalize only that scalar.
            if namespace == "system" and key == "database_uuid":
                value = str(row[0])
                self.put(namespace, key, value)
                return value
            raise

    def put(self, namespace: str, key: str, value: Any) -> None:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO metadata(namespace,key,value) VALUES(?,?,?) "
                "ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP",
                (namespace, key, payload),
            )

    def audit(self, category: str, identity: str, payload: Any) -> bool:
        """Persist one compact, idempotent system-owned audit fact."""
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO lifecycle_audit(category,identity,payload) "
                "VALUES(?,?,?)",
                (category, identity, body),
            )
        return cursor.rowcount == 1

    def record_season_cache_checkpoint(
        self, league_id: str, season: int, checksum: str, status: str,
    ) -> None:
        """Record only cache lifecycle metadata, never provider payloads."""
        self.put("season_cache_checkpoint", f"{league_id}:{season}", {
            "league_id": str(league_id), "season": int(season),
            "checksum": str(checksum), "status": str(status),
        })
        self.audit("season_cache_checkpoint", f"{league_id}:{season}:{checksum}", {
            "status": str(status), "derived_from": "sleeper_season_cache_checksum",
        })

    def record_season_chain(self, league_id: str, manifest: dict[str, Any]) -> None:
        """Persist the compact provider chain and cache lifecycle, never payloads."""
        self.put("sleeper_season_chain", str(league_id), manifest)

    def season_chain(self, league_id: str) -> dict[str, Any] | None:
        value = self.get("sleeper_season_chain", str(league_id))
        return dict(value) if isinstance(value, dict) else None

    def record_sync_generation(self, league_id: str, generation: str) -> None:
        self.put("sync_generation", str(league_id), {
            "generation": str(generation),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

    def database_uuid(self) -> str:
        return str(self.get("system", "database_uuid"))

    def health(self) -> dict[str, object]:
        with self.connection() as connection:
            rows = int(connection.execute("SELECT count(*) FROM metadata").fetchone()[0])
            audits = int(connection.execute("SELECT count(*) FROM lifecycle_audit").fetchone()[0])
        return {
            "status": "healthy", "schema_version": self.schema_version,
            "bytes": self.path.stat().st_size, "metadata_rows": rows,
            "audit_rows": audits, "ownership": "permanent_system_metadata",
        }


minimal_metadata_store = MinimalMetadataStore(METADATA_DATABASE_FILE)
