"""Authenticated identity remains distinct from a changing evidence generation."""
import copy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.trades import create_trades_router
from services import trade_intelligence as trade
from src.core.accounts import AccountService
from src.core.league_runtime import LeagueRuntimeManager
from src.platform.account_context import AccountContextMiddleware, current_account
from src.platform.league_context import LeagueContextMiddleware, current_league_context
from tests import test_trade_discovery_repair as discovery
from tests import test_trade_workspace_batch1 as boundary


class TradeNavigationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = discovery.DiscoveryRepairTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.account = boundary.AuthenticatedTradeBoundaryTests()
        self.account.setUp()
        self.addCleanup(self.account.doCleanups)
        self.account.data.clear()
        self.account.data.update(self.fixture.data)

    def test_real_evidence_publication_rejects_mixed_search_not_authenticated_identity(self):
        context = self.account.client.get('/api/trades/workspace').json()['workspace_context']
        original = trade.evaluate_trade_request
        published = False

        def evaluate(data, payload, **kwargs):
            nonlocal published
            result = original(data, payload, **kwargs)
            if not published:
                data['market_data']['generation'] = 'publication-during-search'
                published = True
            return result

        payload = dict(workflow='trade_for', active_roster_id=1, partner_roster_id=2,
                       asset_id='2w', strategy='RETOOL', workspace_context=context)
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=evaluate):
            response = self.account.client.post('/api/trades/generate', json=payload,
                                               headers={'X-CSRF-Token': self.account.csrf})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail']['code'], 'canonical_evidence_changed')
        self.assertNotIn('results', response.json())
        self.assertEqual(context, self.account.client.get('/api/trades/workspace').json()['workspace_context'])
        response = self.account.client.post('/api/trades/generate', json=payload,
                                           headers={'X-CSRF-Token': self.account.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['count'], 3)
        self.assertTrue(all(row['proposal']['partner_roster_id'] == 2 for row in response.json()['results']))

    def test_every_generation_guard_preserves_discard_policy_and_distinct_error(self):
        payload = self.fixture.proposal(sent=['1q', '1qb'], instruction='make it cheaper')
        for operation, request in (
            (trade.generate_trade_workflow, dict(payload, workflow='trade_for', asset_id='2w')),
            (trade.generate_trade_workflow, dict(payload, workflow='recommended', partner_roster_id=0)),
            (trade.assist_trade_request, payload),
            (trade.create_trade_alternatives, payload),
            (trade.compare_trade_requests, [payload, dict(payload, assets_sent=['1q'])]),
        ):
            with self.subTest(operation=operation.__name__), patch(
                'services.trade_intelligence._trade_search_boundary', side_effect=['before', 'after']
            ), self.assertRaises(trade.TradeInputError) as caught:
                operation(self.account.data, request)
            self.assertEqual(caught.exception.code, 'canonical_evidence_changed')

    def test_real_account_league_session_and_franchise_isolation_with_colliding_ids(self):
        store = self.account.store
        service = AccountService(store)
        other_id, _ = service.create_account('other-manager', 'Same name', 'fixture-only password')
        for account_id, leagues in ((self.account.account_id, ('100', '200')),
                                   (other_id, ('300',))):
            for league in leagues:
                store.upsert_membership(account_id, {'league_id': league, 'name': 'Same league'},
                                        'fixture-user', 1, 'Same franchise', 'active')
            store.activate(account_id, leagues[0])
        other_token, other_csrf = service.new_session(other_id)
        manager = LeagueRuntimeManager(max_warm=3, hydrator=None)
        for league in ('100', '200', '300'):
            data = copy.deepcopy(self.account.data)
            data['league']['league_id'] = league
            data['teams'][1]['team_name'] = 'Private counterparty ' + league
            runtime = manager.attach_default(league, {'data': data}, warm=True)
            runtime.canonical_context = SimpleNamespace(league_id=league, data=data,
                projection=self.fixture.fixture.reader, runtime=runtime)
        app = FastAPI()
        app.add_middleware(LeagueContextMiddleware, manager=manager, default_league_id='100', import_enabled=False)
        app.add_middleware(AccountContextMiddleware, service=service, required=True)

        async def fresh():
            pass

        app.include_router(create_trades_router(ensure_fresh=fresh,
            require_data=lambda: current_league_context().data, page=lambda title, body: body))
        first = TestClient(app)
        first.cookies.update(self.account.client.cookies)
        second = TestClient(app)
        second.cookies.set('dtos_session', other_token)
        clients = [first, second]
        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(lambda n: clients[n % 2].get(
                '/api/trades/workspace?league=200&front_office=2').json(), range(8)))
        for n, response in enumerate(responses):
            league = '100' if n % 2 == 0 else '300'
            self.assertEqual(response['workspace_context']['league_id'], league)
            self.assertEqual(response['active_front_office'], 1)
            self.assertEqual(response['teams'][1]['team_name'], 'Private counterparty ' + league)
        old = responses[0]['workspace_context']
        request = dict(self.account.payload, workspace_context=old)
        with patch('routes.trades.evaluate_trade_request') as engine:
            for client, csrf, expected in ((second, other_csrf, 'workspace_context_changed'),
                                          (first, other_csrf, 'csrf_rejected')):
                response = client.post('/api/trades/evaluate', json=request, headers={'X-CSRF-Token': csrf})
                self.assertIn(expected, response.text)
                self.assertNotIn('Private counterparty', response.text)
            response = first.post('/api/trades/evaluate', json=dict(request, active_roster_id=2),
                                  headers={'X-CSRF-Token': self.account.csrf})
            self.assertIn('unauthorized_franchise', response.text)
            store.activate(self.account.account_id, '200')
            response = first.post('/api/trades/evaluate', json=request,
                                  headers={'X-CSRF-Token': self.account.csrf})
            self.assertIn('workspace_context_changed', response.text)
            engine.assert_not_called()
        current = first.get('/api/trades/workspace').json()
        self.assertEqual(current['workspace_context']['league_id'], '200')
        self.assertEqual(current['teams'][1]['team_name'], 'Private counterparty 200')
        def approved_context(data, payload):
            return {'league': current_league_context().league_id,
                    'account': current_account().account_id,
                    'franchise': payload['active_roster_id']}

        with patch('routes.trades.evaluate_trade_request', side_effect=approved_context):
            response = first.post('/api/trades/evaluate',
                json=dict(request, workspace_context=current['workspace_context']),
                headers={'X-CSRF-Token': self.account.csrf})
        self.assertEqual(response.json(), {'league': '200', 'account': self.account.account_id, 'franchise': 1})
        store.activate(self.account.account_id, '100')
        self.assertEqual(first.get('/api/trades/workspace').json()['workspace_context'], old)
        # Account/session binding also isolates otherwise identical league and
        # roster contexts, rather than relying only on differing league IDs.
        store.upsert_membership(other_id, {'league_id': '100', 'name': 'Same league'},
                                'fixture-user', 1, 'Same franchise', 'active')
        store.activate(other_id, '100')
        same_account_token, same_account_csrf = service.new_session(self.account.account_id)
        isolated = TestClient(app)
        isolated.cookies.set('dtos_session', same_account_token)
        for client, csrf in ((second, other_csrf), (isolated, same_account_csrf)):
            current = client.get('/api/trades/workspace').json()['workspace_context']
            self.assertEqual((current['league_id'], current['roster_id']), ('100', 1))
            self.assertNotEqual(current['binding'], old['binding'])
            with patch('routes.trades.evaluate_trade_request') as engine:
                response = client.post('/api/trades/evaluate', json=request, headers={'X-CSRF-Token': csrf})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['detail']['code'], 'workspace_context_changed')
                engine.assert_not_called()
