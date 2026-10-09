"""Journey corrections retain pricing, history and recommendation admission."""
import unittest
from dataclasses import replace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.front_office_intelligence import build_league_model
from tests import test_historical_asset_graph as history
from tests import test_market_render_cache as market
from tests import test_fois_presentation as fois
from tests.test_trade_intelligence import fixture_data
from services.trade_search_policy import missing_evidence_guidance


class JourneyEvidenceTests(unittest.TestCase):
    def test_retained_legacy_momentum_is_withheld_without_rewriting_scores(self):
        fixture = fois.FOISPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        score = FOISEngine().evaluate(FOISFacts(
            'A', 'franchise', 'owner', (SeasonResult(2025, 9, 5, 1, league_size=10),),
        ))
        fixture.repository.save(replace(score, management_momentum='Stable'), 'legacy')
        restored = fixture.repository.league('A', score.model_version)[0]
        self.assertEqual(restored.management_momentum, 'Unavailable')
        self.assertEqual(restored.category_scores, score.category_scores)
        self.assertEqual(restored.confidence, score.confidence)

    def test_missing_impact_guidance_names_system_limit_and_real_next_step(self):
        guidance = missing_evidence_guidance({'recommendation_trace': {
            'rule_reasons': ['SUPPORTED_TEAM_IMPACT_UNAVAILABLE']}})
        self.assertIn('projection coverage and optimal legal-lineup impact', guidance)
        self.assertIn('cannot supply or upload', guidance)
        self.assertIn('Review the Market', guidance)
        self.assertNotIn('Provide the missing', guidance)

    def test_adequate_relevant_trade_history_keeps_behavior_available(self):
        data = fixture_data()
        data['transactions'] = [{'type': 'trade', 'roster_ids': [1, 2]} for _ in range(5)]
        report = build_league_model(data).reports[1]
        self.assertIn('5 observed completed trades', report.negotiation_style)
        self.assertIn('observation period unavailable', report.negotiation_style)
        self.assertNotIn('Selective trade participant', report.negotiation_style)
        self.assertIn('0 observed completed trades', build_league_model(data).reports[3].negotiation_style)

    def test_one_season_cannot_establish_stable_momentum(self):
        score = FOISEngine().evaluate(FOISFacts(
            'A', 'franchise', 'owner', (SeasonResult(2025, 9, 5, 1, league_size=10),),
        ))
        self.assertEqual(score.management_momentum, 'Unavailable')

    def test_sparse_trade_sample_does_not_establish_behavior(self):
        for count in (0, 1, 4):
            data = fixture_data()
            data['transactions'] = [{'type': 'trade', 'roster_ids': [1, 2]} for _ in range(count)]
            report = build_league_model(data).reports[1]
            self.assertIn(f'{count} observed completed trades', report.negotiation_style)
            self.assertIn('does not establish skill or selectivity', report.negotiation_style)
            self.assertNotIn('Conservative Trader', report.philosophies)

    def test_sparse_market_selection_has_visible_recovery(self):
        fixture = market.MarketRenderedRouteTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        response = fixture.client.get('/market?selected=DTOS-P-6149')
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="selected-asset"', response.text)
        self.assertIn('Asset details unavailable', response.text)
        self.assertIn('Browse current Market', response.text)
        self.assertNotIn('>Trade For<', response.text)

    def test_acquired_pick_route_resolves_owner_and_contains_history(self):
        fixture = history.HistoricalAssetGraphTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture._append('trade', 'acquired-fourth', 2026, {
            'transaction_id': 'acquired-fourth', 'type': 'trade', 'status': 'complete',
            'roster_ids': [2, 3], 'adds': {}, 'drops': {}, 'draft_picks': [{
                'season': 2027, 'round': 4, 'roster_id': 3,
                'previous_owner_id': 3, 'owner_id': 2,
            }], 'source_league_id': 'L26',
        })
        fixture.current_data['teams'] = [
            {'roster_id': 2, 'team_name': 'Current human franchise'},
            {'roster_id': 3, 'team_name': 'Original human franchise'},
        ]
        app = FastAPI()
        app.include_router(create_historical_assets_router(
            league_id=fixture.league_id, require_data=lambda: fixture.current_data,
            page=lambda _, body: body,
        ))
        with patch('routes.historical_assets.historical_store', fixture.store), TestClient(app) as client:
            response = client.get('/picks/PICK-2027-R4-ORIG3')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Current human franchise', response.text)
        self.assertIn('Original human franchise', response.text)
        self.assertIn('Current owner identity', response.text)
        self.assertIn('ROOT:franchise:2', response.text)
        self.assertIn('aria-label="Pick ownership history"', response.text)
