"""Actual authenticated hydration and real spawned-worker failure boundaries.

Only disposable sources/accounts are used. No production FOIS regeneration.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import psutil

from src.core.fois import process_execution as execution
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from routes.fois import create_fois_router
from src.platform.league_context import current_league_context
from services.league_maintenance import ensure_fois_refresh
from src.core.league_runtime import LeagueRuntime, RuntimeState
from tests.test_fois_process_execution import cache_input, fixture
from tests import test_cold_league_recovery as cold
from tests.test_import_commissioner_integrity import snapshot


class NavigationReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.f = cold.ColdLeagueRecoveryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.mode = 'valid'
        self.enterContext(patch.object(self.f.dtos.AssetMarketCache, 'reconcile'))
        self.enterContext(patch.object(self.f.dtos, 'start_background_backfill',
            new_callable=AsyncMock, return_value={'status': 'complete'}))
        self.enterContext(patch.object(self.f.dtos, 'history_progress_contracts'))
        self.enterContext(patch.object(self.f.dtos, 'resolve_historical_trade_market', new_callable=AsyncMock))
        self.enterContext(patch('services.league_maintenance.ensure_periodic_refresh'))
        self.service = FOISService(FOISRepository(Path(self.f.folder.name) / 'fois.sqlite3'))
        self.enterContext(patch.object(self.f.dtos, 'fois_service', self.service))
        self.f.app.include_router(create_fois_router(service=self.service,
            require_data=lambda: current_league_context().data,
            page=self.f.dtos.page, generate=self.f.dtos._request_fois_calculation))

    def drain(self):
        async def finish():
            runtime = self.f.manager.resident('200')
            while runtime and runtime.background_tasks:
                await asyncio.gather(*tuple(runtime.background_tasks))
        self.f.client.portal.call(finish)

    def test_home_healthy_optional_fois(self):
        with patch.object(self.f.dtos, '_generate_fois_coordinated',
                          new_callable=AsyncMock, return_value=()):
            self.assertEqual(self.f.client.get('/').status_code, 200)

    def test_home_and_account_survive_fois_timeout_without_account_mutation(self):
        before = snapshot(self.f.store)
        with patch.object(self.f.dtos, '_generate_fois_coordinated',
                          new_callable=AsyncMock,
                          side_effect=RuntimeError('FOIS compute process timed out.')):
            response = self.f.client.get('/')
            self.assertEqual(response.status_code, 200, response.text)
            self.drain()
            self.assertIn('FOIS', response.text)
            self.assertNotIn('Traceback', response.text)
            self.assertEqual(self.f.client.get('/account').status_code, 200)
            self.assertEqual(self.f.client.get('/api/recovery-context').status_code, 200)
            self.assertEqual(self.f.client.get('/league').status_code, 200)
            self.assertIn('temporarily unavailable', self.f.client.get('/').text)
            status = self.f.client.get('/api/fois/status').json()
            self.assertEqual((status['state'], status['evidence_state']), ('failed', 'unavailable'))
            self.assertEqual(status['league_id'], '200')
            self.assertIn('unavailable', self.f.client.get('/fois').text)
        self.assertEqual(snapshot(self.f.store), before)

    def test_programming_error_in_optional_fois_is_isolated_and_not_a_zero(self):
        with patch.object(self.f.dtos, '_generate_fois_coordinated', new_callable=AsyncMock,
                          side_effect=ValueError('private diagnostic')) as compute:
            self.assertEqual(self.f.client.get('/').status_code, 200)
            self.drain()
            calls = len(self.f.source_requests)
            for _ in range(10):
                response = self.f.client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('private diagnostic', response.text)
            self.assertEqual(len(self.f.source_requests), calls)
            self.assertEqual(compute.await_count, 1)
            # A query cannot override authenticated account selection.
            self.assertEqual(self.f.client.get('/api/fois/status?league_id=100').json()['league_id'], '200')
            selected = self.f.client.post('/api/account/active-league', json={'league_id': '100'},
                headers={'X-CSRF-Token': self.f.csrf})
            self.assertEqual(selected.status_code, 200)
            other = self.f.client.get('/api/fois/status').json()
            self.assertNotEqual(other['state'], 'failed')
            self.assertEqual(other['league_id'], '100')

    def test_slow_fois_never_holds_home_or_duplicate_browsing(self):
        gate = self.f.client.portal.call(asyncio.Event)
        entered = threading.Event()

        async def slow(_data):
            entered.set()
            await gate.wait()
            return ()

        with patch.object(self.f.dtos, '_generate_fois_coordinated', side_effect=slow) as compute, \
                ThreadPoolExecutor(max_workers=5) as pool:
            first = pool.submit(self.f.client.get, '/')
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(first.result(timeout=1).status_code, 200)
                responses = list(pool.map(lambda _: self.f.client.get('/'), range(12)))
                self.assertTrue(all(response.status_code == 200 for response in responses))
                self.assertEqual(self.f.client.get('/account/leagues').status_code, 200)
                status = self.f.client.get('/api/fois/status').json()
                self.assertEqual(status['state'], 'running')
                response = self.f.client.post('/api/fois/leagues/200/calculate',
                    headers={'X-CSRF-Token': self.f.csrf})
                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.json()['generation_status'], 'pending')
                self.assertEqual(compute.await_count, 1)
            finally:
                self.f.client.portal.call(gate.set)
                first.result(timeout=3)
                self.drain()

    def test_explicit_failure_is_503_and_later_real_engine_retry_recovers(self):
        original = self.f.dtos._generate_fois_coordinated
        with patch.object(self.f.dtos, '_generate_fois_coordinated', new_callable=AsyncMock,
                          side_effect=RuntimeError('private diagnostic')) as compute:
            self.assertEqual(self.f.client.get('/').status_code, 200)
            self.drain()
            response = self.f.client.post('/api/fois/leagues/200/calculate', headers={'X-CSRF-Token': self.f.csrf})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private diagnostic', response.text)
            # Explicit fixture history avoids any provider/history backfill.
            self.f.manager.resident('200').state['data']['fois_history'] = {}
            compute.side_effect = original
            response = self.f.client.post('/api/fois/leagues/200/calculate', headers={'X-CSRF-Token': self.f.csrf})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()['scores'])
            self.assertEqual(self.f.client.get('/api/fois/status').json()['state'], 'complete')
            self.assertEqual(self.f.manager.resident('200').canonical_context.fois_state, 'ready')

    def test_rendered_phone_home_failure_and_scoped_fois_navigation(self):
        rows = []
        from fastapi.staticfiles import StaticFiles
        from tests import test_public_readiness as onboarding
        # The released standings/phone styles must be served in this reduced
        # authenticated app, just as in the production application.
        self.f.app.mount('/static', StaticFiles(directory=Path(__file__).resolve().parents[1] / 'static'), name='static')
        # Hydrate once; every subsequent browser read must reuse the failed
        # optional status rather than starting another analytical flight.
        with patch.object(self.f.dtos, '_generate_fois_coordinated', new_callable=AsyncMock,
                          side_effect=RuntimeError('private diagnostic')) as compute:
            self.assertEqual(self.f.client.get('/').status_code, 200)
            self.drain()
            before = snapshot(self.f.store)
            calls = len(self.f.source_requests)
            with onboarding.PublicOnboardingTests.browser(self.f, 390, 844) as page:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    self.assertEqual(page.goto(self.f.origin + '/', wait_until='networkidle').status, 200)
                    notice = page.get_by_role('status').filter(has_text='FOIS')
                    self.assertIn('temporarily unavailable', notice.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width, page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,100),right:e.getBoundingClientRect().right})).slice(0,15)"))
                    link = notice.get_by_role('link')
                    link.focus()
                    self.assertTrue(link.evaluate('e=>e===document.activeElement'))
                    bounds = notice.bounding_box()
                    with page.expect_navigation(wait_until='networkidle'):
                        page.keyboard.press('Enter')
                    self.assertIn('unavailable', page.locator('body').inner_text())
                    self.assertNotIn('private diagnostic', page.locator('body').inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width, page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,100),right:e.getBoundingClientRect().right})).slice(0,15)"))
                    self.assertEqual(page.goto(self.f.origin + '/account', wait_until='networkidle').status, 200)
                    rows.append({'width': width, 'height': height, 'home_notice': bounds,
                                 'home_account_fois_accessible': True, 'overflow': False})
            self.assertEqual(snapshot(self.f.store), before)
            self.assertEqual(len(self.f.source_requests), calls)
            self.assertEqual(compute.await_count, 1)
        target = os.environ.get('DTOS_FOIS_BROWSER_EVIDENCE')
        if target:
            Path(target).write_text(json.dumps(rows, indent=2))

    def test_auth_and_csrf_remain_before_optional_computation(self):
        with patch.object(self.f.dtos, '_generate_fois_coordinated', new_callable=AsyncMock) as compute:
            response = self.f.client.post('/api/fois/leagues/200/calculate', headers={'X-CSRF-Token': 'foreign'})
            self.assertEqual(response.status_code, 403)
            self.f.client.cookies.clear()
            self.assertEqual(self.f.client.get('/', follow_redirects=False).status_code, 303)
            compute.assert_not_called()


class OptionalFlightTests(unittest.IsolatedAsyncioTestCase):
    async def test_retained_evidence_stays_retained_on_failure(self):
        runtime = LeagueRuntime('200', status=RuntimeState.WARM)
        runtime.state['data'] = {'league': {'league_id': '200'}}
        runtime.canonical_context = SimpleNamespace(fois_state='retained')
        generate = AsyncMock(side_effect=RuntimeError('timeout'))
        ensure_fois_refresh(runtime, generate)
        ensure_fois_refresh(runtime, generate)
        await asyncio.gather(*tuple(runtime.background_tasks))
        self.assertEqual(generate.await_count, 1)
        self.assertEqual(runtime.canonical_context.fois_state, 'retained')
        self.assertEqual(runtime.lifecycle['fois_generation'], 'failed')

    async def test_default_startup_and_periodic_refresh_publish_scoped_success_and_failure(self):
        import dtos_app
        runtime = LeagueRuntime('200', status=RuntimeState.WARM)
        data = {'league': {'league_id': '200'}}
        runtime.state['data'] = data
        runtime.canonical_context = SimpleNamespace(fois_state='retained')
        scores = (SimpleNamespace(generated_at='2026-10-19T00:00:00Z'),)
        service = SimpleNamespace(repository=SimpleNamespace(league=lambda *_: scores))
        manager = SimpleNamespace(resident=lambda league: runtime if league == '200' else None)
        with patch.object(dtos_app, 'league_runtime_manager', manager), patch.object(dtos_app, 'fois_service', service), \
                patch.object(dtos_app, '_generate_fois_coordinated', new_callable=AsyncMock, return_value=scores) as generate:
            self.assertEqual(await dtos_app._generate_resident_fois(data), scores)
            self.assertEqual(runtime.canonical_context.fois_state, 'ready')
            self.assertEqual(runtime.lifecycle['fois_generation'], 'complete')
            # A failed refresh must retain the just-completed valid evidence.
            generate.side_effect = RuntimeError('private failure')
            with self.assertRaisesRegex(RuntimeError, 'temporarily|unavailable'):
                await dtos_app._generate_resident_fois(data)
            self.assertEqual(runtime.canonical_context.fois_state, 'retained')
            self.assertEqual(runtime.lifecycle['fois_generation'], 'failed')
            generate.side_effect = None
            self.assertEqual(await dtos_app._generate_resident_fois(data), scores)
            self.assertEqual(runtime.canonical_context.fois_state, 'ready')

    async def test_superseded_generation_cannot_claim_ready(self):
        runtime = LeagueRuntime('200', status=RuntimeState.WARM)
        runtime.state['data'] = {'league': {'league_id': '200'}}
        runtime.source_generations = {'rosters': 'A'}
        runtime.canonical_context = SimpleNamespace(fois_state='pending')
        entered, release = asyncio.Event(), asyncio.Event()

        async def controlled(_data):
            entered.set()
            await release.wait()
            return (SimpleNamespace(generated_at='2026-10-19T00:00:00Z'),)

        ensure_fois_refresh(runtime, controlled)
        await entered.wait()
        runtime.source_generations = {'rosters': 'B'}
        release.set()
        await asyncio.gather(*tuple(runtime.background_tasks))
        self.assertNotEqual(runtime.canonical_context.fois_state, 'ready')
        self.assertEqual(runtime.lifecycle['fois_generation'], 'superseded')


class HeavyAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_then_fois_is_serial_and_cancelled_reservation_releases(self):
        import dtos_app
        from src.platform.lifecycle import LifecycleCoordinator
        coordinator = LifecycleCoordinator()
        entered, release = threading.Event(), threading.Event()
        def market():
            with coordinator.phase('asset_market_build'):
                with coordinator.phase('historical_cache'):
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError('Market barrier not released')
        writer = asyncio.create_task(asyncio.to_thread(market))
        self.assertTrue(await asyncio.to_thread(entered.wait, 2))
        service = SimpleNamespace(generate=AsyncMock(return_value=()))
        with patch.object(dtos_app, 'lifecycle_coordinator', coordinator), patch.object(dtos_app, 'fois_service', service):
            request = asyncio.create_task(dtos_app._generate_fois_coordinated({}))
            try:
                for _ in range(10):
                    await asyncio.sleep(0)
                service.generate.assert_not_awaited()
                self.assertFalse(request.done())
                for _ in range(3):
                    request.cancel()
                    await asyncio.sleep(0)
                self.assertFalse(request.done())
            finally:
                release.set()
            await writer
            with self.assertRaises(asyncio.CancelledError):
                await request
            self.assertEqual(coordinator._fois_generation, 0)
            service.generate.assert_not_awaited()
            await dtos_app._generate_fois_coordinated({})
            service.generate.assert_awaited_once()
            self.assertEqual(coordinator._fois_generation, 0)


class WorkerTimeoutReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await execution.shutdown_fois_executor()

    async def checkpoint(self):
        for _ in range(4):
            ready = asyncio.get_running_loop().create_future()
            asyncio.get_running_loop().call_soon(ready.set_result, None)
            await ready

    async def test_cancellation_during_submission_drains_handle_then_stops_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'fois.sqlite3')
            cache = cache_input(root, fixture())
            worker = (await execution.warm_fois_executor())['pid']
            original = execution._submit
            entered, release = threading.Event(), threading.Event()

            def held(_function, *_args):
                future = original(time.sleep, 30)
                entered.set()
                if not release.wait(4):
                    raise AssertionError('Submission barrier was not released')
                return future

            with patch.object(execution, '_submit', side_effect=held):
                task = asyncio.create_task(execution.generate_fois_isolated(fixture(), repository, cache_file=cache))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                    for _ in range(3):
                        task.cancel()
                        await self.checkpoint()
                    self.assertFalse(task.done())
                    self.assertTrue(list(root.glob('.dtos-fois-compute-*')))
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(task), 4)
            self.assertFalse(psutil.pid_exists(worker))
            self.assertFalse(list(root.glob('.dtos-fois-compute-*')))
            self.assertEqual(execution._IN_FLIGHT, 0)

    async def test_repeated_cancellation_cannot_outrun_worker_shutdown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'fois.sqlite3')
            cache = cache_input(root, fixture())
            worker = (await execution.warm_fois_executor())['pid']
            submit, stop = execution._submit, execution.shutdown_fois_executor_sync
            entered, release = threading.Event(), threading.Event()

            def held_stop():
                entered.set()
                if not release.wait(4):
                    raise AssertionError('Shutdown barrier was not released')
                return stop()

            with patch.object(execution, '_submit', side_effect=lambda _fn, *_args: submit(time.sleep, 30)), \
                    patch.object(execution, 'shutdown_fois_executor_sync', side_effect=held_stop):
                task = asyncio.create_task(execution.generate_fois_isolated(fixture(), repository, cache_file=cache, timeout=.1))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                    for _ in range(5):
                        task.cancel()
                        await self.checkpoint()
                    self.assertFalse(task.done())
                    self.assertTrue(list(root.glob('.dtos-fois-compute-*')))
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(task), 4)
            self.assertFalse(psutil.pid_exists(worker))
            self.assertFalse(list(root.glob('.dtos-fois-compute-*')))

    async def test_second_generation_is_busy_without_copy_or_stopping_first(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'fois.sqlite3')
            cache = cache_input(root, fixture())
            worker = (await execution.warm_fois_executor())['pid']
            submit = execution._submit
            entered = threading.Event()

            def slow(_function, *_args):
                future = submit(time.sleep, 30)
                entered.set()
                return future

            with patch.object(execution, '_submit', side_effect=slow), \
                    patch.object(execution, '_prepare_working_database', wraps=execution._prepare_working_database) as prepare:
                first = asyncio.create_task(execution.generate_fois_isolated(fixture(), repository, cache_file=cache))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                    with self.assertRaises(execution.FOISExecutionBusy):
                        await execution.generate_fois_isolated(fixture(), repository, cache_file=cache)
                    self.assertTrue(psutil.pid_exists(worker))
                    self.assertFalse(first.done())
                    self.assertEqual(prepare.call_count, 1)
                finally:
                    first.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await first
            self.assertFalse(list(root.glob('.dtos-fois-compute-*')))

    async def test_publication_writer_drains_before_cancelled_scratch_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'fois.sqlite3')
            cache = cache_input(root, fixture())
            original = execution._validate_and_publish
            entered, release = threading.Event(), threading.Event()

            def held(*args):
                entered.set()
                if not release.wait(4):
                    raise AssertionError('Publication barrier was not released')
                return original(*args)

            with patch.object(execution, '_validate_and_publish', side_effect=held):
                task = asyncio.create_task(execution.generate_fois_isolated(fixture(), repository, cache_file=cache))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                    for _ in range(3):
                        task.cancel()
                        await self.checkpoint()
                    self.assertFalse(task.done())
                    self.assertTrue(list(root.glob('.dtos-fois-compute-*')))
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(task), 4)
            # Publication already began: finish its atomic transaction rather
            # than deleting a source while the writer still uses it.
            self.assertEqual(len(repository.league('fois-process-fixture', '5.1')), 2)
            self.assertFalse(list(root.glob('.dtos-fois-compute-*')))

    async def test_timeout_reaps_owned_worker_before_return_and_keeps_canonical(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'fois.sqlite3')
            cache = cache_input(root, fixture())
            before = repository.path.read_bytes(), cache.read_bytes()
            worker = (await execution.warm_fois_executor())['pid']
            original = execution._submit

            def slow(_function, *_args):
                return original(time.sleep, 30)

            with patch.object(execution, '_submit', side_effect=slow), \
                    patch.object(execution, '_validate_and_publish') as publish:
                with self.assertRaisesRegex(RuntimeError, 'timed out'):
                    await execution.generate_fois_isolated(
                        fixture(), repository, cache_file=cache, timeout=.1)
                self.assertFalse(psutil.pid_exists(worker), 'Timed-out child remains resident/running')
                self.assertEqual(execution._IN_FLIGHT, 0)
                self.assertFalse(list(root.glob('.dtos-fois-compute-*')))
                publish.assert_not_called()
                self.assertEqual((repository.path.read_bytes(), cache.read_bytes()), before)
            scores, _, _ = await execution.generate_fois_isolated(
                fixture(), repository, cache_file=cache)
            self.assertTrue(scores)
