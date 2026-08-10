"""Idempotent SQLite persistence for explainable FOIS score snapshots."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from threading import RLock

from src.core.fois.models import (
    Directionality,
    FrontOfficeCategoryScore,
    FrontOfficeIntelligenceScore,
    FrontOfficeMetricScore,
    MetricStatus,
    GMTenure,
    TakeoverSnapshot,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fois_scores (
  score_key TEXT PRIMARY KEY,
  league_id TEXT NOT NULL,
  franchise_id TEXT NOT NULL,
  owner_id TEXT,
  evaluation_start_season INTEGER NOT NULL,
  evaluation_end_season INTEGER NOT NULL,
  model_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  source_fingerprint TEXT NOT NULL,
  payload TEXT NOT NULL,
  UNIQUE(league_id, franchise_id, evaluation_start_season, evaluation_end_season, model_version)
);
CREATE INDEX IF NOT EXISTS idx_fois_league
ON fois_scores(league_id, model_version, franchise_id);
CREATE TABLE IF NOT EXISTS fois_scores_v2 (
  score_key TEXT PRIMARY KEY,
  league_id TEXT NOT NULL,
  franchise_id TEXT NOT NULL,
  gm_id TEXT,
  tenure_id TEXT,
  owner_id TEXT,
  evaluation_start_season INTEGER NOT NULL,
  evaluation_end_season INTEGER NOT NULL,
  model_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  source_fingerprint TEXT NOT NULL,
  payload TEXT NOT NULL,
  UNIQUE(league_id, tenure_id, evaluation_start_season, evaluation_end_season, model_version)
);
CREATE INDEX IF NOT EXISTS idx_fois_v2_league
ON fois_scores_v2(league_id, model_version, franchise_id);
CREATE TABLE IF NOT EXISTS fois_gm_tenures (
  tenure_id TEXT PRIMARY KEY,
  league_id TEXT NOT NULL,
  franchise_id TEXT NOT NULL,
  gm_id TEXT NOT NULL,
  gm_name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  active INTEGER NOT NULL,
  UNIQUE(league_id, franchise_id, gm_id, started_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fois_one_active_tenure
ON fois_gm_tenures(league_id, franchise_id) WHERE active=1;
CREATE INDEX IF NOT EXISTS idx_fois_gm
ON fois_gm_tenures(league_id, gm_id, started_at);
CREATE TABLE IF NOT EXISTS fois_takeover_snapshots (
  takeover_id TEXT PRIMARY KEY,
  tenure_id TEXT NOT NULL UNIQUE,
  captured_at TEXT NOT NULL,
  payload TEXT NOT NULL,
  FOREIGN KEY(tenure_id) REFERENCES fois_gm_tenures(tenure_id)
);
CREATE TABLE IF NOT EXISTS fois_snapshot_history (
  snapshot_id TEXT PRIMARY KEY,
  score_key TEXT NOT NULL,
  tenure_id TEXT,
  league_id TEXT NOT NULL,
  gm_id TEXT,
  model_version TEXT NOT NULL,
  brain_snapshot_id TEXT,
  generated_at TEXT NOT NULL,
  source_fingerprint TEXT NOT NULL,
  payload TEXT NOT NULL,
  UNIQUE(score_key, source_fingerprint)
);
CREATE TABLE IF NOT EXISTS fois_evidence_links (
  score_key TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  PRIMARY KEY(score_key, evidence_id)
);
"""


class FOISRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def save(
        self,
        score: FrontOfficeIntelligenceScore,
        source_fingerprint: str,
    ) -> bool:
        payload = json.dumps(asdict(score), sort_keys=True, separators=(",", ":"))
        with self._lock, self._connection() as connection:
            existing = connection.execute(
                "SELECT source_fingerprint FROM fois_scores_v2 WHERE score_key=?",
                (score.score_key,),
            ).fetchone()
            if existing and existing["source_fingerprint"] == source_fingerprint:
                return False
            connection.execute(
                """INSERT INTO fois_scores_v2(
                score_key,league_id,franchise_id,gm_id,tenure_id,owner_id,
                evaluation_start_season,evaluation_end_season,model_version,
                generated_at,source_fingerprint,payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(score_key) DO UPDATE SET
                owner_id=excluded.owner_id,generated_at=excluded.generated_at,
                source_fingerprint=excluded.source_fingerprint,payload=excluded.payload""",
                (
                    score.score_key, score.league_id, score.franchise_id,
                    score.gm_id, score.tenure_id, score.owner_id, score.evaluation_start_season,
                    score.evaluation_end_season, score.model_version,
                    score.generated_at, source_fingerprint, payload,
                ),
            )
            snapshot_id = __import__("hashlib").sha256(
                f"{score.score_key}|{source_fingerprint}".encode()
            ).hexdigest()
            connection.execute(
                """INSERT OR IGNORE INTO fois_snapshot_history(
                snapshot_id,score_key,tenure_id,league_id,gm_id,model_version,
                brain_snapshot_id,generated_at,source_fingerprint,payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (snapshot_id, score.score_key, score.tenure_id, score.league_id,
                 score.gm_id, score.model_version, score.brain_snapshot_id,
                 score.generated_at, source_fingerprint, payload),
            )
            connection.executemany(
                "INSERT OR IGNORE INTO fois_evidence_links(score_key,evidence_id,evidence_type) VALUES (?,?,?)",
                ((score.score_key, evidence_id, "canonical_history") for evidence_id in score.evidence_references),
            )
            connection.commit()
        return True

    def get(
        self,
        league_id: str,
        franchise_id: str,
        model_version: str,
    ) -> FrontOfficeIntelligenceScore | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT payload FROM fois_scores_v2
                WHERE league_id=? AND franchise_id=? AND model_version=?
                ORDER BY evaluation_end_season DESC LIMIT 1""",
                (league_id, franchise_id, model_version),
            ).fetchone()
        return _score(json.loads(row["payload"])) if row else None

    def league(
        self,
        league_id: str,
        model_version: str,
    ) -> tuple[FrontOfficeIntelligenceScore, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT payload FROM fois_scores_v2
                WHERE league_id=? AND model_version=?
                ORDER BY franchise_id""",
                (league_id, model_version),
            ).fetchall()
        return tuple(_score(json.loads(row["payload"])) for row in rows)

    def count(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM fois_scores_v2").fetchone()[0])

    def ensure_tenure(self, tenure: GMTenure, takeover: TakeoverSnapshot | None = None) -> GMTenure:
        """Persist one active GM tenure without transferring a prior GM score."""
        with self._lock, self._connection() as connection:
            active = connection.execute(
                "SELECT * FROM fois_gm_tenures WHERE league_id=? AND franchise_id=? AND active=1",
                (tenure.league_id, tenure.franchise_id),
            ).fetchone()
            if active and active["gm_id"] != tenure.gm_id:
                connection.execute(
                    "UPDATE fois_gm_tenures SET active=0,ended_at=? WHERE tenure_id=?",
                    (tenure.started_at, active["tenure_id"]),
                )
            connection.execute(
                """INSERT OR IGNORE INTO fois_gm_tenures(
                tenure_id,league_id,franchise_id,gm_id,gm_name,started_at,ended_at,active
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (tenure.tenure_id, tenure.league_id, tenure.franchise_id,
                 tenure.gm_id, tenure.gm_name, tenure.started_at,
                 tenure.ended_at, int(tenure.active)),
            )
            if takeover is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO fois_takeover_snapshots(takeover_id,tenure_id,captured_at,payload) VALUES (?,?,?,?)",
                    (takeover.takeover_id, takeover.tenure_id, takeover.captured_at,
                     json.dumps(asdict(takeover), sort_keys=True, separators=(",", ":"))),
                )
            connection.commit()
        return tenure

    def tenures(self, league_id: str, *, franchise_id: str | None = None) -> tuple[GMTenure, ...]:
        sql = "SELECT * FROM fois_gm_tenures WHERE league_id=?"
        params: list[str] = [league_id]
        if franchise_id is not None:
            sql += " AND franchise_id=?"
            params.append(franchise_id)
        sql += " ORDER BY started_at,tenure_id"
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return tuple(GMTenure(
            row["tenure_id"], row["league_id"], row["franchise_id"], row["gm_id"],
            row["gm_name"], row["started_at"], row["ended_at"], bool(row["active"]),
        ) for row in rows)

    def tenure_for_gm(self, league_id: str, gm_id: str) -> GMTenure | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM fois_gm_tenures WHERE league_id=? AND gm_id=? ORDER BY active DESC,started_at DESC LIMIT 1",
                (league_id, gm_id),
            ).fetchone()
        if row is None:
            return None
        return GMTenure(row["tenure_id"], row["league_id"], row["franchise_id"],
                        row["gm_id"], row["gm_name"], row["started_at"],
                        row["ended_at"], bool(row["active"]))

    def takeover(self, tenure_id: str) -> TakeoverSnapshot | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM fois_takeover_snapshots WHERE tenure_id=?", (tenure_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload"])
        return TakeoverSnapshot(**{**payload,
            "roster_asset_ids": tuple(payload["roster_asset_ids"]),
            "draft_pick_ids": tuple(payload["draft_pick_ids"]),
            "inherited_obligations": tuple(payload["inherited_obligations"]),
        })

    def timeline(self, league_id: str, gm_id: str) -> tuple[FrontOfficeIntelligenceScore, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM fois_snapshot_history WHERE league_id=? AND gm_id=? ORDER BY generated_at,snapshot_id",
                (league_id, gm_id),
            ).fetchall()
        return tuple(_score(json.loads(row["payload"])) for row in rows)

    def score_for_gm(self, league_id: str, gm_id: str, model_version: str) -> FrontOfficeIntelligenceScore | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT payload FROM fois_scores_v2
                WHERE league_id=? AND gm_id=? AND model_version=?
                ORDER BY generated_at DESC LIMIT 1""",
                (league_id, gm_id, model_version),
            ).fetchone()
        return _score(json.loads(row["payload"])) if row else None


def _metric(payload: dict) -> FrontOfficeMetricScore:
    return FrontOfficeMetricScore(
        **{
            **payload,
            "directionality": Directionality(payload["directionality"]),
            "status": MetricStatus(payload["status"]),
            "evidence_references": tuple(payload["evidence_references"]),
            "warnings": tuple(payload["warnings"]),
        }
    )


def _category(payload: dict) -> FrontOfficeCategoryScore:
    return FrontOfficeCategoryScore(
        **{
            **payload,
            "metric_scores": tuple(_metric(row) for row in payload["metric_scores"]),
            "evidence_references": tuple(payload["evidence_references"]),
            "warnings": tuple(payload["warnings"]),
            "strengths": tuple(payload.get("strengths") or ()),
            "weaknesses": tuple(payload.get("weaknesses") or ()),
        }
    )


def _score(payload: dict) -> FrontOfficeIntelligenceScore:
    return FrontOfficeIntelligenceScore(
        **{
            **payload,
            "category_scores": tuple(_category(row) for row in payload["category_scores"]),
            "evidence_references": tuple(payload["evidence_references"]),
            "warnings": tuple(payload["warnings"]),
            "strengths": tuple(payload.get("strengths") or ()),
            "weaknesses": tuple(payload.get("weaknesses") or ()),
        }
    )
