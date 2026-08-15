"""FOIS v1.9.0 GM identity, scoring, persistence, and read-contract tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.fois import create_fois_router
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult, TradeFact
from src.core.fois.models import GMTenure, TakeoverSnapshot
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


def seasons(count: int = 16) -> tuple[SeasonResult, ...]:
    return tuple(
        SeasonResult(2000 + index, 9, 5, (index % 10) + 1,
                     playoff=index % 2 == 0, championship=index == 4,
                     league_size=10)
        for index in range(count)
    )


class FOISGeneralManagerIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    def test_full_tenure_has_no_ten_year_cap(self) -> None:
        score = FOISEngine().evaluate(FOISFacts("league", "franchise", "owner", seasons()))
        self.assertEqual(score.seasons_evaluated, 16)
        results = next(row for row in score.category_scores if row.category_key == "results")
        self.assertEqual(len(results.details["timeline"]), 16)

    def test_process_outcome_and_recovery_are_separate(self) -> None:
        facts = FOISFacts(
            "league", "franchise", "owner", seasons(3),
            trades=(TradeFact("trade-1", 2025, True, process_score=90,
                              outcome_score=20, context_score=85,
                              recovery_score=75, impact_weight=4),),
        )
        score = FOISEngine().evaluate(facts)
        trading = next(row for row in score.category_scores if row.category_key == "trading_asset_management")
        values = {row.metric_key: row.raw_value for row in trading.metric_scores}
        self.assertEqual(values["value_captured_at_transaction_time"], 90)
        self.assertEqual(values["subsequent_asset_value_change"], 20)
        self.assertEqual(values["recovery_from_unsuccessful_trades"], 75)

    def test_missing_categories_never_become_zero(self) -> None:
        score = FOISEngine().evaluate(FOISFacts("league", "franchise", "owner", ()))
        self.assertIsNone(score.overall_score)
        self.assertEqual(score.evidence_state, "insufficient_evidence")
        self.assertTrue(all(row.normalized_score is None for row in score.category_scores))

    def test_ownership_change_closes_old_tenure_without_score_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            first = GMTenure("t1", "league", "franchise", "gm:old", "Old GM", "2021-01-01")
            second = GMTenure("t2", "league", "franchise", "gm:new", "New GM", "2026-01-01")
            repository.ensure_tenure(first)
            repository.ensure_tenure(second)
            rows = repository.tenures("league", franchise_id="franchise")
            self.assertEqual([(row.gm_id, row.active) for row in rows], [("gm:old", False), ("gm:new", True)])
            self.assertEqual(rows[0].ended_at, "2026-01-01")
            self.assertIsNone(repository.score_for_gm("league", "gm:new", "2.0"))

    def test_takeover_snapshot_is_immutable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            tenure = GMTenure("t1", "league", "franchise", "gm", "GM", "2025-01-01")
            snapshot = TakeoverSnapshot("takeover", "t1", "2025-01-01", "brain-1",
                                        "Rebuilding", ("player:1",), ("pick:1",), (), {"rank": 10})
            repository.ensure_tenure(tenure, snapshot)
            repository.ensure_tenure(tenure, replace(snapshot, context={"rank": 1}))
            self.assertEqual(repository.takeover("t1").context, {"rank": 10})

    async def test_generation_is_idempotent_and_tenure_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            service = FOISService(repository)
            data = {
                "league": {"league_id": "league", "season": "2026"},
                "teams": [{"roster_id": 1, "owner_id": "owner", "owner": "GM", "players": []}],
                "fois_history": {"1": {"seasons": [row.__dict__ for row in seasons(3)]}},
            }
            first = await service.generate(data)
            second = await service.generate(data)
            self.assertEqual(first[0].score_key, second[0].score_key)
            self.assertEqual(repository.count(), 1)
            self.assertEqual(len(repository.timeline("league", "league:gm:owner")), 1)

    def test_read_apis_expose_canonical_metadata_and_categories(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            service = FOISService(repository)
            app = FastAPI()
            app.include_router(create_fois_router(service=service, require_data=lambda: {}))
            client = TestClient(app)
            root = client.get("/api/fois")
            self.assertEqual(root.status_code, 200)
            self.assertEqual(root.json()["application_version"], "1.10.23")
            self.assertEqual(root.json()["application_build"], 1123)
            paths = app.openapi()["paths"]
            for path in (
                "/api/fois/leagues/{league_id}/rankings",
                "/api/fois/leagues/{league_id}/gms/{gm_id}",
                "/api/fois/leagues/{league_id}/gms/{gm_id}/trading",
                "/api/fois/leagues/{league_id}/gms/{gm_id}/drafting",
                "/api/fois/leagues/{league_id}/compare",
            ):
                self.assertIn(path, paths)

    def test_score_key_changes_across_tenures_not_generation_time(self) -> None:
        facts = FOISFacts("league", "franchise", "owner", seasons(3), tenure_id="tenure-1")
        engine = FOISEngine()
        first = engine.evaluate(facts, generated_at="2026-01-01T00:00:00+00:00")
        replay = engine.evaluate(facts, generated_at="2026-02-01T00:00:00+00:00")
        successor = engine.evaluate(replace(facts, tenure_id="tenure-2", gm_id="new"))
        self.assertEqual(first.score_key, replay.score_key)
        self.assertNotEqual(first.score_key, successor.score_key)


if __name__ == "__main__":
    unittest.main()
