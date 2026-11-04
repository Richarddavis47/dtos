"""A fresh application process must restore only its configured league."""
from __future__ import annotations

import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from src.core.projection_intelligence.service import (
    PROJECTION_CONTRACT_VERSION, PROJECTION_MODEL_VERSION,
    PROJECTION_SCHEMA_VERSION, PROJECTION_SEMANTIC_POLICY_VERSION,
    ProjectionService,
)


class ProjectionStartupScopeTests(unittest.TestCase):
    def probe(self, configured: str, leagues: tuple[str, ...]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "projections.sqlite3"
            ProjectionService(database, league_id=configured)
            with closing(sqlite3.connect(database)) as connection:
                for index, league in enumerate(leagues):
                    snapshot = {
                        "schema_version": PROJECTION_SCHEMA_VERSION,
                        "model_version": PROJECTION_MODEL_VERSION,
                        "contract_version": PROJECTION_CONTRACT_VERSION,
                        "semantic_policy_version": PROJECTION_SEMANTIC_POLICY_VERSION,
                        "league_id": league, "season": 2031, "week": 1,
                        "generated_at": f"2031-09-01T00:00:0{index}+00:00",
                        "projection_snapshot_id": f"snapshot-{league}",
                        "scoring_profile_id": f"scoring-{league}",
                        "players": {},
                    }
                    connection.execute(
                        "INSERT INTO projection_snapshots VALUES (?,?,?,?,?,?)",
                        (snapshot["projection_snapshot_id"], league, 2031, 1,
                         snapshot["generated_at"], json.dumps(snapshot)),
                    )
                connection.commit()
            code = """
import json
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.projections import create_projections_router
from src.core.projection_intelligence.service import projection_service
app = FastAPI()
app.include_router(create_projections_router(service=projection_service))
with patch.object(projection_service, '_connect', side_effect=AssertionError('request database work')):
    with TestClient(app) as client:
        response = client.get('/api/projections?limit=1')
        repeated = client.get('/api/projections?limit=1')
        assert response.status_code == 200 and response.json() == repeated.json()
health = projection_service.health(include_accuracy=False)
print(json.dumps({'payload': response.json(), 'snapshot': health['active_snapshot_id'],
                  'restores': health['snapshot_restores'], 'generations': health['generations']}))
"""
            result = subprocess.run(
                [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "SLEEPER_LEAGUE_ID": configured,
                     "DTOS_PROJECTION_DB_FILE": str(database),
                     "DTOS_CACHE_FILE": str(root / "cache.json")},
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout.strip().splitlines()[-1])

    def test_newer_foreign_snapshot_never_becomes_default_startup_projection(self) -> None:
        result = self.probe("111", ("111", "222"))
        self.assertEqual(result["payload"]["projection"]["league_id"], "111")
        self.assertEqual(result["snapshot"], "snapshot-111")
        self.assertEqual(result["restores"], 1)
        self.assertEqual(result["generations"], 0)

    def test_missing_own_snapshot_remains_pending_not_foreign_fallback(self) -> None:
        result = self.probe("333", ("111", "222"))
        self.assertIsNone(result["payload"]["projection"])
        self.assertEqual(result["payload"]["status"], "pending")
        self.assertIsNone(result["snapshot"])
        self.assertEqual(result["restores"], 0)

    def test_configured_league_override_is_not_special_cased(self) -> None:
        for league in ("111", "222", "333"):
            with self.subTest(league=league):
                result = self.probe(league, ("111", "222", "333"))
                self.assertEqual(result["payload"]["projection"]["league_id"], league)
                self.assertEqual(result["snapshot"], f"snapshot-{league}")


if __name__ == "__main__":
    unittest.main()
