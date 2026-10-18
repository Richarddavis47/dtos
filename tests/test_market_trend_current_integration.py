"""Canonical selected-price producer -> sparse memory -> actual Market HTTP routes."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory.store import HistoricalStore
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from tests.test_market_observation_producer_identity import prepared, checkpoint


class CurrentMarketHTTPTests(unittest.TestCase):
    page_renderer = staticmethod(lambda title, body: HTMLResponse(f'<h1>{title}</h1>{body}'))

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.memory = IntelligenceCheckpointStore(root / 'memory.db')
        for n, raw in enumerate((1200, 1440), 1):
            data, asset = prepared(raw)
            stamp = f'2026-07-0{n}T12:00:00+00:00'
            observations = tuple(replace(row, observed_at=stamp) for row in
                                 CheckpointPipeline._market_observations(data, 'player:1'))
            value = asset['layers']['market_value']['value']
            self.assertEqual(value, (100, 120)[n - 1])
            self.memory.put_sparse(checkpoint(f'history-{n}', value, stamp),
                                   market_context_id='fixture', provider_evidence=observations)
        self.data, _ = prepared(2400)
        self.data['league'] = {'league_id': '1313066632158924800', 'name': 'Isolated Day Traders'}
        self.data['players'] = self.data['normalized_players']
        self.state = {'data': self.data}
        history = HistoricalStore(root / 'history.db')
        self.history = history
        self.cache = AssetMarketCache()
        self.addCleanup(self.cache.clear)
        self.market = self.cache.get(self.data, self.state, history, self.data['league']['league_id'])
        self.assertEqual(self.market.by_id['player:1']['values']['market_value'], 200)
        app = FastAPI()
        with patch('routes.market.intelligence_checkpoint_store', self.memory):
            app.include_router(create_market_router(require_data=lambda: self.data, state=self.state,
                league_id=self.data['league']['league_id'],
                context_resolver=lambda: SimpleNamespace(state=self.state,
                    league_id=self.data['league']['league_id'], market=self.cache),
                page=self.page_renderer))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.patch = patch('routes.market.historical_store', history)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_100_120_200_http_matches_canonical_evaluator(self):
        response = self.client.get('/api/market/assets/player:1')
        self.assertEqual(response.status_code, 200, response.text)
        trend = response.json()['market_trend']
        self.assertEqual(trend['magnitude'], 100)
        self.assertTrue(trend['provenance']['current_endpoint_comparable'])
        self.assertEqual(trend['milestones']['season_start']['change'], 80)

    def test_directory_and_trending_share_v2_comparison(self):
        listing = self.client.get('/api/market/assets').json()
        asset = next(row for row in listing['assets'] if row['asset_id'] == 'player:1')
        self.assertEqual(asset['market_trend']['magnitude'], 100)
        trending = self.client.get('/api/market/trending').json()
        self.assertEqual(trending['method_version'], 'sparse-event-market-trend-2')
        result = next(row for row in trending['most_volatile'] if row['asset_id'] == 'player:1')
        self.assertEqual(result['market_trend']['magnitude'], 100)

    def test_source_revision_refreshes_explicit_cache_without_rewriting_history(self):
        from src.core.market_trends import MarketTrendService
        service = MarketTrendService(self.memory)
        args = dict(as_of='2100-01-01T00:00:00Z')
        self.assertEqual(service.trend_for_asset('player:1', None, **args)['magnitude'], 20)
        data, asset = prepared(1920)
        stamp = '2026-08-01T12:00:00Z'
        observations = tuple(replace(row, observed_at=stamp) for row in
                             CheckpointPipeline._market_observations(data, 'player:1'))
        self.memory.put_sparse(checkpoint('later-fixture-publication',
            asset['layers']['market_value']['value'], stamp),
            market_context_id='fixture', provider_evidence=observations)
        result = service.trend_for_asset('player:1', None, **args)
        self.assertEqual(result['magnitude'], 60)
        self.assertEqual(result['checkpoint_count'], 3)

    def test_settled_reads_no_durable_growth_or_new_provider_work(self):
        def logical_state():
            with self.memory._connect() as connection:
                tables = [row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                return {name: [tuple(row) for row in connection.execute(f'SELECT * FROM "{name}"')]
                        for name in tables}
        self.client.get('/api/market/assets/player:1')
        self.client.get('/api/market/trending')
        before = logical_state()
        files = {path.name: path.stat().st_size for path in Path(self.temp.name).iterdir() if path.is_file()}
        with patch('services.sleeper.sync_sleeper') as sync, patch.object(CheckpointPipeline, 'ingest_runtime') as ingest:
            for _ in range(3):
                for path in ('/api/market/assets/player:1', '/api/market/assets', '/api/market/trending'):
                    self.assertEqual(self.client.get(path).status_code, 200)
            sync.assert_not_called()
            ingest.assert_not_called()
        self.assertEqual(logical_state(), before)
        self.assertEqual({path.name: path.stat().st_size for path in Path(self.temp.name).iterdir() if path.is_file()}, files)

    def test_selected_page_uses_the_same_dated_numeric_comparison(self):
        html = self.client.get('/market?selected=player%3A1').text
        self.assertIn('+100.00 Market points', html)
        self.assertIn('Historical to current publication', html)
        self.assertIn('2026-07-01', html)
        self.assertIn('2026-08-31', html)
        self.assertIn('Source update time/freshness is not established', html)



class CurrentComparisonAdmissionTests(unittest.TestCase):
    def test_selected_canonical_evidence_not_unselected_provider_clock(self):
        from src.core.market_trends.current import current_comparison
        data, _ = prepared(2400)
        data['market_data']['providers']['DynastyProcess']['1']['updated_at'] = '2099-01-01T00:00:00Z'
        accepted = current_comparison(data, 'player:1', 200)
        self.assertEqual(accepted['providers'], ('FantasyCalc',))
        self.assertEqual(accepted['observed_at'], '2026-08-31T12:00:00+00:00')
        self.assertTrue(accepted['source_generations']['FantasyCalc'])
        self.assertIsNone(accepted['source_times'][0]['source_updated_at'])

    def test_current_admission_negative_matrix(self):
        from copy import deepcopy
        from src.core.market_trends.current import current_comparison
        base, _ = prepared(2400)
        for case in ('asset_identity', 'missing_identity', 'canonical_price', 'missing_price',
                     'units', 'native_provider', 'method', 'format_identity', 'clock', 'future',
                     'missing_generation', 'conflicting_generation'):
            with self.subTest(case=case):
                data = deepcopy(base)
                asset = data['valuation_intelligence']['assets']['player:1']
                selected = asset['market_observation_evidence']
                observation = selected['observations'][0]
                semantic = observation['metadata']['comparison_semantics']
                if case == 'asset_identity':
                    asset['asset_id'] = 'player:2'
                elif case == 'missing_identity':
                    asset.pop('asset_id')
                elif case == 'canonical_price':
                    selected['canonical_value'] = 10000
                elif case == 'missing_price':
                    asset['valuation_layers']['market_value']['value'] = None
                elif case == 'units':
                    semantic['value_scale'] = 'native-10000'
                elif case == 'native_provider':
                    semantic['value_concept'] = 'native-provider-price'
                elif case == 'method':
                    semantic.pop('methodology')
                elif case == 'format_identity':
                    import json
                    identities = json.loads(semantic['format_key'])
                    identities[0]['provider'] = 'DynastyProcess'
                    semantic['format_key'] = json.dumps(identities)
                elif case == 'clock':
                    observation['observed_at'] = '2026-W01'
                elif case == 'future':
                    observation['observed_at'] = '2099-01-01T00:00:00Z'
                elif case == 'missing_generation':
                    observation.pop('source_identity')
                elif case == 'conflicting_generation':
                    second = deepcopy(observation)
                    second['source_identity'] = 'conflict'
                    selected['observations'].append(second)
                self.assertEqual(current_comparison(data, 'player:1', 200), {})

    def test_zero_is_supported_but_missing_and_boolean_are_not(self):
        from src.core.market_trends.current import current_comparison
        data, _ = prepared(0)
        # The canonical producer can legitimately publish a numerical zero.
        asset = data['valuation_intelligence']['assets']['player:1']
        asset['valuation_layers']['market_value']['value'] = 0
        asset['market_observation_evidence']['canonical_value'] = 0
        self.assertTrue(current_comparison(data, 'player:1', 0))
        for value in (None, False, float('nan')):
            self.assertEqual(current_comparison(data, 'player:1', value), {})

    def test_history_only_current_missing_mismatched_units_and_identity(self):
        from copy import deepcopy
        from src.core.market_trends import MarketTrendService
        from tests.test_market_trends_step7 import _Reader, _row
        rows = [_row('a', '2026-01-01T00:00:00Z', 100),
                _row('b', '2026-02-01T00:00:00Z', 120)]
        for case in ('compatible', 'bare', 'units', 'identity', 'future', 'missing', 'zero'):
            with self.subTest(case=case):
                semantic = deepcopy(rows[-1])
                value = 0 if case == 'zero' else None if case == 'missing' else 200
                if case == 'bare':
                    semantic = {}
                if case == 'units':
                    semantic['comparison_semantics']['value_scale'] = 'native'
                if case == 'identity':
                    semantic['asset_id'] = 'player:2'
                stamp = '2099-01-01T00:00:00Z' if case == 'future' else '2026-03-01T00:00:00Z'
                result = MarketTrendService(_Reader(rows)).trend_for_asset('player:1', value,
                    current_semantics=semantic, current_evidence_at=stamp)
                admitted = case in {'compatible', 'zero'}
                self.assertEqual(result['provenance']['current_endpoint_comparable'], admitted)
                self.assertEqual(result['magnitude'], -100 if case == 'zero' else 100 if admitted else 20)
                self.assertEqual(result['comparison_scope'], 'historical_to_current' if admitted else 'history_only')
                self.assertIn('history-only' if not admitted and value is not None else
                              'unavailable' if value is None else 'recorded observation time',
                              result['current_qualification'])

    def test_future_unknown_and_missing_history_are_not_stable_zeroes(self):
        from src.core.market_trends import MarketTrendService
        from tests.test_market_trends_step7 import _Reader, _row
        rows = [_row('future', '2099-01-01T00:00:00Z', 9999),
                _row('unknown', '2026-W01', 100)]
        result = MarketTrendService(_Reader(rows)).trend_for_asset('player:1', 200)
        self.assertIsNone(result['magnitude'])
        self.assertEqual(result['comparison_scope'], 'unavailable')
        self.assertEqual(result['checkpoint_count'], 0)
        self.assertEqual(result['provenance']['excluded_evidence_count'], 2)

    def test_one_checkpoint_current_zero_ordering_and_generation_conflict(self):
        from copy import deepcopy
        from src.core.market_trends import MarketTrendService
        from tests.test_market_trends_step7 import _Reader, _row
        rows = [_row('a', '2026-01-01T23:00:00-02:00', 100)]
        current = deepcopy(rows[0])
        service = MarketTrendService(_Reader(rows))
        result = service.trend_for_asset('player:1', 200, current_semantics=current,
                                         current_evidence_at='2026-01-02T00:30:00Z')
        self.assertFalse(result['provenance']['current_endpoint_comparable'])
        result = service.trend_for_asset('player:1', 200, current_semantics=current,
                                         current_evidence_at='2026-01-03T00:00:00Z')
        self.assertEqual(result['magnitude'], 100)
        rows[0]['source_generations'] = {'A': 'same'}
        current['source_generations'] = {'A': 'same'}
        result = service.trend_for_asset('player:1', 200, current_semantics=current,
                                         current_evidence_at='2026-01-03T00:00:00Z')
        self.assertFalse(result['provenance']['current_endpoint_comparable'])

    def test_stale_current_is_dated_and_qualified_not_silently_fresh(self):
        from src.core.market_trends import MarketTrendService
        from tests.test_market_trends_step7 import _Reader, _row
        rows = [_row('a', '2025-01-01T00:00:00Z', 100)]
        current = {**rows[0], 'freshness': 'stale'}
        result = MarketTrendService(_Reader(rows)).trend_for_asset('player:1', 200,
            current_semantics=current, current_evidence_at='2025-02-01T00:00:00Z')
        self.assertEqual(result['magnitude'], 100)
        self.assertEqual(result['comparison_end_at'], '2025-02-01T00:00:00Z')
        self.assertIn('stale source evidence', result['current_qualification'])
        self.assertGreater(result['latest_checkpoint_age_days'], 180)

    def test_explicit_cache_follows_current_clock_and_source_revision(self):
        from src.core.market_trends import MarketTrendService
        from tests.test_market_trends_step7 import _Reader, _row
        rows = [_row('a', '2026-01-01T00:00:00Z', 100)]
        service = MarketTrendService(_Reader(rows), cache_limit=2)
        current = dict(rows[0])
        args = dict(as_of='2026-03-01T00:00:00Z', current_semantics=current)
        missing = service.trend_for_asset('player:1', 200, **args)
        admitted = service.trend_for_asset('player:1', 200,
            current_evidence_at='2026-02-01T00:00:00Z', **args)
        self.assertIsNone(missing['magnitude'])
        self.assertEqual(admitted['magnitude'], 100)
        self.assertLessEqual(len(service._cache), 2)

    def test_missing_zero_and_conflicting_historical_generation(self):
        from src.core.market_trends import MarketTrendService
        from tests.test_market_trends_step7 import _Reader, _row
        rows = [_row('a', '2026-01-01T00:00:00Z', 0),
                _row('b', '2026-02-01T00:00:00Z', 0),
                _row('missing', '2026-03-01T00:00:00Z', None)]
        result = MarketTrendService(_Reader(rows)).trend_for_asset('player:1', None)
        self.assertEqual(result['magnitude'], 0)
        self.assertEqual(result['checkpoint_count'], 2)
        self.assertEqual(result['observed_low'], 0)
        rows[1]['asset_id'] = 'player:other'
        result = MarketTrendService(_Reader(rows)).trend_for_asset('player:1', None)
        self.assertEqual(result['checkpoint_count'], 1)
        self.assertIsNone(result['magnitude'])
        rows[1]['asset_id'] = 'player:1'
        for row in rows[:2]:
            row['source_generations'] = {'A': 'same-generation'}
        rows[1]['value'] = 100
        result = MarketTrendService(_Reader(rows)).trend_for_asset('player:1', None)
        self.assertIsNone(result['magnitude'])
        self.assertIn('CONFLICTING_SOURCE_GENERATION', result['comparison_reasons'])
