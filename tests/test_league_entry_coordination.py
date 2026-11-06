"""League-entry recovery preserves source evidence and heavyweight admission."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from time import monotonic
import unittest
from unittest.mock import AsyncMock, Mock, patch

from services import league_preparation as preparation
from src.core.league_runtime import LeagueRuntime, LeagueRuntimeDeferred, LeagueRuntimeManager, RuntimeState
from src.platform.lifecycle import HeavyWorkDeferred, lifecycle_coordinator
from tests import test_cold_league_recovery as cold
from tests.test_import_commissioner_integrity import snapshot
from tests.test_league_runtime import league_data


class CachedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'league.json'
        self.data = league_data('200')
        self.write()
        self.enterContext(patch.object(preparation, 'league_cache_file', return_value=self.path))
        self.enterContext(patch.object(preparation, 'memory_snapshot', return_value={
            'cgroup_current_bytes': 1024**3, 'cgroup_limit_bytes': 2 * 1024**3}))

    def write(self):
        self.path.write_text(json.dumps({'data': self.data, 'last_sync': datetime.now(timezone.utc).isoformat()}))

    def test_active_fois_allows_admitted_restore_without_sync_or_changing_source(self):
        runtime = LeagueRuntime('200')
        publish = Mock()
        lifecycle_coordinator.reserve_fois_generation()
        try:
            self.assertTrue(preparation.restore_cached_runtime(runtime, publish, expected_season=2026))
        finally:
            lifecycle_coordinator.release_fois_generation()
        publish.assert_called_once_with(runtime)
        self.assertEqual(runtime.state['data'], self.data)
        self.assertEqual(runtime.lifecycle['preparation_state'], 'last_valid')

    def test_foreign_league_season_scoring_and_expired_evidence_are_rejected(self):
        cases = [lambda d: d['league'].update(league_id='300'),
                 lambda d: d['league'].update(season='2025'),
                 lambda d: d.update(scoring_settings={'rec': 99}),
                 lambda d: d.update(roster_positions=['SUPER_FLEX'])]
        original = deepcopy(self.data)
        for change in cases:
            self.data = deepcopy(original)
            change(self.data)
            self.write()
            runtime, publish = LeagueRuntime('200'), Mock()
            self.assertFalse(preparation.restore_cached_runtime(runtime, publish, expected_season=2026))
            self.assertEqual(runtime.state['data'], {})
            publish.assert_not_called()
        self.path.write_text(json.dumps({'data': original, 'last_sync': '2020-01-01T00:00:00+00:00'}))
        self.assertFalse(preparation.restore_cached_runtime(LeagueRuntime('200'), Mock()))

    def test_unknown_or_insufficient_memory_defers_before_decode(self):
        for sample in ({}, {'cgroup_current_bytes': 2 * 1024**3 - 1, 'cgroup_limit_bytes': 2 * 1024**3}):
            with patch.object(preparation, 'memory_snapshot', return_value=sample), patch.object(preparation, 'load_cache_json') as decode:
                with self.assertRaises(HeavyWorkDeferred):
                    preparation.restore_cached_runtime(LeagueRuntime('200'), Mock())
                decode.assert_not_called()

    def test_active_fois_retains_its_outstanding_reserve_and_release_allows_restore(self):
        sample = {'cgroup_current_bytes':1490 * 1024**2, 'cgroup_limit_bytes':2 * 1024**3}
        with patch.object(preparation, 'memory_snapshot', return_value=sample):
            lifecycle_coordinator.reserve_fois_generation()
            try:
                with patch.object(preparation, 'load_cache_json') as decode:
                    with self.assertRaises(HeavyWorkDeferred):
                        preparation.restore_cached_runtime(LeagueRuntime('200'), Mock())
                    decode.assert_not_called()
            finally:
                lifecycle_coordinator.release_fois_generation()
            self.assertTrue(preparation.restore_cached_runtime(LeagueRuntime('200'), Mock()))

    def test_json_week_keys_restore_without_repricing_or_changing_evidence(self):
        from src.core.intelligence.team_strength import restore_cached_week_keys
        evidence = {'available':True, 'optimal':{'projected_points':0}, 'source_generation':'same'}
        data = {'team_strength':{'teams':{'1':{'weekly':{'8':evidence}}}}}
        restore_cached_week_keys(data)
        self.assertIs(data['team_strength']['teams']['1']['weekly'][8], evidence)
        self.assertEqual(evidence['optimal']['projected_points'], 0)
        for weekly in ({'19':evidence}, {'08':evidence}, {8:evidence,'8':evidence}, {'missing':evidence}):
            with self.assertRaises(ValueError):
                restore_cached_week_keys({'team_strength':{'teams':{'1':{'weekly':weekly}}}})


class OwnedRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_periodic_deferral_waits_for_existing_interval_without_starting_fois(self):
        import dtos_app
        with patch.object(dtos_app, 'STATE', {'preparation_state':'waiting_for_capacity'}), patch.object(dtos_app, 'start_sleeper_sync', new_callable=AsyncMock), patch.object(dtos_app.asyncio, 'sleep', new_callable=AsyncMock, side_effect=[None, asyncio.CancelledError]), patch.object(dtos_app, '_generate_resident_fois', new_callable=AsyncMock) as fois, patch.object(dtos_app.asset_market_cache, 'reconcile') as market:
            with self.assertRaises(asyncio.CancelledError):
                await dtos_app.background_sync()
            fois.assert_not_awaited()
            market.assert_not_called()

    async def test_single_flight_cooldown_and_explicit_recovery(self):
        calls = 0
        async def hydrate(runtime):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise HeavyWorkDeferred('controlled busy lease')
            return league_data(runtime.league_id)
        manager = LeagueRuntimeManager(hydrator=hydrate)
        outcomes = await asyncio.gather(*(manager.acquire_request('200') for _ in range(5)), return_exceptions=True)
        self.assertTrue(all(isinstance(row, LeagueRuntimeDeferred) for row in outcomes))
        self.assertEqual(calls, 1)
        self.assertEqual(manager.resident('200').active_requests, 0)
        for _ in range(3):
            with self.assertRaises(LeagueRuntimeDeferred):
                await manager.get('200')
        self.assertEqual(calls, 1)
        manager.resident('200').lifecycle['hydration_retry_after'] = 0
        runtime = await manager.acquire_request('200')
        self.assertEqual(runtime.status, RuntimeState.WARM)
        self.assertEqual(calls, 2)
        await manager.release_request(runtime)
        self.assertEqual(manager.health()['failures'], 0)
        self.assertEqual(manager.health()['deferrals'], 1)
        await manager.shutdown()

    async def test_cancellation_collects_cache_reader_before_releasing_state(self):
        entered, release = threading.Event(), threading.Event()
        runtime = LeagueRuntime('200')
        def restore(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            runtime.apply_data(league_data('200'))
            return True
        with patch.object(preparation, 'restore_cached_runtime', side_effect=restore):
            task = asyncio.create_task(preparation.restore_cached_runtime_owned(runtime, Mock()))
            self.assertTrue(await asyncio.to_thread(entered.wait, 3))
            task.cancel()
            await asyncio.sleep(.01)
            self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(runtime.state['data'])
        await runtime.close()
        self.assertEqual(runtime.state['data'], {})


class EntryHTTPTests(unittest.TestCase):
    setUp = cold.ColdLeagueRecoveryTests.setUp
    upstream = cold.ColdLeagueRecoveryTests.upstream

    def test_restored_one_qb_cache_supports_real_pre_post_trade_evaluation(self):
        from tests.test_trade_resource_admission import TradeResourceHTTPTests
        test = TradeResourceHTTPTests('test_one_qb_supported_legal_pre_post_and_unchanged_source')
        test.setUp()
        try:
            path = Path(self.folder.name) / 'one-qb.json'
            path.write_text(json.dumps({'data':test.f.data, 'last_sync':datetime.now(timezone.utc).isoformat()}))
            runtime = LeagueRuntime(test.f.data['league']['league_id'])
            with patch.object(preparation, 'league_cache_file', return_value=path):
                self.assertTrue(preparation.restore_cached_runtime(runtime, lambda _:None, expected_season=2026))
            test.f.data = runtime.state['data']
            test.test_one_qb_supported_legal_pre_post_and_unchanged_source()
        finally:
            test.doCleanups()

    def test_busy_cold_entry_has_truthful_status_no_source_calls_or_account_mutations(self):
        before = snapshot(self.store)
        lifecycle_coordinator.reserve_fois_generation()
        try:
            response = self.client.get('/', headers={'Accept': 'text/html'})
            self.assertEqual(response.status_code, 503, response.text)
            self.assertIn('League preparation is waiting', response.text)
            self.assertNotIn('No supported roster', response.text)
            self.assertNotIn('Sync error', response.text)
            self.assertEqual(response.headers['retry-after'], '60')
            self.assertEqual(self.client.get('/api/recovery-context').json()['status'], 'deferred')
            self.client.get('/favicon.ico')
            self.assertEqual(self.source_requests, [])
            self.assertEqual(snapshot(self.store), before)
        finally:
            lifecycle_coordinator.release_fois_generation()

    def test_warm_league_reads_work_while_fois_is_active_without_new_preparation(self):
        runtime = self.manager.attach_default('200', {'data': league_data('200')}, warm=True)
        self.dtos._publish_runtime_context(runtime, cold.ProjectionService(league_id='200'))
        lifecycle_coordinator.reserve_fois_generation()
        try:
            self.assertEqual(self.client.get('/api/recovery-context').status_code, 200)
            self.assertEqual(self.source_requests, [])
        finally:
            lifecycle_coordinator.release_fois_generation()

    def test_saved_publication_serves_cold_entry_during_fois_without_new_heavy_work(self):
        data = league_data('200')
        data['league'].update(name='Saved one-QB league')
        data['roster_positions'] = data['league']['roster_positions'] = ['QB','RB','RB','WR','WR','TE','FLEX','FLEX','K','DEF','BN']
        path = Path(self.folder.name) / 'saved.json'
        path.write_text(json.dumps({'data':data, 'last_sync':datetime.now(timezone.utc).isoformat()}))
        before = snapshot(self.store)
        lifecycle_coordinator.reserve_fois_generation()
        try:
            with patch.object(preparation, 'league_cache_file', return_value=path), patch.object(self.dtos, 'sync_sleeper_league', new_callable=AsyncMock) as sync, patch.object(self.dtos, 'start_background_backfill', new_callable=AsyncMock) as history, patch.object(self.dtos, '_generate_fois_coordinated', new_callable=AsyncMock) as fois, patch.object(self.dtos.AssetMarketCache, 'reconcile') as market:
                response = self.client.get('/api/recovery-context')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['name'], 'Saved one-QB league')
                runtime = self.manager.resident('200')
                self.assertEqual(runtime.state['data'], data)
                self.assertEqual(runtime.lifecycle['cache_restore'], 'restored')
                self.assertIn('K', runtime.state['data']['roster_positions'])
                self.assertIn('DEF', runtime.state['data']['roster_positions'])
                self.assertEqual(len(runtime.background_tasks), 1)  # existing periodic cadence only
                sync.assert_not_awaited()
                history.assert_not_awaited()
                fois.assert_not_awaited()
                market.assert_not_called()
            self.assertEqual(snapshot(self.store), before)
        finally:
            lifecycle_coordinator.release_fois_generation()

    def test_manual_retry_after_cooldown_and_fois_release_performs_real_source_hydration(self):
        before = snapshot(self.store)
        lifecycle_coordinator.reserve_fois_generation()
        try:
            self.assertEqual(self.client.get('/api/recovery-context').json()['status'], 'deferred')
            self.assertEqual(self.source_requests, [])
        finally:
            lifecycle_coordinator.release_fois_generation()
        # Advance the retry clock, not a production admission flag. Actual
        # source acquisition/publication still executes against controlled HTTP.
        self.mode = 'valid'
        with patch('src.core.league_runtime.manager.monotonic', return_value=monotonic()+61), patch.object(self.dtos, '_generate_fois_coordinated', new_callable=AsyncMock, return_value=()), patch.object(self.dtos.AssetMarketCache, 'reconcile'), patch.object(self.dtos, 'start_background_backfill', new_callable=AsyncMock, return_value={'status':'unavailable'}), patch.object(self.dtos, 'history_progress_contracts'), patch.object(self.dtos, 'resolve_historical_trade_market', new_callable=AsyncMock), patch('services.league_maintenance.ensure_periodic_refresh'):
            response = self.client.get('/api/recovery-context')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['name'], 'Recovered league')
            self.assertTrue(any(path.endswith('/league/200') for path in self.source_requests))
            self.assertEqual(self.manager.resident('200').status, RuntimeState.WARM)
        self.assertEqual(snapshot(self.store), before)

    def test_busy_page_accessible_at_phone_sizes_without_automatic_retry(self):
        before = snapshot(self.store)
        rows = []
        lifecycle_coordinator.reserve_fois_generation()
        try:
            for width, height in ((320,432), (375,667), (390,844), (1280,900)):
                with cold.onboarding.PublicOnboardingTests.browser(self, width, height) as page:
                    response = page.goto(self.origin + '/', wait_until='networkidle')
                    self.assertEqual(response.status, 503)
                    self.assertTrue(page.get_by_role('heading', name='League preparation is waiting').is_visible())
                    retry = page.get_by_role('link', name='Try this page again', exact=True)
                    self.assertGreaterEqual(retry.bounding_box()['height'], 44)
                    self.assertLessEqual(retry.bounding_box()['y'] + retry.bounding_box()['height'], height)
                    retry.focus()
                    self.assertNotEqual(retry.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    page.keyboard.press('Enter')
                    page.wait_for_load_state('networkidle')
                    self.assertIn('League preparation is waiting', page.locator('body').inner_text())
                    rows.append({'viewport':[width,height], 'retry':retry.bounding_box(), 'overflow':False})
                    touch = page.context.browser.new_page(viewport={'width':width, 'height':height}, has_touch=True)
                    try:
                        touch.context.add_cookies([{'name':'dtos_session','value':self.token,'url':self.origin}])
                        touch.goto(self.origin+'/', wait_until='networkidle')
                        touch.get_by_role('link', name='Try this page again', exact=True).tap()
                        touch.wait_for_load_state('networkidle')
                        self.assertIn('League preparation is waiting', touch.locator('body').inner_text())
                    finally:
                        touch.context.close()
                    target = os.environ.get('DTOS_LEAGUE_ENTRY_EVIDENCE')
                    if target:
                        Path(target).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(target) / f'waiting-{width}.png'), full_page=True)
            self.assertEqual(self.source_requests, [])
            self.assertEqual(snapshot(self.store), before)
        finally:
            lifecycle_coordinator.release_fois_generation()
        if os.environ.get('DTOS_LEAGUE_ENTRY_EVIDENCE'):
            (Path(os.environ['DTOS_LEAGUE_ENTRY_EVIDENCE']) / 'browser.json').write_text(json.dumps(rows, indent=2))
