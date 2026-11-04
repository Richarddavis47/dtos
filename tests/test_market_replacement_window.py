"""Explicitly separate deferred maintenance, active replacement and publication."""
import asyncio
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.core.asset_market.engine import AssetMarketCache, MarketWarmingError
from src.platform.lifecycle import LifecycleCoordinator, lifecycle_coordinator
from tools.validation.market_replacement_window import ReplacementWindow


class ReplacementWindowTests(unittest.TestCase):
    def test_new_fois_flight_cannot_enter_between_admission_and_probe(self):
        async def exercise():
            lock = asyncio.Lock()
            window = ReplacementWindow(timeout=1, preparation_lock=lock)
            async with window.admitted(LifecycleCoordinator()):
                self.assertTrue(lock.locked())
            contender = asyncio.create_task(lock.acquire())
            await asyncio.sleep(.01)
            self.assertFalse(contender.done())
            window.release()
            await contender
            lock.release()
            window.release()  # idempotent; must not release another owner's lock
        asyncio.run(exercise())

    def test_existing_fois_must_finish_before_admission(self):
        coordinator = LifecycleCoordinator()
        window = ReplacementWindow(timeout=1)
        coordinator.reserve_fois_generation()

        async def exercise():
            entered = asyncio.Event()

            async def begin():
                async with window.admitted(coordinator):
                    entered.set()

            task = asyncio.create_task(begin())
            await asyncio.sleep(.02)
            self.assertFalse(entered.is_set())
            self.assertTrue(coordinator.snapshot()['heavy_work']['market_critical'])
            coordinator.release_fois_generation()
            await task
            self.assertTrue(entered.is_set())
            window.release()

        asyncio.run(exercise())
        self.assertFalse(coordinator.snapshot()['heavy_work']['market_critical'])

    def test_admission_timeout_releases_reservation(self):
        coordinator = LifecycleCoordinator()
        coordinator.reserve_fois_generation()
        window = ReplacementWindow(timeout=.01)

        async def exercise():
            async with window.admitted(coordinator):
                self.fail('blocked admission entered')

        with self.assertRaises(TimeoutError):
            asyncio.run(exercise())
        self.assertFalse(coordinator.snapshot()['heavy_work']['market_critical'])

    def test_publication_timeout_does_not_publish(self):
        window = ReplacementWindow(timeout=.01)

        async def arm():
            async with window.admitted(LifecycleCoordinator()):
                pass

        asyncio.run(arm())
        with self.assertRaises(TimeoutError):
            window.before_publication()
        window.release()

    def test_real_cache_http_before_during_and_after_atomic_publication(self):
        lifecycle_coordinator.reset()
        window = ReplacementWindow(timeout=2)
        cache = AssetMarketCache()
        store = SimpleNamespace(path=Path('fixture.sqlite3'))
        data = {'asset_market_semantic_revision': 'new'}
        state = {}
        marker = cache.request_marker(data, state, store, 'league-A')

        def market(generation):
            return SimpleNamespace(
                store=store, _artifact_path=Path('fixture-market.sqlite3'),
                generation=generation, league='league-A', assets=(generation,),
                health=lambda: {'status': 'ready', 'league_id': 'league-A'},
            )

        old, new = market('old'), market('new')
        cache._market = old
        cache._request_marker = ('old',)
        waiting = threading.Event()

        def prepare(*args):
            waiting.set()
            window.before_publication()
            cache._publish(new, 'new-key', 'store-A', marker)

        app = FastAPI()

        @app.get('/probe')
        def probe():
            try:
                value = cache.get(data, state, store, 'league-A', background=True)
                return {'generation': value.generation, 'league': value.league,
                        'assets': value.assets}
            except MarketWarmingError as exc:
                raise HTTPException(503, str(exc)) from exc

        try:
            with TestClient(app) as client, patch.object(
                cache, '_prepare_generation', side_effect=prepare,
            ), patch.object(cache, 'cleanup_artifacts'):
                lifecycle_coordinator.reserve_fois_generation()
                response = client.get('/probe')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['assets'], ['old'])
                self.assertEqual(cache.last_miss_reason, 'heavy_phase_last_valid')
                self.assertEqual(cache.attempted_constructions, 0)
                lifecycle_coordinator.release_fois_generation()

                async def arm():
                    async with window.admitted(lifecycle_coordinator):
                        cache.reconcile(data, state, store, 'league-A')

                asyncio.run(arm())
                self.assertTrue(waiting.wait(1))
                for _ in range(10):
                    self.assertEqual(client.get('/probe').status_code, 503)
                    self.assertIs(cache._market, old)
                window.release()
                self.assertTrue(cache.wait_for_background(2))
                response = client.get('/probe')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    'generation': 'new', 'league': 'league-A', 'assets': ['new'],
                })
                self.assertEqual(cache.build_count, 1)
                self.assertEqual(cache.attempted_constructions, 1)
        finally:
            window.release()
            cache.wait_for_background(2)
            lifecycle_coordinator.reset()
