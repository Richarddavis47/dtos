"""Completed refresh tasks must not own superseded league publications."""
from __future__ import annotations

import asyncio
from contextlib import ExitStack
import gc
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from services import league_maintenance
from src.core.league_runtime import LeagueRuntime, RuntimeState


class Publication(dict):
    """A value-identical dictionary with a weak-referenceable ownership marker."""


class IntervalGate:
    def __init__(self):
        self.arrivals = asyncio.Queue()
        self.permits = asyncio.Queue()
        self.calls = 0

    async def sleep(self, _):
        self.calls += 1
        self.arrivals.put_nowait(self.calls)
        await self.permits.get()

    async def parked(self, expected):
        return await asyncio.wait_for(self.arrivals.get(), 5) == expected


class CompletedRefreshOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = LeagueRuntime("111", status=RuntimeState.WARM)
        self.runtime.apply_data(Publication(
            league={"league_id": "111", "season": "2026", "scoring_settings": {"pass_td": 4}},
            source_generation="first", native_points={"zero": 0, "negative": -2.125},
        ))
        self.gate = IntervalGate()
        self.stack = ExitStack()
        # Isolate only the interval scheduler and unrelated disk accounting.
        # Worker tasks, cancellation, source ownership and publication are real.
        api = SimpleNamespace(
            sleep=self.gate.sleep, create_task=asyncio.create_task,
            shield=asyncio.shield, gather=asyncio.gather,
            to_thread=asyncio.to_thread, CancelledError=asyncio.CancelledError,
        )
        self.stack.enter_context(patch.object(league_maintenance, "asyncio", api))
        self.stack.enter_context(patch(
            "src.platform.storage_accounting.periodic_storage_accounting", return_value={},
        ))

    async def asyncTearDown(self):
        try:
            await self.runtime.close()
            for _ in range(3):
                await asyncio.sleep(0)
        finally:
            self.stack.close()

    async def start(self, refresh):
        league_maintenance.ensure_periodic_refresh(self.runtime, refresh, interval_seconds=900)
        self.assertTrue(await self.gate.parked(1))
        self.gate.permits.put_nowait(None)
        self.assertTrue(await self.gate.parked(2))

    async def settle(self):
        for _ in range(3):
            await asyncio.sleep(0)
        gc.collect()

    def replacement(self):
        self.runtime.apply_data(Publication(
            league={"league_id": "111", "season": "2026", "scoring_settings": {"pass_td": 4}},
            source_generation="second", native_points={"zero": 0, "negative": -2.125},
        ))

    async def test_completed_result_releases_superseded_publication(self):
        old = weakref.ref(self.runtime.state["data"])

        async def refresh(runtime):
            return runtime.state["data"]

        await self.start(refresh)
        self.assertIs(old(), self.runtime.state["data"])
        self.replacement()
        await self.settle()
        self.assertIsNone(old())
        self.assertEqual(self.runtime.state["data"]["native_points"], {"zero": 0, "negative": -2.125})
        self.assertEqual(self.runtime.lifecycle["refresh_state"], "complete")

    async def test_failed_task_drops_traceback_but_preserves_last_valid_source(self):
        old = weakref.ref(self.runtime.state["data"])

        async def refresh(runtime):
            source = runtime.state["data"]
            self.assertEqual(source["source_generation"], "first")
            raise OSError("disposable source failure")

        await self.start(refresh)
        self.assertIs(old(), self.runtime.state["data"])
        self.assertEqual(self.runtime.lifecycle["refresh_state"], "failed")
        self.assertEqual(self.runtime.lifecycle["refresh_error_type"], "OSError")
        self.replacement()
        await self.settle()
        self.assertIsNone(old())
        self.assertEqual(self.runtime.state["data"]["source_generation"], "second")

    async def test_timeout_traceback_does_not_retain_old_generation(self):
        old = weakref.ref(self.runtime.state["data"])

        async def refresh(runtime):
            source = runtime.state["data"]
            self.assertIn("native_points", source)
            raise TimeoutError("disposable timeout")

        await self.start(refresh)
        self.assertEqual(self.runtime.lifecycle["refresh_error_type"], "TimeoutError")
        self.replacement()
        await self.settle()
        self.assertIsNone(old())

    async def test_legitimate_reader_keeps_its_snapshot_until_released(self):
        reader = self.runtime.state["data"]
        old = weakref.ref(reader)
        self.runtime.active_requests = 1

        async def refresh(runtime):
            return runtime.state["data"]

        await self.start(refresh)
        self.replacement()
        await self.settle()
        self.assertIs(old(), reader)
        self.assertEqual(reader["source_generation"], "first")
        self.assertEqual(self.runtime.active_requests, 1)
        self.runtime.active_requests = 0
        del reader
        await self.settle()
        self.assertIsNone(old())
        self.assertEqual(self.runtime.state["data"]["source_generation"], "second")

    async def test_single_flight_and_next_interval_preserve_other_league(self):
        other = Publication(league={"league_id": "222", "scoring_settings": {"pass_td": 6}})
        calls = []

        async def refresh(runtime):
            calls.append(runtime.league_id)
            return runtime.state["data"]

        await self.start(refresh)
        league_maintenance.ensure_periodic_refresh(self.runtime, refresh, interval_seconds=900)
        self.assertEqual(len(self.runtime.background_tasks), 1)
        self.assertEqual(calls, ["111"])
        self.replacement()
        self.gate.permits.put_nowait(None)
        self.assertTrue(await self.gate.parked(3))
        self.assertEqual(calls, ["111", "111"])
        self.assertEqual(other, {"league": {"league_id": "222", "scoring_settings": {"pass_td": 6}}})
        self.assertEqual(self.runtime.state["data"]["league"]["scoring_settings"], {"pass_td": 4})

    async def cancellation(self, repeat):
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        cancelled = []

        async def writer(runtime):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
            runtime.state["data"]["writer_finished"] = True
            finished.set()
            return runtime.state["data"]

        league_maintenance.ensure_periodic_refresh(self.runtime, writer, interval_seconds=900)
        self.assertTrue(await self.gate.parked(1))
        self.gate.permits.put_nowait(None)
        await asyncio.wait_for(entered.wait(), 5)
        task = next(iter(self.runtime.background_tasks))
        try:
            task.cancel()
            await asyncio.sleep(0)
            if repeat:
                task.cancel()
                for _ in range(3):
                    await asyncio.sleep(0)
            self.assertFalse(task.done(), "Maintenance must drain the real writer before exiting")
            self.assertFalse(cancelled)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        self.assertTrue(finished.is_set())
        self.assertTrue(self.runtime.state["data"]["writer_finished"])

    async def test_cancellation_drains_writer(self):
        await self.cancellation(False)

    async def test_repeated_cancellation_does_not_detach_or_cancel_writer(self):
        await self.cancellation(True)
