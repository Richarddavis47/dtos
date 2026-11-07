"""Global evidence scheduling needs scalar season identity, not a league graph."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

import dtos_app


class Publication(dict):
    pass


class GlobalEvidenceOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, *, status='complete', failure=False, ready=True, season='2026', reader=False):
        arrivals, permits = asyncio.Queue(), asyncio.Queue()
        calls, states = [], []
        old = Publication(nfl_state={'season': season}, native={'score': -2.125})
        observed = weakref.ref(old)
        state = {'data': old}
        owned_reader = old if reader else None
        del old

        async def sleep(seconds):
            arrivals.put_nowait(seconds)
            await permits.get()

        async def ingest(selected, path):
            calls.append(selected)
            if failure:
                raise RuntimeError('disposable acquisition failure')
            return {'status': status}

        metrics = SimpleNamespace(mark_background=lambda *values: states.append(values))
        proxy = SimpleNamespace(sleep=sleep, CancelledError=asyncio.CancelledError)
        with patch.object(dtos_app, 'STATE', state), patch.object(dtos_app, 'asyncio', proxy), \
             patch.object(dtos_app, 'runtime_metrics', metrics), \
             patch.object(dtos_app.lifecycle_coordinator, 'startup_complete', return_value=ready), \
             patch('services.global_evidence_ingestion.ingest_in_background', new=ingest):
            task = asyncio.create_task(dtos_app.refresh_global_evidence())
            try:
                self.assertEqual(await asyncio.wait_for(arrivals.get(), 2), 30)
                permits.put_nowait(None)
                delay = await asyncio.wait_for(arrivals.get(), 2)
                self.assertEqual(delay, 30 if not ready or not season or status == 'deferred' else 21600)
                state['data'] = Publication(nfl_state={'season': '2027'}, native={'score': 0})
                for _ in range(3):
                    await asyncio.sleep(0)
                if reader:
                    self.assertIs(observed(), owned_reader)
                    self.assertEqual(owned_reader['native']['score'], -2.125)
                    del owned_reader
                    for _ in range(3):
                        await asyncio.sleep(0)
                self.assertIsNone(observed(), 'Sleeping evidence scheduler pins an obsolete complete league graph')
                self.assertEqual(state['data']['native']['score'], 0)
                self.assertEqual(calls, [2026] if ready and season else [])
                if ready and season:
                    self.assertEqual(states[-1], ('global_evidence', 'failed' if failure else status))
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(task.done())

    async def test_completed_ingestion_does_not_pin_source_through_six_hour_sleep(self):
        await self.exercise()

    async def test_failed_or_deferred_ingestion_releases_unneeded_source(self):
        for options in ({'failure': True}, {'status': 'deferred'}):
            with self.subTest(options=options):
                await self.exercise(**options)

    async def test_waiting_for_startup_or_season_does_not_pin_source(self):
        for options in ({'ready': False}, {'season': None}):
            with self.subTest(options=options):
                await self.exercise(**options)

    async def test_actual_old_reader_preserves_evidence_until_it_releases(self):
        await self.exercise(reader=True)
