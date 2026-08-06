"""Indexed, append-only SQLite store for historical league evidence."""
from __future__ import annotations

import json
import hashlib
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
CREATE INDEX IF NOT EXISTS idx_import_runs_league_status_completed
ON import_runs(league_id, status, completed_at);
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
CREATE TABLE IF NOT EXISTS import_jobs (
  job_id TEXT PRIMARY KEY,
  league_id TEXT NOT NULL,
  requested_seasons TEXT NOT NULL,
  requested_data_types TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT,
  last_progress_at TEXT,
  completed_at TEXT,
  failed_at TEXT,
  current_season INTEGER,
  current_week INTEGER,
  current_data_type TEXT,
  total_steps INTEGER NOT NULL DEFAULT 0,
  completed_steps INTEGER NOT NULL DEFAULT 0,
  inserted_records INTEGER NOT NULL DEFAULT 0,
  updated_records INTEGER NOT NULL DEFAULT 0,
  unchanged_records INTEGER NOT NULL DEFAULT 0,
  skipped_records INTEGER NOT NULL DEFAULT 0,
  failed_records INTEGER NOT NULL DEFAULT 0,
  retry_count INTEGER NOT NULL DEFAULT 0,
  next_retry_at TEXT,
  last_error_type TEXT,
  last_error_message TEXT,
  last_error_context TEXT,
  requested_by TEXT NOT NULL,
  worker_identity TEXT,
  lock_expiration TEXT,
  schema_version TEXT NOT NULL,
  importer_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_import_jobs_league_status
ON import_jobs(league_id, status, created_at);
CREATE TABLE IF NOT EXISTS import_checkpoints (
  checkpoint_key TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  league_id TEXT NOT NULL,
  season INTEGER NOT NULL,
  week INTEGER,
  data_type TEXT NOT NULL,
  provider TEXT NOT NULL,
  importer_version TEXT NOT NULL,
  status TEXT NOT NULL,
  completed_at TEXT,
  records_written INTEGER NOT NULL DEFAULT 0,
  records_unchanged INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  FOREIGN KEY(job_id) REFERENCES import_jobs(job_id)
);
CREATE INDEX IF NOT EXISTS idx_import_checkpoints_scope
ON import_checkpoints(league_id, season, data_type, provider, importer_version);
CREATE TABLE IF NOT EXISTS import_locks (
  lock_key TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  worker_identity TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
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
            connection.executemany(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                ((version,) for version in range(1, DATABASE_MIGRATION_VERSION + 1)),
            )

    def create_job(self, job: dict[str, Any]) -> None:
        columns = tuple(job)
        placeholders = ",".join("?" for _ in columns)
        with self._lock, self.connection() as connection:
            connection.execute(
                f"INSERT INTO import_jobs({','.join(columns)}) VALUES ({placeholders})",
                tuple(
                    json.dumps(value) if isinstance(value, (list, dict)) else value
                    for value in job.values()
                ),
            )

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ",".join(f"{column}=?" for column in fields)
        values = [
            json.dumps(value) if isinstance(value, (list, dict)) else value
            for value in fields.values()
        ]
        with self._lock, self.connection() as connection:
            connection.execute(
                f"UPDATE import_jobs SET {assignments} WHERE job_id=?",
                (*values, job_id),
            )

    def jobs(self, league_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM import_jobs WHERE league_id=?
                ORDER BY created_at DESC LIMIT ?""",
                (league_id, limit),
            ).fetchall()
        return [_decode_job(dict(row)) for row in rows]

    def checkpoint(
        self, *, checkpoint_key: str, job_id: str, league_id: str,
        season: int, week: int | None, data_type: str, provider: str,
        importer_version: str, status: str, completed_at: str | None = None,
        records_written: int = 0, records_unchanged: int = 0,
        error: str | None = None,
    ) -> None:
        with self._lock, self.connection() as connection:
            connection.execute(
                """INSERT INTO import_checkpoints(
                checkpoint_key,job_id,league_id,season,week,data_type,provider,
                importer_version,status,completed_at,records_written,
                records_unchanged,error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(checkpoint_key) DO UPDATE SET
                job_id=excluded.job_id,status=excluded.status,
                completed_at=excluded.completed_at,
                records_written=excluded.records_written,
                records_unchanged=excluded.records_unchanged,error=excluded.error""",
                (
                    checkpoint_key, job_id, league_id, season, week, data_type,
                    provider, importer_version, status, completed_at,
                    records_written, records_unchanged, error,
                ),
            )

    def checkpoints(self, league_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM import_checkpoints WHERE league_id=?
                ORDER BY season,week,data_type""",
                (league_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def acquire_lock(
        self, lock_key: str, job_id: str, worker_identity: str,
        acquired_at: str, expires_at: str,
    ) -> bool:
        with self._lock, self.connection() as connection:
            connection.execute(
                "DELETE FROM import_locks WHERE expires_at <= ?", (acquired_at,),
            )
            cursor = connection.execute(
                """INSERT OR IGNORE INTO import_locks(
                lock_key,job_id,worker_identity,acquired_at,expires_at)
                VALUES (?,?,?,?,?)""",
                (lock_key, job_id, worker_identity, acquired_at, expires_at),
            )
            return cursor.rowcount == 1

    def release_lock(self, lock_key: str, job_id: str) -> None:
        with self._lock, self.connection() as connection:
            connection.execute(
                "DELETE FROM import_locks WHERE lock_key=? AND job_id=?",
                (lock_key, job_id),
            )

    def renew_job_lease(self, job_id: str, expires_at: str) -> None:
        with self._lock, self.connection() as connection:
            connection.execute(
                "UPDATE import_locks SET expires_at=? WHERE job_id=?",
                (expires_at, job_id),
            )
            connection.execute(
                """UPDATE import_jobs SET lock_expiration=?,
                last_progress_at=datetime('now') WHERE job_id=?""",
                (expires_at, job_id),
            )

    def locks(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM import_locks ORDER BY lock_key",
                ).fetchall()
            ]

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

    def append_many(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Append one bounded batch in one transaction on a worker thread."""
        values = [
            (
                record["record_key"], record["entity_type"], record["league_id"],
                record.get("season"), record.get("week"),
                record.get("franchise_id"), record.get("player_id"),
                record["source_record_id"], record["observed_at"],
                record["retrieved_at"], record["provider"],
                record["availability"], record["confidence"],
                record["calculation_method"], int(record.get("derived", False)),
                record["schema_version"],
                json.dumps(
                    record["payload"], separators=(",", ":"), sort_keys=True,
                    default=lambda value: getattr(value, "value", str(value)),
                ),
            )
            for record in records
        ]
        with self._lock, self.connection() as connection:
            before = connection.total_changes
            connection.executemany(
                """INSERT OR IGNORE INTO historical_records(
                record_key, entity_type, league_id, season, week, franchise_id,
                player_id, source_record_id, observed_at, retrieved_at, provider,
                availability, confidence, calculation_method, derived,
                schema_version, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            written = connection.total_changes - before
        return written, len(records) - written

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

    def dataset_version(self, league_id: str) -> str:
        """Return a deterministic identity for every stored input to graph reads."""
        with self.connection() as connection:
            record = connection.execute(
                """SELECT count(*), coalesce(max(id), 0),
                coalesce(max(retrieved_at), '') FROM historical_records
                WHERE league_id=?""",
                (league_id,),
            ).fetchone()
            identities = connection.execute(
                """SELECT count(*), coalesce(max(rowid), 0),
                coalesce(max(valid_from), '') FROM player_identity""",
            ).fetchone()
            quality = connection.execute(
                """SELECT issue_key, resolved FROM data_quality_issues
                WHERE league_id=? ORDER BY issue_key""",
                (league_id,),
            ).fetchall()
        source = json.dumps(
            {
                "league_id": league_id,
                "records": tuple(record),
                "identities": tuple(identities),
                "quality": [tuple(row) for row in quality],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(source.encode()).hexdigest()

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
                """SELECT * FROM import_runs WHERE league_id=?
                ORDER BY started_at DESC, rowid DESC""",
                (league_id,),
            ).fetchall()
        return [{**dict(row), "errors": json.loads(row["errors"])} for row in rows]

    def latest_completed_foundation(
        self, league_id: str,
    ) -> dict[str, Any] | None:
        """Return the newest usable completed backfill, not the latest attempt."""
        with self.connection() as connection:
            row = connection.execute(
                """SELECT run.* FROM import_runs AS run
                WHERE run.league_id=?
                  AND run.status='complete'
                  AND run.completed_at IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM historical_records AS record
                    WHERE record.league_id=run.league_id
                      AND record.entity_type='league_season'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM data_quality_issues AS issue
                    WHERE issue.league_id=run.league_id
                      AND issue.severity='blocking'
                      AND issue.resolved=0
                  )
                ORDER BY run.completed_at DESC, run.started_at DESC
                LIMIT 1""",
                (league_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["errors"] = json.loads(result["errors"])
        return result

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


def _decode_job(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("requested_seasons", "requested_data_types"):
        row[key] = json.loads(row[key])
    return row
