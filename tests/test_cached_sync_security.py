"""Synthetic cached synchronization failures through actual private HTTP paths."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from src.core.sync_status import safe_sync_state, synchronization_warning
from src.platform.observability import RequestObservabilityMiddleware, request_id_context
from tests import test_diagnostic_security as fixtures


PRIVATE_ERROR = "PRIVATE_SYNC_MARKER /private/sleeper.sqlite3 source-league-987654321 Authorization: Bearer FAKE_CREDENTIAL"
FORBIDDEN = ("PRIVATE_SYNC_MARKER", "/private/sleeper", "987654321", "FAKE_CREDENTIAL", "Traceback")


class CachedSyncHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DiagnosticSecurityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.app.add_middleware(RequestObservabilityMiddleware)
        self.f.sign_in('bob')
        self.state = self.f.states['222']
        self.state['data']['teams'][0]['roster_id'] = 2
        self.state['last_error'] = PRIVATE_ERROR
        self.state['transactions_last_error'] = PRIVATE_ERROR

    def assert_safe(self, response, status=200):
        self.assertEqual(response.status_code, status, response.text)
        wire = response.text + json.dumps(dict(response.headers))
        for marker in FORBIDDEN:
            self.assertNotIn(marker, wire)
        self.assertIn('no-store', response.headers.get('cache-control', ''))
        self.assertIn('private', response.headers.get('cache-control', ''))

    def test_original_scout_endpoints_and_related_full_serialized_bodies(self):
        before = copy.deepcopy(self.f.states)
        for path in ['/api/inspect/team/2', '/api/inspect/trades', '/api/inspect',
                     '/api/inspect/pages', '/api/inspect/player/p1', '/api/inspect/front-office/2']:
            with self.subTest(path=path):
                response = self.f.client.get(path, headers={'X-Request-ID': 'fixture-sync-198'})
                self.assert_safe(response)
                self.assertIn(synchronization_warning(self.state), response.text)
                self.assertEqual(response.headers['x-request-id'], 'fixture-sync-198')
                self.assertEqual(response.json()['last_updated'], before['222']['last_sync'])
        team = self.f.client.get('/api/inspect/team/2').text
        self.assertIn('PRIVATE_MANAGER_222', team)  # Authorized last-valid facts remain.
        self.assertNotIn('PRIVATE_MANAGER_111', team)
        self.assertEqual(self.f.states, before)
        self.f.no_work.assert_not_called()

    def test_alternate_formats_slash_and_legacy_errors(self):
        for path in ['/api/inspect/team/2/', '/api/inspect%2fteam%2f2', '/api/inspect/trades/']:
            for accept in ['application/json', 'text/html']:
                self.assert_safe(self.f.client.get(path, headers={'Accept': accept}))
        self.assert_safe(self.f.client.get('/api/inspect/player/missing'), 404)
        self.assert_safe(self.f.client.get('/api/inspect/live/health'))
        # Empty cached data must fail safely without claiming last-valid recovery.
        self.state['data'] = {}
        self.assert_safe(self.f.client.get('/api/inspect/team/2'), 503)

    def test_statuses_remain_safe_and_public_probes_do_not_acquire_context(self):
        calls = self.f.manager.acquire_request.await_count
        for path in ['/api/status', '/health/live', '/health', '/health/ready']:
            response = self.f.client.get(path)
            self.assertIn(response.status_code, (200, 503))
            for marker in FORBIDDEN:
                self.assertNotIn(marker, response.text)
        self.assertEqual(calls, self.f.manager.acquire_request.await_count)
        self.f.no_work.assert_not_called()

    def test_anonymous_foreign_revoked_and_expired_sessions(self):
        for cookie in [None, 'expired-or-unrecognized-session']:
            self.f.client.cookies.clear()
            if cookie:
                self.f.client.cookies.set('dtos_session', cookie)
            self.assert_safe(self.f.client.get('/api/inspect/trades'), 401)
        self.f.sign_in('bob')
        for path in ['/api/inspect/team/1', '/api/inspect/trades?league=111', '/api/inspect/team/2?front_office=1']:
            self.assert_safe(self.f.client.get(path), 403)
        self.f.store.revoke_session(self.f.sessions['bob'])
        self.assert_safe(self.f.client.get('/api/inspect/trades'), 401)
        self.f.manager.acquire_request.assert_not_called()

    def test_existing_operator_inspection_is_safe_and_authorized(self):
        response = self.f.client.get('/api/inspect/team/1', headers={'X-DTOS-Inspection-Auth': 'fixture-only-token'})
        self.assert_safe(response)
        self.assertIn('PRIVATE_MANAGER_111', response.text)
        self.assertNotIn('PRIVATE_MANAGER_222', response.text)

    def test_shared_html_and_transaction_recovery_paths(self):
        import dtos_app
        from routes.transactions import create_transactions_router
        from src.platform.league_context import RuntimeStateProxy, current_league_context
        self.f.app.add_api_route('/market/sync-recovery', lambda: dtos_app.page('League recovery', '<h2>Saved league data</h2>'))
        self.f.app.include_router(create_transactions_router(
            ensure_fresh=AsyncMock(), refresh_transactions=self.f.no_work,
            require_data=lambda: current_league_context().state["data"],
            state=RuntimeStateProxy(self.f.states['111']), page=dtos_app.page))
        for path in ['/market/sync-recovery', '/transactions?refresh=error']:
            response = self.f.client.get(path)
            self.assert_safe(response)
            self.assertIn(synchronization_warning(self.state), response.text)
            self.assertIn('/account', response.text)
        self.f.no_work.assert_not_called()

    def test_manual_sync_json_and_prepared_health_never_reflect_legacy_error(self):
        from src.core.intelligence import intelligence_orchestrator
        token, csrf = self.f.service.new_session(self.f.accounts['bob'])
        self.f.client.cookies.set('dtos_session', token)
        # Router closure is the existing explicit sync action, not a read.
        self.f.no_work.side_effect = None
        self.f.no_work.return_value = self.state
        response = self.f.client.post('/sync', headers={'X-CSRF-Token': csrf, 'Accept': 'application/json'})
        self.assert_safe(response)
        self.assertEqual(response.json(), {'ok': False, 'last_sync': self.state['last_sync'],
                                          'error': synchronization_warning(self.state)})
        self.assertEqual(self.f.no_work.await_count, 1)
        self.assertEqual(intelligence_orchestrator.health(self.state)['sleeper']['last_error'],
                         synchronization_warning(self.state))


class CachedSyncProducerTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sync_failure_restores_exact_last_valid_identity_and_safe_status(self):
        from services import sleeper
        state = {'data': {'league': {'league_id': '222'}, 'value': 0}, 'syncing': False,
                 'last_sync': '2026-10-01T12:00:00Z', 'transactions_last_sync': 'older',
                 'transactions_last_error': None}
        original = state['data']
        class NeverStringify(RuntimeError):
            def __str__(self):
                raise AssertionError('Exception text must never be inspected')
        with patch.object(sleeper, 'sleeper_get', AsyncMock(side_effect=NeverStringify(PRIVATE_ERROR))), \
             patch.object(sleeper, 'save_cache') as save, \
             self.assertLogs('dtos.request', level='WARNING') as logs:
            await sleeper._sync_sleeper(league_id='222', state=state)
        self.assertIs(state['data'], original)
        self.assertEqual(state['data']['value'], 0)
        self.assertEqual(state['last_sync'], '2026-10-01T12:00:00Z')
        self.assertEqual(state['transactions_last_sync'], 'older')
        self.assertEqual(state['last_error'], synchronization_warning(state))
        self.assertFalse(state['syncing'])
        save.assert_not_called()
        self.check_logs(logs, 'league_sync')

    def check_logs(self, captured, operation):
        record = next(row for row in captured.records if row.getMessage() == 'synchronization_failure')
        self.assertEqual(record.diagnostic['operation'], operation)
        self.assertLessEqual(len(record.diagnostic['frames']), 6)
        self.assertTrue(record.diagnostic['frames'])
        self.assertIsNone(record.exc_info)
        wire = json.dumps(record.diagnostic) + record.getMessage()
        for marker in FORBIDDEN:
            self.assertNotIn(marker, wire)

    async def test_actual_transaction_failure_preserves_facts_and_logs_without_credentials(self):
        from services import sleeper
        data = {'league': {'league_id': '222'}, 'week': 7, 'transactions': [{'transaction_id': 'exact', 'faab': 0}]}
        state = {'data': data, 'transactions_last_sync': 'last-valid', 'transactions_syncing': False}
        token = request_id_context.set('fixture-sync-correlation-198')
        try:
            with patch.object(sleeper, 'sleeper_get', AsyncMock(side_effect=RuntimeError(PRIVATE_ERROR))), \
                 self.assertLogs('dtos.request', level='WARNING') as logs:
                result = await sleeper.sync_transactions(state=state, league_id='222')
        finally:
            request_id_context.reset(token)
        self.assertFalse(result)
        self.assertIs(state['data'], data)
        self.assertEqual(data['transactions'], [{'transaction_id': 'exact', 'faab': 0}])
        self.assertEqual(state['transactions_last_sync'], 'last-valid')
        self.assertFalse(state['transactions_syncing'])
        self.assertEqual(state['transactions_last_error'], synchronization_warning(state, transactions=True))
        self.check_logs(logs, 'transaction_sync')
        self.assertEqual(logs.records[0].request_id, 'fixture-sync-correlation-198')

    async def test_safe_cache_roundtrip_does_not_persist_legacy_exception_text_or_mutate_facts(self):
        from services import sleeper
        state = {'data': {'league': {'league_id': '222'}, 'zero': 0}, 'last_error': PRIVATE_ERROR,
                 'transactions_last_error': PRIVATE_ERROR, 'last_sync': 'last-valid'}
        before = copy.deepcopy(state)
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / 'cache.json'
            with patch.object(sleeper, 'league_cache_file', return_value=cache):
                sleeper.save_cache(state=state, league_id='222')
                self.assertTrue(cache.exists())
                self.assertNotIn(PRIVATE_ERROR, cache.read_text())
                reloaded = {}
                sleeper.load_cache(state=reloaded, league_id='222')
                self.assertEqual(reloaded['data'], state['data'])
                self.assertEqual(reloaded['last_sync'], 'last-valid')
                self.assertEqual(reloaded['last_error'], synchronization_warning(state))
                # An older cache is normalized in memory without rewriting it on read.
                cache.write_text(json.dumps(state))
                disk_before = cache.read_bytes()
                sleeper.load_cache(state=reloaded, league_id='222')
                self.assertEqual(cache.read_bytes(), disk_before)
                self.assertNotIn(PRIVATE_ERROR, json.dumps(reloaded))
        self.assertEqual(state, before)

    async def test_missing_failure_success_and_no_data_have_distinct_status(self):
        state = {'data': {}, 'last_error': PRIVATE_ERROR, 'transactions_last_error': None}
        self.assertIn('No saved league data', safe_sync_state(state)['last_error'])
        self.assertIsNone(safe_sync_state(state)['transactions_last_error'])
        state.update(data={'zero': 0}, last_error=None)
        self.assertIsNone(safe_sync_state(state)['last_error'])
        self.assertIn('last successfully loaded', synchronization_warning(state))
        self.assertIs(safe_sync_state(state)['data'], state['data'])


if __name__ == '__main__':
    unittest.main()
