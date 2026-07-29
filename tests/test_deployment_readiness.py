"""Deployment readiness, lightweight health, and diagnostics regressions."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import dtos_app
from routes.api import create_api_router
from src.platform.observability import (
    install_observability,
    runtime_metrics,
)


class DeploymentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_ready = runtime_metrics.ready
        self.original_reason = runtime_metrics.readiness_reason
        self.original_ready_at = runtime_metrics.ready_at
        self.original_background = dict(runtime_metrics.background_tasks)

    def tearDown(self) -> None:
        runtime_metrics.ready = self.original_ready
        runtime_metrics.readiness_reason = self.original_reason
        runtime_metrics.ready_at = self.original_ready_at
        runtime_metrics.background_tasks = self.original_background

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

    def test_cached_maintenance_waits_before_background_work(self) -> None:
        events: list[str] = []

        async def wait(_: float) -> None:
            events.append("delay")

        async def completed() -> dict:
            events.append("work")
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
                    completed()
                ),
            ), patch.object(
                dtos_app,
                "start_background_backfill",
                side_effect=lambda _: asyncio.create_task(completed()),
            ):
                asyncio.run(dtos_app.deployment_maintenance())
        finally:
            dtos_app.STATE["data"] = original_data
        self.assertEqual(events[0], "delay")
        self.assertEqual(events.count("work"), 2)

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


if __name__ == "__main__":
    unittest.main()
