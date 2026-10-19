"""Reserve-production decisions over actual publications and Trade HTTP paths.

All scores and prices are disposable controlled evidence, not live claims.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import unittest

from routes.trades import create_trades_router
from services.trade_intelligence import (
    assist_trade_request, build_trade_workspace, evaluate_trade_request, generate_trade_workflow,
)
from src.core.intelligence.team_strength import prepare_for_data
from src.core.projection_intelligence.sleeper_provider import freshness_state
from src.core.trade_intelligence.package_quality import package_profile
from tests import test_capital_strategy_reconciliation as capital
from tests import test_trade_discovery_repair as discovery
from tests import test_trade_endorsement_integrity as integrity
from tests import test_trade_workspace_batch1 as boundary


class ReserveQualityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = capital.CapitalStrategyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.data = self.fixture.data
        for team in self.data['teams']:
            for player in team['players']:
                player['status'] = 'Active'
        self.fixture.points.update(a=50, b=40, e=0, c=60, d=1, f=0)
        self.fixture.publish()

    def evaluate(self, sent=('b',), received=('d',), strategy='REBUILD'):
        return self.fixture.evaluate(list(sent), list(received), intent=strategy)

    def package(self, evaluation, side='active'):
        return evaluation['dimensions']['package_quality'][side]

    def quality(self, evaluation, side='active'):
        return self.package(evaluation, side)['reserve_quality']

    def assert_reserve_cost(self, evaluation):
        self.assertNotIn('No material downside identified', evaluation['major_drawback'])
        self.assertRegex(evaluation['major_drawback'].lower(), r'reserve|replacement')
        self.assertTrue(self.quality(evaluation)['material_loss'])

    def test_reported_equal_slot_40_to_1_loss_cannot_claim_no_downside(self):
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(strategy=strategy):
                e = self.evaluate(strategy=strategy)
                self.assertEqual(e['lineup_impact']['active']['delta'], 0)
                self.assertEqual(e['values']['sent'], e['values']['received'])
                self.assertEqual(set(self.package(e)['reserve_slot_changes'].values()), {0})
                # Check the actual old misleading wording before inspecting the
                # additive DTO, so a before-run captures the user-facing defect.
                self.assertNotIn('No material downside identified', e['major_drawback'])
                self.assert_reserve_cost(e)
                for row in self.package(e)['reserve_quality_by_week'].values():
                    self.assertEqual((row['pre_points'], row['post_points'], row['delta']),
                                     (40, 1, -39))
                    self.assertEqual(row['pre_slots'], row['post_slots'])
                    self.assertEqual(row['availability'], 'supported')

    def test_supported_contender_window_resolves_existing_win_now_strategy(self):
        self.data['teams'][0].pop('strategy', None)
        workspace = build_trade_workspace(self.data, 1)
        workspace['competitive_windows'] = {'1': {
            'classification': 'Contender',
            'generation': self.data['team_strength']['semantic_generation']}}
        e = evaluate_trade_request(self.data, {'active_roster_id': 1,
            'partner_roster_id': 2, 'assets_sent': ['b'], 'assets_received': ['d']},
            workspace=workspace, projection_reader=self.fixture.reader)['evaluation']
        self.assertEqual(e['recommendation_trace']['manager_strategy'], {
            'strategy': 'WIN NOW', 'source': 'canonical_competitive_window'})
        self.assert_reserve_cost(e)

    def test_authenticated_http_same_count_loss_is_disclosed(self):
        auth = boundary.AuthenticatedTradeBoundaryTests()
        auth.setUp()
        self.addCleanup(auth.doCleanups)
        app = auth.client.app
        app.router.routes.clear()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(),
            require_data=lambda: self.data, page=lambda title, body: body))
        with patch('services.trade_intelligence._trade_projection_service',
                   return_value=self.fixture.reader), auth.client as client:
            context = client.get('/api/trades/workspace').json()['workspace_context']
            response = client.post('/api/trades/evaluate', json={
                'active_roster_id': 1, 'partner_roster_id': 2,
                'assets_sent': ['b'], 'assets_received': ['d'], 'strategy': 'REBUILD',
                'workspace_context': context}, headers={'X-CSRF-Token': auth.csrf})
            self.assertEqual(response.status_code, 200, response.text)
            e = response.json()['evaluation']
            self.assertNotIn('No material downside identified', e['explanation_html'])
            self.assert_reserve_cost(e)
            self.assertEqual(self.quality(e)['mean_weekly_delta'], -39)
            self.assertRegex(e['decision_context']['main_cost'].lower(), r'reserve|replacement')

    def test_equal_counts_distinguish_quality_gain_and_loss(self):
        loss = self.evaluate()
        self.fixture.points.update(b=1, d=40)
        self.fixture.publish()
        gain = self.evaluate()
        self.assertEqual(self.package(loss)['reserve_slot_changes'],
                         self.package(gain)['reserve_slot_changes'])
        self.assertEqual(self.quality(loss)['mean_weekly_delta'], -39)
        self.assertEqual(self.quality(gain)['mean_weekly_delta'], 39)
        self.assertTrue(self.quality(gain)['material_gain'])
        self.assertFalse(self.quality(loss)['material_gain'])
        self.assertEqual(gain['lineup_impact']['active']['delta'], 0)

    def test_mean_uses_unique_weeks_not_overlapping_horizon_totals(self):
        e = self.evaluate()
        quality = self.quality(e)
        self.assertEqual(quality['mean_weekly_delta'], -39)
        self.assertEqual(len(self.package(e)['reserve_quality_by_week']), 4)
        self.assertEqual(quality['weeks_counted_once'], [2, 3, 4, 5])

    def test_other_week_gains_do_not_hide_a_material_replacement_loss(self):
        for week, rows in self.fixture.payloads.items():
            for row in rows:
                if row['player_id'] == 'd':
                    row['stats']['pass_yd'] = 30 if week == 2 else 60
        self.fixture.reader.publish_horizon(self.fixture.payloads, data=self.data,
            league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.fixture.reader, self.data)
        e = self.evaluate(strategy='WIN NOW')
        self.assertEqual(self.quality(e)['mean_weekly_delta'], 5)
        self.assertTrue(self.quality(e)['material_loss'])
        self.assertFalse(self.quality(e)['material_gain'])
        self.assertEqual(self.quality(e)['loss_weeks'], [2])
        self.assertIn('supported weeks 2', e['major_drawback'])
        self.assertNotIn('No material downside identified', e['major_drawback'])

    def test_supported_consolidation_keeps_material_starter_gain_with_depth_cost(self):
        self.fixture.points.update(a=20, b=14, e=13, c=28, d=3, f=4)
        self.fixture.prices(a=125, b=125, c=250)
        self.fixture.publish()
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(strategy=strategy):
                e = self.evaluate(sent=('a', 'b'), received=('c',), strategy=strategy)
                self.assertEqual(e['lineup_impact']['active']['delta'], 8)
                self.assertEqual(self.package(e)['assessment'], 'SUPPORTED CONSOLIDATION')
                self.assertEqual(e['recommendation'], 'WORTH PURSUING')
                self.assertEqual(self.quality(e)['mean_weekly_delta'], -1)
                self.assertRegex(e['major_drawback'].lower(), r'reserve|replacement')

    def test_three_strong_superflex_qbs_keep_meaningful_third_qb_strength(self):
        self.data['league']['roster_positions'] = ['QB', 'SUPER_FLEX'] + ['BN'] * 6
        self.fixture.points.update(a=30, b=29, e=28, c=27, d=26, f=25)
        self.fixture.publish()
        e = self.evaluate(sent=('e',), received=('f',), strategy='WIN NOW')
        self.assertEqual(e['lineup_impact']['active']['delta'], 0)
        self.assertEqual(self.quality(e)['mean_weekly_delta'], -3)
        self.assert_reserve_cost(e)
        for row in self.package(e)['reserve_quality_by_week'].values():
            self.assertEqual((row['pre_points'], row['post_points']), (28, 25))

    def test_flex_superflex_replacements_follow_actual_legal_slots(self):
        self.data['league']['roster_positions'] = ['QB', 'FLEX', 'SUPER_FLEX'] + ['BN'] * 8
        positions = {'a': 'QB', 'b': 'RB', 'e': 'WR', 'c': 'QB', 'd': 'RB', 'f': 'WR'}
        for team in self.data['teams']:
            for player in team['players']:
                player['position'] = positions[player['id']]
                self.data['players'][player['id']]['position'] = player['position']
        self.fixture.points.update(a=30, b=25, e=24, c=35, d=26, f=27)
        for rid, pid, position, points in ((1, 'g', 'QB', 20), (1, 'h', 'RB', 19),
                (1, 'i', 'WR', 18), (2, 'j', 'QB', 15), (2, 'k', 'RB', 2),
                (2, 'l', 'WR', 1)):
            self.data['teams'][rid - 1]['players'].append({'id': pid, 'name': pid,
                'position': position, 'status': 'Active', 'roster_slot': 'Bench'})
            self.data['players'][pid] = {'position': position, 'full_name': pid, 'age': 25}
            self.fixture.points[pid] = points
        self.fixture.prices()
        self.fixture.publish()
        e = self.evaluate(sent=('h',), received=('l',))
        self.assertEqual(e['lineup_impact']['active']['delta'], 0)
        self.assertEqual(self.quality(e)['mean_weekly_delta'], -18)
        for row in self.package(e)['reserve_quality_by_week'].values():
            self.assertEqual((row['pre_points'], row['post_points']), (57, 39))
            self.assertEqual((row['pre_slots'], row['post_slots']), (3, 3))
        for week in e['multi_horizon_impact']['sides']['active']['weekly'].values():
            for state in ('pre', 'post'):
                entries = week[state]['reserve_capacity']['entries']
                self.assertEqual(len({row['asset_id'] for row in entries}), 3)
                for row in entries:
                    if row['slot'] == 'QB':
                        self.assertEqual(row['position'], 'QB')
                    if row['slot'] == 'FLEX':
                        self.assertIn(row['position'], ('RB', 'WR', 'TE'))

    def test_unavailable_and_ir_players_are_not_replacement_strength(self):
        for status, roster_slot in (('Out', 'Bench'), ('Inactive', 'Bench'),
                                    ('Retired', 'Bench'), ('Active', 'IR')):
            with self.subTest(status=status, roster_slot=roster_slot):
                player = next(p for p in self.data['teams'][0]['players'] if p['id'] == 'b')
                player.update(status=status, roster_slot=roster_slot)
                self.data['players']['b']['status'] = status
                self.fixture.publish()
                e = self.evaluate(sent=('e',), received=('f',))
                for row in self.package(e)['reserve_quality_by_week'].values():
                    self.assertEqual(row['pre_points'], 0)
                    self.assertEqual(row['post_points'], 0)
                self.assertFalse(self.quality(e)['material_gain'])

    def test_uncertain_replacement_status_remains_provisional(self):
        for status in ('Questionable', 'Doubtful', 'Unknown'):
            with self.subTest(status=status):
                player = next(p for p in self.data['teams'][0]['players'] if p['id'] == 'b')
                player['status'] = status
                self.data['players']['b']['status'] = status
                self.fixture.publish()
                e = self.evaluate()
                self.assert_reserve_cost(e)
                for row in self.package(e)['reserve_quality_by_week'].values():
                    self.assertEqual(row['conclusion_state'], 'provisional')
                    self.assertTrue(row['limitations'])

    def test_weak_reserve_quantity_does_not_establish_quality_gain(self):
        self.fixture.points.update(b=1, d=1)
        for rid, pid in ((1, 'weak_one'), (1, 'weak_two'), (2, 'weak_three')):
            team = self.data['teams'][rid - 1]
            team['players'].append({'id': pid, 'name': pid, 'position': 'QB',
                                    'status': 'Active', 'roster_slot': 'Bench'})
            self.data['players'][pid] = {'position': 'QB', 'full_name': pid, 'age': 25}
            self.fixture.points[pid] = 0
        self.fixture.prices()
        self.fixture.publish()
        e = self.evaluate()
        self.assertEqual(self.quality(e)['mean_weekly_delta'], 0)
        self.assertFalse(self.quality(e)['material_gain'])
        self.assertFalse(e['generated_trade_eligible'])

    def test_genuine_zero_is_supported_reserve_production(self):
        self.fixture.points.update(b=0, d=0)
        self.fixture.publish()
        e = self.evaluate()
        self.assertEqual(self.quality(e)['mean_weekly_delta'], 0)
        for row in self.package(e)['reserve_quality_by_week'].values():
            self.assertEqual((row['pre_points'], row['post_points'], row['delta']), (0, 0, 0))
            self.assertEqual(row['availability'], 'supported')

    def test_missing_reserve_projection_is_unavailable_not_zero(self):
        self.fixture.points.pop('d')
        self.fixture.publish()
        e = self.evaluate()
        self.assertEqual(e['lineup_impact']['active']['delta'], 0)
        self.assertIsNone(self.quality(e)['mean_weekly_delta'])
        self.assertFalse(self.quality(e)['complete'])
        self.assertIsNone(e['recommendation'])
        self.assertFalse(e['generated_trade_eligible'])
        self.assertNotIn('SUPPORTED_MARKET_LINEUP_AND_DEPTH_PARITY', e['reason_codes'])
        for row in self.package(e)['reserve_quality_by_week'].values():
            self.assertIsNone(row['delta'])
            self.assertNotEqual(row['availability'], 'supported')
        self.assertNotIn('No material downside identified', e['major_drawback'])

    def test_material_starter_gain_with_unknown_reserve_cost_is_not_clean_smash(self):
        self.fixture.points.pop('e')
        self.fixture.publish()
        e = self.evaluate(sent=('a',), received=('c',), strategy='WIN NOW')
        self.assertEqual(e['lineup_impact']['active']['delta'], 10)
        self.assertFalse(self.quality(e)['complete'])
        self.assertIsNone(self.quality(e)['mean_weekly_delta'])
        self.assertEqual(e['recommendation'], 'WORTH PURSUING')
        self.assertIn('MATERIAL_PRODUCTION_GAIN_WITH_DISCLOSED_ROSTER_COST', e['reason_codes'])
        self.assertNotIn('SUPPORTED_HORIZON_BENEFIT_WITHOUT_DEPTH_OR_CAPACITY_LOSS',
                         e['reason_codes'])
        self.assertIn('Reserve replacement production is unavailable', e['major_drawback'])

    def test_counterparty_unknown_reserve_quality_cannot_be_strong(self):
        case = integrity.EndorsementIntegrityTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.configure(sent=400, received=400, delta=4, spare_qb=False)
        partner = case.data['teams'][1]
        for pid, position, points in (('2wc', 'WR', 3), ('2qc', 'QB', None)):
            partner['players'].append({'id': pid, 'name': pid, 'position': position,
                                      'status': 'Active', 'roster_slot': 'Bench'})
            case.data['players'][pid] = {'full_name': pid, 'position': position, 'age': 25}
            if points is not None:
                case.publisher.points[pid] = points
        case.publisher.prices(**{'1q': 400, '2w': 400})
        case.publisher.publish()
        e = case.evaluate(strategy='RETOOL')
        partner_strategy = e['dimensions']['strategic_fit']['partner']
        self.assertEqual(partner_strategy['production_evidence']['mean_weekly_delta'], 8)
        self.assertEqual(set(partner_strategy['reserve_slot_changes'].values()), {0})
        self.assertFalse(partner_strategy['reserve_quality']['complete'])
        counterparty = e['dimensions']['counterparty_plausibility']
        self.assertNotEqual(counterparty['assessment'], 'STRONG')
        self.assertNotIn('COUNTERPARTY_LINEUP_AND_MARKET_GAIN', counterparty['reason_codes'])

    def publish_source_clock(self, observed):
        for rows in self.fixture.payloads.values():
            for row in rows:
                row['updated_at'] = observed.isoformat()
        self.fixture.reader.publish_horizon(self.fixture.payloads, data=self.data,
            league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.fixture.reader, self.data)

    def test_warm_reserve_source_qualification_ages_without_solving(self):
        observed = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=1)
        self.publish_source_clock(observed)
        impact = self.evaluate()['multi_horizon_impact']['sides']['active']
        original = deepcopy(impact)
        snapshot = deepcopy(self.fixture.reader.snapshot())
        for seconds, expected in ((0, 'Fresh'), (3600, 'Aging'), (21600, 'Stale')):
            with self.subTest(seconds=seconds), \
                    patch('src.core.trade_intelligence.package_quality.freshness_state',
                          side_effect=lambda clock: freshness_state(clock,
                              now=observed + timedelta(seconds=seconds))), \
                    patch('src.core.intelligence.team_strength.optimal_legal_lineup',
                          side_effect=AssertionError('source-clock display reran a lineup solve')):
                quality = package_profile((), (), impact)['reserve_quality']
                self.assertEqual(quality['projection_freshness'], [expected])
                self.assertEqual(quality['mean_weekly_delta'], -39)
                self.assertEqual(quality['conclusion_state'],
                                 'current' if seconds == 0 else 'provisional')
        self.assertEqual(impact, original)
        self.assertEqual(self.fixture.reader.snapshot(), snapshot)

    def test_future_source_clock_does_not_claim_fresh_replacement_evidence(self):
        self.publish_source_clock(datetime.now(timezone.utc) + timedelta(hours=1))
        e = self.evaluate()
        self.assertEqual(self.quality(e)['projection_freshness'], ['Unavailable'])
        self.assertEqual(self.quality(e)['conclusion_state'], 'provisional')
        self.assert_reserve_cost(e)

    def test_evaluation_does_not_mutate_projection_or_neutral_market_evidence(self):
        before = deepcopy(self.data)
        snapshot = deepcopy(self.fixture.reader.snapshot())
        values = []
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            values.append(self.evaluate(strategy=strategy)['values'])
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[1], values[2])
        self.assertEqual(self.data, before)
        self.assertEqual(self.fixture.reader.snapshot(), snapshot)

    def test_severe_overpay_and_missing_market_guards_remain_intact(self):
        case = integrity.EndorsementIntegrityTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        rejected = case.evaluate()
        self.assertEqual(rejected['recommendation'], 'REJECT')
        self.assertFalse(rejected['generated_trade_eligible'])
        case.configure(sent=500, received=400, delta=5)
        case.data['market_data']['providers']['FantasyCalc'].pop('1q')
        missing = case.evaluate()
        self.assertFalse(missing['generated_trade_eligible'])
        self.assertIn('not an endorsement', missing['decision_context']['qualification'])
        self.assertIn('Market cost cannot be fully assessed', missing['decision_context']['main_cost'])

    def test_discovery_and_adjust_publish_the_same_reserve_evidence_as_builder(self):
        case = discovery.DiscoveryRepairTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        for team in case.data['teams']:
            for player in team['players']:
                player['status'] = 'Active'
        case.fixture.publish()
        rows = []
        for workflow, asset in (('trade_for', '2w'), ('shop', '1q'), ('recommended', None)):
            result = generate_trade_workflow(case.data, {'workflow': workflow,
                'active_roster_id': 1, 'asset_id': asset, 'strategy': 'RETOOL'})
            self.assertTrue(result['results'], (workflow, result.get('search_evidence')))
            rows.extend(result['results'])
        adjusted = assist_trade_request(case.data, {**case.proposal(),
            'instruction': 'make this trade work'})
        self.assertTrue(adjusted['results'], adjusted)
        rows.extend(adjusted['results'])
        for row in rows:
            direct = evaluate_trade_request(case.data, {**row['proposal'], 'strategy': 'RETOOL'},
                projection_reader=case.fixture.reader)['evaluation']
            self.assertEqual(row['evaluation']['dimensions']['package_quality'],
                             direct['dimensions']['package_quality'])
            self.assertEqual(row['evaluation']['generated_trade_eligible'],
                             direct['generated_trade_eligible'])


if __name__ == '__main__':
    unittest.main()
