"""Idempotent SQLite persistence for explainable FOIS score snapshots."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from threading import RLock

from src.core.fois.models import (
    Directionality,
    FrontOfficeCategoryScore,
    FrontOfficeIntelligenceScore,
    FrontOfficeMetricScore,
    MetricStatus,
    EvaluationKind,
    FOIS_MODEL_VERSION,
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
            active_count = int(connection.execute(
                "SELECT COUNT(*) FROM fois_gm_tenures WHERE league_id=? AND active=1",
                (league_id,),
            ).fetchone()[0])
            if active_count:
                rows = connection.execute(
                    """SELECT scores.payload FROM fois_scores_v2 AS scores
                    JOIN fois_gm_tenures AS tenure ON tenure.tenure_id=scores.tenure_id
                    WHERE scores.league_id=? AND scores.model_version=? AND tenure.active=1
                    ORDER BY scores.franchise_id""",
                    (league_id, model_version),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT payload FROM fois_scores_v2
                    WHERE league_id=? AND model_version=? ORDER BY franchise_id""",
                    (league_id, model_version),
                ).fetchall()
        scores = tuple(_score(json.loads(row["payload"])) for row in rows)
        by_franchise: dict[str, FrontOfficeIntelligenceScore] = {}
        for score in scores:
            existing = by_franchise.get(score.franchise_id)
            if existing is None or (score.generated_at, score.score_key) > (
                existing.generated_at, existing.score_key,
            ):
                by_franchise[score.franchise_id] = score
        return tuple(by_franchise[key] for key in sorted(by_franchise))

    def league_ids(self, model_version: str) -> tuple[str, ...]:
        """Return persisted FOIS leagues without loading score payloads."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT league_id FROM fois_scores_v2 "
                "WHERE model_version=? ORDER BY league_id",
                (model_version,),
            ).fetchall()
        return tuple(str(row["league_id"]) for row in rows)

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

    def timeline(
        self, league_id: str, gm_id: str,
        model_version: str = FOIS_MODEL_VERSION,
    ) -> tuple[FrontOfficeIntelligenceScore, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM fois_snapshot_history WHERE league_id=? AND gm_id=? AND model_version=? ORDER BY generated_at,snapshot_id",
                (league_id, gm_id, model_version),
            ).fetchall()
        values = tuple(_score(json.loads(row["payload"])) for row in rows)
        current = self.score_for_gm(league_id, gm_id, model_version) if values else None
        return tuple(
            replace(
                value,
                evaluation_kind=(
                    EvaluationKind.CURRENT_CANONICAL.value
                    if current is not None and value.score_key == current.score_key
                    and value.model_version == current.model_version
                    and value.generated_at == current.generated_at
                    else EvaluationKind.HISTORICAL_SNAPSHOT.value
                ),
            )
            for value in values
        )

    def canonical_health(self, league_id: str, model_version: str) -> dict[str, object]:
        current = self.league(league_id, model_version)
        gm_ids = tuple(row.gm_id for row in current if row.gm_id)
        with self._connection() as connection:
            snapshots = int(connection.execute(
                "SELECT COUNT(*) FROM fois_snapshot_history WHERE league_id=? AND model_version=?",
                (league_id, model_version),
            ).fetchone()[0])
            tenures = int(connection.execute(
                "SELECT COUNT(*) FROM fois_gm_tenures WHERE league_id=? AND active=0",
                (league_id,),
            ).fetchone()[0])
            obsolete = int(connection.execute(
                "SELECT COUNT(*) FROM fois_snapshot_history WHERE league_id=? AND model_version<>?",
                (league_id, model_version),
            ).fetchone()[0])
            duplicate_derivations = int(connection.execute(
                """SELECT COALESCE(SUM(c-1),0) FROM (
                SELECT COUNT(*) AS c FROM fois_snapshot_history
                WHERE league_id=? AND model_version=? GROUP BY score_key
                )""",
                (league_id, model_version),
            ).fetchone()[0])
            current_bytes = int(connection.execute(
                "SELECT COALESCE(SUM(LENGTH(payload)),0) FROM fois_scores_v2 WHERE league_id=? AND model_version=?",
                (league_id, model_version),
            ).fetchone()[0])
            snapshot_bytes = int(connection.execute(
                "SELECT COALESCE(SUM(LENGTH(payload)),0) FROM fois_snapshot_history WHERE league_id=?",
                (league_id,),
            ).fetchone()[0])
        return {
            "current_gm_count": len(current),
            "current_canonical_count": len(current),
            "duplicate_current_count": len(gm_ids) - len(set(gm_ids)),
            "historical_snapshot_count": max(0, snapshots - len(current)),
            "historical_tenure_count": tenures,
            "duplicate_derivation_count": duplicate_derivations,
            "incomplete_obsolete_derivation_count": obsolete,
            "current_evaluation_bytes": current_bytes,
            "historical_snapshot_bytes": snapshot_bytes,
            "total_fois_bytes": current_bytes + snapshot_bytes,
            "overall_completeness": round(
                sum(row.completeness for row in current) / len(current), 2,
            ) if current else 0.0,
            "confidence_distribution": [row.confidence for row in current],
            "supported_weight_distribution": [row.supported_weight for row in current],
            "unavailable_dimension_count": sum(
                category.normalized_score is None
                for row in current for category in row.category_scores
            ),
        }

    def score_for_gm(self, league_id: str, gm_id: str, model_version: str) -> FrontOfficeIntelligenceScore | None:
        with self._connection() as connection:
            active_count = int(connection.execute(
                "SELECT COUNT(*) FROM fois_gm_tenures WHERE league_id=? AND active=1",
                (league_id,),
            ).fetchone()[0])
            if active_count:
                row = connection.execute(
                    """SELECT scores.payload FROM fois_scores_v2 AS scores
                    JOIN fois_gm_tenures AS tenure ON tenure.tenure_id=scores.tenure_id
                    WHERE scores.league_id=? AND scores.gm_id=? AND scores.model_version=?
                    AND tenure.active=1 ORDER BY scores.generated_at DESC LIMIT 1""",
                    (league_id, gm_id, model_version),
                ).fetchone()
            else:
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
            "tendencies": tuple(payload.get("tendencies") or ()),
            "unavailable_tendencies": tuple(payload.get("unavailable_tendencies") or ()),
        }
    )
