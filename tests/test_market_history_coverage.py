"""Canonical sparse observations to cached customer views; no live source reads."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory.store import HistoricalStore
from src.core.intelligence_memory.models import CheckpointTrigger
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.ui.render_cache import GenerationRenderCache
from tests.test_market_observation_producer_identity import prepared, checkpoint


class MarketHistoryFixture:
    """Existing real producers, stores and Market routes with disposable evidence."""
    def __init__(self, case, *, points=((1200, '2026-07-01'), (1440, '2026-07-02')),
                 current_raw=2400, league='2300000000000000001', page=None, picks=False, raw_trend=None):
        self.temp = TemporaryDirectory()
        case.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = IntelligenceCheckpointStore(self.root/'memory.sqlite3')
        self.history = HistoricalStore(self.root/'history.sqlite3')
        self.cache = AssetMarketCache()
        case.addCleanup(self.cache.clear)
        self.picks = picks
        self.data, _ = self.priced_data(current_raw)
        # These leagues share the admitted external reference, not an invented
        # conversion to their different lineup/scoring rules.
        self.data['league'] = {'league_id': league, 'name': 'Disposable Market league',
            'season': '2026', 'roster_positions': ['QB','RB','WR','TE','FLEX','K','DEF','BN']}
        self.data['players'] = deepcopy(self.data['normalized_players'])
        if raw_trend is not None:
            self.data['market_data']['providers']['FantasyCalc']['1']['trend_30_day'] = raw_trend
        self.state = {'data': self.data, 'last_sync': 'unchanged-source-publication'}
        for n, (raw, day) in enumerate(points):
            self.add_point('retained-'+str(n), raw, day)
        self.market = self.cache.get(self.data, self.state, self.history, league)
        self.page_cache = GenerationRenderCache('coverage-page')
        self.body_cache = GenerationRenderCache('coverage-body')
        case.enterContext(patch('routes.market.market_render_cache', self.page_cache))
        case.enterContext(patch('routes.market.market_body_render_cache', self.body_cache))
        case.enterContext(patch('routes.market.historical_store', self.history))
        case.enterContext(patch('services.sleeper.sync_sleeper', side_effect=AssertionError('No sync on a trend read')))
        case.enterContext(patch.object(CheckpointPipeline, 'ingest_runtime', side_effect=AssertionError('No history acquisition on a trend read')))
        self.app = FastAPI()
        with patch('routes.market.intelligence_checkpoint_store', self.memory):
            self.app.include_router(create_market_router(require_data=lambda: self.data,
                state=self.state, league_id=league,
                context_resolver=lambda: SimpleNamespace(state=self.state,
                    league_id=str(self.data['league']['league_id']), market=self.cache),
                page=page or (lambda title, body: HTMLResponse(f'<h1>{title}</h1>{body}'))))
        self.client = TestClient(self.app)
        case.addCleanup(self.client.close)

    def priced_data(self, raw):
        data, asset = prepared(raw)
        if self.picks:
            from src.core.valuation.normalization import prepare_market_normalization
            from src.core.valuation.universe import ValuationUniverse
            from src.core.valuation_intelligence.engine import _score_asset
            data['pick_ledger'].append({**data['pick_ledger'][0], 'original_roster_id':5,
                'original_team':'Different original franchise', 'current_owner_id':4})
            data['market_data']['pick_quotes'] = {'FantasyCalc':[{
                'provider':'FantasyCalc', 'value':raw, 'market_format':'fc:12:2qb:ppr',
                'year':2027, 'round':1, 'pick_type':'generic_round', 'confidence':90,
                'availability':'current', 'retrieved_at':datetime.now(timezone.utc).isoformat()}]}
            prepare_market_normalization(data['market_data'])
            universe = ValuationUniverse(data, {'data':data})
            data['valuation_intelligence']['assets'] = {
                identity:_score_asset(row, [], {}, None) for identity,row in universe.by_id.items()}
            asset = universe.by_id['player:1']
        return data, asset

    def add_point(self, identity, raw, day, *, trigger=CheckpointTrigger.SEASON_START,
                  quote_day=None, context='fixture', semantics=None, asset_id='player:1'):
        data, asset = self.priced_data(raw)
        stamp = day+'T12:00:00+00:00'
        quote_stamp = (quote_day or day)+'T12:00:00+00:00'
        observations = tuple(replace(row, observed_at=quote_stamp) for row in
            CheckpointPipeline._market_observations(data, asset_id))
        if semantics:
            observations = tuple(replace(row, metadata={**row.metadata,
                'comparison_semantics': {**row.metadata['comparison_semantics'], **semantics}})
                for row in observations)
        value = data['valuation_intelligence']['assets'][asset_id]['valuation_layers']['market_value']['value']
        point = replace(checkpoint(identity, value, stamp), trigger_type=trigger,
                        asset_id=asset_id, asset_type='future_pick' if asset_id.startswith('pick:') else 'player')
        return self.memory.put_sparse(point, market_context_id=context, provider_evidence=observations)

    def trend(self, asset_id='player:1'):
        response = self.client.get('/api/market/assets/'+asset_id)
        assert response.status_code == 200, response.text
        return response.json()['market_trend']

    def html(self, asset_id='player:1'):
        response = self.client.get('/market', params={'selected':asset_id})
        assert response.status_code == 200, response.text
        return response.text


class MarketHistoryCoverageTests(unittest.TestCase):
    def test_new_checkpoint_invalidates_both_html_caches_without_price_refresh(self):
        f = MarketHistoryFixture(self)
        before = f.html()
        self.assertIn('+100.00 Market points', before)
        generation = f.market.semantic_generation
        f.add_point('earlier-supported-point', 960, '2026-06-01')
        trend = f.trend()
        self.assertEqual((trend['magnitude'], trend['checkpoint_count']), (120, 3))
        directory = f.client.get('/api/market/assets').json()['assets']
        self.assertEqual(next(r for r in directory if r['asset_id']=='player:1')['market_trend']['magnitude'], 120)
        trending = f.client.get('/api/market/trending').json()
        self.assertEqual(next(r for r in trending['most_volatile'] if r['asset_id']=='player:1')['market_trend']['magnitude'], 120)
        after = f.html()
        self.assertIn('+120.00 Market points', after)
        self.assertIn(trend['comparison_start_at'], after)
        self.assertIn('3 retained checkpoints', after)
        self.assertEqual(f.market.semantic_generation, generation)
        self.assertEqual(after, f.html())

    def test_new_event_reference_changes_milestone_without_inventing_a_price(self):
        f = MarketHistoryFixture(self)
        self.assertNotIn('Midseason:', f.html())
        price_generation = f.memory.observation_generation()
        result = f.add_point('later-midseason-reference', 1440, '2026-09-01',
            quote_day='2026-07-02', trigger=CheckpointTrigger.MIDSEASON)
        self.assertFalse(result[3], 'A repeated quote must not create another price observation')
        self.assertEqual(f.memory.observation_generation(), price_generation)
        self.assertEqual(f.trend()['milestones']['midseason']['change'], 80)
        self.assertIn('Midseason: +80.00 Market points', f.html())
        self.assertEqual(f.trend()['checkpoint_count'], 2)

    def test_daily_aging_updates_rendered_confidence_without_new_source_evidence(self):
        f = MarketHistoryFixture(self)
        for month in range(1,7):
            f.add_point('earlier-month-'+str(month), 600+month*120, f'2026-{month:02d}-01')
        initial_generation = f.memory.observation_generation()
        boundary = datetime(2026,7,2,12,tzinfo=timezone.utc)+timedelta(days=180)
        class Clock(datetime):
            instant = boundary
            @classmethod
            def now(cls, tz=None):
                return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)
        with patch('src.core.market_trends.service.datetime', Clock):
            before = f.trend()
            self.assertEqual(before['latest_checkpoint_age_days'], 180)
            self.assertIn(before['confidence'].upper()+' CONFIDENCE', f.html())
            Clock.instant += timedelta(days=1)
            after = f.trend()
            self.assertEqual(after['latest_checkpoint_age_days'], 181)
            self.assertNotEqual(before['confidence'], after['confidence'])
            for key in ('magnitude','comparison_start_at','comparison_end_at','checkpoint_count','current_qualification'):
                self.assertEqual(before[key],after[key],key)
            self.assertIn(after['confidence'].upper()+' CONFIDENCE', f.html())
            self.assertEqual(f.memory.observation_generation(), initial_generation)

    def test_admitted_checkpoint_dates_and_values_reach_existing_disclosure(self):
        f = MarketHistoryFixture(self, points=((960,'2026-06-01'), (1200,'2026-06-15'), (1440,'2026-07-02')))
        trend = f.trend()
        html = f.html()
        self.assertIn('Retained Market observations', html)
        for row in trend['checkpoints']:
            self.assertIn('data-observation-id="'+row['observation_id']+'"', html)
            self.assertIn(row['observed_at'], html)
            self.assertIn(f'{row["value"]:,.2f}', html)
        self.assertIn('Current published endpoint', html)
        self.assertIn('not daily', html)

    def test_supported_zero_is_a_comparison_without_claiming_a_stable_trend(self):
        f = MarketHistoryFixture(self, points=((0,'2026-07-01'),), current_raw=0)
        trend = f.trend()
        self.assertEqual(trend['magnitude'], 0)
        self.assertEqual(trend['direction'], 'insufficient_evidence')
        self.assertTrue(trend['provenance']['current_endpoint_comparable'])
        html = f.html()
        self.assertIn('+0.00 Market points', html)
        self.assertIn('More evidence is needed to classify the trend', html)
        self.assertNotIn('STABLE ·', html)
        self.assertIn('Dated price comparisons are available', html)
        trending = f.client.get('/api/market/trending').json()
        self.assertEqual(trending['availability'], 'unavailable')
        self.assertIn('classify a trend', trending['unavailable_reason'])

    def test_source_catalogue_is_not_presented_as_selected_price_providers(self):
        f = MarketHistoryFixture(self)
        self.assertEqual(f.trend()['provenance']['current_evidence']['providers'], ['FantasyCalc'])
        html = f.html()
        self.assertIn('Current Market price provider', html)
        self.assertIn('FantasyCalc', html)
        self.assertNotIn('Participating provider', html)
        self.assertIn('Provider catalogue entry', html)

    def test_player_dossier_links_the_same_canonical_comparison_without_raw_contamination(self):
        from routes.transactions import create_transactions_router
        from src.core.data_platform import data_platform
        from src.core.data_platform.storage import SnapshotWarehouse
        f = MarketHistoryFixture(self,raw_trend=-999)
        self.enterContext(patch.object(data_platform,'warehouse',SnapshotWarehouse()))
        f.app.include_router(create_transactions_router(ensure_fresh=AsyncMock(),
            refresh_transactions=AsyncMock(),require_data=lambda:f.data,state=f.state,
            page=lambda title,body:HTMLResponse(body)))
        response = f.client.get('/players/1?front_office=4')
        self.assertEqual(response.status_code,200)
        self.assertIn('FantasyCalc raw-price 30-day change (provider units): -999',response.text)
        self.assertIn('href="/market?selected=player%3A1">Observed canonical Market history',response.text)
        destination = f.client.get('/market?selected=player%3A1')
        self.assertEqual(destination.status_code,200)
        self.assertIn('+100.00 Market points',destination.text)
        self.assertNotIn('-999',destination.text)
        self.assertEqual(f.trend()['magnitude'],100)

    def test_no_history_never_becomes_an_unchanged_zero(self):
        f = MarketHistoryFixture(self, points=())
        trend = f.trend()
        self.assertIsNone(trend['magnitude'])
        self.assertEqual(trend['checkpoint_count'], 0)
        html = f.html()
        self.assertIn('0 dated checkpoints available to this comparison', html)
        self.assertNotIn('+0.00 Market points', html)
        self.assertNotIn('data-observation-id=', html)

    def test_one_checkpoint_without_a_later_endpoint_keeps_known_price_not_a_change(self):
        f = MarketHistoryFixture(self, points=((1440,'2026-08-31'),), current_raw=1440)
        trend = f.trend()
        self.assertEqual(trend['checkpoint_count'], 1)
        self.assertIsNone(trend['magnitude'])
        self.assertFalse(trend['provenance']['current_endpoint_comparable'])
        html = f.html()
        self.assertIn('1 dated checkpoint available to this comparison', html)
        self.assertIn('120.00', html)
        self.assertNotIn('Current published endpoint:', html)
        self.assertNotIn('+0.00 Market points', html)

    def test_retained_but_ineligible_records_are_not_claimed_absent(self):
        f = MarketHistoryFixture(self,points=((1200,'2099-07-01'),))
        trend = f.trend()
        self.assertEqual(trend['checkpoint_count'],0)
        self.assertEqual(trend['provenance']['excluded_evidence_count'],1)
        self.assertIsNone(trend['magnitude'])
        html = f.html()
        self.assertIn('1 retained record could not be used as eligible dated prices',html)
        self.assertNotIn('0 recorded prices',html)
        self.assertNotIn('+0.00 Market points',html)

    def test_preview_is_bounded_without_truncating_the_canonical_comparison(self):
        f = MarketHistoryFixture(self, points=tuple(
            (1200 if n%2 else 1440, f'2026-01-{n:02d}') for n in range(1,16)))
        trend = f.trend()
        self.assertEqual(trend['checkpoint_count'], 15)
        html = f.html()
        self.assertLessEqual(html.count('data-observation-id='), 12)
        self.assertIn(trend['checkpoints'][0]['observation_id'], html)
        self.assertIn(trend['checkpoints'][-1]['observation_id'], html)
        self.assertIn('Intermediate checkpoints are omitted', html)
        self.assertIn('all admitted evidence', html)

    def test_exact_pick_original_franchise_history_is_not_substituted(self):
        f = MarketHistoryFixture(self, points=(), picks=True)
        identity = 'pick:2027:1:4'
        for n,(raw,day) in enumerate(((1200,'2026-07-01'),(1440,'2026-07-02'))):
            f.add_point('exact-pick-'+str(n),raw,day,asset_id=identity,context='exact-pick-fixture')
        a = f.trend(identity)
        b = f.trend('pick:2027:1:5')
        self.assertEqual(a['asset_id'],identity)
        self.assertEqual(a['checkpoint_count'],2)
        self.assertIsNotNone(a['magnitude'])
        self.assertEqual(b['checkpoint_count'],0)
        self.assertIsNone(b['magnitude'])
        html = f.html(identity)
        self.assertIn('Retained Market observations', html)
        self.assertIn('pick:2027:1:4', html)
        self.assertNotIn('data-observation-id=', f.html('pick:2027:1:5'))

    def test_incompatible_units_do_not_acquire_canonical_movement_or_zero(self):
        f = MarketHistoryFixture(self)
        f.html()
        f.add_point('native-unit-boundary',960,'2026-06-01',semantics={'value_scale':'native-provider-units'})
        trend = f.trend()
        self.assertEqual(trend['direction'],'not_comparable')
        self.assertIsNone(trend['magnitude'])
        html = f.html()
        self.assertIn('Not compared across this evidence boundary',html)
        self.assertNotIn('+0.00 Market points',html)
        self.assertNotIn('+100.00 Market points',html)

    def test_format_boundary_remains_not_comparable_and_not_player_movement(self):
        f = MarketHistoryFixture(self)
        f.html()
        f.add_point('other-provider-format', 960, '2026-06-01',
            semantics={'format_key':'incompatible-format-evidence'})
        trend = f.trend()
        self.assertEqual(trend['direction'], 'not_comparable')
        self.assertIsNone(trend['magnitude'])
        self.assertIn('INCOMPATIBLE_OBSERVATION_BOUNDARY', trend['comparison_reasons'])
        html = f.html()
        self.assertNotIn('+100.00 Market points', html)
        self.assertIn('This is not player movement', html)

    def test_settled_reads_preserve_every_record_and_do_not_prepare_again(self):
        f = MarketHistoryFixture(self)
        f.html()
        def rows():
            with f.memory._connect() as c:
                return {table:[tuple(r) for r in c.execute('SELECT * FROM '+table)] for table in
                    ('global_market_observations','market_observation_references','intelligence_checkpoints')}
        before = rows()
        builds = f.cache.metrics()['build_count']
        for _ in range(3):
            f.html()
            f.trend()
        self.assertEqual(f.cache.metrics()['build_count'], builds)
        self.assertEqual(rows(), before)
