"""Secured build 2198 boundaries with the actual public-entry opt-in enabled."""
from __future__ import annotations

import copy
import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.api import create_api_router
from routes.inspect import create_inspection_router
from routes.public_entry import create_public_entry_router
from src.core.league_runtime import LeagueRuntimeError, LeagueRuntimeNotFound
from src.platform.account_context import AccountContextMiddleware, current_account
from src.platform.inspection_security import OperationalInspectionBoundary
from src.platform.league_context import LeagueContextMiddleware, RuntimeStateProxy, current_league_context
from src.platform.observability import RequestObservabilityMiddleware
from tests import test_diagnostic_security as fixtures
from unittest.mock import patch


PRIVATE_ERROR = 'PRIVATE_WELCOME_PREFLIGHT /private/league.sqlite3 source-987654321 Bearer FAKE_CREDENTIAL'


class PublicWelcomeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DiagnosticSecurityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.state = self.f.states['222']
        self.state['last_error'] = PRIVATE_ERROR
        self.state['data']['teams'][0]['roster_id'] = 2
        self.app = self.make_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def make_app(self, *, required=True):
        app = FastAPI()
        state = RuntimeStateProxy(self.f.states['111'])
        app.add_middleware(LeagueContextMiddleware, manager=self.f.manager,
                           default_league_id='111', import_enabled=True)
        app.add_middleware(AccountContextMiddleware, service=self.f.service,
                           required=required, public_welcome=True)
        app.add_middleware(OperationalInspectionBoundary)
        app.add_middleware(RequestObservabilityMiddleware)
        app.include_router(create_public_entry_router())
        app.include_router(create_inspection_router(state=state, context_resolver=current_league_context))
        app.include_router(create_api_router(ensure_fresh=self.f.no_work, require_data=self.f.no_work,
                           sync_sleeper=self.f.no_work, state=state, league_id='111'))
        @app.get('/')
        async def private_home():
            context = current_account()
            return {'actor': context.username, 'league': context.membership.league_id,
                    'franchise': context.membership.roster_id}
        return app

    def safe(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        for marker in ('PRIVATE_WELCOME_PREFLIGHT', '/private/league', '987654321', 'FAKE_CREDENTIAL'):
            self.assertNotIn(marker, response.text + json.dumps(dict(response.headers)))
        if response.request.url.path.startswith('/api/inspect'):
            self.assertIn('no-store', response.headers.get('cache-control', ''))
            self.assertIn('private', response.headers.get('cache-control', ''))

    def test_anonymous_welcome_and_all_registered_inspection_remain_separate(self):
        expected = self.client.get('/welcome').content
        for path in self.app.openapi()['paths']:
            if not path.startswith('/api/inspect'):
                continue
            path = path.replace('{roster_id}', '2').replace('{player_id}', 'p1')
            path = path.replace('{page_id}', 'home').replace('{surface_id}', 'home').replace('{matchup_id}', '1')
            with self.subTest(path=path):
                self.safe(self.client.get(path, follow_redirects=False), 401)
        for path in ['/api/inspect/team/2/', '/api/inspect%2fteam%2f2', '/api/inspect//team/2',
                     '/api/inspect/operations/identity', '/api/platform/health', '/api/platform/health/']:
            self.safe(self.client.get(path, follow_redirects=False), 401)
        self.assertEqual(self.client.get('/').content, expected)
        self.f.manager.acquire_request.assert_not_awaited()
        self.f.no_work.assert_not_called()

    def test_member_cached_warning_is_safe_and_last_valid_facts_are_retained(self):
        self.client.cookies.set('dtos_session', self.f.sessions['bob'])
        before = copy.deepcopy(self.f.states)
        for path in ['/api/inspect/team/2', '/api/inspect/trades', '/api/inspect/player/p1',
                     '/api/inspect/front-office/2', '/api/inspect/live/health']:
            response = self.client.get(path, headers={'X-Request-ID':'welcome-security-199'})
            self.safe(response, 200)
            self.assertEqual(response.headers['x-request-id'], 'welcome-security-199')
        response = self.client.get('/api/inspect/team/2')
        self.assertIn('PRIVATE_MANAGER_222', response.text)
        self.assertIn('last successfully loaded', response.text)
        self.assertEqual(response.json()['last_updated'], self.state['last_sync'])
        self.assertEqual(self.f.states, before)
        self.f.no_work.assert_not_called()

    def test_503_422_500_remain_safe_and_welcome_never_acquires_a_failed_runtime(self):
        self.client.cookies.set('dtos_session', self.f.sessions['bob'])
        expected = self.client.get('/welcome').content
        for kind, status in [(LeagueRuntimeError,503),(LeagueRuntimeNotFound,422),(RuntimeError,500)]:
            self.f.manager.acquire_request.side_effect = kind(PRIVATE_ERROR)
            self.safe(self.client.get('/api/inspect/live/teams'), status)
            count = self.f.manager.acquire_request.await_count
            self.assertEqual(self.client.get('/welcome').content, expected)
            self.assertEqual(count, self.f.manager.acquire_request.await_count)
        self.f.no_work.assert_not_called()

    def test_member_foreign_franchise_revoked_and_csrf_boundaries_survive(self):
        self.client.cookies.set('dtos_session', self.f.sessions['bob'])
        for path in ['/api/inspect/team/1', '/api/inspect/team/2?league=111', '/api/inspect/trades?front_office=1']:
            self.safe(self.client.get(path),403)
        response = self.client.get('/')
        self.assertEqual(response.json(), {'actor':'bob','league':'222','franchise':2})
        self.assertEqual(response.headers['cache-control'],'no-store, private')
        self.assertEqual(self.client.post('/sync').status_code,403)
        self.f.store.revoke_session(self.f.sessions['bob'])
        self.safe(self.client.get('/api/inspect/team/2'),401)
        self.assertEqual(self.client.get('/',follow_redirects=False).headers['location'],'/welcome')
        self.f.no_work.assert_not_called()

    def test_operator_error_observation_is_strictly_privileged_not_public_demo_data(self):
        # Privileged access remains, but operational responses also withhold raw errors.
        marker='OPERATOR_ONLY_PREFLIGHT /private/operator.sqlite3 FAKE_OPERATOR_CREDENTIAL'
        expected = self.client.get('/welcome').content
        with patch('routes.api.intelligence_orchestrator.last_error',marker):
            for required in [True,False]:
                with TestClient(self.make_app(required=required)) as client:
                    for path in ['/api/platform/health','/api/platform/health/', '/api/platform%2fhealth?inspection=true']:
                        anonymous=client.get(path,follow_redirects=False)
                        self.assertEqual(anonymous.status_code,401)
                        self.assertNotIn(marker,anonymous.text)
                    client.cookies.set('dtos_session',self.f.sessions['bob'])
                    member=client.get('/api/platform/health')
                    self.assertEqual(member.status_code,403)
                    self.assertNotIn(marker,member.text)
                    self.assertIn('no-store, private',member.headers['cache-control'])
                    operator=client.get('/api/platform/health',headers={'X-DTOS-Inspection-Auth':'fixture-only-token'})
                    self.assertEqual(operator.status_code,200)
                    for private in (marker, '/private/operator.sqlite3', 'FAKE_OPERATOR_CREDENTIAL'):
                        self.assertNotIn(private, operator.text)
                    self.assertEqual(operator.json()['orchestration']['error_code'], 'orchestration_failed')
                    self.assertIn('no-store, private',operator.headers['cache-control'])
                    self.assertEqual(client.get('/welcome').content,expected)
                    self.assertNotIn(marker,client.get('/api/status').text)
        self.f.no_work.assert_not_called()

    def test_public_health_allowlists_stay_minimal_and_source_independent(self):
        for path, keys in [('/health/live',{'status','version'}),
                           ('/health',{'status','version','build','deployment'}),
                           ('/health/ready',{'status','version','build','deployment','reason'}),
                           ('/api/status',{'status','version','build','deployment'})]:
            response=self.client.get(path)
            self.assertIn(response.status_code,(200,503))
            self.assertEqual(set(response.json()),keys)
            self.assertNotIn(PRIVATE_ERROR,response.text)
        self.f.manager.acquire_request.assert_not_awaited()
        self.f.no_work.assert_not_called()


if __name__ == '__main__':
    unittest.main()
