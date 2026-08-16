"""SQLite persistence for compact, immutable DTOS intelligence checkpoints."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from .models import (
    CheckpointTrigger, EvidenceCompleteness, GlobalMarketObservation,
    HistoricalResolutionState, IntelligenceCheckpoint, MarketObservationDecision, MarketObservationReference,
    PickLineage, ProvenanceType, SourceObservation,
)
from .market_memory import MarketObservationMaterialityPolicy, semantic_fingerprint

SCHEMA_VERSION = 4


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
  observations_json TEXT NOT NULL,
  global_market_observation_id TEXT
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
CREATE TABLE IF NOT EXISTS global_market_observations (
  observation_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  market_context_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  canonical_value REAL NOT NULL,
  intrinsic_value REAL,
  confidence INTEGER NOT NULL,
  evidence_completeness TEXT NOT NULL,
  provider_evidence_json TEXT NOT NULL,
  provenance_type TEXT NOT NULL,
  semantic_fingerprint TEXT NOT NULL,
  model_version TEXT NOT NULL,
  normalization_version TEXT NOT NULL,
  materiality_policy_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_global_market_observation_latest
ON global_market_observations(asset_id, market_context_id, observed_at DESC);
CREATE TABLE IF NOT EXISTS market_observation_references (
  reference_id TEXT PRIMARY KEY,
  checkpoint_id TEXT NOT NULL UNIQUE,
  observation_id TEXT,
  asset_id TEXT NOT NULL,
  league_id TEXT,
  event_id TEXT,
  trigger_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  market_state TEXT NOT NULL,
  provenance_type TEXT NOT NULL,
  market_context_id TEXT,
  resolver_version TEXT,
  resolution_state TEXT,
  unavailable_reason TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(checkpoint_id) REFERENCES intelligence_checkpoints(checkpoint_id),
  FOREIGN KEY(observation_id) REFERENCES global_market_observations(observation_id)
);
CREATE INDEX IF NOT EXISTS idx_market_reference_observation
ON market_observation_references(observation_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_market_reference_league
ON market_observation_references(league_id, trigger_type, occurred_at);
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
            if "global_market_observation_id" not in columns:
                connection.execute(
                    "ALTER TABLE intelligence_checkpoints ADD COLUMN global_market_observation_id TEXT"
                )
            reference_columns = {
                str(row[1]) for row in connection.execute(
                    "PRAGMA table_info(market_observation_references)"
                ).fetchall()
            }
            for name in (
                "market_context_id", "resolver_version", "resolution_state",
                "unavailable_reason",
            ):
                if name not in reference_columns:
                    connection.execute(
                        f"ALTER TABLE market_observation_references ADD COLUMN {name} TEXT"
                    )
            connection.execute(
                """UPDATE market_observation_references
                SET market_context_id=(SELECT market_context_id
                    FROM global_market_observations o
                    WHERE o.observation_id=market_observation_references.observation_id),
                    resolver_version='1.0', resolution_state='complete'
                WHERE observation_id IS NOT NULL AND resolver_version IS NULL"""
            )
            connection.execute(
                """UPDATE market_observation_references
                SET resolver_version='1.0', resolution_state='final_unavailable',
                    unavailable_reason='legacy_resolution_unavailable'
                WHERE observation_id IS NULL AND trigger_type='trade_execution'
                  AND provenance_type='unavailable'
                  AND resolver_version IS NULL"""
            )
            from .market_memory import market_context_id
            missing_context = connection.execute(
                """SELECT r.reference_id,c.asset_type,c.scoring_profile_id
                FROM market_observation_references r
                JOIN intelligence_checkpoints c ON c.checkpoint_id=r.checkpoint_id
                WHERE r.market_context_id IS NULL AND r.resolver_version='1.0'"""
            ).fetchall()
            for row in missing_context:
                connection.execute(
                    "UPDATE market_observation_references SET market_context_id=? WHERE reference_id=?",
                    (market_context_id(
                        asset_type=str(row["asset_type"]),
                        scoring_profile_id=row["scoring_profile_id"],
                    ), row["reference_id"]),
                )
            connection.execute(
                """INSERT INTO intelligence_metadata(key,value) VALUES('schema_version',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (str(SCHEMA_VERSION),),
            )
        self._migration_summary = self.migrate_embedded_market_evidence()

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
            "global_market_observation_id": checkpoint.global_market_observation_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def _put_checkpoint(
        self, connection: sqlite3.Connection, checkpoint: IntelligenceCheckpoint,
    ) -> tuple[IntelligenceCheckpoint, bool]:
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
            checkpoint.schema_version, observations, checkpoint.global_market_observation_id,
        )
        cursor = connection.execute(
            """INSERT OR IGNORE INTO intelligence_checkpoints(
            checkpoint_id,semantic_key,asset_id,asset_type,league_id,roster_id,
            scoring_profile_id,observed_at,season,week,trigger_type,
            provenance_type,dtos_value,intrinsic_value,contender_value,
            rebuilder_value,market_value,confidence,evidence_completeness,
            model_version,normalization_version,brain_identity,related_event_id,
            knowledge_state,schema_version,observations_json,global_market_observation_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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

    def put(self, checkpoint: IntelligenceCheckpoint) -> tuple[IntelligenceCheckpoint, bool]:
        with self._lock, self._connect() as connection:
            return self._put_checkpoint(connection, checkpoint)

    def checkpoints(
        self, *, league_id: str | None = None, asset_id: str | None = None,
        roster_id: str | None = None,
        limit: int = 1000,
    ) -> list[IntelligenceCheckpoint]:
        clauses: list[str] = []
        values: list[Any] = []
        if league_id is not None:
            clauses.append("c.league_id=?")
            values.append(str(league_id))
        if asset_id is not None:
            clauses.append("c.asset_id=?")
            values.append(str(asset_id))
        if roster_id is not None:
            clauses.append("c.roster_id=?")
            values.append(str(roster_id))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT c.*,
                COALESCE(c.market_value,o.canonical_value) AS resolved_market_value,
                COALESCE(c.intrinsic_value,o.intrinsic_value) AS resolved_intrinsic_value,
                COALESCE(c.confidence,o.confidence) AS resolved_confidence,
                COALESCE(c.evidence_completeness,o.evidence_completeness)
                    AS resolved_evidence_completeness,
                CASE WHEN c.observations_json='[]' AND o.provider_evidence_json IS NOT NULL
                     THEN o.provider_evidence_json ELSE c.observations_json END
                    AS resolved_observations_json
                FROM intelligence_checkpoints c
                LEFT JOIN global_market_observations o
                  ON o.observation_id=c.global_market_observation_id
                {where} ORDER BY c.observed_at LIMIT ?""",
                (*values, max(1, min(int(limit), 10_000))),
            ).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: sqlite3.Row) -> IntelligenceCheckpoint:
        evidence_json = (
            row["resolved_observations_json"]
            if "resolved_observations_json" in row.keys() else row["observations_json"]
        )
        observations = tuple(SourceObservation(**item) for item in json.loads(evidence_json))
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
            market_value=row["resolved_market_value"] if "resolved_market_value" in row.keys() else row["market_value"],
            confidence=row["resolved_confidence"] if "resolved_confidence" in row.keys() else row["confidence"],
            evidence_completeness=EvidenceCompleteness(
                row["resolved_evidence_completeness"] if "resolved_evidence_completeness" in row.keys()
                else row["evidence_completeness"]
            ),
            model_version=row["model_version"], normalization_version=row["normalization_version"],
            brain_identity=row["brain_identity"], related_event_id=row["related_event_id"],
            knowledge_state=row["knowledge_state"], schema_version=row["schema_version"],
            observations=observations,
            global_market_observation_id=row["global_market_observation_id"],
        )

    @staticmethod
    def _decode_observation(row: sqlite3.Row) -> GlobalMarketObservation:
        return GlobalMarketObservation(
            observation_id=row["observation_id"], asset_id=row["asset_id"],
            asset_type=row["asset_type"], market_context_id=row["market_context_id"],
            observed_at=row["observed_at"], canonical_value=row["canonical_value"],
            intrinsic_value=row["intrinsic_value"], confidence=row["confidence"],
            evidence_completeness=EvidenceCompleteness(row["evidence_completeness"]),
            provider_evidence=tuple(
                SourceObservation(**item) for item in json.loads(row["provider_evidence_json"])
            ),
            provenance_type=ProvenanceType(row["provenance_type"]),
            semantic_fingerprint=row["semantic_fingerprint"],
            model_version=row["model_version"],
            normalization_version=row["normalization_version"],
            materiality_policy_version=row["materiality_policy_version"],
            schema_version=row["schema_version"],
        )

    def _resolve_observation_on_connection(
        self, connection: sqlite3.Connection, checkpoint: IntelligenceCheckpoint,
        *, market_context_id: str,
        policy: MarketObservationMaterialityPolicy,
        provider_evidence: tuple[SourceObservation, ...] | None = None,
    ) -> tuple[GlobalMarketObservation | None, MarketObservationDecision, bool]:
        if checkpoint.market_value is None:
            return None, MarketObservationDecision.UNAVAILABLE, False
        canonical_value = float(checkpoint.market_value)
        provider_evidence = tuple(
            checkpoint.observations if provider_evidence is None else provider_evidence
        )
        fingerprint = semantic_fingerprint(
            asset_id=checkpoint.asset_id, asset_type=checkpoint.asset_type,
            market_context_id=market_context_id, canonical_value=canonical_value,
            intrinsic_value=(float(checkpoint.intrinsic_value)
                             if checkpoint.intrinsic_value is not None else None),
            confidence=checkpoint.confidence,
            completeness=checkpoint.evidence_completeness,
            provider_evidence=provider_evidence,
            model_version=checkpoint.model_version,
            normalization_version=checkpoint.normalization_version,
        )
        row = connection.execute(
            """SELECT * FROM global_market_observations
            WHERE asset_id=? AND market_context_id=? AND observed_at<=?
            ORDER BY observed_at DESC,created_at DESC LIMIT 1""",
            (checkpoint.asset_id, market_context_id, checkpoint.timestamp),
        ).fetchone()
        previous = self._decode_observation(row) if row else None
        if previous and not policy.materially_changed(
            previous, market_context_id=market_context_id,
            canonical_value=canonical_value, confidence=checkpoint.confidence,
            evidence_completeness=checkpoint.evidence_completeness,
            provider_evidence=provider_evidence,
        ):
            return previous, MarketObservationDecision.REUSED_OBSERVATION, False
        observation_id = hashlib.sha256(
            f"market-observation-v1|{checkpoint.asset_id}|{market_context_id}|{checkpoint.timestamp}|{fingerprint}".encode()
        ).hexdigest()
        connection.execute(
            """INSERT OR IGNORE INTO global_market_observations(
            observation_id,asset_id,asset_type,market_context_id,observed_at,
            canonical_value,intrinsic_value,confidence,evidence_completeness,
            provider_evidence_json,provenance_type,semantic_fingerprint,
            model_version,normalization_version,materiality_policy_version,schema_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (observation_id, checkpoint.asset_id, checkpoint.asset_type,
             market_context_id, checkpoint.timestamp, canonical_value,
             checkpoint.intrinsic_value, checkpoint.confidence,
             checkpoint.evidence_completeness.value,
             json.dumps([item.__dict__ for item in provider_evidence], sort_keys=True,
                        separators=(",", ":")),
             checkpoint.provenance_type.value, fingerprint,
             checkpoint.model_version, checkpoint.normalization_version,
             policy.version, "1.0"),
        )
        created = connection.execute("SELECT changes()").fetchone()[0] == 1
        result = connection.execute(
            "SELECT * FROM global_market_observations WHERE observation_id=?",
            (observation_id,),
        ).fetchone()
        return self._decode_observation(result), (
            MarketObservationDecision.NEW_OBSERVATION if created
            else MarketObservationDecision.REUSED_OBSERVATION
        ), created

    def resolve_observation(
        self, checkpoint: IntelligenceCheckpoint, *, market_context_id: str,
        policy: MarketObservationMaterialityPolicy | None = None,
    ) -> tuple[GlobalMarketObservation | None, MarketObservationDecision, bool]:
        """Atomically create or reuse one global state; league identity is never part of it."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._resolve_observation_on_connection(
                connection, checkpoint, market_context_id=market_context_id,
                policy=policy or MarketObservationMaterialityPolicy(),
            )

    def _put_reference_on_connection(
        self, connection: sqlite3.Connection, checkpoint: IntelligenceCheckpoint,
        observation: GlobalMarketObservation | None,
        decision: MarketObservationDecision,
        *, market_context_id: str | None = None, resolver_version: str | None = None,
        resolution_state: HistoricalResolutionState | None = None,
        unavailable_reason: str | None = None,
    ) -> tuple[MarketObservationReference, bool]:
        reference_id = hashlib.sha256(
            ("market-reference-v1|" + checkpoint.checkpoint_id).encode()
        ).hexdigest()
        reference = MarketObservationReference(
            reference_id=reference_id, checkpoint_id=checkpoint.checkpoint_id,
            observation_id=observation.observation_id if observation else None,
            asset_id=checkpoint.asset_id, league_id=checkpoint.league_id,
            event_id=checkpoint.related_event_id, trigger_type=checkpoint.trigger_type,
            occurred_at=checkpoint.timestamp, market_state=decision,
            provenance_type=checkpoint.provenance_type,
            market_context_id=market_context_id, resolver_version=resolver_version,
            resolution_state=resolution_state, unavailable_reason=unavailable_reason,
        )
        cursor = connection.execute(
            """INSERT OR IGNORE INTO market_observation_references(
            reference_id,checkpoint_id,observation_id,asset_id,league_id,event_id,
            trigger_type,occurred_at,market_state,provenance_type,market_context_id,
            resolver_version,resolution_state,unavailable_reason)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (reference.reference_id, reference.checkpoint_id, reference.observation_id,
             reference.asset_id, reference.league_id, reference.event_id,
             reference.trigger_type.value, reference.occurred_at,
             reference.market_state.value, reference.provenance_type.value,
             reference.market_context_id, reference.resolver_version,
             reference.resolution_state.value if reference.resolution_state else None,
             reference.unavailable_reason),
        )
        inserted = cursor.rowcount == 1
        return reference, inserted

    def put_reference(
        self, checkpoint: IntelligenceCheckpoint,
        observation: GlobalMarketObservation | None,
        decision: MarketObservationDecision,
    ) -> tuple[MarketObservationReference, bool]:
        with self._lock, self._connect() as connection:
            return self._put_reference_on_connection(
                connection, checkpoint, observation, decision,
            )

    def put_sparse(
        self, checkpoint: IntelligenceCheckpoint, *, market_context_id: str,
        policy: MarketObservationMaterialityPolicy | None = None,
        provider_evidence: tuple[SourceObservation, ...] | None = None,
        resolver_version: str | None = None,
        resolution_state: HistoricalResolutionState | None = None,
        unavailable_reason: str | None = None,
    ) -> tuple[IntelligenceCheckpoint, bool, MarketObservationDecision, bool, bool]:
        """Commit observation, compact checkpoint, and reference as one transaction."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT c.*,
                COALESCE(c.market_value,o.canonical_value) AS resolved_market_value,
                COALESCE(c.intrinsic_value,o.intrinsic_value) AS resolved_intrinsic_value,
                COALESCE(c.confidence,o.confidence) AS resolved_confidence,
                COALESCE(c.evidence_completeness,o.evidence_completeness)
                    AS resolved_evidence_completeness,
                CASE WHEN c.observations_json='[]' AND o.provider_evidence_json IS NOT NULL
                     THEN o.provider_evidence_json ELSE c.observations_json END
                    AS resolved_observations_json,
                r.market_state AS resolved_market_state
                FROM intelligence_checkpoints c
                LEFT JOIN global_market_observations o
                  ON o.observation_id=c.global_market_observation_id
                LEFT JOIN market_observation_references r
                  ON r.checkpoint_id=c.checkpoint_id
                WHERE c.league_id IS ? AND c.related_event_id=? AND c.asset_id=?
                  AND c.trigger_type=? LIMIT 1""",
                (checkpoint.league_id, checkpoint.related_event_id,
                 checkpoint.asset_id, checkpoint.trigger_type.value),
            ).fetchone()
            if existing is not None:
                return (
                    self._decode(existing), False,
                    MarketObservationDecision(existing["resolved_market_state"]),
                    False, False,
                )
            observation, decision, observation_created = self._resolve_observation_on_connection(
                connection, checkpoint, market_context_id=market_context_id,
                policy=policy or MarketObservationMaterialityPolicy(),
                provider_evidence=provider_evidence,
            )
            compact = replace(
                checkpoint,
                global_market_observation_id=(observation.observation_id if observation else None),
                market_value=None if observation else checkpoint.market_value,
                intrinsic_value=None if observation else checkpoint.intrinsic_value,
                # Checkpoint-local evidence (for example a weekly projection)
                # remains attached to the event. Only compact market-provider
                # evidence is normalized into the global observation.
                observations=checkpoint.observations,
            )
            persisted, checkpoint_created = self._put_checkpoint(connection, compact)
            _, reference_created = self._put_reference_on_connection(
                connection, persisted, observation, decision,
                market_context_id=market_context_id,
                resolver_version=resolver_version,
                resolution_state=resolution_state,
                unavailable_reason=unavailable_reason,
            )
        if observation:
            persisted = replace(
                persisted, market_value=observation.canonical_value,
                intrinsic_value=observation.intrinsic_value,
                observations=(
                    persisted.observations or observation.provider_evidence
                ),
                evidence_completeness=observation.evidence_completeness,
                confidence=observation.confidence,
            )
        return (
            persisted, checkpoint_created, decision,
            observation_created, reference_created,
        )

    def compatible_resolution(
        self, checkpoint: IntelligenceCheckpoint, *, market_context_id: str,
        resolver_version: str,
    ) -> tuple[IntelligenceCheckpoint, GlobalMarketObservation | None, HistoricalResolutionState] | None:
        """Return the exact compatible event/asset result using bounded point reads."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT c.*, r.resolution_state, r.market_context_id,
                r.resolver_version, o.*
                FROM market_observation_references r
                JOIN intelligence_checkpoints c ON c.checkpoint_id=r.checkpoint_id
                LEFT JOIN global_market_observations o ON o.observation_id=r.observation_id
                WHERE c.league_id IS ? AND c.related_event_id=? AND c.asset_id=?
                  AND c.asset_type=? AND c.trigger_type=? AND c.observed_at=?
                  AND r.market_context_id=? AND r.resolver_version=? LIMIT 1""",
                (checkpoint.league_id, checkpoint.related_event_id, checkpoint.asset_id,
                 checkpoint.asset_type, checkpoint.trigger_type.value, checkpoint.timestamp,
                 market_context_id, resolver_version),
            ).fetchone()
            if row is None:
                return None
            state = HistoricalResolutionState(row["resolution_state"])
            checkpoint_row = connection.execute(
                """SELECT c.*,
                COALESCE(c.market_value,o.canonical_value) AS resolved_market_value,
                COALESCE(c.intrinsic_value,o.intrinsic_value) AS resolved_intrinsic_value,
                COALESCE(c.confidence,o.confidence) AS resolved_confidence,
                COALESCE(c.evidence_completeness,o.evidence_completeness)
                    AS resolved_evidence_completeness,
                CASE WHEN c.observations_json='[]' AND o.provider_evidence_json IS NOT NULL
                     THEN o.provider_evidence_json ELSE c.observations_json END
                    AS resolved_observations_json
                FROM intelligence_checkpoints c
                LEFT JOIN global_market_observations o
                  ON o.observation_id=c.global_market_observation_id
                WHERE c.checkpoint_id=?""",
                (row["checkpoint_id"],),
            ).fetchone()
            stored_checkpoint = self._decode(checkpoint_row)
            observation = None
            if row["observation_id"] is not None:
                observation_row = connection.execute(
                    "SELECT * FROM global_market_observations WHERE observation_id=?",
                    (row["observation_id"],),
                ).fetchone()
                observation = self._decode_observation(observation_row)
        return stored_checkpoint, observation, state

    def compatible_resolutions(
        self,
        requests: list[tuple[IntelligenceCheckpoint, str, str]],
        *,
        decode_batch_size: int = 128,
    ) -> tuple[
        list[tuple[IntelligenceCheckpoint, GlobalMarketObservation | None, HistoricalResolutionState] | None],
        dict[str, int],
    ]:
        """Read compatible durable resolutions in one bounded connection.

        ``requests`` contains checkpoint, market-context, and resolver-version
        tuples. Temporary tables keep the lookup indexed without constructing a
        parameter list proportional to the archive size. They exist only for the
        lifetime of this read connection.
        """
        if not requests:
            return [], {
                "sqlite_connections": 0, "sqlite_queries": 0,
                "rows_loaded": 0, "objects_decoded": 0, "batches": 0,
            }
        batch_size = max(1, int(decode_batch_size))
        with self._connect() as connection:
            connection.execute(
                """CREATE TEMP TABLE bulk_resolution_requests(
                request_id INTEGER PRIMARY KEY, league_id TEXT, event_id TEXT,
                asset_id TEXT, asset_type TEXT, trigger_type TEXT,
                occurred_at TEXT, market_context_id TEXT, resolver_version TEXT)"""
            )
            connection.executemany(
                """INSERT INTO bulk_resolution_requests VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    (
                        index, checkpoint.league_id, checkpoint.related_event_id,
                        checkpoint.asset_id, checkpoint.asset_type,
                        checkpoint.trigger_type.value, checkpoint.timestamp,
                        context, resolver_version,
                    )
                    for index, (checkpoint, context, resolver_version) in enumerate(requests)
                ),
            )
            connection.execute(
                """CREATE TEMP TABLE bulk_resolution_matches(
                request_id INTEGER PRIMARY KEY, checkpoint_id TEXT NOT NULL,
                observation_id TEXT, resolution_state TEXT NOT NULL)"""
            )
            connection.execute(
                """INSERT OR IGNORE INTO bulk_resolution_matches
                SELECT q.request_id,r.checkpoint_id,r.observation_id,r.resolution_state
                FROM bulk_resolution_requests q
                JOIN market_observation_references r
                  ON r.league_id IS q.league_id
                 AND r.event_id=q.event_id
                 AND r.asset_id=q.asset_id
                 AND r.trigger_type=q.trigger_type
                 AND r.occurred_at=q.occurred_at
                 AND r.market_context_id=q.market_context_id
                 AND r.resolver_version=q.resolver_version
                JOIN intelligence_checkpoints c
                  ON c.checkpoint_id=r.checkpoint_id
                 AND c.asset_type=q.asset_type
                ORDER BY q.request_id,r.created_at,r.reference_id"""
            )
            match_rows = connection.execute(
                """SELECT request_id,checkpoint_id,observation_id,resolution_state
                FROM bulk_resolution_matches ORDER BY request_id"""
            ).fetchall()
            checkpoint_rows = connection.execute(
                """SELECT c.*,
                COALESCE(c.market_value,o.canonical_value) AS resolved_market_value,
                COALESCE(c.intrinsic_value,o.intrinsic_value) AS resolved_intrinsic_value,
                COALESCE(c.confidence,o.confidence) AS resolved_confidence,
                COALESCE(c.evidence_completeness,o.evidence_completeness)
                    AS resolved_evidence_completeness,
                CASE WHEN c.observations_json='[]' AND o.provider_evidence_json IS NOT NULL
                     THEN o.provider_evidence_json ELSE c.observations_json END
                    AS resolved_observations_json
                FROM intelligence_checkpoints c
                JOIN (SELECT DISTINCT checkpoint_id FROM bulk_resolution_matches) m
                  ON m.checkpoint_id=c.checkpoint_id
                LEFT JOIN global_market_observations o
                  ON o.observation_id=c.global_market_observation_id"""
            ).fetchall()
            observation_rows = connection.execute(
                """SELECT o.* FROM global_market_observations o
                JOIN (SELECT DISTINCT observation_id FROM bulk_resolution_matches
                      WHERE observation_id IS NOT NULL) m
                  ON m.observation_id=o.observation_id"""
            ).fetchall()

        checkpoints: dict[str, IntelligenceCheckpoint] = {}
        observations: dict[str, GlobalMarketObservation] = {}
        batches = 0
        for offset in range(0, len(checkpoint_rows), batch_size):
            batches += 1
            for row in checkpoint_rows[offset:offset + batch_size]:
                decoded = self._decode(row)
                checkpoints[decoded.checkpoint_id] = decoded
            time.sleep(0)
        for offset in range(0, len(observation_rows), batch_size):
            batches += 1
            for row in observation_rows[offset:offset + batch_size]:
                decoded = self._decode_observation(row)
                observations[decoded.observation_id] = decoded
            time.sleep(0)

        results: list[
            tuple[IntelligenceCheckpoint, GlobalMarketObservation | None, HistoricalResolutionState] | None
        ] = [None] * len(requests)
        for row in match_rows:
            stored = checkpoints.get(str(row["checkpoint_id"]))
            if stored is None:
                continue
            observation_id = row["observation_id"]
            results[int(row["request_id"])] = (
                stored,
                observations.get(str(observation_id)) if observation_id is not None else None,
                HistoricalResolutionState(row["resolution_state"]),
            )
        metrics = {
            "sqlite_connections": 1,
            "sqlite_queries": 3,
            "rows_loaded": len(match_rows) + len(checkpoint_rows) + len(observation_rows),
            "objects_decoded": len(checkpoints) + len(observations),
            "batches": batches,
        }
        return results, metrics

    def observations(
        self, *, asset_id: str | None = None, market_context_id: str | None = None,
        limit: int = 100,
    ) -> list[GlobalMarketObservation]:
        clauses, values = [], []
        if asset_id:
            clauses.append("asset_id=?")
            values.append(asset_id)
        if market_context_id:
            clauses.append("market_context_id=?")
            values.append(market_context_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM global_market_observations{where} ORDER BY observed_at DESC LIMIT ?",
                (*values, max(1, min(int(limit), 500))),
            ).fetchall()
        return [self._decode_observation(row) for row in rows]

    def observation_at_or_before(
        self, *, asset_id: str, market_context_id: str, event_at: str,
    ) -> GlobalMarketObservation | None:
        """Read one legitimate pre-event state without creating an observation."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM global_market_observations
                WHERE asset_id=? AND market_context_id=? AND observed_at<=?
                ORDER BY observed_at DESC,created_at DESC LIMIT 1""",
                (asset_id, market_context_id, event_at),
            ).fetchone()
        return self._decode_observation(row) if row else None

    def market_memory_health(self) -> dict[str, Any]:
        with self._connect() as connection:
            observations = connection.execute(
                "SELECT COUNT(*) FROM global_market_observations"
            ).fetchone()[0]
            references = connection.execute(
                "SELECT COUNT(*) FROM market_observation_references"
            ).fetchone()[0]
            unavailable = connection.execute(
                "SELECT COUNT(*) FROM market_observation_references WHERE observation_id IS NULL"
            ).fetchone()[0]
            final_unavailable = connection.execute(
                "SELECT COUNT(*) FROM market_observation_references WHERE resolution_state=?",
                (HistoricalResolutionState.FINAL_UNAVAILABLE.value,),
            ).fetchone()[0]
            retryable_unavailable = connection.execute(
                "SELECT COUNT(*) FROM market_observation_references WHERE resolution_state=?",
                (HistoricalResolutionState.RETRYABLE_UNAVAILABLE.value,),
            ).fetchone()[0]
            reused = connection.execute(
                "SELECT COUNT(*) FROM market_observation_references WHERE market_state=?",
                (MarketObservationDecision.REUSED_OBSERVATION.value,),
            ).fetchone()[0]
            cross_league = connection.execute(
                """SELECT COUNT(*) FROM (SELECT observation_id FROM market_observation_references
                WHERE observation_id IS NOT NULL GROUP BY observation_id
                HAVING COUNT(DISTINCT league_id)>1)"""
            ).fetchone()[0]
            by_asset = dict(connection.execute(
                "SELECT asset_type,COUNT(*) FROM global_market_observations GROUP BY asset_type"
            ).fetchall())
            contexts = connection.execute(
                "SELECT COUNT(DISTINCT market_context_id) FROM global_market_observations"
            ).fetchone()[0]
            observation_bytes = connection.execute(
                """SELECT COALESCE(SUM(length(observation_id)+length(asset_id)+length(asset_type)+
                length(market_context_id)+length(observed_at)+length(provider_evidence_json)+
                length(provenance_type)+length(semantic_fingerprint)+length(model_version)+
                length(normalization_version)+length(materiality_policy_version)+length(schema_version)+64),0)
                FROM global_market_observations"""
            ).fetchone()[0]
            reference_bytes = connection.execute(
                """SELECT COALESCE(SUM(length(reference_id)+length(checkpoint_id)+
                COALESCE(length(observation_id),0)+length(asset_id)+COALESCE(length(league_id),0)+
                COALESCE(length(event_id),0)+length(trigger_type)+length(occurred_at)+
                length(market_state)+length(provenance_type)+
                COALESCE(length(market_context_id),0)+COALESCE(length(resolver_version),0)+
                COALESCE(length(resolution_state),0)+COALESCE(length(unavailable_reason),0)+24),0)
                FROM market_observation_references"""
            ).fetchone()[0]
            references_by_trigger = dict(connection.execute(
                "SELECT trigger_type,COUNT(*) FROM market_observation_references GROUP BY trigger_type"
            ).fetchall())
            observations_by_provenance = dict(connection.execute(
                "SELECT provenance_type,COUNT(*) FROM global_market_observations GROUP BY provenance_type"
            ).fetchall())
            migrated_exactly = connection.execute(
                """SELECT COUNT(*) FROM intelligence_checkpoints c
                JOIN market_observation_references r ON r.checkpoint_id=c.checkpoint_id
                WHERE c.market_value IS NOT NULL AND r.observation_id IS NOT NULL"""
            ).fetchone()[0]
            migrated_shared = connection.execute(
                """SELECT COALESCE(SUM(reference_count-1),0) FROM (
                SELECT COUNT(*) AS reference_count FROM intelligence_checkpoints c
                JOIN market_observation_references r ON r.checkpoint_id=c.checkpoint_id
                WHERE c.market_value IS NOT NULL AND r.observation_id IS NOT NULL
                GROUP BY r.observation_id HAVING COUNT(*)>1)"""
            ).fetchone()[0]
            legacy_embedded = connection.execute(
                """SELECT COUNT(*) FROM intelligence_checkpoints c
                LEFT JOIN market_observation_references r ON r.checkpoint_id=c.checkpoint_id
                WHERE c.market_value IS NOT NULL AND r.reference_id IS NULL"""
            ).fetchone()[0]
            no_market_evidence = connection.execute(
                """SELECT COUNT(*) FROM intelligence_checkpoints c
                JOIN market_observation_references r ON r.checkpoint_id=c.checkpoint_id
                WHERE c.market_value IS NULL AND r.observation_id IS NULL"""
            ).fetchone()[0]
            page_count = connection.execute("PRAGMA page_count").fetchone()[0]
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        durable_migration = {
            "checkpoints_examined": (
                migrated_exactly + legacy_embedded + no_market_evidence
            ),
            "migratable_exactly": migrated_exactly,
            "migratable_with_shared_observation": migrated_shared,
            "legacy_embedded_evidence": legacy_embedded,
            "no_market_evidence": no_market_evidence,
            "unavailable": no_market_evidence,
            "equivalence_failures": legacy_embedded,
            "last_run": dict(self._migration_summary),
        }
        return {
            "status": "healthy", "observation_count": observations,
            "reference_count": references, "unavailable_references": unavailable,
            "final_unavailable_references": final_unavailable,
            "retryable_unavailable_references": retryable_unavailable,
            "observations_reused": reused, "cross_league_reuse_count": cross_league,
            "duplicate_observation_writes_avoided": reused,
            "observations_by_asset_type": by_asset, "market_contexts": contexts,
            "materiality_policy_version": MarketObservationMaterialityPolicy().version,
            "observation_bytes": observation_bytes, "reference_bytes": reference_bytes,
            "durable_resolution_metadata_bytes": reference_bytes,
            "references_by_trigger": references_by_trigger,
            "observations_by_provenance": observations_by_provenance,
            "database_allocated_bytes": page_count * page_size,
            "request_time_writes": 0, "league_id_in_observation_identity": False,
            "historical_observation_current_fallback": 0,
            "per_league_permanent_historical_market_bytes": 0,
            "permanent_provider_snapshot_bytes": 0,
            "checkpoint_migration": durable_migration,
        }

    def migrate_embedded_market_evidence(self) -> dict[str, int]:
        """Link exact legacy evidence without rewriting or discarding embedded facts."""
        from .market_memory import market_context_id

        counts = {
            "checkpoints_examined": 0, "migratable_exactly": 0,
            "migratable_with_shared_observation": 0,
            "legacy_embedded_evidence": 0, "no_market_evidence": 0,
            "unavailable": 0, "references_created": 0,
            "observations_created": 0, "equivalence_failures": 0,
        }
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM intelligence_checkpoints
                WHERE checkpoint_id NOT IN (
                  SELECT checkpoint_id FROM market_observation_references
                ) ORDER BY observed_at,checkpoint_id"""
            ).fetchall()
        for row in rows:
            counts["checkpoints_examined"] += 1
            checkpoint = self._decode(row)
            if checkpoint.market_value is None:
                counts["no_market_evidence"] += 1
                _, inserted = self.put_reference(
                    checkpoint, None, MarketObservationDecision.UNAVAILABLE,
                )
                counts["references_created"] += int(inserted)
                counts["unavailable"] += 1
                continue
            if not checkpoint.provenance_type.definitive_process_evidence:
                counts["legacy_embedded_evidence"] += 1
                continue
            try:
                observation, decision, created = self.resolve_observation(
                    checkpoint,
                    market_context_id=market_context_id(
                        asset_type=checkpoint.asset_type,
                        scoring_profile_id=checkpoint.scoring_profile_id,
                    ),
                )
                if observation is None:
                    raise ValueError("Exact market evidence did not resolve an observation.")
                reference, inserted = self.put_reference(checkpoint, observation, decision)
                with self._lock, self._connect() as connection:
                    connection.execute(
                        """UPDATE intelligence_checkpoints
                        SET global_market_observation_id=?
                        WHERE checkpoint_id=? AND global_market_observation_id IS NULL""",
                        (observation.observation_id, reference.checkpoint_id),
                    )
                counts["migratable_exactly"] += 1
                counts["migratable_with_shared_observation"] += int(
                    decision is MarketObservationDecision.REUSED_OBSERVATION
                )
                counts["observations_created"] += int(created)
                counts["references_created"] += int(inserted)
            except Exception:
                counts["equivalence_failures"] += 1
                counts["legacy_embedded_evidence"] += 1
        return counts

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
        market = self.market_memory_health()
        count = int(health["checkpoint_count"])
        average = int(health["bytes"] / count) if count else 1024
        observations = int(market["observation_count"])
        references = int(market["reference_count"])
        observation_average = int(market["observation_bytes"] / observations) if observations else 1024
        reference_average = int(market["reference_bytes"] / references) if references else 256
        return {
            "average_bytes_per_checkpoint": average,
            "30_leagues": average * 3_000,
            "100_leagues": average * 10_000,
            "1000_leagues": average * 100_000,
            "100000_leagues": average * 10_000_000,
            "global_sparse_market": {
                "average_bytes_per_observation": observation_average,
                "average_bytes_per_reference": reference_average,
                "observation_growth_driver": "meaningful_global_market_state_changes",
                "reference_growth_driver": "meaningful_league_and_global_events",
                "league_count_is_not_observation_growth_driver": True,
            },
            "assumption": (
                "100 compact event references per league; global observations grow only "
                "with materially distinct market states; excludes disposable provider caches"
            ),
        }
