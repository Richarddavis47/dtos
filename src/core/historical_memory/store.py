"""Indexed, append-only SQLite store for historical league evidence."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from src.core.historical_memory.models import DATABASE_MIGRATION_VERSION

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_records (
  id INTEGER PRIMARY KEY,
  record_key TEXT NOT NULL UNIQUE,
  entity_type TEXT NOT NULL,
  league_id TEXT NOT NULL,
  season INTEGER,
  week INTEGER,
  franchise_id TEXT,
  player_id TEXT,
  source_record_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  provider TEXT NOT NULL,
  availability TEXT NOT NULL,
  confidence INTEGER NOT NULL,
  calculation_method TEXT NOT NULL,
  derived INTEGER NOT NULL DEFAULT 0,
  schema_version TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_entity ON historical_records(league_id, entity_type, season, week);
CREATE INDEX IF NOT EXISTS idx_history_player ON historical_records(league_id, player_id, season, week);
CREATE INDEX IF NOT EXISTS idx_history_franchise ON historical_records(league_id, franchise_id, season, week);
CREATE TABLE IF NOT EXISTS player_identity (
  dtos_player_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  provider_player_id TEXT NOT NULL,
  display_name TEXT,
  confidence INTEGER NOT NULL,
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  metadata TEXT NOT NULL,
  PRIMARY KEY(provider, provider_player_id, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_identity_dtos ON player_identity(dtos_player_id);
CREATE TABLE IF NOT EXISTS import_runs (
  run_id TEXT PRIMARY KEY,
  league_id TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  checkpoint TEXT,
  records_written INTEGER NOT NULL DEFAULT 0,
  records_unchanged INTEGER NOT NULL DEFAULT 0,
  errors TEXT NOT NULL DEFAULT '[]',
  workbook_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_quality_issues (
  issue_key TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  league_id TEXT NOT NULL,
  season INTEGER,
  severity TEXT NOT NULL,
  category TEXT NOT NULL,
  detail TEXT NOT NULL,
  resolved INTEGER NOT NULL DEFAULT 0
);
"""


class HistoricalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self) -> None:
        with self._lock, self.connection() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                (DATABASE_MIGRATION_VERSION,),
            )

    def append(
        self,
        *,
        record_key: str,
        entity_type: str,
        league_id: str,
        source_record_id: str,
        observed_at: str,
        retrieved_at: str,
        provider: str,
        availability: str,
        confidence: int,
        calculation_method: str,
        schema_version: str,
        payload: dict[str, Any],
        season: int | None = None,
        week: int | None = None,
        franchise_id: str | None = None,
        player_id: str | None = None,
        derived: bool = False,
    ) -> bool:
        values = (
            record_key, entity_type, league_id, season, week, franchise_id, player_id,
            source_record_id, observed_at, retrieved_at, provider, availability,
            confidence, calculation_method, int(derived), schema_version,
            json.dumps(
                payload, separators=(",", ":"), sort_keys=True,
                default=lambda value: getattr(value, "value", str(value)),
            ),
        )
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO historical_records(
                record_key, entity_type, league_id, season, week, franchise_id,
                player_id, source_record_id, observed_at, retrieved_at, provider,
                availability, confidence, calculation_method, derived,
                schema_version, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            return cursor.rowcount == 1

    def records(
        self,
        league_id: str,
        entity_type: str | None = None,
        *,
        season: int | None = None,
        week: int | None = None,
        franchise_id: str | None = None,
        player_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        clauses = ["league_id = ?"]
        values: list[Any] = [league_id]
        for column, value in (
            ("entity_type", entity_type), ("season", season), ("week", week),
            ("franchise_id", franchise_id), ("player_id", player_id),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        where = " AND ".join(clauses)
        with self.connection() as connection:
            count = int(connection.execute(f"SELECT count(*) FROM historical_records WHERE {where}", values).fetchone()[0])
            rows = connection.execute(
                f"""SELECT entity_type, league_id, season, week, franchise_id,
                player_id, provider, source_record_id, observed_at, retrieved_at,
                availability, confidence, calculation_method, derived,
                schema_version, payload FROM historical_records WHERE {where}
                ORDER BY season DESC, week DESC, id DESC LIMIT ? OFFSET ?""",
                (*values, limit, offset),
            ).fetchall()
        return count, [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def upsert_identity(
        self, dtos_player_id: str, provider: str, provider_player_id: str,
        display_name: str, confidence: int, valid_from: str, metadata: dict[str, Any],
    ) -> None:
        with self._lock, self.connection() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO player_identity(
                dtos_player_id, provider, provider_player_id, display_name,
                confidence, valid_from, metadata) VALUES (?,?,?,?,?,?,?)""",
                (dtos_player_id, provider, provider_player_id, display_name, confidence, valid_from, json.dumps(metadata, sort_keys=True)),
            )

    def identities(self, unresolved_only: bool = False) -> list[dict[str, Any]]:
        clause = " WHERE confidence < 70" if unresolved_only else ""
        with self.connection() as connection:
            rows = connection.execute(f"SELECT * FROM player_identity{clause} ORDER BY dtos_player_id").fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in rows]

    def import_status(self, league_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM import_runs WHERE league_id=? ORDER BY started_at DESC", (league_id,),
            ).fetchall()
        return [{**dict(row), "errors": json.loads(row["errors"])} for row in rows]

    def quality(self, league_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM data_quality_issues WHERE league_id=? ORDER BY severity, season, category", (league_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def start_run(self, run_id: str, league_id: str, started_at: str, workbook_status: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO import_runs(run_id,league_id,status,started_at,workbook_status) VALUES (?,?,?,?,?)",
                (run_id, league_id, "running", started_at, workbook_status),
            )

    def update_run(
        self, run_id: str, *, status: str, checkpoint: str | None,
        written: int, unchanged: int, errors: list[str], completed_at: str | None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE import_runs SET status=?,checkpoint=?,records_written=?,
                records_unchanged=?,errors=?,completed_at=? WHERE run_id=?""",
                (status, checkpoint, written, unchanged, json.dumps(errors), completed_at, run_id),
            )

    def add_quality_issue(
        self, issue_key: str, run_id: str, league_id: str, season: int | None,
        severity: str, category: str, detail: str,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO data_quality_issues(
                issue_key,run_id,league_id,season,severity,category,detail)
                VALUES (?,?,?,?,?,?,?)""",
                (issue_key, run_id, league_id, season, severity, category, detail),
            )
