from __future__ import annotations

import asyncio
from contextlib import closing
import gc
import json
from pathlib import Path
import tempfile
import unittest
import weakref
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.league_runtime import create_league_runtime_router
from src.core.league_runtime import (
    LeagueRuntimeManager,
    LeagueRuntimeNotFound,
    RuntimeState,
    StructuredCacheKey,
    scoring_profile_id,
)
from services import sleeper as sleeper_service
from src.core.projection_intelligence.service import ProjectionService


def league_data(league_id: str, *, points_per_reception: float = 1.0) -> dict:
    return {
        "league": {
            "league_id": league_id,
            "season": "2026",
            "name": f"League {league_id}",
            "scoring_settings": {"rec": points_per_reception, "pass_td": 4},
            "roster_positions": ["QB", "RB", "WR", "FLEX", "BN"],
        },
        "scoring_settings": {"rec": points_per_reception, "pass_td": 4},
        "roster_positions": ["QB", "RB", "WR", "FLEX", "BN"],
        "teams": [{"roster_id": 1, "league_id": league_id}],
        "players": {f"player-{league_id}": {"player_id": f"player-{league_id}"}},
        "pick_ledger": [{"asset_id": f"pick:{league_id}:2027:1:1"}],
    }


class StructuredIdentityTests(unittest.TestCase):
    def test_scoring_profile_is_order_independent_but_materially_sensitive(self) -> None:
        first = scoring_profile_id({"rec": 1, "pass_td": 4}, roster_positions=("QB", "RB"))
        reordered = scoring_profile_id({"pass_td": 4.0, "rec": 1.0}, roster_positions=("QB", "RB"))
        different = scoring_profile_id({"rec": 0.5, "pass_td": 4}, roster_positions=("QB", "RB"))
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, different)

    def test_structured_keys_cannot_collide_across_leagues(self) -> None:
        base = dict(
            season=2026, week=1, subsystem="brain", model_version="1.0",
            source_generation="generation-one", scoring_profile="scoring-one",
        )
        a = StructuredCacheKey(league_id="100", **base)
        b = StructuredCacheKey(league_id="200", **base)
        self.assertNotEqual(a, b)
        self.assertNotEqual(hash(a), hash(b))
        self.assertEqual(a.namespace, "league:100:brain")

    def test_invalid_structured_key_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            StructuredCacheKey("", 2026, "brain", "1", "g")


class LeagueRuntimeManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_lazy_hydration_and_single_flight(self) -> None:
        calls = 0

        async def hydrate(runtime):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return league_data(runtime.league_id)

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        first, second = await asyncio.gather(manager.get("100"), manager.get("100"))
        self.assertIs(first, second)
        self.assertEqual(calls, 1)
        self.assertEqual(first.status, RuntimeState.WARM)
        await manager.shutdown()

    async def test_a_b_a_has_no_state_bleed(self) -> None:
        async def hydrate(runtime):
            return league_data(runtime.league_id, points_per_reception=1 if runtime.league_id == "100" else 0.5)

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        league_a = await manager.get("100")
        league_b = await manager.get("200")
        restored_a = await manager.get("100")
        self.assertIs(league_a, restored_a)
        self.assertIsNot(league_a.state, league_b.state)
        self.assertEqual(league_a.state["data"]["teams"][0]["league_id"], "100")
        self.assertEqual(league_b.state["data"]["teams"][0]["league_id"], "200")
        self.assertNotEqual(league_a.scoring_profile, league_b.scoring_profile)
        await manager.shutdown()

    async def test_concurrent_a_b_never_uses_last_request_wins(self) -> None:
        gate = asyncio.Event()

        async def hydrate(runtime):
            await gate.wait()
            return league_data(runtime.league_id)

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        a_task = asyncio.create_task(manager.get("100"))
        b_task = asyncio.create_task(manager.get("200"))
        gate.set()
        a, b = await asyncio.gather(a_task, b_task)
        self.assertEqual(a.league_id, "100")
        self.assertEqual(b.league_id, "200")
        self.assertNotEqual(a.state["data"]["players"], b.state["data"]["players"])
        await manager.shutdown()

    async def test_lru_eviction_releases_reachable_runtime_state(self) -> None:
        async def hydrate(runtime):
            data = league_data(runtime.league_id)
            data["large"] = bytearray(1_000_000)
            return data

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        a = await manager.get("100")
        reference = weakref.ref(a)
        await manager.get("200")
        del a
        await manager.get("300")
        gc.collect()
        self.assertIsNone(manager.resident("100"))
        self.assertIsNone(reference())
        self.assertEqual(manager.health()["warm_runtime_count"], 2)
        self.assertEqual(manager.evictions, 1)
        await manager.shutdown()

    async def test_failed_secondary_league_preserves_first(self) -> None:
        async def hydrate(runtime):
            if runtime.league_id == "200":
                raise ConnectionError("fixture unavailable")
            return league_data(runtime.league_id)

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        a = await manager.get("100")
        with self.assertRaises(ConnectionError):
            await manager.get("200")
        self.assertEqual(a.status, RuntimeState.WARM)
        self.assertEqual(a.state["data"]["league"]["league_id"], "100")
        await manager.shutdown()

    async def test_invalid_league_does_not_create_runtime(self) -> None:
        manager = LeagueRuntimeManager(max_warm=2, hydrator=lambda _: None)
        with self.assertRaises(LeagueRuntimeNotFound):
            await manager.get("not-a-league")
        self.assertEqual(manager.health()["resident_runtime_count"], 0)


class LeagueRuntimeRouteTests(unittest.IsolatedAsyncioTestCase):
    def test_feature_gate_does_not_create_secondary_runtime(self) -> None:
        manager = LeagueRuntimeManager(max_warm=2, hydrator=None)
        app = FastAPI()
        app.include_router(create_league_runtime_router(manager=manager))
        with TestClient(app) as client:
            response = client.post("/api/leagues/200/runtime")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(manager.health()["resident_runtime_count"], 0)


class LeaguePersistenceIsolationTests(unittest.TestCase):
    def test_secondary_sleeper_caches_are_namespaced(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            default = Path(folder) / "cache.json"
            with patch.object(sleeper_service, "CACHE_FILE", default), patch.object(
                sleeper_service, "LEAGUE_ID", "100",
            ):
                a = sleeper_service.league_cache_file("100")
                b = sleeper_service.league_cache_file("200")
            self.assertEqual(a, default)
            self.assertNotEqual(a, b)
            self.assertEqual(b.parent, default.parent)
            self.assertNotIn("100", b.name)

    def test_projection_restore_is_filtered_by_league(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "projections.sqlite3"
            bootstrap = ProjectionService(database)
            with closing(bootstrap._connect()) as connection:
                a = {
                    "league_id": "100", "schema_version": "1.2",
                    "model_version": "dtos-forward-production-3",
                    "contract_version": "1", "semantic_policy_version": "1",
                    "projection_snapshot_id": "a", "generated_at": "2026-01-01T00:00:00+00:00",
                }
                b = {**a, "league_id": "200", "projection_snapshot_id": "b", "generated_at": "2026-01-02T00:00:00+00:00"}
                connection.execute(
                    "INSERT INTO projection_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                    ("a", "100", 2026, 1, a["generated_at"], json.dumps(a)),
                )
                connection.execute(
                    "INSERT INTO projection_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                    ("b", "200", 2026, 1, b["generated_at"], json.dumps(b)),
                )
                connection.commit()
            service_a = ProjectionService(database, league_id="100")
            service_b = ProjectionService(database, league_id="200")
            data_a = {"league": {"league_id": "100"}}
            data_b = {"league": {"league_id": "200"}}
            self.assertTrue(service_a.restore_into(data_a))
            self.assertTrue(service_b.restore_into(data_b))
            self.assertEqual(data_a["projection_intelligence"]["projection_snapshot_id"], "a")
            self.assertEqual(data_b["projection_intelligence"]["projection_snapshot_id"], "b")
            self.assertFalse(service_a.restore_into({"league": {"league_id": "200"}}))

class LeagueRuntimeRouteValidationTests(unittest.TestCase):
    def test_invalid_id_fails_without_poisoning_state(self) -> None:
        manager = LeagueRuntimeManager(max_warm=2, hydrator=None)
        app = FastAPI()
        app.include_router(create_league_runtime_router(manager=manager, import_enabled=True))
        with TestClient(app) as client:
            response = client.post("/api/leagues/not-valid/runtime")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(manager.health()["resident_runtime_count"], 0)

class LeagueRuntimeStressTests(unittest.IsolatedAsyncioTestCase):
    async def test_thirty_leagues_never_exceed_bound(self) -> None:
        async def hydrate(runtime):
            return league_data(runtime.league_id)

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        maximum = 0
        for number in range(100, 130):
            runtime = await manager.get(str(number))
            self.assertEqual(runtime.league_id, str(number))
            maximum = max(maximum, manager.health()["warm_runtime_count"])
        health = manager.health()
        self.assertEqual(maximum, 2)
        self.assertEqual(health["resident_runtime_count"], 2)
        self.assertEqual(health["evictions"], 28)
        await manager.shutdown()

    async def test_shutdown_cancels_tasks_and_drops_all_state(self) -> None:
        async def hydrate(runtime):
            return league_data(runtime.league_id)

        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        runtime = await manager.get("100")
        runtime.background_tasks.add(asyncio.create_task(asyncio.sleep(30)))
        await manager.shutdown()
        self.assertEqual(runtime.status, RuntimeState.CLOSED)
        self.assertEqual(runtime.state["data"], {})
        self.assertEqual(manager.health()["resident_runtime_count"], 0)


if __name__ == "__main__":
    unittest.main()
