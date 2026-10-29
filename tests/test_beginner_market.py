"""One indexed Market query contract through the released HTTP routes."""
import unittest
import copy
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from services.market_navigation import market_return
from tests import test_asset_market as market_fixture


class BeginnerMarketTests(unittest.TestCase):
    def setUp(self):
        self.fixture = f = market_fixture.AssetMarketTests()
        f.setUp()
        self.addCleanup(f.tearDown)
        for pid, name, pos in [('13346', 'Denzel Boston', 'WR'), ('44', 'Boston Backup', 'WR'), ('45', 'Boston Quarterback', 'QB')]:
            f.data['players'][pid] = {'full_name': name, 'position': pos, 'team': 'SEA', 'status': 'Active'}
            f.data['valuation_intelligence']['assets']['player:' + pid] = market_fixture._brain_asset('player:' + pid, int(pid), None, None)
        for year in (2028, 2029):
            for round_number in (1, 2, 3):
                for original in (1, 2, 3):
                    if year == 2028 and round_number == 1 and original == 1:
                        continue
                    f.data['pick_ledger'].append({'season': year, 'round': round_number, 'original_roster_id': original, 'original_team': 'Origin ' + str(original), 'current_owner_id': 1, 'current_owner': 'Puka Cola Quantum'})
        f.data = copy.deepcopy(f.data)
        f.state["data"] = f.data
        f.data["asset_market_semantic_revision"] = "beginner-fixture-v1"
        f.cache.clear()
        self.market = f.cache.get(f.data, f.state, f.store, f.league_id)
        app = FastAPI()
        app.include_router(create_market_router(require_data=lambda: f.data, page=lambda title, body: HTMLResponse(body), state=f.state, league_id=f.league_id, context_resolver=lambda: SimpleNamespace(state=f.state, league_id=f.league_id, market=f.cache)))
        self.addCleanup(patch.stopall)
        patch("routes.market.historical_store", f.store).start()
        self.client = TestClient(app)

    def get(self, path):
        response = self.fixture._ready_get(self.client, path)
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_single_result_has_no_next_and_offset_is_not_relabelled(self):
        one = self.get('/api/market/search?q=Denzel%20Boston').json()
        self.assertEqual(one['total'], 1)
        self.assertEqual(one['results'][0]['result_position'], 1)
        later = self.get('/api/market/search?q=Denzel%20Boston&offset=50').json()
        self.assertEqual(later['results'], [])
        self.assertEqual(later['total'], 1)
        html = self.get('/market?q=Denzel%20Boston').text
        self.assertNotIn('Next page', html)
        self.assertNotIn('Result #51', html)
        self.assertIn('Browse all assets', html)
        self.assertIn('href="/market?limit=10"', html)

    def test_last_valid_market_notice_does_not_change_prices_or_expose_sync_error(self):
        before = self.get('/api/market/search?q=Denzel%20Boston').json()['results']
        self.fixture.state['last_error'] = 'SYNTHETIC_PRIVATE /private/market credential=fake'
        html = self.get('/market?q=Denzel%20Boston').text
        self.assertIn('Last successful Market available.', html)
        self.assertIn('Market prepared:', html)
        self.assertNotIn('SYNTHETIC_PRIVATE', html)
        self.assertNotIn('/private/market', html)
        self.assertEqual(self.get('/api/market/search?q=Denzel%20Boston').json()['results'], before)
        # A Market-provider fallback is distinct from a failed Sleeper sync.
        # The same admitted prices must survive both HTTP representations.
        self.fixture.state['last_error'] = None
        source_status = self.fixture.data.setdefault('market_data', {}).setdefault('provider_status', {})
        source_status['FantasyCalc'] = {'status': 'failed', 'refresh_result': 'cached_fallback',
                                       'reason': 'SYNTHETIC_PRIVATE /private/market credential=fake'}
        html = self.get('/market?q=Denzel%20Boston').text
        self.assertIn('Market source could not update', html)
        self.assertIn('Some quotes are from its last successful update', html)
        self.assertNotIn('latest league update failed', html)
        self.assertNotIn('SYNTHETIC_PRIVATE', html)
        after = self.get('/api/market/search?q=Denzel%20Boston').json()['results']
        self.assertEqual([(row['asset_id'], row['values']['market_value']) for row in after],
                         [(row['asset_id'], row['values']['market_value']) for row in before])

    def test_failed_replacement_uses_safe_rendered_recovery_without_old_prices(self):
        self.fixture.data['asset_market_semantic_revision'] = 'next-compatible-inputs-needed'
        self.fixture.cache._build_phase = 'failed'
        self.fixture.cache._refresh_state = 'failed'
        self.fixture.cache.last_error = 'SYNTHETIC_PRIVATE /private/source credential=fake'
        with patch.object(self.fixture.cache, '_start_background', return_value=False):
            response = self.client.get('/market?q=Denzel', headers={'Accept': 'text/html'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('Market preparation needs another try', response.text)
        self.assertIn('Try Market again', response.text)
        self.assertNotIn('SYNTHETIC_PRIVATE', response.text)
        self.assertNotIn('Find your next dynasty asset', response.text)

    def test_search_filter_sort_and_nonoverlapping_pages(self):
        first = self.get('/api/market/search?q=Boston&limit=1&sort=market').json()
        second = self.get('/api/market/search?q=Boston&limit=1&offset=1&sort=market').json()
        self.assertEqual(first['total'], 3)
        self.assertNotEqual(first['results'][0]['asset_id'], second['results'][0]['asset_id'])
        self.assertEqual(second['results'][0]['result_position'], 2)
        filtered = self.get('/api/market/search?q=Boston&position=QB&availability=day_traders_free_agent').json()
        self.assertEqual([r['asset_id'] for r in filtered['results']], ['player:45'])
        owned = self.get('/api/market/search?q=Boston&availability=rostered').json()
        self.assertEqual(owned['total'], 0)
        self.assertEqual(self.get('/api/market/search?q=NoSuchPlayer').json()['results'], [])

    def test_structured_exact_pick_rounds_preserve_original_identity(self):
        for round_number in (1, 2, 3):
            rows = self.get('/api/market/search?' + urlencode({'q': f'2029 Round {round_number}', 'position': 'PICK'})).json()['results']
            self.assertEqual(len(rows), 3)
            self.assertEqual({r['asset_id'] for r in rows}, {f'pick:2029:{round_number}:{original}' for original in (1, 2, 3)})
        self.assertEqual(len(self.market.search('2029 2nd')['results']), 3)

    def test_raw_and_canonical_player_ids(self):
        for query in ('13346', 'player:13346', 'DTOS-P-13346'):
            rows = self.get('/api/market/search?' + urlencode({'q': query})).json()['results']
            self.assertEqual([r['asset_id'] for r in rows], ['player:13346'])

    def test_last_page_and_price_invariance(self):
        before = self.market.directory(limit=100)['assets']
        total = len(before)
        page = self.get('/api/market/search?limit=10&offset=' + str(total - 1)).json()
        self.assertEqual(len(page['results']), 1)
        self.assertEqual(page['results'][0]['result_position'], total)
        for row in before:
            after = self.market.detail(row['asset_id'], None)['asset']
            self.assertEqual(row['values']['market_value'], after['values']['market_value'])

    def test_market_return_is_scoped_and_not_an_open_redirect(self):
        original = '/market?q=Denzel+Boston&position=WR&offset=0&limit=10'
        self.assertEqual(market_return(original, 'league-1', 'league-1'), original)
        for path, league in [('https://outside/market', 'league-1'), ('//outside/market', 'league-1'), ('/market?redirect=outside', 'league-1'), (original, 'other')]:
            self.assertIsNone(market_return(path, league, 'league-1'))

    def test_current_ownership_filters_during_last_valid_market_fallback(self):
        # The published price index deliberately stays unchanged. Current
        # roster facts still govern availability, ownership and actions.
        with patch.object(self.fixture.cache, 'get', return_value=self.market):
            self.fixture.data['teams'][0]['players'].append({'id':'13346','roster_slot':'Taxi'})
            result = self.get('/api/market/search?q=Boston&availability=taxi').json()
            self.assertEqual([r['asset_id'] for r in result['results']], ['player:13346'])
            self.assertEqual(result['results'][0]['owner']['roster_id'], 1)
            result = self.get('/api/market/search?q=Boston&availability=day_traders_free_agent').json()
            self.assertNotIn('player:13346', [r['asset_id'] for r in result['results']])
            self.fixture.data['teams'][0]['players'] = None
            result = self.get('/api/market/search?q=Boston&availability=day_traders_free_agent').json()
            self.assertEqual(result['total'], 0)
            self.assertFalse(result['ownership_filter_coverage']['available'])
            self.assertIn('roster evidence is incomplete', self.get('/market?q=Boston&availability=day_traders_free_agent').text)

    def test_released_projection_navigation_asset(self):
        import dtos_app
        from pathlib import Path
        response = TestClient(dtos_app.app).get('/static/js/player-projections.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, Path('static/js/player-projections.js').read_bytes())
        self.assertEqual(response.headers['cache-control'], 'no-cache')
        self.assertIn('text/javascript', response.headers['content-type'])
