"""SQLite persistence for compact, immutable DTOS intelligence checkpoints."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from .models import (
    EvidenceCompleteness, IntelligenceCheckpoint, PickLineage, ProvenanceType,
    SourceObservation,
)

SCHEMA_VERSION = 2


SCHEMA = """
CREATE TABLE IF NOT EXISTS intelligence_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intelligence_checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  semantic_key TEXT NOT NULL UNIQUE,
  asset_id TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  league_id TEXT,
  roster_id TEXT,
  scoring_profile_id TEXT,
  observed_at TEXT NOT NULL,
  season INTEGER NOT NULL,
  week INTEGER,
  trigger_type TEXT NOT NULL,
  provenance_type TEXT NOT NULL,
  dtos_value REAL,
  intrinsic_value REAL,
  contender_value REAL,
  rebuilder_value REAL,
  market_value REAL,
  confidence INTEGER NOT NULL,
  evidence_completeness TEXT NOT NULL,
  model_version TEXT NOT NULL,
  normalization_version TEXT NOT NULL,
  brain_identity TEXT,
  related_event_id TEXT,
  knowledge_state TEXT,
  schema_version TEXT NOT NULL,
  observations_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intelligence_checkpoints_asset
ON intelligence_checkpoints(asset_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_intelligence_checkpoints_league
ON intelligence_checkpoints(league_id, season, trigger_type);
CREATE TABLE IF NOT EXISTS pick_lineage (
  lineage_id TEXT PRIMARY KEY,
  generic_pick_id TEXT NOT NULL UNIQUE,
  season INTEGER NOT NULL,
  round INTEGER NOT NULL,
  original_roster_id TEXT NOT NULL,
  exact_slot TEXT,
  selected_player_id TEXT,
  slot_known_at TEXT,
  selected_at TEXT
);
CREATE TABLE IF NOT EXISTS intelligence_audit (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  checkpoint_id TEXT NOT NULL,
  action TEXT NOT NULL,
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class IntelligenceCheckpointStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                str(row[1]) for row in connection.execute(
                    "PRAGMA table_info(intelligence_checkpoints)"
                ).fetchall()
            }
            if "roster_id" not in columns:
                connection.execute(
                    "ALTER TABLE intelligence_checkpoints ADD COLUMN roster_id TEXT"
                )
            connection.execute(
                """INSERT INTO intelligence_metadata(key,value) VALUES('schema_version',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (str(SCHEMA_VERSION),),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def semantic_key(checkpoint: IntelligenceCheckpoint) -> str:
        payload = {
            "asset_id": checkpoint.asset_id,
            "asset_type": checkpoint.asset_type,
            "league_id": checkpoint.league_id,
            "roster_id": checkpoint.roster_id,
            "timestamp": checkpoint.timestamp,
            "trigger": checkpoint.trigger_type.value,
            "provenance": checkpoint.provenance_type.value,
            "model": checkpoint.model_version,
            "brain": checkpoint.brain_identity,
            "event": checkpoint.related_event_id,
            "values": [checkpoint.dtos_value, checkpoint.intrinsic_value,
                       checkpoint.contender_value, checkpoint.rebuilder_value,
                       checkpoint.market_value],
            "observations": [observation.__dict__ for observation in checkpoint.observations],
            "knowledge_state": checkpoint.knowledge_state,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def put(self, checkpoint: IntelligenceCheckpoint) -> tuple[IntelligenceCheckpoint, bool]:
        semantic_key = self.semantic_key(checkpoint)
        checkpoint_id = checkpoint.checkpoint_id or semantic_key
        checkpoint = replace(checkpoint, checkpoint_id=checkpoint_id)
        observations = json.dumps(
            [observation.__dict__ for observation in checkpoint.observations],
            sort_keys=True, separators=(",", ":"),
        )
        values = (
            checkpoint_id, semantic_key, checkpoint.asset_id, checkpoint.asset_type,
            checkpoint.league_id, checkpoint.roster_id, checkpoint.scoring_profile_id, checkpoint.timestamp,
            checkpoint.season, checkpoint.week, checkpoint.trigger_type.value,
            checkpoint.provenance_type.value, checkpoint.dtos_value,
            checkpoint.intrinsic_value, checkpoint.contender_value,
            checkpoint.rebuilder_value, checkpoint.market_value, checkpoint.confidence,
            checkpoint.evidence_completeness.value, checkpoint.model_version,
            checkpoint.normalization_version, checkpoint.brain_identity,
            checkpoint.related_event_id, checkpoint.knowledge_state,
            checkpoint.schema_version, observations,
        )
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO intelligence_checkpoints(
                checkpoint_id,semantic_key,asset_id,asset_type,league_id,roster_id,
                scoring_profile_id,observed_at,season,week,trigger_type,
                provenance_type,dtos_value,intrinsic_value,contender_value,
                rebuilder_value,market_value,confidence,evidence_completeness,
                model_version,normalization_version,brain_identity,related_event_id,
                knowledge_state,schema_version,observations_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            inserted = cursor.rowcount == 1
            if inserted:
                connection.execute(
                    "INSERT INTO intelligence_audit(checkpoint_id,action) VALUES(?,?)",
                    (checkpoint_id, "created"),
                )
            else:
                row = connection.execute(
                    "SELECT checkpoint_id FROM intelligence_checkpoints WHERE semantic_key=?",
                    (semantic_key,),
                ).fetchone()
                checkpoint = replace(checkpoint, checkpoint_id=str(row["checkpoint_id"]))
        return checkpoint, inserted

    def checkpoints(
        self, *, league_id: str | None = None, asset_id: str | None = None,
        roster_id: str | None = None,
        limit: int = 1000,
    ) -> list[IntelligenceCheckpoint]:
        clauses: list[str] = []
        values: list[Any] = []
        if league_id is not None:
            clauses.append("league_id=?")
            values.append(str(league_id))
        if asset_id is not None:
            clauses.append("asset_id=?")
            values.append(str(asset_id))
        if roster_id is not None:
            clauses.append("roster_id=?")
            values.append(str(roster_id))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM intelligence_checkpoints{where} ORDER BY observed_at LIMIT ?",
                (*values, max(1, min(int(limit), 10_000))),
            ).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: sqlite3.Row) -> IntelligenceCheckpoint:
        observations = tuple(SourceObservation(**item) for item in json.loads(row["observations_json"]))
        from .models import CheckpointTrigger
        return IntelligenceCheckpoint(
            checkpoint_id=row["checkpoint_id"], asset_id=row["asset_id"],
            asset_type=row["asset_type"], league_id=row["league_id"],
            roster_id=row["roster_id"],
            scoring_profile_id=row["scoring_profile_id"], timestamp=row["observed_at"],
            season=row["season"], week=row["week"],
            trigger_type=CheckpointTrigger(row["trigger_type"]),
            provenance_type=ProvenanceType(row["provenance_type"]),
            dtos_value=row["dtos_value"], intrinsic_value=row["intrinsic_value"],
            contender_value=row["contender_value"], rebuilder_value=row["rebuilder_value"],
            market_value=row["market_value"], confidence=row["confidence"],
            evidence_completeness=EvidenceCompleteness(row["evidence_completeness"]),
            model_version=row["model_version"], normalization_version=row["normalization_version"],
            brain_identity=row["brain_identity"], related_event_id=row["related_event_id"],
            knowledge_state=row["knowledge_state"], schema_version=row["schema_version"],
            observations=observations,
        )

    def event_exists(
        self, *, league_id: str | None, event_id: str, asset_id: str,
        trigger_type: str,
    ) -> bool:
        """Point-check canonical event identity before model-dependent capture."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM intelligence_checkpoints
                WHERE league_id IS ? AND related_event_id=? AND asset_id=?
                AND trigger_type=? LIMIT 1""",
                (league_id, event_id, asset_id, trigger_type),
            ).fetchone()
        return row is not None

    def put_lineage(self, lineage: PickLineage) -> tuple[PickLineage, bool]:
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM pick_lineage WHERE generic_pick_id=?",
                (lineage.generic_pick_id,),
            ).fetchone()
            if existing:
                # Execution-time generic identity is immutable; later facts only append lineage.
                connection.execute(
                    """UPDATE pick_lineage SET exact_slot=COALESCE(exact_slot,?),
                    selected_player_id=COALESCE(selected_player_id,?),
                    slot_known_at=COALESCE(slot_known_at,?),selected_at=COALESCE(selected_at,?)
                    WHERE generic_pick_id=?""",
                    (lineage.exact_slot, lineage.selected_player_id, lineage.slot_known_at,
                     lineage.selected_at, lineage.generic_pick_id),
                )
                return lineage, False
            connection.execute(
                "INSERT INTO pick_lineage VALUES(?,?,?,?,?,?,?,?,?)",
                tuple(lineage.__dict__.values()),
            )
            return lineage, True

    def health(self) -> dict[str, Any]:
        with self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM intelligence_checkpoints").fetchone()[0]
            provenance = dict(connection.execute(
                "SELECT provenance_type,COUNT(*) FROM intelligence_checkpoints GROUP BY provenance_type"
            ).fetchall())
            lineage = connection.execute("SELECT COUNT(*) FROM pick_lineage").fetchone()[0]
        size = self.path.stat().st_size if self.path.exists() else 0
        return {
            "status": "healthy", "schema_version": SCHEMA_VERSION,
            "ownership": "permanent_dtos_intelligence", "checkpoint_count": count,
            "provenance_counts": provenance, "pick_lineage_count": lineage,
            "bytes": size, "immutable": True, "daily_logging": False,
        }

    def storage_estimates(self) -> dict[str, Any]:
        health = self.health()
        count = int(health["checkpoint_count"])
        average = int(health["bytes"] / count) if count else 1024
        return {
            "average_bytes_per_checkpoint": average,
            "30_leagues": average * 3_000,
            "100_leagues": average * 10_000,
            "1000_leagues": average * 100_000,
            "assumption": "100 meaningful checkpoints per league; excludes disposable provider caches",
        }
