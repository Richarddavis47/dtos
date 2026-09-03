from __future__ import annotations

import copy
import asyncio
import contextvars
import threading
import time
import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from routes.audit import create_audit_router
from services.projection_audit import build_projection_audit


class FakeMarket:
    league_id = "league-1"
    brain_generation = "brain-1"
    assets = [{
        "asset_id": "player:10", "position": "QB", "owner": "Alpha",
        "availability": "rostered", "confidence": 88,
        "values": {"market_value": 7000, "intrinsic_dtos_value": 7100,
                   "contender_value": 7400, "rebuilder_value": 6800,
                   "liquidity_score": 75},
    }]
    by_id = {row["asset_id"]: row for row in assets}

    def identity(self):
        return {"market_generation": "market-1"}

    def audit_identity(self):
        return {"market_generation": "market-1", "brain_snapshot_id": "1.10.11:brain-1"}

    def directory(self, *, limit, sort):
        return {"assets": [{**self.assets[0], "rank": 1}]}


@dataclass(frozen=True)
class Category:
    category_key: str
    normalized_score: float


@dataclass(frozen=True)
class Score:
    gm_id: str = "gm-1"
    gm_name: str = "General Manager"
    franchise_id: str = "1"
    overall_score: float = 82.0
    overall_letter_grade: str = "B"
    category_scores: tuple[Category, ...] = (
        Category("results", 80), Category("trading_asset_management", 81),
        Category("roster_construction", 82), Category("drafting_talent_evaluation", 83),
    )
    confidence: float = 90
    completeness: float = 95
    brain_snapshot_id: str = "brain-1"
    evidence_references: tuple[str, ...] = ("projection_snapshot:projection-1",)


def fixture():
    data = {
        "league": {"league_id": "league-1", "name": "Day Traders"},
        "nfl_state": {"season_type": "regular"},
        "matchups": {"1": [{
            "team": "Alpha", "owner": "GM A", "roster_id": 1, "points": 12,
            "lineup": [{"id": "10", "name": "J. Daniels", "position": "QB",
                        "nfl_team": "WAS", "slot": "QB", "points": 12}],
        }, {
            "team": "Beta", "owner": "GM B", "roster_id": 2, "points": 0,
            "lineup": [{"id": "11", "name": "Missing Player", "position": "RB",
                        "nfl_team": None, "slot": "RB", "points": 0}],
        }]},
    }
    snapshot = {
        "season": "2026", "week": 1, "projection_snapshot_id": "projection-1",
        "players": {"10": {"sleeper_projection": 17.91, "raw_dtos_projection": 21.5,
                            "dtos_projection": 20.0, "calibration_adjustment": -1.5,
                            "calibration_reason": "External evidence moderates the raw forecast.",
                            "fallback_state": "player_specific", "evidence_depth": 82,
                            "canonical_projection": 19.27, "weekly_floor": 14,
                            "weekly_median": 19.27, "weekly_ceiling": 25,
                            "projection_confidence": 84, "projection_agreement": "High",
                            "sleeper_freshness": "Fresh"}},
    }
    return data, snapshot


class ProjectionAuditTests(unittest.IsolatedAsyncioTestCase):
    def test_player_calibration_restores_team_separation_without_copying_sleeper(self):
        data, snapshot = fixture()
        data["matchups"] = {"5": [{
            "team": "Elite", "owner": "GM E", "roster_id": 1, "points": 0,
            "lineup": [
                {"id": "1", "name": "Elite One", "position": "RB", "slot": "RB"},
                {"id": "2", "name": "Elite Two", "position": "WR", "slot": "WR"},
            ],
        }, {
            "team": "Developing", "owner": "GM D", "roster_id": 2, "points": 0,
            "lineup": [
                {"id": "3", "name": "Reserve One", "position": "RB", "slot": "RB"},
                {"id": "4", "name": "Reserve Two", "position": "WR", "slot": "WR"},
            ],
        }]}
        snapshot["players"] = {
            "1": {"sleeper_projection": 20.0, "raw_dtos_projection": 10.0,
                  "dtos_projection": 17.0, "canonical_projection": 17.0},
            "2": {"sleeper_projection": 18.0, "raw_dtos_projection": 10.0,
                  "dtos_projection": 16.0, "canonical_projection": 16.0},
            "3": {"sleeper_projection": 4.0, "raw_dtos_projection": 10.0,
                  "dtos_projection": 5.0, "canonical_projection": 5.0},
            "4": {"sleeper_projection": 3.0, "raw_dtos_projection": 10.0,
                  "dtos_projection": 4.0, "canonical_projection": 4.0},
        }
        result = build_projection_audit(
            data=data, projection_snapshot=snapshot, projection_health={"status": "ready"},
            market=FakeMarket(), fois_scores=(), now="2026-08-11T00:00:00+00:00",
        )
        elite, developing = result["teams"]
        self.assertEqual(elite["raw_dtos_projected_total"] - developing["raw_dtos_projected_total"], 0)
        self.assertEqual(elite["dtos_projected_total"] - developing["dtos_projected_total"], 24)
        self.assertNotEqual(elite["dtos_projected_total"], elite["sleeper_projected_total"])

    def test_export_is_read_only_complete_and_reconciled(self):
        data, snapshot = fixture()
        original_data, original_snapshot = copy.deepcopy(data), copy.deepcopy(snapshot)
        result = build_projection_audit(
            data=data, projection_snapshot=snapshot, projection_health={"status": "ready"},
            market=FakeMarket(), fois_scores=(Score(),), now="2026-08-11T00:00:00+00:00",
        )
        self.assertEqual(result["audit_summary"]["total_starters"], 2)
        self.assertEqual(result["audit_summary"]["starters_with_both"], 1)
        self.assertEqual(result["players"][0]["dtos_minus_sleeper"], 2.09)
        self.assertEqual(result["players"][0]["raw_dtos_projection"], 21.5)
        self.assertEqual(result["players"][0]["calibration_adjustment"], -1.5)
        self.assertIsNone(result["players"][1]["canonical_projection"])
        self.assertEqual(result["teams"][0]["sleeper_projected_total"], 17.91)
        self.assertEqual(result["teams"][0]["raw_dtos_projected_total"], 21.5)
        self.assertEqual(result["matchups"][0]["teams"][0]["dtos_projected_total"], 20.0)
        distribution = result["audit_summary"]["position_distributions"]["QB"]
        self.assertEqual(distribution["dtos_unique_values"], 1)
        self.assertEqual(result["players"][0]["brain_snapshot_id"], "1.10.11:brain-1")
        self.assertEqual(result["fois"][0]["projection_snapshot_id"], "projection-1")
        self.assertEqual(data, original_data)
        self.assertEqual(snapshot, original_snapshot)

    def test_stage_profile_is_bounded_and_does_not_change_output(self):
        data, snapshot = fixture()
        timings: dict[str, float] = {}
        expected = build_projection_audit(
            data=data, projection_snapshot=snapshot, projection_health={"status": "ready"},
            market=FakeMarket(), fois_scores=(Score(),),
            now="2026-08-11T00:00:00+00:00",
        )
        actual = build_projection_audit(
            data=data, projection_snapshot=snapshot, projection_health={"status": "ready"},
            market=FakeMarket(), fois_scores=(Score(),),
            now="2026-08-11T00:00:00+00:00", timings=timings,
        )
        self.assertEqual(actual, expected)
        self.assertEqual(set(timings), {
            "identity_ms", "rank_maps_ms", "roster_index_ms",
            "player_catalog_ms", "matchup_reconciliation_ms", "summary_ms",
            "total_ms",
        })
        self.assertTrue(all(value >= 0 for value in timings.values()))

    def test_routes_never_build_market_and_csv_is_bounded(self):
        data, snapshot = fixture()

        class Projection:
            def snapshot(self): return snapshot
            def health(self, *, include_accuracy=True):
                return {"status": "ready", "external_requests": 0,
                        "accuracy_included": include_accuracy}

        class Cache:
            calls = 0
            def current(self):
                self.calls += 1
                return FakeMarket()

        class Repository:
            def league(self, league_id, model): return (Score(),)

        class FOIS:
            repository = Repository()

        cache = Cache()
        app = FastAPI()
        app.include_router(create_audit_router(
            require_data=lambda: data, projection_service=Projection(),
            market_cache=cache, fois_service=FOIS(),
        ))
        client = TestClient(app)
        response = client.get("/api/audit/projections/current")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["audit_summary"]["external_provider_calls"], 0)
        csv_response = client.get("/api/audit/projections/current.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("J. Daniels", csv_response.text)
        self.assertEqual(cache.calls, 2)

    def test_missing_retained_market_fails_without_starting_one(self):
        data, snapshot = fixture()

        class Projection:
            def snapshot(self): return snapshot
            def health(self, *, include_accuracy=True): return {}

        class Cache:
            def current(self): return None

        app = FastAPI()
        app.include_router(create_audit_router(
            require_data=lambda: data, projection_service=Projection(),
            market_cache=Cache(), fois_service=object(),
        ))
        self.assertEqual(TestClient(app).get("/api/audit/projections/current").status_code, 503)

    async def test_projection_audit_does_not_block_lightweight_request(self):
        data, snapshot = fixture()
        started = threading.Event()
        release = threading.Event()
        request_context = contextvars.ContextVar("request_context", default="missing")
        observed_context: list[str] = []

        class Projection:
            def snapshot(self): return snapshot
            def health(self, *, include_accuracy=True): return {"status": "ready"}

        class Cache:
            def current(self): return FakeMarket()

        class Repository:
            def league(self, league_id, model): return (Score(),)

        class FOIS:
            repository = Repository()

        app = FastAPI()
        app.include_router(create_audit_router(
            require_data=lambda: data, projection_service=Projection(),
            market_cache=Cache(), fois_service=FOIS(),
        ))

        @app.get("/lightweight")
        async def lightweight() -> dict[str, bool]:
            return {"ready": True}

        real_builder = build_projection_audit

        def slow_builder(**kwargs):
            observed_context.append(request_context.get())
            started.set()
            self.assertTrue(release.wait(2.0))
            return real_builder(**kwargs)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("routes.audit.build_projection_audit", side_effect=slow_builder):
                token = request_context.set("projection-audit-request")
                try:
                    audit_request = asyncio.create_task(
                        client.get("/api/audit/projections/current"),
                    )
                    for _ in range(100):
                        if started.is_set():
                            break
                        await asyncio.sleep(0.005)
                    self.assertTrue(started.is_set())
                    began = time.perf_counter()
                    response = await asyncio.wait_for(client.get("/lightweight"), 0.25)
                    latency_ms = (time.perf_counter() - began) * 1000
                    self.assertFalse(audit_request.done())
                    release.set()
                    audit_response = await audit_request
                finally:
                    request_context.reset(token)

        self.assertEqual(response.status_code, 200)
        self.assertLess(latency_ms, 100)
        self.assertEqual(audit_response.status_code, 200)
        self.assertEqual(observed_context, ["projection-audit-request"])

    async def test_projection_audit_worker_exception_propagates(self):
        data, snapshot = fixture()

        class Projection:
            def snapshot(self): return snapshot
            def health(self, *, include_accuracy=True): return {"status": "ready"}

        class Cache:
            def current(self): return FakeMarket()

        class Repository:
            def league(self, league_id, model): return ()

        class FOIS:
            repository = Repository()

        app = FastAPI()
        app.include_router(create_audit_router(
            require_data=lambda: data, projection_service=Projection(),
            market_cache=Cache(), fois_service=FOIS(),
        ))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "routes.audit.build_projection_audit",
                side_effect=RuntimeError("projection-audit-worker-failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "projection-audit-worker-failure"):
                    await client.get("/api/audit/projections/current")


if __name__ == "__main__":
    unittest.main()
