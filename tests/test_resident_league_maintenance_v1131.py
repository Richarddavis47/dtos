"""Resident league maintenance remains scoped, single-flight and eviction-safe."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from services.league_maintenance import ensure_periodic_refresh
from src.core.league_runtime import LeagueRuntime, RuntimeState


class ResidentMaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_is_resident_scoped_single_flight_and_close_waits_for_writer(self):
        runtime = LeagueRuntime("B", status=RuntimeState.WARM)
        runtime.state["data"] = {"league": {"league_id": "B"}}
        untouched = LeagueRuntime("A", status=RuntimeState.WARM)
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def refresh(selected):
            calls.append(selected.league_id)
            entered.set()
            await release.wait()
            selected.state["data"]["refreshed"] = True

        ensure_periodic_refresh(runtime, refresh, interval_seconds=0.001)
        ensure_periodic_refresh(runtime, refresh, interval_seconds=0.001)
        self.assertEqual(len(runtime.background_tasks), 1)
        self.assertFalse(untouched.background_tasks)
        await asyncio.wait_for(entered.wait(), 1)
        closing = asyncio.create_task(runtime.close())
        await asyncio.sleep(0)
        self.assertFalse(closing.done())
        release.set()
        await asyncio.wait_for(closing, 1)
        self.assertEqual(calls, ["B"])
        self.assertFalse(runtime.background_tasks)
        self.assertEqual(runtime.state["data"], {})
        self.assertEqual(untouched.status, RuntimeState.WARM)

    async def test_refresh_failure_preserves_last_valid_state(self):
        runtime = LeagueRuntime("B", status=RuntimeState.WARM)
        last_valid = {"league": {"league_id": "B"}}
        runtime.state["data"] = last_valid
        failed = asyncio.Event()

        async def refresh(_):
            failed.set()
            raise OSError("synthetic failure")

        ensure_periodic_refresh(runtime, refresh, interval_seconds=0.001)
        await asyncio.wait_for(failed.wait(), 1)
        async def recorded():
            while "refresh_error_type" not in runtime.lifecycle:
                await asyncio.sleep(0)
        # The producer event precedes the maintenance task's error publication.
        await asyncio.wait_for(recorded(), 1)
        self.assertIs(runtime.state["data"], last_valid)
        self.assertEqual(runtime.lifecycle["refresh_error_type"], "OSError")
        await runtime.close()

    async def test_selected_league_resolution_uses_its_market_and_fois_data(self):
        import dtos_app
        runtime = LeagueRuntime("B", status=RuntimeState.WARM)
        runtime.state["data"] = {"league": {"league_id": "B"}}
        runtime.market_context = Mock()
        runtime.market_context.metrics.return_value = {"status": "ready", "build_active": False}
        parent = threading.get_ident()

        def resolve(store, league):
            self.assertNotEqual(threading.get_ident(), parent)
            self.assertEqual(league, "B")
            return {"status": "complete"}

        with patch.object(dtos_app, "intelligence_heavy_lock", asyncio.Lock()), patch.object(
            dtos_app.lifecycle_coordinator, "phase", side_effect=lambda _: nullcontext(),
        ), patch.object(dtos_app.historical_trade_resolution_service, "run_safe", side_effect=resolve), patch.object(
            dtos_app, "_generate_fois_coordinated", new_callable=AsyncMock,
        ) as fois:
            await dtos_app.resolve_historical_trade_market(runtime=runtime)
        fois.assert_awaited_once_with(runtime.state["data"])
        self.assertEqual(runtime.lifecycle["historical_market_resolution"], "complete")

    async def test_refresh_reconciles_selected_market_without_restarting_complete_history(self):
        import dtos_app
        runtime = LeagueRuntime("B", status=RuntimeState.WARM)
        data = {"league": {"league_id": "B", "scoring_settings": {"pass_td": 6}}}
        runtime.state["data"] = data
        context = SimpleNamespace(history_state="complete", market=Mock())
        runtime.canonical_context = context
        with patch.object(dtos_app, "sync_sleeper_league", new_callable=AsyncMock) as sync, patch.object(
            dtos_app, "ProjectionService", return_value=Mock(),
        ), patch.object(dtos_app, "_generate_fois_coordinated", new_callable=AsyncMock), patch.object(
            dtos_app, "_publish_runtime_context", return_value=context,
        ), patch("services.league_maintenance.ensure_periodic_refresh") as periodic, patch.object(
            dtos_app, "start_background_backfill",
        ) as history:
            await dtos_app._refresh_resident_league(runtime)
        self.assertEqual(sync.call_args.args[:2], ("B", runtime.state))
        context.market.reconcile.assert_called_once_with(
            data, runtime.state, dtos_app.canonical_history_store, "B",
        )
        history.assert_not_called()
        periodic.assert_called_once()

    async def test_secondary_sync_cancellation_waits_for_thread_completion(self):
        from services import sleeper
        started, release = threading.Event(), threading.Event()
        state = {}

        async def sync(**kwargs):
            started.set()
            release.wait(2)
            kwargs["state"]["finished"] = True
            return kwargs["state"]

        with patch.object(sleeper, "_sync_sleeper", side_effect=sync):
            task = asyncio.create_task(sleeper.sync_sleeper_league("B", state, projections=Mock()))
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        self.assertTrue(state["finished"])

    async def test_cold_hydration_prepares_own_history_then_resolves_own_trades(self):
        import dtos_app
        runtime = LeagueRuntime("B", status=RuntimeState.WARM)
        runtime.state["data"] = {"league": {"league_id": "B"}}
        context = SimpleNamespace(history_state="available", market=Mock())
        runtime.canonical_context = context
        with patch.object(dtos_app, "sync_sleeper_league", new_callable=AsyncMock), patch.object(
            dtos_app, "ProjectionService", return_value=Mock(),
        ), patch.object(dtos_app, "_generate_fois_coordinated", new_callable=AsyncMock), patch.object(
            dtos_app, "_publish_runtime_context", return_value=context,
        ), patch("services.league_maintenance.ensure_periodic_refresh"), patch.object(
            dtos_app, "start_background_backfill", new_callable=AsyncMock,
            return_value={"status": "complete"},
        ) as history, patch.object(dtos_app, "history_progress_contracts"), patch.object(
            dtos_app, "resolve_historical_trade_market", new_callable=AsyncMock,
        ) as resolve:
            await dtos_app._hydrate_league_runtime(runtime)
            await asyncio.gather(*tuple(runtime.background_tasks))
        history.assert_awaited_once_with(None, league_id="B")
        resolve.assert_awaited_once_with(runtime=runtime)
        self.assertEqual(context.history_state, "complete")

    async def test_finishing_refresh_during_eviction_cannot_spawn_new_work(self):
        import dtos_app
        runtime = LeagueRuntime("B", status=RuntimeState.EVICTING)
        runtime.state["data"] = {"league": {"league_id": "B"}}
        with patch.object(dtos_app, "sync_sleeper_league", new_callable=AsyncMock), patch.object(
            dtos_app, "ProjectionService", return_value=Mock(),
        ), patch.object(dtos_app, "_generate_fois_coordinated", new_callable=AsyncMock), patch.object(
            dtos_app, "_publish_runtime_context",
        ) as publish, patch("services.league_maintenance.ensure_periodic_refresh") as periodic:
            await dtos_app._refresh_resident_league(runtime)
        publish.assert_not_called()
        periodic.assert_not_called()
        self.assertFalse(runtime.background_tasks)
