"""Deployment readiness, lightweight health, and diagnostics regressions."""
from __future__ import annotations

import asyncio
import logging
import unittest
from logging.handlers import QueueHandler
from time import sleep
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import dtos_app
import src.platform.observability as observability
from routes.api import create_api_router
from src.platform.observability import (
    install_observability,
    runtime_metrics,
)
from src.platform.lifecycle import lifecycle_coordinator


class DeploymentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        lifecycle_coordinator.reset()
        self.original_ready = runtime_metrics.ready
        self.original_reason = runtime_metrics.readiness_reason
        self.original_ready_at = runtime_metrics.ready_at
        self.original_background = dict(runtime_metrics.background_tasks)
        self.original_lag = list(runtime_metrics.event_loop_lag_samples_ms)
        self.original_current_lag = runtime_metrics.event_loop_current_lag_ms

    def tearDown(self) -> None:
        lifecycle_coordinator.reset()
        runtime_metrics.ready = self.original_ready
        runtime_metrics.readiness_reason = self.original_reason
        runtime_metrics.ready_at = self.original_ready_at
        runtime_metrics.background_tasks = self.original_background
        runtime_metrics.event_loop_lag_samples_ms = self.original_lag
        runtime_metrics.event_loop_current_lag_ms = self.original_current_lag

    @staticmethod
    def api_client(state: dict) -> TestClient:
        async def noop(**_: object) -> dict:
            return state

        app = FastAPI()
        app.include_router(
            create_api_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: state["data"],
                sync_sleeper=noop,
                state=state,
                league_id="league-1",
            )
        )
        return TestClient(app)

    def test_liveness_is_lightweight_while_readiness_is_false(self) -> None:
        runtime_metrics.mark_not_ready("fixture startup")
        client = self.api_client({"data": {}})
        with patch(
            "routes.api.intelligence_orchestrator.analyze"
        ) as intelligence, patch(
            "routes.api.data_platform.health"
        ) as platform_health:
            live = client.get("/health/live")
            ready = client.get("/health/ready")
            legacy = client.get("/health")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json()["status"], "alive")
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(legacy.status_code, 503)
        intelligence.assert_not_called()
        platform_health.assert_not_called()

    def test_fois_heavy_flights_are_serialized(self) -> None:
        active = 0
        maximum = 0

        async def generate(_data: dict) -> tuple[object, ...]:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return ()

        async def exercise() -> None:
            with patch.object(dtos_app, "intelligence_heavy_lock", asyncio.Lock()), patch.object(
                dtos_app.fois_service, "generate", side_effect=generate,
            ):
                await asyncio.gather(
                    dtos_app._generate_fois_coordinated({}),
                    dtos_app._generate_fois_coordinated({}),
                )

        asyncio.run(exercise())
        self.assertEqual(maximum, 1)

    def test_readiness_becomes_successful_after_cached_data_loads(self) -> None:
        runtime_metrics.mark_ready("Cached league data loaded.")
        client = self.api_client({"data": {"teams": []}})
        ready = client.get("/health/ready")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["status"], "ready")
        self.assertEqual(
            ready.json()["reason"],
            "Cached league data loaded.",
        )

    def test_diagnostic_headers_are_opt_in(self) -> None:
        app = FastAPI()
        install_observability(app)

        @app.get("/probe")
        async def probe() -> dict[str, bool]:
            return {"ok": True}

        client = TestClient(app)
        ordinary = client.get("/probe")
        diagnostic = client.get(
            "/probe",
            headers={"X-DTOS-Diagnostics": "1"},
        )
        self.assertNotIn("X-DTOS-Request-Duration", ordinary.headers)
        for name in (
            "X-DTOS-Request-Start",
            "X-DTOS-Route-Duration",
            "X-DTOS-Request-Duration",
            "X-DTOS-Process-Uptime",
        ):
            self.assertIn(name, diagnostic.headers)

    def test_request_entry_and_completion_share_correlation_id(self) -> None:
        app = FastAPI()
        install_observability(app)

        @app.get("/health/live")
        async def live() -> dict[str, bool]:
            return {"ok": True}

        with self.assertLogs("dtos.request", level="INFO") as captured:
            response = TestClient(app).get(
                "/health/live", headers={"X-Request-ID": "bounded-trace"},
            )
        self.assertEqual(response.status_code, 200)
        events = [record.event for record in captured.records]
        self.assertEqual(events, [
            "request_accepted", "handler_scheduled", "request_complete",
        ])
        self.assertTrue(all(
            record.request_id == "bounded-trace" for record in captured.records
        ))

    def test_request_trace_sink_is_non_blocking(self) -> None:
        app = FastAPI()
        install_observability(app)

        request_logger = logging.getLogger("dtos.request")
        self.assertFalse(request_logger.propagate)
        self.assertEqual(len(request_logger.handlers), 1)
        self.assertIsInstance(request_logger.handlers[0], QueueHandler)

    def test_slow_request_log_sink_does_not_delay_diagnostic_route(self) -> None:
        app = FastAPI()
        install_observability(app)

        @app.get("/probe")
        async def probe() -> dict[str, bool]:
            return {"ok": True}

        listener = observability._request_log_listener
        self.assertIsNotNone(listener)
        assert listener is not None
        target = listener.handlers[0]
        original_emit = target.emit

        def slow_emit(record: logging.LogRecord) -> None:
            sleep(0.1)
            original_emit(record)

        with patch.object(target, "emit", side_effect=slow_emit):
            response = TestClient(app).get(
                "/probe", headers={"X-DTOS-Diagnostics": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            float(response.headers["X-DTOS-Request-Duration"]), 50.0,
        )

    def test_event_loop_lag_window_is_bounded(self) -> None:
        runtime_metrics.event_loop_lag_samples_ms = []
        for value in range(300):
            runtime_metrics.record_event_loop_lag(float(value))
        health = runtime_metrics.health()["event_loop_lag"]
        self.assertEqual(health["sample_count"], 256)
        self.assertEqual(health["current_ms"], 299.0)
        self.assertEqual(health["max_ms"], 299.0)

    def test_cached_maintenance_waits_before_background_work(self) -> None:
        events: list[str] = []

        async def wait(_: float) -> None:
            events.append("delay")

        async def completed(name: str) -> dict:
            events.append(name)
            return {}

        original_data = dtos_app.STATE.get("data")
        dtos_app.STATE["data"] = {"teams": []}
        try:
            with patch.object(
                dtos_app.asyncio,
                "sleep",
                side_effect=wait,
            ), patch.object(
                dtos_app,
                "start_sleeper_sync",
                side_effect=lambda *args, **kwargs: asyncio.create_task(
                    completed("sleeper")
                ),
            ), patch.object(
                dtos_app,
                "start_background_backfill",
                side_effect=lambda _: asyncio.create_task(completed("history")),
            ):
                asyncio.run(dtos_app.deployment_maintenance())
        finally:
            dtos_app.STATE["data"] = original_data
        self.assertEqual(events[0], "delay")
        self.assertEqual(events, ["delay", "sleeper", "history"])

    def test_uncached_failed_sync_remains_not_ready(self) -> None:
        async def completed() -> dict:
            return {}

        original_data = dtos_app.STATE.get("data")
        dtos_app.STATE["data"] = {}
        runtime_metrics.mark_not_ready("fixture")
        try:
            with patch.object(
                dtos_app,
                "start_sleeper_sync",
                side_effect=lambda *args, **kwargs: asyncio.create_task(
                    completed()
                ),
            ), patch.object(
                dtos_app,
                "start_background_backfill",
            ) as backfill, patch.object(
                dtos_app.asyncio,
                "sleep",
            ) as delay:
                asyncio.run(dtos_app.deployment_maintenance())
        finally:
            dtos_app.STATE["data"] = original_data
        self.assertFalse(runtime_metrics.ready)
        self.assertEqual(
            runtime_metrics.readiness_reason,
            "Initial Sleeper synchronization did not produce league data.",
        )
        backfill.assert_not_called()
        delay.assert_not_called()

    def test_request_freshness_does_not_start_competing_startup_sync(self) -> None:
        epoch = lifecycle_coordinator.begin_startup("Fixture startup.")
        with patch.object(dtos_app, "ensure_data_fresh") as fresh:
            asyncio.run(dtos_app.ensure_fresh())
        fresh.assert_not_called()
        lifecycle_coordinator.complete_startup(epoch, "Fixture ready.")
        with patch.object(
            dtos_app, "ensure_data_fresh", new_callable=AsyncMock,
        ) as fresh:
            asyncio.run(dtos_app.ensure_fresh())
        fresh.assert_awaited_once_with()

    def test_visual_capture_waits_for_complete_startup_and_ready_market(self) -> None:
        original_data = dtos_app.STATE.get("data")
        dtos_app.STATE["data"] = {"teams": []}
        market = Mock()
        epoch = lifecycle_coordinator.begin_startup("fixture")
        try:
            with patch.object(
                dtos_app.asset_market_cache, "current", return_value=market,
            ), patch.object(
                dtos_app.asset_market_cache, "metrics",
                return_value={"status": "ready", "build_active": False},
            ), patch.object(
                dtos_app, "live_visual_capture_requests", return_value=("capture",),
            ), patch.object(
                dtos_app.live_visual_service, "schedule", return_value=1,
            ) as schedule:
                self.assertEqual(dtos_app.schedule_live_visual_capture(), 0)
                schedule.assert_not_called()
                lifecycle_coordinator.complete_startup(epoch, "ready")
                self.assertEqual(dtos_app.schedule_live_visual_capture(), 1)
                schedule.assert_called_once_with(("capture",))
        finally:
            dtos_app.STATE["data"] = original_data

    def test_visual_capture_waits_for_atomic_market_publication(self) -> None:
        original_data = dtos_app.STATE.get("data")
        dtos_app.STATE["data"] = {"teams": []}
        epoch = lifecycle_coordinator.begin_startup("fixture")
        lifecycle_coordinator.complete_startup(epoch, "ready")
        try:
            with patch.object(
                dtos_app.asset_market_cache, "current", return_value=None,
            ), patch.object(
                dtos_app.asset_market_cache, "metrics",
                return_value={"status": "warming", "build_active": True},
            ), patch.object(
                dtos_app.live_visual_service, "schedule",
            ) as schedule:
                self.assertEqual(dtos_app.schedule_live_visual_capture(), 0)
                schedule.assert_not_called()
                self.assertEqual(
                    runtime_metrics.health()["background_tasks"]["live_visual_capture"],
                    "waiting",
                )
        finally:
            dtos_app.STATE["data"] = original_data

    def test_market_publication_callback_queues_before_builder_unwinds(self) -> None:
        original_data = dtos_app.STATE.get("data")
        dtos_app.STATE["data"] = {"teams": []}
        market = Mock()
        epoch = lifecycle_coordinator.begin_startup("fixture")
        lifecycle_coordinator.complete_startup(epoch, "ready")
        try:
            with patch.object(
                dtos_app.asset_market_cache, "current", return_value=market,
            ), patch.object(
                dtos_app.asset_market_cache, "metrics",
                return_value={"status": "ready", "build_active": True},
            ), patch.object(
                dtos_app, "live_visual_capture_requests", return_value=("capture",),
            ), patch.object(
                dtos_app.live_visual_service, "schedule", return_value=1,
            ) as schedule:
                self.assertEqual(dtos_app.schedule_live_visual_capture(), 1)
                schedule.assert_called_once_with(("capture",))
        finally:
            dtos_app.STATE["data"] = original_data

    def test_cached_generation_remains_eligible_after_terminal_refresh_failure(self) -> None:
        async def failed_refresh() -> dict:
            dtos_app.STATE["last_error"] = "ConnectError: fixture offline"
            return dtos_app.STATE

        async def completed() -> dict:
            return {}

        original_data = dtos_app.STATE.get("data")
        original_error = dtos_app.STATE.get("last_error")
        dtos_app.STATE["data"] = {"teams": []}
        dtos_app.STATE["last_error"] = None
        try:
            with patch.object(dtos_app.asyncio, "sleep", new_callable=AsyncMock), patch.object(
                dtos_app, "start_sleeper_sync",
                side_effect=lambda *args, **kwargs: asyncio.create_task(failed_refresh()),
            ), patch.object(
                dtos_app, "start_background_backfill",
                side_effect=lambda _: asyncio.create_task(completed()),
            ), patch.object(dtos_app, "history_progress_contracts"):
                asyncio.run(dtos_app.deployment_maintenance())
            fence = lifecycle_coordinator.snapshot()["startup_fence"]
            self.assertEqual(fence["state"], "complete")
            self.assertTrue(lifecycle_coordinator.market_build_allowed())
        finally:
            dtos_app.STATE["data"] = original_data
            dtos_app.STATE["last_error"] = original_error

    def test_fois_failure_does_not_block_canonical_startup(self) -> None:
        async def completed() -> dict:
            return {}

        original_data = dtos_app.STATE.get("data")
        original_error = dtos_app.STATE.get("last_error")
        dtos_app.STATE["data"] = {"teams": []}
        dtos_app.STATE["last_error"] = None
        try:
            with patch.object(
                dtos_app.asyncio, "sleep", new_callable=AsyncMock,
            ), patch.object(
                dtos_app, "start_sleeper_sync",
                side_effect=lambda *args, **kwargs: asyncio.create_task(completed()),
            ), patch.object(
                dtos_app, "start_background_backfill",
                side_effect=lambda _: asyncio.create_task(completed()),
            ), patch.object(
                dtos_app, "history_progress_contracts",
            ), patch.object(
                dtos_app.fois_service, "generate", new_callable=AsyncMock,
                side_effect=ValueError("invalid optional evidence"),
            ):
                asyncio.run(dtos_app.deployment_maintenance())
            fence = lifecycle_coordinator.snapshot()["startup_fence"]
            self.assertEqual(fence["state"], "complete")
            self.assertTrue(lifecycle_coordinator.market_build_allowed())
            self.assertEqual(
                runtime_metrics.health()["background_tasks"]["fois_generation"],
                "failed",
            )
        finally:
            dtos_app.STATE["data"] = original_data
            dtos_app.STATE["last_error"] = original_error

    def test_periodic_interval_begins_only_after_startup_epoch(self) -> None:
        events: list[str] = []
        epoch = lifecycle_coordinator.begin_startup("Fixture startup.")

        async def deployment(startup_epoch: int) -> None:
            events.append("startup")
            lifecycle_coordinator.complete_startup(startup_epoch, "Ready.")

        async def periodic() -> None:
            events.append("periodic")

        with patch.object(
            dtos_app, "deployment_maintenance", side_effect=deployment,
        ), patch.object(dtos_app, "background_sync", side_effect=periodic):
            asyncio.run(dtos_app.startup_and_periodic_maintenance(epoch))
        self.assertEqual(events, ["startup", "periodic"])


if __name__ == "__main__":
    unittest.main()
