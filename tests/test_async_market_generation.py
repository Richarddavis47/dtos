"""Asynchronous cold Asset Market generation and responsiveness contracts."""
from __future__ import annotations

import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.core.asset_market import AssetMarketCache, MarketWarmingError
from src.platform.lifecycle import lifecycle_coordinator


class AsyncMarketGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        lifecycle_coordinator.reset()
        self.cache = AssetMarketCache()
        self.data = {
            "valuation_intelligence": {
                "generated_at": "2026-08-07T00:00:00+00:00",
                "schema_version": "1.0",
            },
        }
        self.state = {"last_sync": "2026-08-07T00:00:00+00:00"}
        self.store = SimpleNamespace(path=None)

    def tearDown(self) -> None:
        self.cache.wait_for_background()
        self.cache.clear()
        lifecycle_coordinator.reset()

    def _blocked_preparation(self):
        entered = threading.Event()
        release = threading.Event()
        worker_ids: list[int] = []

        def key(*_args):
            worker_ids.append(threading.get_ident())
            entered.set()
            release.wait(2)
            raise RuntimeError("controlled preparation stop")

        return entered, release, worker_ids, key

    def test_cold_request_returns_before_archive_generation_preparation(self) -> None:
        entered, release, worker_ids, key = self._blocked_preparation()
        caller = threading.get_ident()
        try:
            with patch.object(self.cache, "key", side_effect=key) as prepare:
                started = time.perf_counter()
                with self.assertRaises(MarketWarmingError):
                    self.cache.get(
                        self.data, self.state, self.store, "league-1",
                        background=True,
                    )
                elapsed = (time.perf_counter() - started) * 1000
                self.assertLess(elapsed, 50)
                self.assertTrue(entered.wait(1))
                self.assertEqual(prepare.call_count, 1)
                self.assertNotEqual(worker_ids, [caller])
                health = self.cache.health()["cache"]
                self.assertTrue(health["build_active"])
                self.assertEqual(health["build_phase"], "preparing_generation")
        finally:
            release.set()

    def test_request_thread_never_resolves_uuid_dataset_or_cache_key(self) -> None:
        entered, release, worker_ids, key = self._blocked_preparation()
        durable_threads: list[int] = []
        try:
            with patch.object(self.cache, "key", side_effect=key), patch.object(
                self.cache, "durable_generation",
                side_effect=lambda *_args: durable_threads.append(threading.get_ident()),
            ):
                with self.assertRaises(MarketWarmingError):
                    self.cache.get(
                        self.data, self.state, self.store, "league-1",
                        background=True,
                    )
                self.assertTrue(entered.wait(1))
                self.assertNotIn(threading.get_ident(), worker_ids)
                self.assertEqual(durable_threads, [])
        finally:
            release.set()

    def test_concurrent_cold_requests_claim_one_worker(self) -> None:
        entered, release, _worker_ids, key = self._blocked_preparation()
        errors: list[type[BaseException]] = []

        def request() -> None:
            try:
                self.cache.get(
                    self.data, self.state, self.store, "league-1",
                    background=True,
                )
            except BaseException as exc:
                errors.append(type(exc))

        try:
            with patch.object(self.cache, "key", side_effect=key) as prepare:
                threads = [threading.Thread(target=request) for _ in range(12)]
                for thread in threads:
                    thread.start()
                self.assertTrue(entered.wait(1))
                for thread in threads:
                    thread.join(1)
                self.assertEqual(errors, [MarketWarmingError] * 12)
                self.assertEqual(prepare.call_count, 1)
        finally:
            release.set()

    def test_failure_is_metadata_only_and_preserves_last_valid_model(self) -> None:
        previous = SimpleNamespace(
            store=self.store, generated_at="prior", assets=(),
            brain_generation="brain-prior", dataset_version="history-prior",
            build_duration_ms=1.0,
        )
        self.cache._market = previous  # type: ignore[assignment]
        self.cache._request_marker = ("previous",)
        with patch.object(
            self.cache, "key", side_effect=RuntimeError("fixture preparation failure"),
        ):
            served = self.cache.get(
                self.data, self.state, self.store, "league-1", background=True,
            )
            self.assertIs(served, previous)
            self.assertTrue(self.cache.wait_for_background())
        health = self.cache.health()["cache"]
        self.assertEqual(health["build_phase"], "failed")
        self.assertEqual(health["refresh_state"], "failed")
        self.assertEqual(health["last_error"], "fixture preparation failure")
        self.assertTrue(health["last_valid_model"])

    def test_unrelated_endpoints_remain_responsive_during_preparation(self) -> None:
        entered, release, _worker_ids, key = self._blocked_preparation()
        app = FastAPI()

        @app.get("/market-probe")
        async def market_probe():
            try:
                return self.cache.get(
                    self.data, self.state, self.store, "league-1",
                    background=True,
                )
            except MarketWarmingError as exc:
                raise HTTPException(503, str(exc)) from exc

        @app.get("/health/live")
        async def live():
            return {"status": "alive"}

        @app.get("/history-probe")
        async def history():
            return {"records": 30_726, "progress": "5/6"}

        try:
            with patch.object(self.cache, "key", side_effect=key):
                client = TestClient(app)
                started = time.perf_counter()
                self.assertEqual(client.get("/market-probe").status_code, 503)
                self.assertTrue(entered.wait(1))
                self.assertEqual(client.get("/health/live").status_code, 200)
                self.assertEqual(client.get("/history-probe").status_code, 200)
                self.assertLess((time.perf_counter() - started) * 1000, 500)
        finally:
            release.set()

    def test_prohibited_maintenance_starts_no_generation_worker(self) -> None:
        with patch.object(self.cache, "_start_background") as start:
            with lifecycle_coordinator.phase("historical_import"):
                with self.assertRaises(MarketWarmingError):
                    self.cache.get(
                        self.data, self.state, self.store, "league-1",
                        background=True,
                    )
        start.assert_not_called()
        self.assertFalse(self.cache.health()["cache"]["build_active"])


if __name__ == "__main__":
    unittest.main()
