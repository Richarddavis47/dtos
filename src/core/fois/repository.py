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
                "SELECT source_fingerprint FROM fois_scores WHERE score_key=?",
                (score.score_key,),
            ).fetchone()
            if existing and existing["source_fingerprint"] == source_fingerprint:
                return False
            connection.execute(
                """INSERT INTO fois_scores(
                score_key,league_id,franchise_id,owner_id,
                evaluation_start_season,evaluation_end_season,model_version,
                generated_at,source_fingerprint,payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(score_key) DO UPDATE SET
                owner_id=excluded.owner_id,generated_at=excluded.generated_at,
                source_fingerprint=excluded.source_fingerprint,payload=excluded.payload""",
                (
                    score.score_key, score.league_id, score.franchise_id,
                    score.owner_id, score.evaluation_start_season,
                    score.evaluation_end_season, score.model_version,
                    score.generated_at, source_fingerprint, payload,
                ),
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
                """SELECT payload FROM fois_scores
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
                """SELECT payload FROM fois_scores
                WHERE league_id=? AND model_version=?
                ORDER BY franchise_id""",
                (league_id, model_version),
            ).fetchall()
        return tuple(_score(json.loads(row["payload"])) for row in rows)

    def count(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM fois_scores").fetchone()[0])


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
        }
    )
