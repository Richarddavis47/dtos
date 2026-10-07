"""Ownership/action contracts across manager boundaries; prices are independent."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from components.asset_intelligence import player_dossier
from routes.api import create_api_router
from routes.market import create_market_router
from routes.transactions import create_transactions_router
from routes.trades import create_trades_router
from services.asset_intelligence import build_player_dossier
from services.trade_intelligence import generate_trade_workflow, validate_targeted_player_action, TradeInputError
from src.core.asset_market import AssetMarketCache
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from src.core.historical_memory.store import HistoricalStore
from src.core.player_ownership import PlayerOwnershipIndex
from src.core.valuation.calibration import cached_market_facts
from tests.test_canonical_asset_facts import facts_fixture
from tests.test_market_render_cache import _Cache


async def fresh(*args, **kwargs):
    pass


def player_app(data, page=lambda title, body: HTMLResponse(body)):
    app = FastAPI()
    app.include_router(create_transactions_router(ensure_fresh=fresh, require_data=lambda: data,
        refresh_transactions=fresh, state={}, page=page))
    app.include_router(create_trades_router(ensure_fresh=fresh, require_data=lambda: data, page=page))
    app.include_router(create_market_router(require_data=lambda: data, state={'data': data}, league_id='league-1', page=page))
    app.include_router(create_api_router(ensure_fresh=fresh, require_data=lambda: data,
        sync_sleeper=fresh, state={'data': data}, league_id='league-1'))
    return app


class PlayerActionTests(unittest.TestCase):
    def setUp(self):
        self.data = facts_fixture()
        self.warehouse = patch.object(data_platform, 'warehouse', SnapshotWarehouse())
        self.warehouse.start()
        self.addCleanup(self.warehouse.stop)

    def test_free_agent_market_value_and_no_dossier_trade_actions(self):
        report, team, teams = build_player_dossier(self.data, 'free', 1)
        html = player_dossier(report, team, teams, ownership=PlayerOwnershipIndex(self.data).resolve('free', 1))
        self.assertIsNotNone(report.market_fact.value)
        self.assertIn('Free Agent', html)
        self.assertNotIn('/trades/trade-for?', html)
        self.assertNotIn('/trades/shop?', html)
        self.assertNotIn('href=""', html)

    def test_my_player_shop_and_other_player_trade_for(self):
        for pid, expected, owner in (('1-QB-0', 'shop', 1), ('10225', 'trade-for', 2)):
            report, team, teams = build_player_dossier(self.data, pid, 1)
            ownership = PlayerOwnershipIndex(self.data).resolve(pid, 1)
            html = player_dossier(report, team, teams, ownership=ownership)
            self.assertIn(f'/trades/{expected}?', html)
            self.assertIn(f'owner_roster_id={owner}', html)
            self.assertEqual(ownership['actions'], ['VIEW_PLAYER', 'SHOP_ASSET' if owner == 1 else 'TRADE_FOR'])
            self.assertNotIn('/trades/trade-for?' if owner == 1 else '/trades/shop?', html)

    def test_incomplete_conflicting_and_unresolved_are_unknown(self):
        cases = []
        data = deepcopy(self.data)
        del data['teams'][0]['players']
        cases.append(data)
        data = deepcopy(self.data)
        data['league']['total_rosters'] = 10
        cases.append(data)
        data = deepcopy(self.data)
        data['teams'][0]['players'].append(next(p for p in data['teams'][1]['players'] if p['id'] == '10225'))
        cases.append(data)
        for data in cases:
            state = PlayerOwnershipIndex(data).resolve('10225', 1)
            self.assertEqual(state['state'], 'UNKNOWN')
            self.assertEqual(state['actions'], ['VIEW_PLAYER'])
            self.assertIsNone(state['owner'])
            self.assertIn('Ownership unavailable', state['label'])
            with self.assertRaises(TradeInputError):
                validate_targeted_player_action(data, '10225', 1, 'trade_for')
        self.assertEqual(PlayerOwnershipIndex(self.data).resolve('unresolved', 1)['state'], 'UNKNOWN')
        self.assertEqual(PlayerOwnershipIndex({'teams': []}).resolve('free', 1)['state'], 'UNKNOWN')
        self.assertEqual(PlayerOwnershipIndex(self.data).resolve('10225', 999)['actions'], ['VIEW_PLAYER'])

    def test_ownership_transitions_and_strategy_preserve_entire_market_fact(self):
        original = cached_market_facts(self.data['market_data'], ['10225'])['10225'].to_dict()
        old = PlayerOwnershipIndex(self.data).resolve('10225', 1)
        player = next(p for p in self.data['teams'][1]['players'] if p['id'] == '10225')
        self.data['teams'][1]['players'].remove(player)
        free = PlayerOwnershipIndex(self.data).resolve('10225', 1)
        self.assertEqual(free['state'], 'FREE_AGENT')
        self.assertNotEqual(old['generation'], free['generation'])
        for team_index, state, action in ((2, 'OWNED_BY_OTHER', 'TRADE_FOR'), (0, 'OWNED_BY_ME', 'SHOP_ASSET')):
            self.data['teams'][team_index]['players'].append(player)
            owned = PlayerOwnershipIndex(self.data).resolve('10225', 1)
            self.assertEqual(owned['state'], state)
            self.assertIn(action, owned['actions'])
            self.assertNotEqual(owned['generation'], free['generation'])
            self.data['teams'][team_index]['strategy'] = 'Rebuild'
            self.assertEqual(cached_market_facts(self.data['market_data'], ['10225'])['10225'].to_dict(), original)
            self.data['teams'][team_index]['players'].remove(player)
        self.assertEqual(cached_market_facts(self.data['market_data'], ['10225'])['10225'].to_dict(), original)

    def test_targeted_links_and_api_reject_free_agent_before_search(self):
        with TestClient(player_app(self.data)) as client, patch('services.trade_intelligence.build_trade_workspace') as workspace:
            for route in ('trade-for', 'shop'):
                response = client.get(f'/trades/{route}?front_office=1&asset_id=free&owner_roster_id=2')
                self.assertEqual(response.status_code, 422)
                self.assertIn('Free Agent', response.text)
                self.assertNotIn('id="trade-builder"', response.text)
            response = client.post('/api/trades/generate', json={'workflow':'trade_for', 'active_roster_id':1, 'asset_id':'free'})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()['detail']['code'], 'player_action_unavailable')
            self.assertIn('Free Agent', response.json()['detail']['message'])
            workspace.assert_not_called()

    def test_valid_deep_link_uses_actual_owner_and_my_player_rejected(self):
        with TestClient(player_app(self.data)) as client:
            response = client.get('/trades/trade-for?front_office=1&asset_id=10225&owner_roster_id=999')
            self.assertEqual(response.status_code, 200)
            self.assertIn('data-owner-roster="2"', response.text)
            self.assertEqual(client.get('/trades/shop?front_office=1&asset_id=1-QB-0').status_code, 200)
            self.assertEqual(client.get('/trades/trade-for?front_office=1&asset_id=1-QB-0').status_code, 422)
            self.assertEqual(client.get('/trades/shop?front_office=1&asset_id=10225').status_code, 422)
            self.assertEqual(client.get('/trades/create?front_office=1').status_code, 200)

    def test_pick_boundary_is_not_player_free_agency(self):
        self.assertIsNone(validate_targeted_player_action(self.data, '2027-R1-2', 1, 'trade_for'))
        with TestClient(player_app(self.data)) as client:
            self.assertEqual(client.get('/trades/trade-for?front_office=1&asset_id=2027-R1-2&owner_roster_id=2').status_code, 200)

    def test_cross_page_market_ownership_and_cache_transitions(self):
        with TemporaryDirectory() as folder:
            cache = AssetMarketCache()
            market = cache.get(self.data, {'data': self.data}, HistoricalStore(Path(folder) / 'history.sqlite3'), 'league-1')
            self.addCleanup(cache.clear)
            self.addCleanup(cache.wait_for_background)
            with patch('routes.market.asset_market_cache', _Cache(market)), TestClient(player_app(self.data)) as client:
                price = client.get('/api/market/assets/player:free').json()['asset']['market_fact']
                for owner_index, state, action in ((None, 'FREE_AGENT', None), (1, 'OWNED_BY_OTHER', '/trades/trade-for?'), (0, 'OWNED_BY_ME', '/trades/shop?'), (None, 'FREE_AGENT', None)):
                    for team in self.data['teams']:
                        team['players'][:] = [p for p in team['players'] if p['id'] != 'free']
                    if owner_index is not None:
                        self.data['teams'][owner_index]['players'].append({'id': 'free', 'position': 'WR', 'name': 'Available Free Agent'})
                    detail = client.get('/api/market/assets/player:free?front_office=1').json()['asset']
                    self.assertEqual(detail['ownership']['state'], state)
                    self.assertEqual(detail['market_fact'], price)
                    self.assertEqual(detail['availability'], 'day_traders_free_agent' if owner_index is None else 'rostered')
                    rows = client.get('/api/market/assets?limit=100').json()['assets']
                    row = next(r for r in rows if r['asset_id'] == 'player:free')
                    self.assertEqual(row['owner'], detail['owner'])
                    html = client.get('/market?front_office=1&selected=player:free&q=Available').text
                    dossier = client.get('/players/free?front_office=1').text
                    for body in (html, dossier):
                        self.assertIn(f'data-ownership-state="{state}"', body)
                        if action:
                            self.assertIn(action, body)
                        else:
                            self.assertNotIn('/trades/trade-for?', body)
                            self.assertNotIn('/trades/shop?', body)
                    intelligence = client.get('/api/players/free/intelligence').json()
                    self.assertEqual(intelligence['ownership']['owner'], detail['owner'])
                    self.assertEqual(intelligence['market_fact'], price)

    def test_unknown_dossier_labels_and_deep_link(self):
        self.data['league']['total_rosters'] = 10
        with TestClient(player_app(self.data)) as client:
            body = client.get('/players/free?front_office=1').text
            self.assertIn('Ownership unavailable', body)
            self.assertNotIn('Not rostered in the active league.', body)
            self.assertNotIn('/trades/trade-for?', body)
            response = client.get('/trades/trade-for?front_office=1&asset_id=free')
            self.assertEqual(response.status_code, 422)
            self.assertIn('incomplete', response.text)

    def test_manual_free_agent_invalid_and_unknown_ownership_rejected(self):
        from services.trade_intelligence import evaluate_trade_request
        payload = {'active_roster_id':1, 'partner_roster_id':2, 'assets_sent':['1-QB-0'], 'assets_received':['free']}
        with self.assertRaises(TradeInputError) as error:
            evaluate_trade_request(self.data, payload)
        self.assertEqual(error.exception.code, 'missing_asset')
        self.data['league']['total_rosters'] = 10
        payload['assets_received'] = ['10225']
        with self.assertRaises(TradeInputError) as error:
            evaluate_trade_request(self.data, payload)
        self.assertEqual(error.exception.code, 'ownership_unavailable')

    def test_no_new_io_and_constant_time_card_lookup(self):
        started = perf_counter()
        index = PlayerOwnershipIndex(self.data)
        for _ in range(10000):
            index.resolve('10225', 1)
        self.assertLess(perf_counter() - started, 1)
        with patch('services.trade_intelligence.build_trade_workspace') as workspace:
            with self.assertRaises(TradeInputError):
                generate_trade_workflow(self.data, {'workflow':'trade_for', 'active_roster_id':1, 'asset_id':'free'})
            workspace.assert_not_called()


if __name__ == '__main__':
    unittest.main()
