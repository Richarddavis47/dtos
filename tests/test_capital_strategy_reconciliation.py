"""P1 capital acceptance contracts over canonical prices and real legal lineups."""
import copy
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.trades import create_trades_router

from services.trade_intelligence import (
    TradeInputError, assist_trade_request, build_trade_workspace, evaluate_trade_request,
    generate_trade_workflow, _trade_for_eligible,
)
from src.core.intelligence.team_strength import prepare_for_data
from src.core.projection_intelligence.service import ProjectionService
from src.core.trade_intelligence.bilateral import evaluate_bilateral
from src.core.trade_intelligence.models import TradeProposal
from src.core.valuation.config import NORMALIZATION_VERSION
from tests.test_trade_intelligence import fixture_data


class CapitalStrategyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = fixture_data()
        self.data['teams'] = self.data['teams'][:2]
        self.data['week'] = 2
        self.data['league'].update(season=2026, sport='nfl', roster_positions=['QB', 'BN', 'BN', 'BN', 'BN'],
            scoring_settings={'pass_yd': 1}, settings={'leg': 2, 'last_scored_leg': 1,
                'start_week': 1, 'playoff_week_start': 4, 'playoff_teams': 4,
                'playoff_round_type': 0, 'playoff_type': 0})
        self.data['players'] = {}
        self.points = {}
        for team, ids, scores, intent in zip(self.data['teams'], [('a', 'b', 'e'), ('c', 'd', 'f')],
                                           [(10, 5, 6), (8, 3, 4)], ['REBUILD', 'WIN NOW']):
            team['strategy'] = intent
            team['players'] = [{'id': pid, 'position': 'QB', 'name': pid,
                                'roster_slot': 'Starter' if i == 0 else 'Bench'} for i, pid in enumerate(ids)]
            for pid, points in zip(ids, scores):
                self.data['players'][pid] = {'position': 'QB', 'full_name': pid, 'age': 31 if pid == 'a' else 24}
                self.points[pid] = points
            # Acquired first: original franchise differs from current owner.
            team['picks_owned'] = [{'year': 2028, 'round': r, 'original_roster_id': team['roster_id'] + 2,
                                   'current_owner_id': team['roster_id']} for r in (1, 2, 4)]
        self.prices()
        self.reader = ProjectionService(Path(self.tmp.name) / 'projection.sqlite3')
        self.publish()

    def prices(self, **players):
        self.data['market_data'] = {'providers': {'FantasyCalc': {
            pid: {'value': players.get(pid, 250) * 12, 'confidence': 90} for pid in self.points}}}
        now = datetime.now(timezone.utc).isoformat()
        self.data['market_data']['pick_quotes'] = {'FantasyCalc': [
            {'provider': 'FantasyCalc', 'market_format': 'fc:12:2qb:ppr', 'year': 2028, 'round': r,
             'pick_type': 'generic_round', 'availability': 'current', 'retrieved_at': now,
             'value': value * 12, 'confidence': 80,
             'normalization_reference': {'provider': 'FantasyCalc', 'raw_value': float(value * 12),
                 'normalized_value': value, 'version': NORMALIZATION_VERSION,
                 'generation': 'capital-fixture', 'method': 'provider_range_linear'}}
            for r, value in ((1, 250), (2, 100), (4, 20))]}

    def publish(self):
        self.payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week,
            'stats': {'pass_yd': points}, 'player': {'position': 'QB'}} for pid, points in self.points.items()]
            for week in (2, 3, 4, 5)}
        self.reader.publish_horizon(self.payloads, data=self.data, league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.reader, self.data)

    def evaluate(self, sent, received, active=1, intent='REBUILD', workflow='create', workspace=None):
        return evaluate_trade_request(self.data, {'active_roster_id': active, 'partner_roster_id': 3 - active,
            'assets_sent': sent, 'assets_received': received, 'strategy': intent, 'workflow': workflow},
            workspace=workspace, projection_reader=self.reader)['evaluation']

    def test_all_six_legal_package_shapes_qualify(self):
        # A, B, C, D, E, F: each cost is assessed under that manager's intent.
        cases = [
            ('A', ['a'], ['2028-R1-4'], 1, 'REBUILD', {}),
            ('B', ['2028-R1-4'], ['a'], 2, 'WIN NOW', {}),
            ('C', ['c', '2028-R2-4'], ['a'], 2, 'WIN NOW', {'a': 350}),
            ('D', ['a'], ['c', '2028-R2-4'], 1, 'REBUILD', {'a': 350}),
            ('E', ['2028-R1-4', '2028-R2-4'], ['a'], 2, 'WIN NOW', {'a': 350}),
            ('F', ['a', 'b'], ['2028-R1-4'], 1, 'REBUILD', {'a': 150, 'b': 100}),
        ]
        for shape, sent, received, active, intent, prices in cases:
            with self.subTest(shape=shape):
                self.prices(**prices)
                report = self.evaluate(sent, received, active, intent)
                self.assertTrue(report['legal'])
                self.assertEqual(report['recommendation'], 'WORTH PURSUING')
                self.assertTrue(report['generated_trade_eligible'])
                self.assertEqual(report['dimensions']['counterparty_plausibility']['assessment'], 'PLAUSIBLE')
                self.assertNotIn('FUTURE_CAPITAL_TRADEOFF_UNRESOLVED', report['reason_codes'])
                self.assertIsNone(report['dimensions']['strategic_fit']['active']['future_capital']['utility_delta'])

    def test_strategy_changes_fit_never_market_or_lineups(self):
        before = copy.deepcopy(self.data)
        rebuild = self.evaluate(['a'], ['2028-R1-4'])
        win = self.evaluate(['a'], ['2028-R1-4'], intent='WIN NOW')
        self.assertEqual(rebuild['recommendation'], 'WORTH PURSUING')
        self.assertEqual(win['recommendation'], 'NOT WORTH IT')
        self.assertEqual(rebuild['market_evidence'], win['market_evidence'])
        self.assertEqual(rebuild['multi_horizon_impact'], win['multi_horizon_impact'])
        self.assertEqual(self.data, before)
        self.assertIn('give up current production', rebuild['why_you_would_do_it'])
        self.assertIn('give up current production', rebuild['explanation_html'])
        report = self.evaluate(['2028-R1-4'], ['a'], active=2, intent='WIN NOW')
        self.assertIn('costs future flexibility', report['explanation_html'])

    def test_retool_balanced_mixed_exchange(self):
        self.prices(a=350)
        report = self.evaluate(['c', '2028-R2-4'], ['a'], active=2, intent='RETOOL')
        self.assertEqual(report['recommendation'], 'WORTH PURSUING')
        self.assertIn('RETOOL_PRODUCTION_FIT', report['reason_codes'])
        self.assertTrue(report['generated_trade_eligible'])

    def test_smash_and_fair_labels_are_available_with_capital(self):
        # A reserve player at fair terms: capital improves with no starter loss.
        report = self.evaluate(['b'], ['2028-R1-4'])
        self.assertEqual(report['recommendation'], 'SMASH ACCEPT')
        report = self.evaluate(['2028-R1-3'], ['2028-R1-4'], intent='RETOOL')
        self.assertEqual(report['recommendation'], 'FAIR / OPTIONAL')
        self.assertFalse(report['generated_trade_eligible'])
        self.assertFalse(_trade_for_eligible(report))  # parity alone is no credible counterparty benefit
        self.prices(b=100)
        report = self.evaluate(['b'], ['2028-R1-4'])
        self.assertEqual(report['market_evidence']['difference'], 150)
        self.assertEqual(report['recommendation'], 'SMASH ACCEPT')

    def test_bad_return_and_tiny_positive_signal_do_not_rescue_counterparty(self):
        self.prices(a=900)
        report = self.evaluate(['a'], ['2028-R4-4'])
        self.assertEqual(report['recommendation'], 'REJECT')
        self.assertFalse(report['generated_trade_eligible'])
        reverse = self.evaluate(['2028-R4-4'], ['a'], active=2, intent='WIN NOW')
        self.assertEqual(reverse['dimensions']['counterparty_plausibility']['assessment'], 'LOW')
        self.assertFalse(reverse['generated_trade_eligible'])
        # One tiny positive week must not erase three large losses.
        workspace = build_trade_workspace(self.data, 1)
        proposal = TradeProposal(1, 2, (workspace['pools'][1][0],), (workspace['pools'][2][0],), 'Fixture')
        impact = copy.deepcopy(report['multi_horizon_impact'])
        partner = impact['sides']['partner']
        for week, row in partner['weekly'].items():
            row['delta'] = .01 if int(week) == 2 else -10
        partner['horizons']['current_week']['delta'] = .01
        partner['horizons']['rest_of_regular_season']['delta'] = -9.99
        partner['horizons']['playoff_window']['delta'] = -20
        result = evaluate_bilateral(proposal, active_team={}, partner_team={}, league=self.data['league'], horizon_impact=impact)
        self.assertEqual(result['dimensions']['counterparty_plausibility']['assessment'], 'LOW')

    def test_missing_price_identity_projection_or_strategy_remains_unresolved(self):
        workspace = build_trade_workspace(self.data, 1)
        for missing in ('trade_value', 'season'):
            modified = dict(workspace, pools=dict(workspace['pools']))
            modified['pools'][2] = tuple(replace(a, **{missing: None}) if a.kind == 'pick' else a for a in workspace['pools'][2])
            report = self.evaluate(['a'], ['2028-R1-4'], workspace=modified)
            self.assertIsNone(report['recommendation'])
            self.assertIn('FUTURE_CAPITAL_TRADEOFF_UNRESOLVED', report['reason_codes'])
            self.assertFalse(report['generated_trade_eligible'])
        self.data['teams'][0].pop('strategy')
        report = evaluate_trade_request(self.data, {'active_roster_id': 1, 'partner_roster_id': 2,
            'assets_sent': ['a'], 'assets_received': ['2028-R1-4']}, projection_reader=self.reader)['evaluation']
        self.assertIsNone(report['recommendation'])
        self.data['team_strength']['projection_generation'] = 'stale'
        report = self.evaluate(['a'], ['2028-R1-4'])
        self.assertIsNone(report['recommendation'])
        self.assertIn('SUPPORTED_TEAM_IMPACT_UNAVAILABLE', report['reason_codes'])

    def test_unknown_playoff_calendar_is_missing_evidence_not_an_evaluator_exception(self):
        self.data['league']['settings']['playoff_teams'] = 2
        self.publish()
        report = self.evaluate(['a'], ['2028-R1-4'])
        self.assertIsNone(report['recommendation'])
        self.assertIn('FUTURE_CAPITAL_TRADEOFF_UNRESOLVED', report['reason_codes'])
        self.assertFalse(report['generated_trade_eligible'])

    def test_window_defaults_must_match_generation_and_explicit_intent_wins(self):
        workspace = build_trade_workspace(self.data, 1)
        for team in workspace['teams']:
            team.pop('strategy', None)
        generation = self.data['team_strength']['semantic_generation']
        workspace['competitive_windows'] = {'1': {'classification': 'Rebuilding', 'generation': generation},
                                            '2': {'classification': 'Contender', 'generation': generation}}
        payload = {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': ['a'], 'assets_received': ['2028-R1-4']}
        report = evaluate_trade_request(self.data, payload, workspace=workspace, projection_reader=self.reader)['evaluation']
        self.assertTrue(report['generated_trade_eligible'])
        self.assertEqual(report['recommendation_trace']['manager_strategy']['source'], 'canonical_competitive_window')
        explicit = self.evaluate(['a'], ['2028-R1-4'], intent='WIN_NOW', workspace=workspace)
        self.assertEqual(explicit['recommendation'], 'NOT WORTH IT')
        workspace['competitive_windows']['1']['generation'] = 'old'
        report = evaluate_trade_request(self.data, payload, workspace=workspace, projection_reader=self.reader)['evaluation']
        self.assertIsNone(report['recommendation'])

    def test_market_premium_requires_material_production(self):
        self.prices(a=200)
        report = self.evaluate(['2028-R1-4'], ['a'], active=2, intent='WIN NOW')
        self.assertEqual(report['market_evidence']['difference'], -50)
        self.assertEqual(report['recommendation'], 'WORTH PURSUING')
        self.points['a'] = 8.01
        self.publish()
        report = self.evaluate(['2028-R1-4'], ['a'], active=2, intent='WIN NOW')
        self.assertEqual(report['recommendation'], 'NOT WORTH IT')
        self.assertFalse(report['generated_trade_eligible'])

    def test_rebuild_discloses_mixed_production_instead_of_claiming_preservation(self):
        # A strong average must not conceal a current-week sacrifice.
        self.prices(a=350)
        for week, rows in self.payloads.items():
            for row in rows:
                if row['player_id'] == 'c':
                    row['stats']['pass_yd'] = 4 if week == 2 else 14
        self.reader.publish_horizon(self.payloads, data=self.data, league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.reader, self.data)
        report = self.evaluate(['a'], ['c', '2028-R2-4'])
        self.assertEqual(report['recommendation_trace']['production_evidence']['mean_weekly_delta'], 2)
        self.assertEqual(report['lineup_impact']['active']['delta'], -4)
        self.assertEqual(report['recommendation'], 'WORTH PURSUING')
        self.assertIn('losses in some horizons', report['why_you_would_do_it'])
        self.assertNotIn('production is preserved', report['why_you_would_do_it'])

    def test_exact_acquired_pick_identity_and_unknown_range_preserved(self):
        report = self.evaluate(['a'], ['2028-R1-4'])
        pick = report['dimensions']['strategic_fit']['active']['future_capital']['received'][0]
        self.assertEqual((pick['asset_id'], pick['year'], pick['round'], pick['original_franchise'], pick['canonical_owner']),
                         ('2028-R1-4', 2028, 1, 4, 2))
        self.assertEqual(pick['projected_range'], 'UNKNOWN')
        self.assertEqual(pick['range_confidence'], 'LOW')
        self.assertEqual(pick['market_price'], 250)
        self.assertIn('low_confidence_pick_range', report['major_limitations'])
        workspace = build_trade_workspace(self.data, 1)
        workspace['pools'][2] = tuple(replace(a, projected_range='EARLY', projected_range_confidence='HIGH')
                                    if a.kind == 'pick' else a for a in workspace['pools'][2])
        supported = self.evaluate(['a'], ['2028-R1-4'], workspace=workspace)
        exact = supported['dimensions']['strategic_fit']['active']['future_capital']['received'][0]
        self.assertEqual((exact['asset_id'], exact['projected_range'], exact['range_confidence']), ('2028-R1-4', 'EARLY', 'HIGH'))
        workspace = build_trade_workspace(self.data, 1)
        workspace['pools'][2] = tuple(replace(a, original_roster_id=9) if a.kind == 'pick' else a for a in workspace['pools'][2])
        with self.assertRaisesRegex(TradeInputError, 'exact pick identity'):
            self.evaluate(['a'], ['2028-R1-4'], workspace=workspace)

    def test_unique_weeks_not_overlapping_horizon_sum(self):
        report = self.evaluate(['a'], ['2028-R1-4'])
        production = report['recommendation_trace']['production_evidence']
        self.assertEqual(production['weeks_counted_once'], [2, 3, 4, 5])
        self.assertEqual(production['mean_weekly_delta'], -4)
        horizons = report['recommendation_trace']['horizons']
        self.assertEqual(horizons['current_week']['delta'], -4)
        self.assertEqual(horizons['next_n']['delta'], -12)
        self.assertEqual(horizons['playoff_window']['delta'], -8)

    def test_capacity_and_duplicate_assets_block_execution_not_strategy(self):
        self.data['league']['roster_positions'] = ['QB', 'BN', 'BN']
        self.publish()
        report = self.evaluate(['a'], ['c', '2028-R2-4'])
        self.assertTrue(report['legal'])
        self.assertEqual(report['legality']['execution_status'], 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER')
        report = self.evaluate(['2028-R1-4'], ['a'], active=2, intent='WIN NOW')
        self.assertEqual(report['legality']['execution_status'], 'REQUIRES ROSTER RESOLUTION')
        self.assertFalse(report['generated_trade_eligible'])
        with self.assertRaises(TradeInputError):
            self.evaluate(['a', 'a'], ['2028-R1-4'])

    def test_generated_shop_trade_for_recommended_and_adjustment_use_real_evaluator(self):
        before = copy.deepcopy(self.data)
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.reader):
            for workflow, active, target, intent in (
                ('shop', 1, 'a', 'REBUILD'), ('shop', 2, '2028-R1-4', 'WIN NOW'),
                ('trade_for', 2, 'a', 'WIN NOW'), ('recommended', 1, None, 'REBUILD'),
                ('recommended', 2, None, 'WIN NOW')):
                with self.subTest(workflow=workflow, active=active):
                    result = generate_trade_workflow(self.data, {'workflow': workflow,
                        'active_roster_id': active, 'asset_id': target, 'strategy': intent,
                        **({'shop_preference': 'draft_capital'} if workflow == 'shop' and active == 1 else {})})
                    self.assertGreater(result['count'], 0)
                    self.assertTrue(any(row['evaluation']['recommendation_trace']['future_capital_changed'] for row in result['results']))
                    for row in result['results']:
                        payload = dict(row['proposal'], strategy=intent)
                        manual = evaluate_trade_request(self.data, payload, projection_reader=self.reader)['evaluation']
                        self.assertEqual(row['evaluation'], manual)
            adjusted = assist_trade_request(self.data, {'active_roster_id': 2, 'partner_roster_id': 1,
                'assets_sent': ['2028-R4-4'], 'assets_received': ['a'], 'strategy': 'WIN NOW',
                'instruction': 'make this trade work'})
            self.assertGreater(adjusted['count'], 0)
            self.assertTrue(all(_trade_for_eligible(row['evaluation']) for row in adjusted['results']))
        self.assertEqual(self.data, before)

    def test_route_api_strategy_and_capital_contract(self):
        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: self.data,
                                               page=lambda title, body: body))
        with TestClient(app) as client, patch('src.core.projection_intelligence.projection_service', self.reader), \
                patch('services.trade_intelligence._trade_projection_service', return_value=self.reader):
            payload = {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': ['a'],
                       'assets_received': ['2028-R1-4'], 'strategy': 'REBUILD'}
            response = client.post('/api/trades/evaluate', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['evaluation']['recommendation'], 'WORTH PURSUING')
            pick = response.json()['proposal_presentation']['receive'][0]
            self.assertEqual((pick['year'], pick['round'], pick['original_franchise'], pick['current_owner']), (2028, 1, 4, 2))
            response = client.post('/api/trades/generate', json={'workflow': 'shop', 'active_roster_id': 1,
                'asset_id': 'a', 'strategy': 'REBUILD', 'shop_preference': 'draft_capital'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertGreater(response.json()['count'], 0)
            response = client.post('/api/trades/evaluate', json=dict(payload, strategy='UNKNOWN'))
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()['detail']['code'], 'invalid_strategy')

    def test_browser_strategy_controls_real_capital_evaluation(self):
        from urllib.parse import urlsplit
        from playwright.sync_api import sync_playwright
        from tools.validation.browser_runtime import launch_chromium
        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: self.data,
                                               page=lambda title, body: body))
        with TestClient(app) as client, patch('src.core.projection_intelligence.projection_service', self.reader), \
                sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width in (390, 1280):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 900})
                        page.set_default_timeout(8000)
                        results, errors = [], []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        def route(request):
                            parsed = urlsplit(request.request.url)
                            if parsed.netloc != 'dtos.test':
                                return request.abort()
                            response = client.request(request.request.method, parsed.path + '?' + parsed.query,
                                content=request.request.post_data, headers={k: v for k, v in request.request.headers.items()
                                if k == 'content-type'})
                            if parsed.path == '/api/trades/evaluate':
                                results.append(response.json()['evaluation'])
                            request.fulfill(status=response.status_code,
                                content_type=response.headers.get('content-type'), body=response.content)
                        page.route('**/*', route)
                        page.goto('https://dtos.test/trades/create?front_office=2')
                        page.get_by_label('Counterparty', exact=True).select_option('1')
                        page.get_by_label('Your strategy', exact=True).select_option('WIN NOW')
                        page.locator('#trade-sent-board button[data-asset-id="2028-R1-4"]').click()
                        if width < 760:
                            page.get_by_role('button', name='Their assets', exact=True).click()
                        page.locator('#trade-received-board button[data-asset-id="a"]').click()
                        page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                        page.locator('#trade-result .dtos-explanation').wait_for()
                        self.assertEqual(results[-1]['recommendation'], 'WORTH PURSUING')
                        self.assertIn('costs future flexibility', page.locator('#trade-result').inner_text())
                        page.get_by_label('Your strategy', exact=True).select_option('REBUILD')
                        self.assertTrue(page.locator('#trade-result').is_hidden())
                        page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                        page.locator('#trade-result .dtos-explanation').wait_for()
                        self.assertEqual(results[-1]['recommendation'], 'NOT WORTH IT')
                        self.assertEqual(results[0]['market_evidence'], results[1]['market_evidence'])
                        self.assertEqual(errors, [])
                        page.close()
            finally:
                browser.close()
