"""Production memory lifecycle and bounded persistence regressions."""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from services import sleeper
from src.core.asset_market import AssetMarketCache, MarketWarmingError, asset_market_cache
from src.platform.lifecycle import LifecycleCoordinator, lifecycle_coordinator


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_cache_metrics = (
            asset_market_cache.build_count,
            asset_market_cache.hits,
            asset_market_cache.last_error,
            asset_market_cache.last_miss_reason,
        )
        asset_market_cache.clear()
        asset_market_cache.build_count = 0
        asset_market_cache.hits = 0
        asset_market_cache.last_error = None
        asset_market_cache.last_miss_reason = None

    def tearDown(self) -> None:
        lifecycle_coordinator.reset()
        asset_market_cache.clear()
        (
            asset_market_cache.build_count,
            asset_market_cache.hits,
            asset_market_cache.last_error,
            asset_market_cache.last_miss_reason,
        ) = self.original_cache_metrics

    def test_heavy_phases_are_serialized_and_history_is_bounded(self) -> None:
        coordinator = LifecycleCoordinator(history_limit=2)
        active = 0
        maximum = 0
        guard = threading.Lock()

        def run(name: str) -> None:
            nonlocal active, maximum
            with coordinator.phase(name):
                with guard:
                    active += 1
                    maximum = max(maximum, active)
                time.sleep(0.01)
                with guard:
                    active -= 1

        threads = [
            threading.Thread(target=run, args=(name,))
            for name in ("sleeper_sync", "historical_import", "asset_market_build")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(maximum, 1)
        self.assertEqual(len(coordinator.snapshot()["recent_phases"]), 2)

    def test_market_health_is_metadata_only_when_no_snapshot_exists(self) -> None:
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: (_ for _ in ()).throw(
                AssertionError("health must not load canonical data")
            ),
            state={}, league_id="league-1",
            page=lambda title, body: HTMLResponse(body),
        ))
        response = TestClient(app).get("/api/market/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "warming")
        self.assertEqual(response.json()["cache"]["build_count"], 0)

    def test_market_build_is_deferred_during_heavy_phase(self) -> None:
        cache = AssetMarketCache()
        with lifecycle_coordinator.phase("sleeper_sync"):
            with self.assertRaises(MarketWarmingError):
                cache.get({}, {}, object(), "league-1")
        self.assertEqual(cache.build_count, 0)

    def test_no_model_market_request_returns_bounded_warming_response(self) -> None:
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: {}, state={}, league_id="league-1",
            page=lambda title, body: HTMLResponse(body),
        ))
        with lifecycle_coordinator.phase("provider_network"):
            response = TestClient(app).get("/api/market/assets")
        self.assertEqual(response.status_code, 503)
        self.assertIn("warming", response.json()["detail"])

    def test_last_valid_market_is_served_during_heavy_phase(self) -> None:
        store = object()
        market = SimpleNamespace(store=store)
        cache = AssetMarketCache()
        cache._market = market  # type: ignore[assignment]
        cache._store_identity = "private"
        with lifecycle_coordinator.phase("valuation_intelligence"):
            self.assertIs(cache.get({}, {}, store, "league-1"), market)
        self.assertEqual(cache.last_miss_reason, "heavy_phase_last_valid")

    def test_streamed_cache_write_is_atomic_and_preserves_previous_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cache.json"
            target.write_text('{"previous":true}', encoding="utf-8")
            state = {"data": {"players": {"1": {"name": "One"}}}, "syncing": True}
            with patch.object(sleeper, "CACHE_FILE", target), patch.object(
                sleeper, "STATE", state,
            ):
                with patch.object(
                    sleeper.json, "dumps", side_effect=AssertionError,
                ):
                    sleeper.save_cache()
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {
                    "data": {"players": {"1": {"name": "One"}}},
                })
                with patch.object(sleeper.os, "replace", side_effect=OSError("fixture")):
                    state["data"] = {"players": {"2": {"name": "Two"}}}
                    sleeper.save_cache()
                self.assertIn('"1"', target.read_text(encoding="utf-8"))
                self.assertFalse(list(target.parent.glob("*.tmp")))

    def test_memory_snapshot_never_contains_private_paths(self) -> None:
        payload = lifecycle_coordinator.snapshot()
        encoded = json.dumps(payload)
        self.assertNotIn(str(Path.home()), encoded)
        self.assertNotIn("database", encoded.casefold())


if __name__ == "__main__":
    unittest.main()
