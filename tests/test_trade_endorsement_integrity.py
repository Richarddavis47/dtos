"""Recommendation promotion over canonical prices, publications and workflows."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from routes.trades import create_trades_router
from services.trade_intelligence import (
    assist_trade_request, build_trade_workspace, evaluate_trade_request, generate_trade_workflow,
)
from services.trade_search_policy import classify
from tests import test_trade_discovery_repair as discovery
from tests import test_trade_workspace_batch1 as boundary


class EndorsementIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = discovery.DiscoveryRepairTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.data = self.fixture.data
        self.data['teams'] = self.data['teams'][:2]
        self.publisher = self.fixture.fixture
        self.publisher.points = {k: v for k, v in self.publisher.points.items()
                                 if k.startswith(('1', '2'))}
        self.data['players'] = {k: v for k, v in self.data['players'].items()
                                if k in self.publisher.points}
        for team in self.data['teams']:
            for player in team['players']:
                player['status'] = 'Active'
        self.payload = dict(active_roster_id=1, partner_roster_id=2,
                            assets_sent=['1q'], assets_received=['2w'], strategy='REBUILD')
        self.configure()

    def configure(self, *, sent=995, received=75, delta=.01, spare_qb=True):
        # QB loss is six points; incoming WR replaces a five-point starter.
        # Their WR reserve remains eleven, so this is complementary for them.
        team = self.data['teams'][0]
        team['players'] = [p for p in team['players'] if p['id'] != '1qc']
        self.publisher.points.pop('1qc', None)
        self.data['players'].pop('1qc', None)
        if spare_qb:
            player = {'id': '1qc', 'name': 'Reserve QB', 'position': 'QB',
                      'status': 'Active', 'roster_slot': 'Bench'}
            team['players'].append(player)
            self.data['players']['1qc'] = {'full_name': 'Reserve QB', 'position': 'QB', 'age': 25}
            self.publisher.points['1qc'] = 13
        self.publisher.points['2w'] = 11 + delta
        self.publisher.prices(**{'1q': sent, '2w': received})
        self.publisher.publish()

    def evaluate(self, *, workspace=None, **updates):
        return evaluate_trade_request(self.data, {**self.payload, **updates},
                                      workspace=workspace,
                                      projection_reader=self.publisher.reader)['evaluation']

    def assert_unfavorable(self, evaluation):
        self.assertTrue(evaluation['legal'])
        self.assertIn(evaluation['recommendation'], ('REJECT', 'NOT WORTH IT'))
        self.assertFalse(evaluation['generated_trade_eligible'])
        self.assertEqual(classify(evaluation), 'STRATEGICALLY POOR')

    def test_reported_scout_case_cannot_be_favorably_promoted(self):
        e = self.evaluate()
        self.assertEqual((e['values']['sent'], e['values']['received']), (995, 75))
        production = e['dimensions']['strategic_fit']['active']['production_evidence']
        self.assertAlmostEqual(production['mean_weekly_delta'], .01)
        self.assertFalse(production['material_gain'])
        self.assertEqual(e['dimensions']['counterparty_plausibility']['assessment'], 'PLAUSIBLE')
        self.assert_unfavorable(e)

    def test_severe_loss_is_not_promoted_under_any_explicit_strategy(self):
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(strategy=strategy):
                self.assert_unfavorable(self.evaluate(strategy=strategy))

    def test_complete_http_evaluation_and_trade_for_do_not_promote_scout_case(self):
        auth = boundary.AuthenticatedTradeBoundaryTests()
        auth.setUp()
        self.addCleanup(auth.doCleanups)
        app = auth.client.app
        app.router.routes.clear()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(),
            require_data=lambda: self.data, page=lambda title, body: body))
        with auth.client as client:
            context = client.get('/api/trades/workspace').json()['workspace_context']
            headers = {'X-CSRF-Token': auth.csrf}
            response = client.post('/api/trades/evaluate',
                json={**self.payload, 'workspace_context': context}, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            evaluated = response.json()['evaluation']
            response = client.post('/api/trades/generate', json={
                'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': '2w',
                'workspace_context': context,
                'strategy': 'REBUILD', 'excluded_assets': ['1qb', '1w', '1wb',
                    '2028-R1-21', '2028-R2-21', '2028-R4-21', '2q', '2qb', '2wb',
                    '2028-R1-22', '2028-R2-22', '2028-R4-22']}, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['results'], [])
            self.assert_unfavorable(evaluated)

    def test_canonical_contender_window_resolves_win_now_without_changing_guard(self):
        self.data['teams'][0].pop('strategy', None)
        workspace = build_trade_workspace(self.data, 1)
        generation = self.data['team_strength']['semantic_generation']
        workspace['competitive_windows'] = {'1': {
            'classification': 'Contender', 'generation': generation}}
        payload = {k: v for k, v in self.payload.items() if k != 'strategy'}
        e = evaluate_trade_request(self.data, payload, workspace=workspace,
                                   projection_reader=self.publisher.reader)['evaluation']
        self.assertEqual(e['recommendation_trace']['manager_strategy'], {
            'strategy': 'WIN NOW', 'source': 'canonical_competitive_window'})
        self.assert_unfavorable(e)

    def test_materiality_boundary_reuses_existing_weekly_threshold(self):
        for delta, favorable in ((.99, False), (1, True), (1.01, True)):
            self.configure(sent=100, received=90, delta=delta)
            with self.subTest(delta=delta):
                e = self.evaluate(strategy='WIN NOW')
                production = e['dimensions']['strategic_fit']['active']['production_evidence']
                self.assertEqual(production['material_weekly_threshold'], 1)
                self.assertEqual(production['material_gain'], favorable)
                if favorable:
                    self.assertEqual(e['recommendation'], 'WORTH PURSUING')
                else:
                    self.assert_unfavorable(e)

    def test_player_plus_exact_pick_cannot_bypass_the_same_severe_loss_guard(self):
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(strategy=strategy):
                e = self.evaluate(assets_sent=['1q', '2028-R4-21'], strategy=strategy)
                self.assert_unfavorable(e)
                self.assertIn('SEVERE_MARKET_LOSS', e['reason_codes'])

    def test_missing_market_remains_uncertain_and_genuine_zero_remains_supported(self):
        workspace = build_trade_workspace(self.data, 1)
        from dataclasses import replace
        workspace['pools'][1] = tuple(replace(a, trade_value=None) if a.asset_id == '1q' else a
                                      for a in workspace['pools'][1])
        e = self.evaluate(workspace=workspace)
        self.assertIsNone(e['values']['sent'])
        self.assertIsNone(e['recommendation'])
        self.assertFalse(e['generated_trade_eligible'])
        self.configure(sent=0, received=0, delta=0)
        e = self.evaluate()
        self.assertEqual(e['values']['sent'], 0)
        self.assertEqual(e['values']['received'], 0)
        self.assertEqual(e['market_evidence']['availability'], 'full')
        self.assertEqual(e['recommendation'], 'FAIR / OPTIONAL')

    def test_tiny_zero_negative_and_unknown_gains_do_not_rescue_overpay(self):
        for delta in (.01, 0, -.01):
            self.configure(sent=100, received=90, delta=delta)
            for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
                with self.subTest(delta=delta, strategy=strategy):
                    self.assert_unfavorable(self.evaluate(strategy=strategy))
        self.publisher.points.pop('2w')
        from src.core.projection_intelligence.service import ProjectionService
        self.publisher.reader = ProjectionService(Path(self.publisher.tmp.name) / 'missing.sqlite3')
        e = self.evaluate()
        self.assertIsNone(e['recommendation'])
        self.assertIsNone(e['dimensions']['strategic_fit']['active']['production_evidence']['mean_weekly_delta'])
        self.assertFalse(e['generated_trade_eligible'])
        self.assertEqual(classify(e), 'MISSING REQUIRED EVIDENCE')

    def test_complementary_400_exchange_retains_four_and_eight_point_gains(self):
        self.configure(sent=400, received=400, delta=4, spare_qb=False)
        e = self.evaluate(strategy='RETOOL')
        self.assertEqual(e['values']['sent'], 400)
        self.assertEqual(e['values']['received'], 400)
        for side, expected in (('active', 4), ('partner', 8)):
            production = e['dimensions']['strategic_fit'][side]['production_evidence']
            self.assertEqual(production['mean_weekly_delta'], expected)
        self.assertEqual(e['recommendation'], 'WORTH PURSUING')
        self.assertTrue(e['generated_trade_eligible'])
        self.assertEqual(classify(e), 'CREDIBLE RECOMMENDATION')

    def test_material_win_now_overpay_is_preserved_and_sources_do_not_change(self):
        self.configure(sent=500, received=400, delta=8)
        before = deepcopy(self.data)
        snapshot = self.publisher.reader.snapshot()
        e = self.evaluate(strategy='WIN NOW')
        self.assertEqual(e['values']['sent'] - e['values']['received'], 100)
        self.assertTrue(e['dimensions']['strategic_fit']['active']['production_evidence']['material_gain'])
        self.assertEqual(e['recommendation'], 'WORTH PURSUING')
        self.assertEqual(self.data, before)
        self.assertEqual(self.publisher.reader.snapshot(), snapshot)

    def test_policy_generation_invalidates_old_assessment_without_changing_facts(self):
        from services.home_trade_opportunities import source_identity
        from src.core.intelligence import TRADE_EVALUATION_POLICY_VERSION
        before = deepcopy(self.data)
        with patch('src.core.intelligence.TRADE_EVALUATION_POLICY_VERSION',
                   'scoped-trade-effects-v4-discovery'):
            old = source_identity(self.data)
        current = source_identity(self.data)
        self.assertNotEqual(old, current)
        self.assertEqual(current, source_identity(self.data))
        self.assertEqual(self.evaluate()['provenance']['strategy_methodology'],
                         TRADE_EVALUATION_POLICY_VERSION)
        self.assertEqual(self.data, before)

    def test_all_discovery_and_adjust_results_agree_with_manual_evaluator(self):
        for workflow, target in (('trade_for', '2w'), ('shop', '1q'), ('recommended', None)):
            with self.subTest(workflow=workflow):
                result = generate_trade_workflow(self.data, {
                    'workflow': workflow, 'active_roster_id': 1, 'asset_id': target,
                    'strategy': 'REBUILD'})
                for row in result['results']:
                    manual = self.evaluate(**row['proposal'], strategy='REBUILD')
                    self.assertEqual(row['evaluation'], manual)
                    self.assertNotIn(manual['recommendation'], ('REJECT', 'NOT WORTH IT'))
                    self.assertNotEqual((row['proposal']['assets_sent'], row['proposal']['assets_received']),
                                        (['1q'], ['2w']))
        result = assist_trade_request(self.data, {**self.payload, 'instruction': 'make this trade work'})
        for row in result['results']:
            manual = self.evaluate(**row['proposal'], strategy='REBUILD')
            self.assertEqual(row['evaluation'], manual)
            self.assertNotIn(manual['recommendation'], ('REJECT', 'NOT WORTH IT'))

    def test_released_client_renders_rejection_at_supported_phone_widths(self):
        from tests import test_trade_decision_http_browser as browser_fixtures
        harness = browser_fixtures.DecisionHTTPBrowserTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        harness.data, harness.f = self.data, self.publisher
        self.enterContext(patch('services.trade_intelligence._trade_projection_service',
                                return_value=self.publisher.reader))
        self.enterContext(patch('src.core.projection_intelligence.projection_service',
                                self.publisher.reader))
        measurements = []
        for width, height in ((320, 432), (375, 667), (390, 844)):
            with self.subTest(width=width), harness.browser(width, height) as page:
                harness.ready(page)
                page.select_option('#trade-partner', '2')
                page.select_option('#trade-strategy', 'REBUILD')
                harness.select(page, 'sent', '1q')
                harness.select(page, 'received', '2w')
                page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                page.get_by_text('REJECT', exact=True).first.wait_for()
                e = harness.responses[-1]['evaluation']
                self.assert_unfavorable(e)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                measurements.append({'width': width, 'height': height,
                    'label': e['recommendation'], 'eligible': e['generated_trade_eligible'],
                    'values': e['values'], 'mean_weekly_delta': e['recommendation_trace']['production_evidence']['mean_weekly_delta'],
                    'document_width': page.evaluate('document.documentElement.scrollWidth')})
        target = os.environ.get('DTOS_TRADE_ENDORSEMENT_EVIDENCE')
        if target:
            Path(target).write_text(json.dumps(measurements, indent=2))


if __name__ == '__main__':
    unittest.main()
