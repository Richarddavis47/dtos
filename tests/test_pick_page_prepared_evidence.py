"""The Picks page reads prepared evidence, not full trade orchestration."""
from datetime import datetime, timezone
import unittest
import tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.draft import create_draft_router
from src.core.valuation.config import NORMALIZATION_VERSION


class PickPagePreparedEvidenceTests(unittest.TestCase):
    def data(self):
        quote = dict(provider='FantasyCalc', market_format='fc:12:2qb:ppr',
                     availability='current', value=100, confidence=85,
                     retrieved_at=datetime.now(timezone.utc).isoformat(), source_updated_at=None,
                     year=2027, round=1, pick_type='generic_round', value_scale='fc_native',
                     normalization_reference=dict(provider='FantasyCalc', raw_value=100.0,
                         normalized_value=414, version=NORMALIZATION_VERSION,
                         generation='prepared-1', method='provider_range_linear'))
        pick = dict(season='2027', round=1, roster_id=1, owner_id=2)
        return dict(league={'league_id': 'A'}, teams=[
            {'roster_id': 1, 'team_name': 'Original'}, {'roster_id': 2, 'team_name': 'Owner'}],
            traded_picks=[pick], pick_ledger=[{**pick, 'year': 2027, 'league_id': 'A',
                'original_roster_id': 1, 'current_owner_id': 2}],
            market_data={'pick_quotes': {'FantasyCalc': [quote]}})

    def render(self, data):
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_draft_router(ensure_fresh=fresh, require_data=lambda: data,
                                               page=lambda title, body: HTMLResponse(body)))
        with patch('services.asset_intelligence.intelligence_orchestrator.analyze',
                   side_effect=AssertionError('Picks must not run full orchestration')):
            with TestClient(app) as client:
                response = client.get('/picks')
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_prepared_price_identity_and_unknown_range(self):
        html = self.render(self.data())
        self.assertIn('Market price: 414', html)
        self.assertIn('FantasyCalc', html)
        self.assertIn('generic_round', html)
        self.assertIn('Projected range: UNKNOWN', html)
        self.assertIn('Exact slot: Unavailable', html)
        self.assertIn('href="/teams/1">Original', html)
        self.assertIn('href="/teams/2">Owner', html)
        self.assertNotIn('Dynasty Value', html)
        self.assertNotIn('/100', html)

    def test_missing_price_is_not_internal_score_or_zero(self):
        data = self.data()
        data['market_data'] = {}
        html = self.render(data)
        self.assertIn('Market price: Unavailable', html)
        self.assertNotIn('Market price: 0', html)

    def test_foreign_prepared_owner_cannot_override_active_ledger(self):
        data = self.data()
        data['pick_ledger'][0].update(league_id='B', current_owner_id=1)
        html = self.render(data)
        self.assertIn('Current owner</span><a href="/teams/2">Owner', html)

    def test_source_supported_zero_price_stays_zero(self):
        data = self.data()
        data['market_data']['pick_quotes']['FantasyCalc'][0]['normalization_reference']['normalized_value'] = 0
        self.assertIn('Market price: 0', self.render(data))

    def test_authenticated_runtime_round_trip_restores_prepared_page(self):
        from routes.accounts import create_accounts_router
        from src.core.accounts import AccountService, AccountStore
        from src.core.league_runtime import LeagueRuntimeManager, CanonicalLeagueContext
        from src.platform.account_context import AccountContextMiddleware
        from src.platform.league_context import LeagueContextMiddleware, current_league_context

        first = self.data()
        first['league']['league_id'] = '100'
        first['pick_ledger'][0]['league_id'] = '100'
        second = deepcopy(first)
        second['league']['league_id'] = '200'
        second['pick_ledger'][0].update(league_id='200', current_owner_id=1)
        second['teams'][0]['team_name'] = 'Other original'
        second['market_data'] = {}
        data_by_league = {'100': first, '200': second}

        async def hydrate(runtime):
            runtime.canonical_context = CanonicalLeagueContext(runtime, None, None, None, None)
            return deepcopy(data_by_league[runtime.league_id])
        async def fresh():
            pass
        manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
        with tempfile.TemporaryDirectory() as folder:
            service = AccountService(AccountStore(Path(folder) / 'accounts.sqlite3'))
            account, _ = service.create_account('parity', 'Parity', 'test-only secure password')
            for league in data_by_league:
                service.store.upsert_membership(account, {'league_id': league, 'season': '2026', 'name': league},
                                                'test-user', 1, league, 'active')
            service.store.activate(account, '100')
            token, csrf = service.new_session(account)
            app = FastAPI()
            app.include_router(create_accounts_router(service=service, runtime_manager=manager))
            app.include_router(create_draft_router(ensure_fresh=fresh,
                require_data=lambda: current_league_context().state['data'],
                page=lambda title, body: HTMLResponse(body)))
            app.add_middleware(LeagueContextMiddleware, manager=manager, default_league_id='999', import_enabled=True)
            app.add_middleware(AccountContextMiddleware, service=service, required=True)
            with TestClient(app) as client:
                client.cookies.set('dtos_session', token)
                pages = []
                for league in ['100', '200', '100']:
                    response = client.post('/api/account/active-league', json={'league_id': league},
                                           headers={'X-CSRF-Token': csrf})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()['active_league']['league_id'], league)
                    page = client.get('/picks')
                    self.assertEqual(page.status_code, 200)
                    pages.append(page.text)
                self.assertEqual(pages[0], pages[2])
                self.assertNotEqual(pages[0], pages[1])
                self.assertIn('Market price: 414', pages[0])
                self.assertIn('Market price: Unavailable', pages[1])
                self.assertIn('Other original', pages[1])
                self.assertNotIn('Other original', pages[2])
