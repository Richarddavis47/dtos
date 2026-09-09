"""Real router + account middleware proof; no provider calls or auth exemptions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.league_runtime import create_league_runtime_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import (
    AccountContextMiddleware, STATIC_LEAGUE_API_PATHS, current_account,
    league_path_identity,
)
from validation.routes import discover_http_endpoints, validate_routes


class ReservedLeagueRouteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.folder.name) / 'accounts.sqlite3')
        self.service = AccountService(self.store)
        self.sessions = []
        for username, league, roster in [('alpha', '100', 1), ('beta', '200', 7)]:
            account, _ = self.service.create_account(username, username, 'a secure test password')
            self.store.upsert_membership(account, {'league_id': league, 'season': '2026', 'name': username},
                                         username, roster, username, 'active')
            self.store.activate(account, league)
            token, csrf = self.service.new_session(account)
            self.sessions.append((account, token, csrf))
        self.manager = Mock()
        self.manager.validate_league_id.side_effect = lambda value: value
        self.manager.resident.return_value = None
        self.manager.health.return_value = {'status': 'healthy'}
        self.measure = Mock(return_value={'measured': True})

        def scoped_health():
            context = current_account()
            return {'account': context.account_id, 'league': context.membership.league_id,
                    'roster': context.membership.roster_id}

        self.app = FastAPI()
        self.app.include_router(create_league_runtime_router(manager=self.manager,
            resource_health=scoped_health, resource_measurement=self.measure))
        self.app.add_middleware(AccountContextMiddleware, service=self.service, required=True)

    def tearDown(self):
        self.folder.cleanup()

    def client(self, index=None):
        client = TestClient(self.app)
        if index is not None:
            client.cookies.set('dtos_session', self.sessions[index][1])
        return client

    def test_authenticated_static_handlers_and_scope(self):
        for index, league, roster in [(0, '100', 1), (1, '200', 7), (0, '100', 1)]:
            with self.client(index) as client:
                response = client.get('/api/leagues/resources?league_id=999&front_office=99')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'account': self.sessions[index][0], 'league': league, 'roster': roster})
                self.assertIn('no-store', response.headers['cache-control'])
                self.assertEqual(client.get('/api/leagues/runtime').json(), {'status': 'healthy'})
        self.manager.validate_league_id.assert_not_called()

    def test_anonymous_stays_unauthorized(self):
        with self.client() as client:
            for path in STATIC_LEAGUE_API_PATHS | {'/api/leagues/100/runtime'}:
                method = 'POST' if path.endswith('/measure') else 'GET'
                response = client.request(method, path)
                self.assertEqual(response.status_code, 401, path)
                self.assertEqual(response.json()['status'], 'authentication_required')
        self.measure.assert_not_called()

    def test_active_membership_still_required(self):
        account, _ = self.service.create_account('empty', 'Empty', 'a secure test password')
        token, _ = self.service.new_session(account)
        with self.client() as client:
            client.cookies.set('dtos_session', token)
            response = client.get('/api/leagues/resources')
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['status'], 'active_league_required')

    def test_dynamic_membership_isolation(self):
        for index, own, other in [(0, '100', '200'), (1, '200', '100')]:
            with self.client(index) as client:
                response = client.get(f'/api/leagues/{own}/runtime')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['league_id'], own)
                for league in [other, '999', 'resources', 'runtime', 'arbitrary']:
                    response = client.get(f'/api/leagues/{league}/runtime')
                    self.assertEqual(response.status_code, 403, league)
                    self.assertEqual(response.json()['status'], 'unauthorized_league')

    def test_measurement_keeps_csrf_and_method_contract(self):
        with self.client(0) as client:
            self.assertEqual(client.post('/api/leagues/resources/measure').status_code, 403)
            self.measure.assert_not_called()
            response = client.post('/api/leagues/resources/measure', headers={'X-CSRF-Token': self.sessions[0][2]})
            self.assertEqual(response.status_code, 200)
            self.measure.assert_called_once()
            self.assertEqual(client.get('/api/leagues/resources/measure').status_code, 405)
            self.assertEqual(client.post('/api/leagues/200/runtime', headers={'X-CSRF-Token': self.sessions[0][2]}).status_code, 403)

    def test_exact_paths_only_and_trailing_slash(self):
        for path in STATIC_LEAGUE_API_PATHS:
            self.assertIsNone(league_path_identity(path))
            self.assertIsNone(league_path_identity(path + '/'))
        for path in ['/api/leagues/resources/private', '/api/leagues/runtime/100',
                     '/api/leagues/resources//', '/api/fois/leagues/resources/health',
                     '/league/resources', '/api/leagues/arbitrary']:
            self.assertIsNotNone(league_path_identity(path), path)
            with self.client(0) as client:
                self.assertEqual(client.get(path).status_code, 403, path)
        with self.client(0) as client:
            self.assertEqual(client.get('/api/leagues/resources/').status_code, 200)

    def test_static_registry_matches_actual_router_and_openapi(self):
        endpoints = discover_http_endpoints(self.app.routes)
        static = {item.path for item in endpoints if item.path.startswith('/api/leagues/') and '{' not in item.path}
        self.assertEqual(static, STATIC_LEAGUE_API_PATHS)
        validate_routes(self.app.routes).require_valid()
        paths = self.app.openapi()['paths']
        self.assertEqual(set(paths), static | {'/api/leagues/{league_id}/runtime'})
        self.assertEqual(set(paths['/api/leagues/resources/measure']), {'post'})


if __name__ == '__main__':
    unittest.main()
