"""Actual authenticated HTTP boundaries with disposable runtime failures."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from routes.league_runtime import create_league_runtime_router
from src.core.league_runtime import LeagueRuntime, LeagueRuntimeError, LeagueRuntimeNotFound
from src.platform.observability import RequestObservabilityMiddleware
from src.platform.runtime_errors import runtime_error_payload
from tests import test_diagnostic_security as fixtures


SECRET = "PRIVATE_RUNTIME_MARKER /private/runtime.sqlite3 source-league-987654321 Authorization: Bearer PRIVATE_CREDENTIAL"


class RuntimeErrorSecurityTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DiagnosticSecurityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.app.add_middleware(RequestObservabilityMiddleware)
        self.client = TestClient(self.f.app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.token, self.csrf = self.f.service.new_session(self.f.accounts['bob'])
        self.client.cookies.set('dtos_session', self.token)

    def assert_safe(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        # Check the complete serialized body and headers, not only parsed keys.
        wire = response.text + json.dumps(dict(response.headers))
        for marker in ['PRIVATE_', '/private/', '987654321', 'Traceback', 'Bearer']:
            self.assertNotIn(marker, wire)
        self.assertIn('no-store', response.headers.get('cache-control', ''))
        self.assertIn('private', response.headers.get('cache-control', ''))

    def test_secondary_league_exact_scout_503_422_500_controls(self):
        before = copy.deepcopy(self.f.states)
        for error, status in [(LeagueRuntimeError, 503), (LeagueRuntimeNotFound, 422), (RuntimeError, 500)]:
            with self.subTest(error=error.__name__):
                self.f.manager.acquire_request.side_effect = error(SECRET)
                response = self.client.get('/api/inspect/live/teams', headers={'X-Request-ID': 'fixture-runtime-197'})
                self.assert_safe(response, status)
                expected = {'status': 'diagnostic_unavailable'} if status == 500 else runtime_error_payload(status)
                self.assertEqual(response.json(), expected)
                self.assertEqual(response.headers['x-request-id'], 'fixture-runtime-197')
        self.assertEqual(self.f.states, before)
        self.f.manager.release_request.assert_not_called()
        self.f.no_work.assert_not_called()

    def test_default_and_secondary_api_html_head_and_slash_paths(self):
        for who in ['alice', 'bob']:
            self.client.cookies.set('dtos_session', self.f.sessions[who])
            for error, status in [(LeagueRuntimeError, 503), (LeagueRuntimeNotFound, 422)]:
                self.f.manager.acquire_request.side_effect = error(SECRET)
                for path in ['/api/inspect/live/teams/', '/api/players', '/market', '/trades', '/league']:
                    with self.subTest(who=who, error=error.__name__, path=path):
                        response = self.client.get(path, headers={'Accept': 'text/html'}, follow_redirects=False)
                        self.assert_safe(response, status)
                        if not path.startswith('/api/'):
                            self.assertIn('Try this page again', response.text)
                            self.assertIn('/account/leagues', response.text)
                        else:
                            self.assertEqual(response.json(), runtime_error_payload(status))
                response = self.client.head('/league', headers={'Accept': 'text/html'})
                self.assert_safe(response, status)
                self.assertEqual(response.content, b'')

    def test_real_source_mismatch_is_not_returned_or_committed(self):
        runtime = LeagueRuntime('222')
        async def mismatched(*_args, **_kwargs):
            runtime.apply_data({'league': {'league_id': '987654321', 'season': '2026'}})
        self.f.manager.acquire_request.side_effect = mismatched
        response = self.client.get('/api/inspect/live/teams')
        self.assert_safe(response, 503)
        self.assertEqual(runtime.state['data'], {})

    def test_explicit_runtime_hydration_and_validation_failures(self):
        manager = Mock()
        manager.get = AsyncMock()
        manager.validate_league_id.return_value = '222'
        self.f.app.include_router(create_league_runtime_router(manager=manager, import_enabled=True))
        self.assert_safe(self.client.post('/api/leagues/222/runtime'), 403)
        manager.get.assert_not_called()
        for error, status in [(LeagueRuntimeError, 503), (LeagueRuntimeNotFound, 422), (RuntimeError, 503)]:
            manager.get.side_effect = error(SECRET)
            response = self.client.post('/api/leagues/222/runtime', headers={'X-CSRF-Token': self.csrf})
            self.assert_safe(response, status)
            self.assertEqual(response.json(), runtime_error_payload(status))
        manager.validate_league_id.side_effect = LeagueRuntimeNotFound(SECRET)
        self.assert_safe(self.client.get('/api/leagues/222/runtime'), 422)

    def test_cached_runtime_errors_are_safe_for_members_and_unmodified_for_operators(self):
        manager = Mock()
        own = {'league_id': '222', 'status': 'failed', 'last_error': SECRET}
        foreign = {'league_id': '111', 'status': 'failed', 'last_error': SECRET}
        shared = {'runtimes': [own, foreign], 'resident_league_ids': ['111', '222'], 'in_flight': []}
        manager.health.return_value = shared
        manager.validate_league_id.return_value = '222'
        manager.resident.return_value.public_health.return_value = own
        manager.get = AsyncMock(return_value=manager.resident.return_value)
        self.f.app.include_router(create_league_runtime_router(manager=manager, import_enabled=True))
        before = copy.deepcopy(shared)
        for path in ['/api/leagues/runtime', '/api/leagues/222/runtime']:
            self.assert_safe(self.client.get(path), 200)
        self.assert_safe(self.client.post('/api/leagues/222/runtime', headers={'X-CSRF-Token': self.csrf}), 200)
        self.assertEqual(shared, before)
        response = self.client.get('/api/leagues/runtime', headers={'X-DTOS-Inspection-Auth': 'fixture-only-token'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(SECRET, response.text)
        self.assertIn('no-store, private', response.headers['cache-control'])
        own['last_error'] = None
        self.assertIsNone(self.client.get('/api/leagues/222/runtime').json()['last_error'])

    def test_safe_logs_keep_correlation_type_and_locations_without_message_or_credentials(self):
        class NeverStringify(LeagueRuntimeError):
            def __str__(self):
                raise AssertionError('Exception messages must not be inspected')
        self.f.manager.acquire_request.side_effect = NeverStringify(SECRET)
        with self.assertLogs('dtos.request', level='WARNING') as captured:
            response = self.client.get('/api/inspect/live/teams', headers={'X-Request-ID': 'fixture-log-197'})
        self.assert_safe(response, 503)
        record = next(r for r in captured.records if r.getMessage() == 'league_runtime_failure')
        self.assertEqual(record.request_id, 'fixture-log-197')
        self.assertEqual(record.status_code, 503)
        self.assertEqual(record.diagnostic['exception_type'], 'NeverStringify')
        self.assertLessEqual(len(record.diagnostic['frames']), 6)
        self.assertTrue(record.diagnostic['frames'])
        self.assertIsNone(record.exc_info)
        for marker in ['PRIVATE_', '/private/', '987654321', 'Bearer']:
            self.assertNotIn(marker, json.dumps(record.diagnostic) + record.getMessage())

    def test_failure_recovery_and_public_probes_do_not_start_expensive_work(self):
        self.f.manager.acquire_request.side_effect = LeagueRuntimeError(SECRET)
        self.assert_safe(self.client.get('/api/inspect/live/teams'), 503)
        calls = self.f.manager.acquire_request.await_count
        for path in ['/health', '/health/live', '/health/ready', '/api/status', '/health/ready/']:
            response = self.client.get(path)
            self.assertIn(response.status_code, [200, 503])
            self.assertNotIn('PRIVATE_', response.text)
        self.assertEqual(calls, self.f.manager.acquire_request.await_count)
        self.f.manager.acquire_request.side_effect = lambda league, **_kwargs: self.f.runtimes[league]
        response = self.client.get('/api/inspect/live/teams')
        self.assertEqual(response.status_code, 200)
        self.assertIn('PRIVATE_MANAGER_222', response.text)
        self.assertNotIn('PRIVATE_MANAGER_111', response.text)
        self.assertEqual(self.f.manager.release_request.await_count, 1)
        self.f.no_work.assert_not_called()

    def test_auth_denials_still_precede_runtime_failure(self):
        self.f.manager.acquire_request.side_effect = LeagueRuntimeError(SECRET)
        self.client.cookies.clear()
        self.assert_safe(self.client.get('/api/inspect/live/teams'), 401)
        self.client.cookies.set('dtos_session', self.token)
        for path in ['/api/inspect/team/1', '/api/inspect/live/teams?league=111', '/api/leagues/111/runtime']:
            self.assert_safe(self.client.get(path), 403)
        self.f.store.revoke_session(self.token)
        self.assert_safe(self.client.get('/api/inspect/live/teams'), 401)
        self.f.manager.acquire_request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
