"""Cross-page contracts against real manager boundaries and canonical pricing."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from services.asset_intelligence import build_player_dossier
from services.trade_intelligence import build_trade_workspace
from src.core.data_platform import data_platform
from src.core.data_platform.provider_activation import player_context
from src.core.valuation.calibration import cached_market_facts
from src.core.valuation.normalization import prepare_market_normalization
from src.core.valuation.universe import ValuationUniverse
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory.store import HistoricalStore
from tests.test_trade_intelligence import fixture_data


def facts_fixture():
    data = fixture_data()
    data['league']['season'] = '2026'
    data['week'] = 3
    stamp = datetime.now(timezone.utc).isoformat()
    market = data['market_data']
    for old_id, player_id, name in (('2-TE-8', '10225', 'Trey McBride'), ('2-QB-0', '4984', 'Josh Allen')):
        data['players'][player_id] = data['players'].pop(old_id)
        data['players'][player_id]['full_name'] = name
        for row in data['teams'][1]['players']:
            if row['id'] == old_id:
                row.update(id=player_id, name=name)
        market['providers']['FantasyCalc'][player_id] = market['providers']['FantasyCalc'].pop(old_id)
    data['players']['free'] = {'full_name': 'Available Free Agent', 'position': 'WR', 'team': 'BUF', 'status': 'Active'}
    data['players']['missing'] = {'full_name': 'Unpriced Player', 'position': 'WR', 'team': 'BUF'}
    market['providers']['FantasyCalc']['free'] = {'value': 3200, 'confidence': 85}
    for row in market['providers']['FantasyCalc'].values():
        row.update(format='dynasty_2qb', retrieved_at=stamp, source_updated_at=stamp)
    prepare_market_normalization(market)
    return data


class CanonicalAssetFactTests(unittest.TestCase):
    def setUp(self):
        from src.core.data_platform.storage import SnapshotWarehouse
        self.warehouse = patch.object(data_platform, 'warehouse', SnapshotWarehouse())
        self.warehouse.start()
        self.addCleanup(self.warehouse.stop)

    def consumers(self, data, player_id, roster_id=1):
        report, _, _ = build_player_dossier(data, player_id, roster_id)
        detail = data_platform.player_report(player_id, data)
        asset = next(row for row in ValuationUniverse.streaming(data, {}).iter_assets() if row['asset_id'] == 'player:' + player_id)
        workspace = build_trade_workspace(data, roster_id)
        trade = next((row for pool in workspace['pools'].values() for row in pool if row.asset_id == player_id), None)
        rows = [report.market_fact.to_dict(), detail['market_fact'], asset['market_fact']]
        if trade is not None:
            rows.append(trade.market_fact)
            self.assertEqual(trade.market_value, rows[0]['value'])
            self.assertEqual(trade.trade_value, rows[0]['value'])
        self.assertEqual(report.core_values.market.score, rows[0]['value'])
        self.assertEqual(detail['consensus']['value'], rows[0]['value'])
        self.assertEqual(asset['layers']['market_value']['value'], rows[0]['value'])
        for row in rows[1:]:
            for key in ('player_id', 'value', 'generation', 'availability', 'freshness', 'unavailability_reason', 'confidence', 'fallback'):
                self.assertEqual(row[key], rows[0][key], key)
        if report.value_profile is not None:
            self.assertEqual(report.value_profile.market_consensus.value, rows[0]['value'])
            self.assertEqual(report.value_profile.intelligence_card.market_value, rows[0]['value'])
        return rows[0], report, asset, trade

    def test_opposing_mcbride_and_allen_and_owned_and_free_agent(self):
        data = facts_fixture()
        for pid in ('10225', '4984', '1-QB-0', 'free'):
            with self.subTest(player=pid):
                fact, _, asset, trade = self.consumers(data, pid)
                self.assertIsNotNone(fact['value'])
                self.assertEqual(fact['availability'], 'available')
                self.assertEqual(asset['identity']['free_agent'], pid == 'free')
                expected_owner = 1 if pid == '1-QB-0' else 2
                if trade:
                    self.assertEqual(trade.source_roster_id, expected_owner)

    def test_truly_unavailable_and_explicit_rejection_reasons(self):
        data = facts_fixture()
        fact, _, _, _ = self.consumers(data, 'missing')
        self.assertIsNone(fact['value'])
        self.assertIn('No supported Market evidence', fact['unavailability_reason'])
        for changes, reason in (({'identity_status': 'unresolved'}, 'identity'),
                                ({'format': 'redraft'}, 'compatible format'),
                                ({'availability': 'stale_beyond_usable'}, 'stale beyond'),
                                ({'confidence': 0}, 'valid supported')):
            changed = deepcopy(data)
            changed['market_data']['providers']['FantasyCalc']['4984'].update(changes)
            fact, _, _, _ = self.consumers(changed, '4984')
            self.assertIsNone(fact['value'])
            self.assertIn(reason, fact['unavailability_reason'])

    def test_warming_last_valid_then_refreshed_and_cold(self):
        data = facts_fixture()
        old, _, _, _ = self.consumers(data, '4984')
        data['market_data'].update(status='warming', provider_status={'FantasyCalc': {'status': 'failed', 'refresh_result': 'cached_fallback'}})
        retained, _, _, _ = self.consumers(data, '4984')
        self.assertEqual(retained['value'], old['value'])
        self.assertTrue(retained['fallback'])
        self.assertEqual(retained['retrieved_at'], old['retrieved_at'])
        data['market_data']['provider_status'] = {'FantasyCalc': {'status': 'healthy', 'refresh_result': 'success'}}
        data['market_data']['providers']['FantasyCalc']['4984']['value'] = 9000
        prepare_market_normalization(data['market_data'])
        refreshed, _, _, _ = self.consumers(data, '4984')
        self.assertFalse(refreshed['fallback'])
        self.assertNotEqual(refreshed['generation'], retained['generation'])
        self.assertNotEqual(refreshed['value'], retained['value'])
        data['market_data'] = {'providers': {}, 'status': 'warming'}
        cold, _, _, _ = self.consumers(data, '4984')
        self.assertIsNone(cold['value'])
        self.assertIn('warming', cold['unavailability_reason'])

    def test_stale_but_usable_and_source_clock_not_retrieval(self):
        data = facts_fixture()
        row = data['market_data']['providers']['FantasyCalc']['4984']
        row['source_updated_at'] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        fact, _, _, _ = self.consumers(data, '4984')
        self.assertIsNotNone(fact['value'])
        self.assertEqual(fact['freshness'], 'stale')
        self.assertNotEqual(fact['source_updated_at'], fact['retrieved_at'])
        row['source_updated_at'] = None
        fact, _, _, _ = self.consumers(data, '4984')
        self.assertEqual(fact['freshness'], 'unknown')
        self.assertIsNone(fact['source_updated_at'])

    def test_incompatible_secondary_is_not_averaged_and_valid_secondary_stands_alone(self):
        data = facts_fixture()
        first = cached_market_facts(data['market_data'], ['4984'])['4984']
        data['market_data']['providers']['DynastyProcess'] = {'4984': {'value': 9999, 'confidence': 90, 'format': 'dynasty_2qb'}}
        fact, _, _, _ = self.consumers(data, '4984')
        self.assertEqual(fact['value'], first.value)
        self.assertEqual(fact['evidence_coverage'], ['FantasyCalc'])
        del data['market_data']['providers']['FantasyCalc']['4984']
        fact, _, _, _ = self.consumers(data, '4984')
        self.assertIsNotNone(fact['value'])
        self.assertEqual(fact['evidence_coverage'], ['DynastyProcess'])
        self.assertIsNone(fact['unavailability_reason'])

    def test_portfolio_provider_cache_cannot_replace_published_quotes(self):
        from src.core.data_platform.defaults import build_data_platform
        from src.core.data_platform.storage import SnapshotWarehouse
        from src.core.market_intelligence.engine import MarketIntelligence
        from src.core.market_intelligence.history import MarketHistoryStore
        from src.core.asset_intelligence import AssetContext, evaluate_player
        data = facts_fixture()
        data['market_data']['allow_cached_fallback'] = True
        platform = build_data_platform()
        platform.warehouse = SnapshotWarehouse()
        engine = MarketIntelligence(platform=platform, history=MarketHistoryStore())
        context = SimpleNamespace(cached_data=data, league_id='league-1', active_roster_id=1)
        reports = {'4984': evaluate_player({**data['players']['4984'], 'id': '4984'}, AssetContext('league-1', 1, {}))}
        engine.evaluate(context, reports, ())
        data['market_data']['providers']['FantasyCalc']['4984']['value'] = 9000
        prepare_market_normalization(data['market_data'])
        market = engine.evaluate(context, reports, ()).assets['4984']
        quote = next(q for q in market.consensus.quotes if q.provider == 'FantasyCalc')
        self.assertEqual(quote.value, 9000)
        fact = cached_market_facts(data['market_data'], ['4984'])['4984']
        self.assertEqual(market.consensus.value, fact.value)
        self.assertEqual(quote.normalized_value, fact.providers_used[0].normalized_value)

    def test_strategy_and_ownership_do_not_reprice_global_facts(self):
        data = facts_fixture()
        first, _, _, _ = self.consumers(data, '4984')
        data['teams'][0]['strategy'] = 'Rebuild'
        opposing, _, _, _ = self.consumers(data, '4984', 2)
        self.assertEqual(first, opposing)
        moved = next(row for row in data['teams'][1]['players'] if row['id'] == '4984')
        data['teams'][1]['players'].remove(moved)
        data['teams'][0]['players'].append(moved)
        owned, _, asset, trade = self.consumers(data, '4984')
        self.assertEqual(first, owned)
        self.assertEqual(trade.source_roster_id, 1)
        self.assertEqual(asset['identity']['current_owner']['roster_id'], 1)
        self.assertEqual(player_context('4984', data)['league']['owned_by'], data['teams'][0]['team_name'])

    def test_exact_acquired_pick_identity_is_preserved(self):
        data = facts_fixture()
        data['teams'][0]['picks_owned'].append({'season': 2028, 'round': 1, 'original_roster_id': 2,
            'original_team': 'Team 2', 'current_owner_id': 1})
        pick = next(row for row in build_trade_workspace(data, 1)['pools'][1] if row.asset_id == '2028-R1-2')
        self.assertEqual((pick.season, pick.round, pick.original_roster_id, pick.current_owner_id), (2028, 1, 2, 1))
        self.assertEqual((pick.projected_range, pick.projected_range_confidence), ('UNKNOWN', 'LOW'))
        self.assertIsNone(pick.market_fact)
        self.assertIsNone(pick.redraft_value)

    def test_retained_market_generation_discloses_its_own_source_fact(self):
        data = facts_fixture()
        with tempfile.TemporaryDirectory() as folder:
            store = HistoricalStore(Path(folder) / 'history.sqlite3')
            cache = AssetMarketCache()
            try:
                market = cache.get(data, {'data': data}, store, 'league-1')
                row = market.detail('player:4984')['asset']
                import json
                self.assertEqual(row['market_fact'], json.loads(json.dumps(asdict(cached_market_facts(data['market_data'], ['4984'])['4984']))))
                # Last-valid artifact retains its source generation while a new
                # generation is preparing; it does not borrow current provenance.
                retained = row['market_fact']
                data['market_data']['providers']['FantasyCalc']['4984']['value'] = 10000
                prepare_market_normalization(data['market_data'])
                current = asdict(cached_market_facts(data['market_data'], ['4984'])['4984'])
                self.assertNotEqual(retained['generation'], current['generation'])
                self.assertEqual(market.detail('player:4984')['asset']['market_fact'], retained)
            finally:
                cache.wait_for_background()
                cache.clear()

    def test_market_player_and_trade_http_boundaries_agree(self):
        from routes.api import create_api_router
        from routes.market import create_market_router
        from routes.trades import create_trades_router
        from tests.test_market_render_cache import _Cache
        import json
        data = facts_fixture()
        async def fresh(*args, **kwargs):
            pass
        with tempfile.TemporaryDirectory() as folder:
            store = HistoricalStore(Path(folder) / 'history.sqlite3')
            cache = AssetMarketCache()
            try:
                market = cache.get(data, {'data': data}, store, 'league-1')
                app = FastAPI()
                app.include_router(create_api_router(ensure_fresh=fresh, require_data=lambda: data,
                    sync_sleeper=fresh, state={'data': data}, league_id='league-1'))
                app.include_router(create_market_router(require_data=lambda: data, state={'data': data},
                    league_id='league-1', page=lambda title, body: HTMLResponse(body)))
                app.include_router(create_trades_router(ensure_fresh=fresh, require_data=lambda: data,
                    page=lambda title, body: HTMLResponse(body)))
                with patch('routes.market.asset_market_cache', _Cache(market)), TestClient(app) as client:
                    response = client.get('/api/trades/workspace?front_office=1')
                    self.assertEqual(response.status_code, 200)
                    trade_rows = {row['asset_id']: row for team in response.json()['teams'] for row in team['assets']}
                    for pid in ('4984', '10225', '1-QB-0', 'free', 'missing'):
                        with self.subTest(player=pid):
                            player = client.get('/api/players/' + pid + '/intelligence')
                            self.assertEqual(player.status_code, 200)
                            fact = player.json()['market_fact']
                            expected = json.loads(json.dumps(asdict(cached_market_facts(data['market_data'], [pid])[pid])))
                            self.assertEqual(fact, expected)
                            market_response = client.get('/api/market/assets/player:' + pid)
                            self.assertEqual(market_response.status_code, 200)
                            self.assertEqual(market_response.json()['asset']['market_fact'], fact)
                            self.assertEqual(market_response.json()['asset']['values']['market_value'], fact['value'])
                            if pid in trade_rows:
                                self.assertEqual(trade_rows[pid]['market_fact'], fact)
            finally:
                cache.wait_for_background()
                cache.clear()

    def test_projection_availability_uses_same_selected_week_panel(self):
        from routes.transactions import create_transactions_router
        from tests.test_batch6_matchup_season import fixture
        data = facts_fixture()
        data['players']['2'] = {'full_name': 'Projected Player', 'position': 'QB', 'team': 'BUF'}
        _, service, _ = fixture('league-1')
        pinned = {**service.snapshot(), 'horizon_snapshot_ids': {'3': 'p3', '5': 'p5'}}
        service.snapshot = lambda: pinned
        runtime = SimpleNamespace(projection=service)
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_transactions_router(ensure_fresh=fresh, require_data=lambda: data,
            refresh_transactions=fresh, state={}, page=lambda _, body: HTMLResponse(body)))
        with patch('routes.transactions.current_league_context', return_value=runtime), TestClient(app) as client:
            body = client.get('/players/2?front_office=1&week=3').text
            self.assertIn('Current projections:</b> Available · Sleeper week 3 · 27.33 points', body)
            self.assertNotIn('Current projections:</b> None', body)
            self.assertNotIn('Current projections:</b> null', body)
            service.week_snapshot = lambda week, **kw: {**pinned, 'week': week, 'players': {'2': {'canonical_projection': None}}}
            body = client.get('/players/2?week=5').text
            self.assertIn('No supported player projection for this week.', body)
            self.assertNotIn('Current projections:</b> 0', body)


if __name__ == '__main__':
    unittest.main()
