"""v1.10.36 canonical current-GM, history, confidence, and leaderboard contracts."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.fois import create_fois_router
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult, TradeFact, WaiverFact
from src.core.fois.identity import canonical_league_identity, identity_from_team
from src.core.fois.models import EvaluationKind, MetricStatus
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


def _history(wins: int = 9) -> dict[str, object]:
    return {
        "seasons": [
            SeasonResult(season, wins, 14 - wins, index + 1, league_size=10).__dict__
            for index, season in enumerate(range(2021, 2026))
        ],
        "expected_seasons": 5,
        "trades": [
            TradeFact(f"trade-{index}", 2021 + index % 5, None,
                      process_score=65 + index, partner_id=str(index % 4 + 1)).__dict__
            for index in range(6)
        ],
        "waivers": [WaiverFact(f"waiver-{index}", 2025, None, meaningful=True).__dict__
                    for index in range(6)],
    }


def _data(count: int = 10) -> dict[str, object]:
    return {
        "league": {
            "league_id": "season-2026", "root_league_id": "dynasty-root",
            "season": "2026", "name": "Day Traders",
        },
        "teams": [
            {"roster_id": index, "owner_id": f"owner-{index}",
             "owner": f"GM {index}", "team_name": f"Franchise {index}", "players": []}
            for index in range(1, count + 1)
        ],
        "fois_history": {str(index): _history(5 + index % 6) for index in range(1, count + 1)},
    }


class CanonicalFOISLeaderboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = FOISRepository(Path(self.directory.name) / "fois.sqlite3")
        self.service = FOISService(self.repository)

    def tearDown(self) -> None:
        self.directory.cleanup()

    async def test_ten_current_gms_produce_ten_canonical_rows_and_no_duplicates(self) -> None:
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            scores = await self.service.generate(_data())
        health = self.repository.canonical_health("season-2026", scores[0].model_version)
        self.assertEqual((health["current_gm_count"], health["current_canonical_count"],
                          health["duplicate_current_count"]), (10, 10, 0))
        self.assertEqual(len({score.gm_id for score in scores}), 10)
        self.assertTrue(all(score.evaluation_kind == EvaluationKind.CURRENT_CANONICAL for score in scores))

    async def test_unchanged_generation_is_idempotent_and_deduplicates_snapshots(self) -> None:
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            await self.service.generate(_data())
            before = self.repository.canonical_health("season-2026", "4.0")
            await self.service.generate(_data())
            after = self.repository.canonical_health("season-2026", "4.0")
        self.assertEqual(before["current_gm_count"], after["current_gm_count"])
        self.assertEqual(before["historical_snapshot_count"], after["historical_snapshot_count"])
        self.assertEqual(self.service.status()["snapshots_written"], 0)
        self.assertEqual(self.service.status()["snapshots_deduplicated"], 10)

    async def test_changed_generation_moves_prior_record_under_explicit_history(self) -> None:
        first = _data(1)
        changed = _data(1)
        changed["fois_history"]["1"] = _history(12)
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            await self.service.generate(first)
            await self.service.generate(changed)
        gm_id = "dynasty-root:gm:owner-1"
        timeline = self.repository.timeline("season-2026", gm_id)
        self.assertEqual(sum(row.evaluation_kind == "current_canonical" for row in timeline), 1)
        self.assertTrue(any(row.evaluation_kind == "historical_snapshot" for row in timeline))

    def test_identity_survives_season_league_ids_and_franchise_rename(self) -> None:
        old = {"league_id": "season-2025", "root_league_id": "dynasty-root"}
        new = {"league_id": "season-2026", "root_league_id": "dynasty-root"}
        first = identity_from_team(canonical_league_identity(old), {
            "roster_id": 2, "owner_id": "owner", "owner": "GM", "team_name": "Old Name",
        })
        second = identity_from_team(canonical_league_identity(new), {
            "roster_id": 2, "owner_id": "owner", "owner": "GM", "team_name": "New Name",
        })
        self.assertEqual((first.gm_id, first.franchise_id), (second.gm_id, second.franchise_id))

    async def test_gm_replacement_creates_new_tenure_and_closes_prior_tenure(self) -> None:
        first = _data(1)
        second = _data(1)
        second["teams"][0]["owner_id"] = "replacement"
        second["teams"][0]["owner"] = "New GM"
        second["fois_history"]["1"]["tenure_started_at"] = "2026-06-01"
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            await self.service.generate(first)
            await self.service.generate(second)
        tenures = self.repository.tenures("season-2026")
        self.assertEqual(len(tenures), 2)
        self.assertEqual([row.active for row in tenures], [False, True])
        self.assertEqual(self.repository.canonical_health("season-2026", "4.0")["current_gm_count"], 1)

    def test_missing_dimensions_are_unavailable_and_supported_weight_is_explicit(self) -> None:
        score = FOISEngine().evaluate(FOISFacts(
            "league", "franchise", "owner", (SeasonResult(2025, 8, 6, 3),),
        ))
        missing = [row for row in score.category_scores if row.normalized_score is None]
        self.assertTrue(missing)
        self.assertTrue(all(all(metric.status != MetricStatus.ACTIVE for metric in row.metric_scores)
                            for row in missing))
        self.assertLess(score.supported_weight, 100)
        self.assertGreater(score.overall_score or 0, 0)

    def test_confidence_and_completeness_are_distinct_and_incomplete_is_not_perfect(self) -> None:
        score = FOISEngine().evaluate(FOISFacts(
            "league", "franchise", "owner", (SeasonResult(2025, 8, 6, 3),), expected_seasons=5,
        ))
        self.assertNotEqual(score.confidence, score.completeness)
        self.assertLess(score.confidence, 100)
        self.assertTrue(score.provisional)

    def test_process_outcome_and_not_gradable_activity_remain_separate(self) -> None:
        score = FOISEngine().evaluate(FOISFacts(
            "league", "franchise", "owner", (SeasonResult(2025, 8, 6, 3),),
            trades=(
                TradeFact("gradable", 2025, None, process_score=85, outcome_score=30),
                TradeFact("not-gradable", 2025, None),
            ),
        ))
        trading = next(row for row in score.category_scores if row.category_key == "trading_asset_management")
        metrics = {row.metric_key: row for row in trading.metric_scores}
        self.assertEqual(metrics["trade_activity"].raw_value, 2)
        self.assertEqual(metrics["value_captured_at_transaction_time"].sample_size, 1)
        self.assertEqual(metrics["subsequent_asset_value_change"].raw_value, 30)

    def test_waiver_activity_is_visible_but_not_fabricated_as_quality(self) -> None:
        score = FOISEngine().evaluate(FOISFacts(
            "league", "franchise", "owner", (SeasonResult(2025, 8, 6, 3),),
            waivers=(WaiverFact("w", 2025, None, meaningful=True),),
        ))
        category = next(row for row in score.category_scores if row.category_key == "waivers_transactions")
        activity = next(row for row in category.metric_scores if row.metric_key == "waiver_activity")
        self.assertEqual(activity.raw_value, 1)
        self.assertIsNone(activity.normalized_score)
        self.assertIsNone(category.normalized_score)

    async def test_leaderboard_and_profile_separate_current_from_history(self) -> None:
        data = _data()
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            await self.service.generate(data)
        app = FastAPI()
        app.include_router(create_fois_router(
            service=self.service, require_data=lambda: data,
            page=lambda _title, body: HTMLResponse(body),
        ))
        client = TestClient(app)
        with patch.object(
            self.repository, "league", wraps=self.repository.league,
        ) as league_read:
            leaderboard = client.get("/fois")
            repeated = client.get("/fois")
        self.assertEqual(repeated.content, leaderboard.content)
        self.assertEqual(league_read.call_count, 2)
        cache_health = client.get("/api/fois/status").json()["render_cache"]
        self.assertEqual(cache_health["fois_render_cache_hits"], 1)
        self.assertEqual(cache_health["fois_render_cache_misses"], 1)
        self.assertEqual(cache_health["fois_render_cache_entries"], 1)
        self.assertGreater(cache_health["fois_render_cache_bytes"], 0)
        self.assertEqual(self.service.status()["request_time_provider_calls"], 0)
        self.assertEqual(leaderboard.text.count('data-fois-current="true"'), 10)
        self.assertIn('data-fois-leaderboard-count="10"', leaderboard.text)
        self.assertEqual(leaderboard.text.count("HISTORICAL SNAPSHOT"), 0)
        ranking = client.get("/api/fois/leagues/season-2026/rankings").json()
        self.assertEqual([row["rank"] for row in ranking["rankings"]], list(range(1, 11)))
        gm_id = ranking["rankings"][0]["gm_id"]
        profile = client.get(f"/fois/gms/{gm_id}?league_id=season-2026")
        self.assertIn("CURRENT GM PROFILE", profile.text)
        self.assertIn("GM History", profile.text)

    async def test_completed_generation_is_prewarmed_before_first_request(self) -> None:
        data = _data()
        app = FastAPI()
        app.include_router(create_fois_router(
            service=self.service, require_data=lambda: data,
            page=lambda _title, body: HTMLResponse(body),
        ))
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            await self.service.generate(data)

        client = TestClient(app)
        before = client.get("/api/fois/status").json()["render_cache"]
        response = client.get("/fois")
        after = client.get("/api/fois/status").json()["render_cache"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before["fois_render_cache_misses"], 1)
        self.assertEqual(after["fois_render_cache_hits"], 1)

    async def test_prewarm_failure_does_not_fail_generation(self) -> None:
        data = _data()

        def broken(_data, _scores) -> None:
            raise RuntimeError("render failed")

        self.service.add_generation_listener(broken)
        with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
            scores = await self.service.generate(data)
        self.assertEqual(len(scores), 10)
        self.assertEqual(self.service.status()["state"], "complete")


if __name__ == "__main__":
    unittest.main()
