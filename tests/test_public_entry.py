"""Actual HTTP/middleware controls over disposable accounts and frozen public bytes."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.accounts import create_accounts_router
from routes.public_entry import create_public_entry_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware, current_account
from src.platform.league_context import LeagueContextMiddleware, _source_independent


class PublicEntryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = AccountStore(Path(self.folder.name) / 'accounts.sqlite3')
        self.service = AccountService(self.store)
        self.manager = SimpleNamespace(acquire_request=AsyncMock(return_value=None),
                                       release_request=AsyncMock(), get=AsyncMock())
        self.app = FastAPI()
        self.app.add_middleware(LeagueContextMiddleware, manager=self.manager,
                                default_league_id='demo-default', import_enabled=True)
        self.app.add_middleware(AccountContextMiddleware, service=self.service,
                                required=True, public_welcome=True)
        self.app.include_router(create_public_entry_router())
        self.app.include_router(create_accounts_router(service=self.service,
                                                      runtime_manager=self.manager))

        @self.app.get('/')
        async def authenticated_home():
            account = current_account()
            return {'actor': account.username, 'league': account.membership.league_id,
                    'franchise': account.membership.roster_id}

        @self.app.get('/teams/{roster}')
        async def private_team(roster: int):
            return {'roster': roster}

        @self.app.get('/api/trades/workspace')
        async def private_workspace():
            return {'private': True}

        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def account(self, username, league='100', roster=1, *, mapped=True):
        identity, _ = self.service.create_account(username, username, 'disposable audit password')
        if mapped:
            self.store.upsert_membership(identity, {'league_id': league, 'name': 'Private League',
                                        'season': '2026'}, username, roster, 'Private Franchise', 'active')
            self.store.activate(identity, league)
        token, csrf = self.service.new_session(identity)
        return identity, token, csrf

    def snapshot(self):
        with sqlite3.connect(Path(self.folder.name) / 'accounts.sqlite3') as connection:
            return tuple(connection.iterdump())

    def test_anonymous_root_only_changes_the_get_head_destination(self):
        for method in ('get', 'head'):
            response = getattr(self.client, method)('/?league=foreign', follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers['location'], '/welcome')
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(response.headers['vary'], 'Cookie')
        self.manager.acquire_request.assert_not_awaited()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.url.path, '/welcome')
        response = self.client.post('/', follow_redirects=False)
        self.assertEqual(response.headers['location'], '/account/sign-in?next=/')

    def test_public_gets_are_source_independent_without_disk_or_runtime_reads(self):
        before = self.snapshot()
        with patch.object(self.manager, 'acquire_request', side_effect=AssertionError('runtime work')), \
             patch('sqlite3.connect', side_effect=AssertionError('anonymous DB work')), \
             patch.object(Path, 'read_text', side_effect=AssertionError('request-time fixture read')):
            content = self.client.get('/welcome').content
            for _ in range(5):
                for query in ('', '?league=foreign&league_id=other&front_office=999',
                              '?asset_id=private-player&inspection=true&mode=custom&revision=9'):
                    response = self.client.get('/welcome' + query)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content, content)
        self.assertEqual(self.snapshot(), before)
        self.manager.get.assert_not_awaited()
        self.assertNotIn(b'<script', content)
        self.assertNotIn(b'<form', content)
        self.assertNotIn(b'/api/', content)

    def test_opted_in_root_is_public_in_auth_optional_development(self):
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=self.service,
                           required=False, public_welcome=True)
        app.include_router(create_public_entry_router())
        with TestClient(app) as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.url.path, '/welcome')

    def test_exact_paths_head_methods_and_public_security_headers(self):
        for path in ('/welcome', '/welcome/'):
            self.assertTrue(_source_independent(path))
        for path in ('/welcome-private', '/welcome/anything', '/WELCOME'):
            self.assertFalse(_source_independent(path))
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('Explore the demo', response.text)
        self.manager.acquire_request.reset_mock()
        redirected = self.client.get('/welcome/', follow_redirects=False)
        self.assertEqual((redirected.status_code, redirected.headers['location']), (303, '/welcome'))
        get = self.client.get('/welcome')
        head = self.client.head('/welcome')
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertEqual(head.headers['content-length'], get.headers['content-length'])
        self.assertEqual(get.headers['cache-control'], 'no-store')
        self.assertNotIn('set-cookie', get.headers)
        self.assertIn("default-src 'none'", get.headers['content-security-policy'])
        for method in ('post', 'put', 'delete'):
            self.assertEqual(getattr(self.client, method)('/welcome').status_code, 405)
        self.manager.acquire_request.assert_not_awaited()

    def test_public_openapi_has_one_unique_documented_operation(self):
        document = self.app.openapi()
        self.assertEqual(set(document['paths']['/welcome']), {'get'})
        operations = [operation['operationId'] for path in document['paths'].values()
                      for operation in path.values() if isinstance(operation, dict)
                      and 'operationId' in operation]
        self.assertEqual(len(operations), len(set(operations)))

    def test_authenticated_home_onboarding_revocation_and_private_boundaries(self):
        _, token, _ = self.account('private-manager', roster=7)
        self.client.cookies.set('dtos_session', token)
        response = self.client.get('/')
        self.assertEqual(response.json(), {'actor': 'private-manager', 'league': '100', 'franchise': 7})
        self.assertEqual(response.headers['cache-control'], 'no-store, private')
        self.assertEqual(response.headers['vary'], 'Cookie')
        self.assertEqual(self.client.get('/api/fois/leagues/foreign').status_code, 403)
        self.assertEqual(self.client.post('/welcome').status_code, 403)
        self.store.revoke_session(token)
        self.assertEqual(self.client.get('/', follow_redirects=False).headers['location'], '/welcome')
        self.assertEqual(self.client.get('/api/trades/workspace').status_code, 401)
        self.assertEqual(self.client.get('/teams/1', follow_redirects=False).headers['location'],
                         '/account/sign-in?next=/teams/1')
        _, unlinked, _ = self.account('not-mapped', mapped=False)
        self.client.cookies.set('dtos_session', unlinked)
        self.assertEqual(self.client.get('/', follow_redirects=False).headers['location'], '/account/leagues')
        self.assertEqual(self.client.get('/api/trades/workspace').status_code, 403)
        self.assertIsNotNone(self.store.account_by_username('private-manager'))

    def test_public_bytes_do_not_vary_by_account_preferences_or_private_scope(self):
        baseline = self.client.get('/welcome').content
        for username, league, roster in [('first-manager', '100', 7), ('second-manager', '200', 9)]:
            _, token, _ = self.account(username, league, roster)
            self.client.cookies.set('dtos_session', token)
            before = self.snapshot()
            with patch.object(self.manager, 'acquire_request', side_effect=AssertionError('hydration')):
                response = self.client.get('/welcome?league=foreign&front_office=12')
            self.assertEqual(response.content, baseline)
            self.assertEqual(self.snapshot(), before)
            self.assertNotIn(username.encode(), response.content)
            self.assertNotIn(b'Private League', response.content)
            self.assertNotIn(token.encode(), response.content)
        self.assertLessEqual(len(baseline), 65536)

    def test_existing_account_destinations_remain_available_without_submission(self):
        for path in ('/account/sign-in', '/account/create', '/account/recover'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['cache-control'])
