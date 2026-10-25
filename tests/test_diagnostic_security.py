"""Protected disposable league facts through the actual account/runtime/router boundaries."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from tools.validation.http_worker import validation_inspection_context
from routes.inspect import create_inspection_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware, current_account
from src.platform.inspection_security import OperationalInspectionBoundary
from src.platform.league_context import LeagueContextMiddleware, RuntimeStateProxy, current_league_context
from src.platform.observability import runtime_metrics
from tests.test_inspection import fixture_state


class DiagnosticSecurityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = AccountStore(Path(folder.name) / 'accounts.sqlite3')
        self.service = AccountService(self.store)
        self.sessions = {}
        self.accounts = {}
        for name, league, roster in [('alice', '111', 1), ('bob', '222', 2), ('peer', '111', 2)]:
            account, _ = self.service.create_account(name, name, 'disposable password only')
            self.store.upsert_membership(account, {'league_id': league, 'name': name, 'season': '2026'},
                                         name, roster, name, 'active')
            self.store.activate(account, league)
            self.sessions[name], _ = self.service.new_session(account)
            self.accounts[name] = account
        self.states = {}
        self.runtimes = {}
        for league in ['111', '222']:
            state = fixture_state()
            state['data']['league']['league_id'] = league
            state['data']['teams'][0].update(owner=f'PRIVATE_MANAGER_{league}', team_name=f'PRIVATE_TEAM_{league}')
            state['data']['pick_ledger'] = [{'canonical_pick_id': f'PRIVATE_PICK_{league}',
                                            'season': '2028', 'round': 1, 'roster_id': 1, 'current_owner_id': 2}]
            state['last_error'] = f'PRIVATE_ERROR_{league} /private/database.sqlite3'
            self.states[league] = state
            self.runtimes[league] = SimpleNamespace(
                canonical_context=SimpleNamespace(state=state, league_id=league, projection=None, market=None),
                touch=Mock())
        self.manager = SimpleNamespace(
            acquire_request=AsyncMock(side_effect=lambda league, **_kwargs: self.runtimes[league]),
            release_request=AsyncMock())
        self.no_work = AsyncMock(side_effect=AssertionError('Expensive work is forbidden'))
        self.operator = patch.dict('os.environ', {'DTOS_INSPECTION_AUTH_TOKEN': 'fixture-only-token',
             'DTOS_INSPECTION_LEAGUE_ID': '111', 'DTOS_INSPECTION_ROSTER_ID': '1'})
        self.operator.start()
        self.addCleanup(self.operator.stop)
        for target in ['routes.inspect.history_progress_contracts', 'src.core.inspection.live.history_progress_contracts']:
            patcher = patch(target, return_value={'canonical_history_progress': {}})
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('routes.inspect.fois_service.repository.league', return_value=())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = self.make_app()
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def make_app(self, required=True):
        app = FastAPI()
        state = RuntimeStateProxy(self.states['111'])
        app.add_middleware(LeagueContextMiddleware, manager=self.manager, default_league_id='111', import_enabled=True)
        app.add_middleware(AccountContextMiddleware, service=self.service, required=required)
        app.add_middleware(OperationalInspectionBoundary)
        app.include_router(create_inspection_router(state=state, context_resolver=current_league_context))
        app.include_router(create_api_router(ensure_fresh=self.no_work, require_data=self.no_work,
            sync_sleeper=self.no_work, state=state, league_id='111', league_resolver=self.no_work))
        for path in ['/', '/league', '/market', '/trades', '/account/my-dtos', '/fois']:
            async def ordinary():
                context = current_account()
                return {'account': context.account_id if context else None}
            app.add_api_route(path, ordinary)
        return app

    def sign_in(self, name):
        self.client.cookies.set('dtos_session', self.sessions[name])

    def assert_private(self, response):
        self.assertIn('no-store', response.headers.get('cache-control', ''))
        self.assertNotIn('PRIVATE_', response.text)
        self.assertNotIn('/private/', response.text)

    def test_all_legacy_handlers_deny_anonymous_before_runtime_or_preparation(self):
        before = copy.deepcopy(self.states)
        routes = [path for path in self.app.openapi()['paths'] if path.startswith('/api/inspect')]
        self.assertGreaterEqual(len(routes), 26)
        for route in routes:
            path = route.replace('{roster_id}', '1').replace('{player_id}', 'p1').replace('{page_id}', 'home')
            path = path.replace('{surface_id}', 'home').replace('{matchup_id}', '1')
            with self.subTest(path=path):
                result = self.client.get(path, follow_redirects=False)
                self.assertEqual(result.status_code, 401)
                self.assert_private(result)
        self.manager.acquire_request.assert_not_called()
        self.no_work.assert_not_called()
        self.assertEqual(before, self.states)

    def test_alternate_paths_methods_and_invalid_credentials_fail_closed(self):
        for path in ['/api/inspect/', '/api/inspect/team/1/', '/api/inspect%2fteam%2f1',
                     '/api/inspect//team/1', '/api/inspect/team/../team/1', '/api/inspect/live/picks',
                     '/api/inspect/operations', '/api/inspect/operations/identity']:
            for method in ['GET', 'HEAD', 'POST', 'OPTIONS', 'DELETE']:
                with self.subTest(path=path, method=method):
                    result = self.client.request(method, path, follow_redirects=False)
                    self.assertEqual(result.status_code, 401)
                    self.assert_private(result)
        for headers in [{'X-DTOS-Inspection-Auth': 'wrong'}, {'Authorization': 'Bearer fixture-only-token'},
                        [('X-DTOS-Inspection-Auth', 'fixture-only-token')] * 2]:
            result = self.client.get('/api/inspect/team/1', headers=headers)
            self.assertEqual(result.status_code, 401)
            self.assert_private(result)

    def test_diagnostics_private_even_with_optional_application_auth(self):
        with TestClient(self.make_app(required=False)) as client:
            result = client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 401)
        self.assert_private(result)

    def test_router_without_account_boundary_also_fails_closed(self):
        app = FastAPI()
        app.include_router(create_inspection_router(state=self.states['111']))
        with TestClient(app) as client:
            result = client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 401)
        self.assert_private(result)

    def test_member_reads_only_authorized_league_and_controlled_franchise(self):
        self.sign_in('alice')
        allowed = self.client.get('/api/inspect/team/1')
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertIn('PRIVATE_MANAGER_111', allowed.text)
        self.assertNotIn('PRIVATE_MANAGER_222', allowed.text)
        self.assertIn('no-store, private', allowed.headers['cache-control'])
        for path in ['/api/inspect/team/2', '/api/inspect/front-office/2',
                     '/api/inspect/team/1?league=222', '/api/inspect/live/teams?league_id=222',
                     '/api/inspect/team/1?league=111&league=222', '/api/inspect/trades?front_office=2']:
            result = self.client.get(path, follow_redirects=False)
            self.assertEqual(result.status_code, 403, (path, result.text))
            self.assert_private(result)
        self.sign_in('peer')
        result = self.client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 403)
        self.assert_private(result)
        self.sign_in('bob')
        result = self.client.get('/api/inspect/live/teams')
        self.assertEqual(result.status_code, 200)
        self.assertIn('PRIVATE_MANAGER_222', result.text)
        self.assertNotIn('PRIVATE_MANAGER_111', result.text)

    def test_existing_operator_credential_remains_scoped_even_with_foreign_session(self):
        self.sign_in('bob')
        headers = {'X-DTOS-Inspection-Auth': 'fixture-only-token'}
        result = self.client.get('/api/inspect/live/teams', headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertIn('PRIVATE_MANAGER_111', result.text)
        self.assertNotIn('PRIVATE_MANAGER_222', result.text)
        self.assertIn('X-DTOS-Inspection-Auth', result.headers['vary'])
        result = self.client.get('/api/inspect/live/teams?league=222', headers=headers)
        self.assertEqual(result.status_code, 403)
        self.assert_private(result)

    def test_revoked_expired_and_unmapped_contexts_do_not_disclose(self):
        self.sign_in('alice')
        self.store.revoke_session(self.sessions['alice'])
        result = self.client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 401)
        self.assert_private(result)
        self.store.create_session(account_id=self.accounts['alice'], token='expired', session_id='expired',
                                  csrf_token='csrf', ttl_hours=-1)
        self.client.cookies.set('dtos_session', 'expired')
        result = self.client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 401)
        self.assert_private(result)
        account, _ = self.service.create_account('unmapped', 'unmapped', 'disposable password')
        token, _ = self.service.new_session(account)
        self.client.cookies.set('dtos_session', token)
        result = self.client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 403)
        self.assert_private(result)

    def test_revoked_membership_is_not_an_active_diagnostic_context(self):
        self.sign_in('alice')
        self.store.upsert_membership(self.accounts['alice'],
            {'league_id': '111', 'name': 'alice', 'season': '2026'}, 'alice', 1, 'alice', 'revoked')
        result = self.client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 403)
        self.assert_private(result)

    def test_internal_exception_is_generic_private_and_context_recovers(self):
        self.sign_in('alice')
        with patch('routes.inspect.InspectionEngine', side_effect=RuntimeError('PRIVATE_ERROR /private/secret')):
            result = self.client.get('/api/inspect/team/1')
        self.assertEqual(result.status_code, 500)
        self.assert_private(result)
        self.assertEqual(result.json(), {'status': 'diagnostic_unavailable'})
        self.assertEqual(self.client.get('/api/inspect/team/1').status_code, 200)
        self.assertEqual(self.manager.acquire_request.await_count, self.manager.release_request.await_count)

    def test_wrong_runtime_fails_without_returning_default_records(self):
        self.sign_in('bob')
        self.manager.acquire_request.side_effect = lambda *_args, **_kwargs: self.runtimes['111']
        result = self.client.get('/api/inspect/live/teams')
        self.assertEqual(result.status_code, 503)
        self.assert_private(result)

    def test_public_probe_allowlists_do_not_resolve_leagues_or_return_internal_errors(self):
        for ready in [False, True]:
            with patch.object(runtime_metrics, 'ready', ready), patch.object(runtime_metrics, 'readiness_reason', 'PRIVATE_RUNTIME_ERROR'):
                for path in ['/health', '/health/live', '/health/ready', '/api/status']:
                    result = self.client.get(path)
                    expected = 200 if ready or path in ['/health/live', '/api/status'] else 503
                    self.assertEqual(result.status_code, expected)
                    self.assert_private(result)
                    self.assertTrue(set(result.json()) <= {'status', 'version', 'build', 'deployment', 'reason'})
        self.manager.acquire_request.assert_not_called()
        self.no_work.assert_not_called()

    def test_rich_health_routes_are_private_in_required_auth_application(self):
        for path in ['/api/platform/health', '/api/data/health', '/api/market/health']:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 401)
            self.assert_private(result)
        self.manager.acquire_request.assert_not_called()

    def test_existing_ordinary_member_navigation_and_operator_boundary_preserved(self):
        self.sign_in('alice')
        for path in ['/', '/league', '/market', '/trades', '/account/my-dtos', '/fois']:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['account'], self.accounts['alice'])
        result = self.client.get('/api/inspect/operations/identity')
        self.assertEqual(result.status_code, 401)
        self.assert_private(result)


class ValidationDiagnosticCredentialTests(unittest.TestCase):
    def test_existing_credential_is_not_overwritten(self):
        values = {'DTOS_INSPECTION_AUTH_TOKEN': 'caller-value', 'DTOS_INSPECTION_LEAGUE_ID': 'caller-league'}
        with patch.dict('os.environ', values):
            import os
            with validation_inspection_context():
                self.assertEqual(os.environ['DTOS_INSPECTION_AUTH_TOKEN'], 'caller-value')
                self.assertEqual(os.environ['DTOS_INSPECTION_LEAGUE_ID'], 'caller-league')

    def test_no_production_credential_is_provisioned(self):
        with patch.dict('os.environ', {'RENDER': 'true', 'DTOS_INSPECTION_AUTH_TOKEN': ''}):
            with self.assertRaisesRegex(RuntimeError, 'Production validation'):
                with validation_inspection_context():
                    self.fail('Must not enter')

    def test_fixture_credential_is_ephemeral_and_restored(self):
        import os
        original = {'RENDER': '', 'DTOS_INSPECTION_AUTH_TOKEN': '',
                    'DTOS_INSPECTION_LEAGUE_ID': 'previous', 'DTOS_INSPECTION_ROSTER_ID': '7'}
        with patch.dict('os.environ', original):
            with validation_inspection_context():
                self.assertGreater(len(os.environ['DTOS_INSPECTION_AUTH_TOKEN']), 20)
                self.assertEqual(os.environ['DTOS_INSPECTION_ROSTER_ID'], '1')
            for key, value in original.items():
                self.assertEqual(os.environ[key], value)
