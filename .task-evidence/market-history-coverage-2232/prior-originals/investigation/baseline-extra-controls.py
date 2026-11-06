"""Canonical sparse observations to cached customer views; no live source reads."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
                 current_raw=2400, league='2300000000000000001', page=None):
        self.temp = TemporaryDirectory()
        case.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = IntelligenceCheckpointStore(self.root/'memory.sqlite3')
        self.history = HistoricalStore(self.root/'history.sqlite3')
        self.cache = AssetMarketCache()
        case.addCleanup(self.cache.clear)
        self.data, _ = prepared(current_raw)
        # These leagues share the admitted external reference, not an invented
        # conversion to their different lineup/scoring rules.
        self.data['league'] = {'league_id': league, 'name': 'Disposable Market league',
            'season': '2026', 'roster_positions': ['QB','RB','WR','TE','FLEX','K','DEF','BN']}
        self.data['players'] = deepcopy(self.data['normalized_players'])
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

    def add_point(self, identity, raw, day, *, trigger=CheckpointTrigger.SEASON_START,
                  quote_day=None, context='fixture', semantics=None):
        data, asset = prepared(raw)
        stamp = day+'T12:00:00+00:00'
        quote_stamp = (quote_day or day)+'T12:00:00+00:00'
        observations = tuple(replace(row, observed_at=quote_stamp) for row in
            CheckpointPipeline._market_observations(data, 'player:1'))
        if semantics:
            observations = tuple(replace(row, metadata={**row.metadata,
                'comparison_semantics': {**row.metadata['comparison_semantics'], **semantics}})
                for row in observations)
        point = replace(checkpoint(identity, asset['layers']['market_value']['value'], stamp), trigger_type=trigger)
        return self.memory.put_sparse(point, market_context_id=context, provider_evidence=observations)

    def trend(self):
        response = self.client.get('/api/market/assets/player:1')
        assert response.status_code == 200, response.text
        return response.json()['market_trend']

    def html(self):
        response = self.client.get('/market?selected=player%3A1')
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

    def test_no_history_never_becomes_an_unchanged_zero(self):
        f = MarketHistoryFixture(self, points=())
        trend = f.trend()
        self.assertIsNone(trend['magnitude'])
        self.assertEqual(trend['checkpoint_count'], 0)
        html = f.html()
        self.assertIn('0 recorded prices', html)
        self.assertNotIn('+0.00 Market points', html)
        self.assertNotIn('data-observation-id=', html)

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
