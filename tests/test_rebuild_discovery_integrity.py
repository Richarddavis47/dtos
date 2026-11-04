"""Source-compatible rebuilding discovery; qualification is never patched."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from services.recommended_trade_search import construct, discover
from src.core.intelligence import generate_proposals
from tests import test_capital_strategy_reconciliation as capital_controls


def evidence(name, value):
    if os.getenv('DTOS_REBUILD_DISCOVERY_EVIDENCE'):
        root = Path(os.environ['DTOS_REBUILD_DISCOVERY_EVIDENCE'])
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + '.json')).write_text(json.dumps(value, indent=2))


class RebuildDiscoveryIntegrityTests(unittest.TestCase):
    def fixture(self):
        f = capital_controls.CapitalStrategyTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        player = f.data['players'].pop('a')
        f.data['players']['z-veteran'] = dict(player, full_name='Veteran producer', age=32)
        for row in f.data['teams'][0]['players']:
            if row['id'] == 'a':
                row.update(id='z-veteran', name='Veteran producer')
        f.points['z-veteran'] = f.points.pop('a')
        f.data['league']['roster_positions'] = ['QB'] + ['BN'] * 16
        for i in range(9):
            pid = f'core-{i}'
            f.data['players'][pid] = {'position': 'QB', 'full_name': f'Young reserve {i}', 'age': 22}
            f.points[pid] = 7
            f.data['teams'][0]['players'].append({'id': pid, 'position': 'QB', 'name': f'Young reserve {i}', 'roster_slot': 'Bench'})
        f.prices(**{'z-veteran': 350, **{f'core-{i}': 350 for i in range(9)}})
        # These are fictional provider quotes, not forced canonical prices.
        # The full-population player normalizer yields 445/225; the compatible
        # exact second's quote is 220, making the witnessed package 445/445.
        for quote in f.data['market_data']['pick_quotes']['FantasyCalc']:
            if quote['round'] == 2:
                quote['value'] = 220 * 12
                quote['normalization_reference'].update(raw_value=float(220 * 12), normalized_value=220)
        f.publish()
        self.enterContext(patch('services.trade_intelligence._trade_projection_service', return_value=f.reader))
        return f

    def request(self, **updates):
        return dict(dict(active_roster_id=1, workflow='recommended', strategy='REBUILD'), **updates)

    def witness(self):
        return dict(active_roster_id=1, partner_roster_id=2, assets_sent=['z-veteran'],
                    assets_received=['c', '2028-R2-4'], strategy='REBUILD')

    def test_qualified_veteran_mixed_return_is_explored_without_changing_its_verdict(self):
        f = self.fixture()
        before = deepcopy(f.data)
        witness = trade.evaluate_trade_request(f.data, self.witness(), projection_reader=f.reader)['evaluation']
        self.assertEqual(witness['market_evidence']['sent']['total'], 445)
        self.assertEqual(witness['market_evidence']['received']['total'], 445)
        self.assertEqual(witness['recommendation'], 'WORTH PURSUING')
        self.assertTrue(witness['generated_trade_eligible'])
        self.assertEqual(witness['dimensions']['counterparty_plausibility']['assessment'], 'PLAUSIBLE')
        observed = []
        original = trade.evaluate_trade_request
        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result
        with patch.object(trade, 'evaluate_trade_request', side_effect=capture):
            result = trade.generate_trade_workflow(f.data, self.request())
        rows = [row for row in observed if set(row['proposal']['assets_sent']) == {'z-veteran'}
                and set(row['proposal']['assets_received']) == {'c', '2028-R2-4'}]
        self.assertTrue(rows, 'A qualified, supported mixed return was lost before evaluation.')
        for row in rows:
            for key in ['market_evidence', 'lineup_impact', 'multi_horizon_impact', 'recommendation', 'generated_trade_eligible']:
                self.assertEqual(row['evaluation'][key], witness[key])
        self.assertLessEqual(result['search_evidence']['full_evaluations'], 180)
        self.assertEqual(f.data, before)
        evidence('qualified-mixed-return', {'canonical_sent': 445, 'canonical_received': 445,
            'witness_evaluated': True, 'unchanged_verdict': witness['recommendation'],
            'counterparty': 'PLAUSIBLE', 'search': result['search_evidence'], 'inputs_unchanged': True})

    def test_both_thesis_anchors_survive_selection_and_disaggregation_is_covered(self):
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        trade._requested_strategy(workspace, self.request())
        diagnostics = {}
        rows = construct(workspace, {'partner_id': 2, 'send': {'asset_id': 'z-veteran'},
            'receive': {'asset_id': '2028-R2-4'}}, set(), set(), search_phase=1, search_diagnostics=diagnostics)
        self.assertLessEqual(len(rows), 6)
        self.assertTrue(rows)
        for row in rows:
            self.assertIn('z-veteran', [a.asset_id for a in row.assets_sent])
            self.assertIn('2028-R2-4', [a.asset_id for a in row.assets_received])
        self.assertTrue(any({a.asset_id for a in row.assets_sent} == {'z-veteran'}
            and {a.asset_id for a in row.assets_received} == {'c', '2028-R2-4'} for row in rows))

    def test_rebuild_covers_multiple_exact_capital_returns_with_existing_thesis_bounds(self):
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        trade._requested_strategy(workspace, self.request())
        reader = trade._search_reader(f.data, self.request(), trade._trade_search_boundary(f.data))
        result = discover(f.data, workspace, reader, set(), set(), max_theses=24, search_phase=1)
        ids = {row['receive']['asset_id'] for row in result['theses']
               if row['type'] == 'CAPITAL_SUPPORTED_SLOT_OPPORTUNITY' and row['send']['asset_id'] == 'z-veteran'}
        self.assertTrue({'2028-R1-4', '2028-R2-4'}.issubset(ids))
        self.assertLessEqual(len(result['theses']), 24)

    def test_unseeded_strategies_share_prices_and_projections_not_selection_policy(self):
        f = self.fixture()
        before = deepcopy(f.data)
        reports = {}
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            reports[strategy] = trade.generate_trade_workflow(f.data, self.request(strategy=strategy))
            self.assertLessEqual(reports[strategy]['search_evidence']['full_evaluations'], 180)
            self.assertEqual(f.data, before)
        evaluations = [trade.evaluate_trade_request(f.data, dict(self.witness(), strategy=strategy), projection_reader=f.reader)['evaluation']
                       for strategy in reports]
        for report in evaluations[1:]:
            self.assertEqual(report['market_evidence'], evaluations[0]['market_evidence'])
            self.assertEqual(report['multi_horizon_impact'], evaluations[0]['multi_horizon_impact'])
        self.assertNotEqual(evaluations[0]['recommendation'], evaluations[-1]['recommendation'])
        evidence('unseeded-strategies', {key: {'search': value['search_evidence'], 'count': value['count'],
            'packages': [r['proposal'] for r in value['results']]} for key, value in reports.items()})

    def test_poor_veteran_return_stays_rejected_despite_rebuild_intent(self):
        f = self.fixture()
        for quote in f.data['market_data']['pick_quotes']['FantasyCalc']:
            if quote['round'] == 2:
                quote['value'] = 1200
                quote['normalization_reference'].update(raw_value=1200.0, normalized_value=100)
        f.publish()
        report = trade.evaluate_trade_request(f.data, self.witness(), projection_reader=f.reader)['evaluation']
        self.assertEqual(report['market_evidence']['sent']['total'], 445)
        self.assertEqual(report['market_evidence']['received']['total'], 325)
        self.assertEqual(report['recommendation'], 'NOT WORTH IT')
        self.assertFalse(report['generated_trade_eligible'])

    def test_zero_results_explain_observed_cost_without_endorsing_search_leads(self):
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        all_ids = {a.asset_id for pool in workspace['pools'].values() for a in pool}
        result = trade.generate_trade_workflow(f.data, self.request(
            excluded_assets=sorted(all_ids - {'z-veteran', '2028-R4-4'})))
        self.assertEqual(result['count'], 0)
        guidance = result['zero_result_guidance']
        self.assertFalse(guidance['recommendation'])
        self.assertIsNone(guidance['acceptance_probability'])
        self.assertIn('No bilateral recommendation', result['quiet_state'])
        self.assertIn('not qualified offers', result['quiet_state'])
        self.assertTrue(guidance['assessed_limit_counts']['strategically_rejected'])
        for row in result['exploratory_results']:
            self.assertFalse(row['evaluation']['generated_trade_eligible'])
        evidence('zero-results', result)

    def test_protection_and_exact_pick_exclusion_survive_expanded_search(self):
        f = self.fixture()
        result = trade.generate_trade_workflow(f.data, self.request(
            protected_assets=['z-veteran'], excluded_assets=['2028-R2-4']))
        for row in result['results'] + result['exploratory_results']:
            self.assertNotIn('z-veteran', row['proposal']['assets_sent'])
            self.assertNotIn('2028-R2-4', row['proposal']['assets_received'])
        self.assertIn('2028-R2-4', {a.asset_id for a in trade.build_trade_workspace(f.data, 1)['pools'][2]})

    def test_dual_anchor_never_replaces_missing_price_with_zero_or_another_asset(self):
        from dataclasses import replace
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        outgoing, incoming = workspace['pools'][1], workspace['pools'][2]
        target = next(a for a in outgoing if a.asset_id == 'z-veteran')
        for value, expected in ((None, False), (0, True)):
            rows = generate_proposals(1, 2,
                tuple(replace(a, market_value=value, trade_value=value) if a is target else a for a in outgoing), incoming,
                required_sent_asset_id=target.asset_id, required_received_asset_id='2028-R2-4',
                construction_only=True, search_phase=1)
            self.assertEqual(bool(rows), expected)
            for row in rows:
                self.assertIn(target.asset_id, [a.asset_id for a in row.assets_sent])
                self.assertIn('2028-R2-4', [a.asset_id for a in row.assets_received])

    def test_generation_transition_cannot_publish_rebuild_recommendations(self):
        f = self.fixture()
        original = trade.evaluate_trade_request
        def transition(*args, **kwargs):
            result = original(*args, **kwargs)
            f.data['league']['scoring_settings']['pass_yd'] = 2
            return result
        with patch.object(trade, 'evaluate_trade_request', side_effect=transition):
            with self.assertRaises(trade.TradeInputError) as caught:
                trade.generate_trade_workflow(f.data, self.request())
        self.assertEqual(caught.exception.code, 'canonical_evidence_changed')

    def test_multiple_buyers_and_refresh_families_remain_bounded_and_deterministic(self):
        from tests import test_trade_discovery_repair as multi
        f = multi.DiscoveryRepairTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        first = trade.generate_trade_workflow(f.data, self.request())
        second = trade.generate_trade_workflow(f.data, self.request())
        self.assertGreaterEqual(first['search_evidence']['teams_searched'], 2)
        self.assertEqual([r['proposal'] for r in first['results']], [r['proposal'] for r in second['results']])
        families = [r['family_id'] for r in first['results']]
        refreshed = trade.generate_trade_workflow(f.data, self.request(excluded_recommendation_families=families))
        self.assertFalse(set(families) & {r['family_id'] for r in refreshed['results']})
        for report in (first, second, refreshed):
            self.assertLessEqual(report['search_evidence']['full_evaluations'], 180)
            for row in report['results']:
                self.assertTrue(row['workflow_eligibility']['eligible'])
        evidence('multiple-buyers', {'first': first['search_evidence'], 'refresh': refreshed['search_evidence']})

    def test_age_is_only_a_search_tiebreak_not_an_automatic_sale_or_price(self):
        f = self.fixture()
        baseline = trade.evaluate_trade_request(f.data, self.witness(), projection_reader=f.reader)['evaluation']
        f.data['players']['z-veteran']['age'] = 22
        f.publish()
        younger = trade.evaluate_trade_request(f.data, self.witness(), projection_reader=f.reader)['evaluation']
        for key in ('market_evidence', 'lineup_impact', 'recommendation', 'generated_trade_eligible'):
            self.assertEqual(baseline[key], younger[key])
        result = trade.generate_trade_workflow(f.data, self.request(protected_assets=['z-veteran']))
        for row in result['results']:
            self.assertNotIn('z-veteran', row['proposal']['assets_sent'])

    def test_incompatible_scoring_does_not_create_observed_capital_opportunities(self):
        f = self.fixture()
        f.data['league']['scoring_settings']['pass_yd'] = 2
        workspace = trade.build_trade_workspace(f.data, 1)
        trade._requested_strategy(workspace, self.request())
        reader = trade._search_reader(f.data, self.request(), trade._trade_search_boundary(f.data))
        report = discover(f.data, workspace, reader, set(), set(), search_phase=0)
        self.assertEqual(report['theses'], [])
        self.assertIn('COMPATIBLE_PREPARED_LINEUPS_UNAVAILABLE', report['limitations'])

    def test_other_league_superflex_uses_its_own_rules_and_exact_pick_owners(self):
        from src.core.intelligence.team_strength import prepare_for_data
        f = self.fixture()
        f.data['league'].update(league_id='league-two', roster_positions=['QB', 'SUPER_FLEX'] + ['BN'] * 16,
                               scoring_settings={'pass_yd': .5})
        f.reader.publish_horizon(f.payloads, data=f.data, league_id='league-two', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(f.reader, f.data)
        before = deepcopy(f.data)
        report = trade.generate_trade_workflow(f.data, self.request())
        self.assertEqual(f.reader.snapshot()['league_id'], 'league-two')
        self.assertGreater(report['search_evidence']['full_evaluations'], 0)
        workspace = trade.build_trade_workspace(f.data, 1)
        for row in report['results']:
            direct = trade.evaluate_trade_request(f.data, row['proposal'], projection_reader=f.reader)['evaluation']
            self.assertEqual(row['evaluation']['multi_horizon_impact'], direct['multi_horizon_impact'])
            self.assertEqual(row['evaluation']['recommendation'], direct['recommendation'])
            self.assertEqual(row['evaluation']['generated_trade_eligible'], direct['generated_trade_eligible'])
            self.assertTrue(row['workflow_eligibility']['eligible'])
            for rid, side in ((1, 'assets_sent'), (row['proposal']['partner_roster_id'], 'assets_received')):
                owned = {a.asset_id: a for a in workspace['pools'][rid]}
                for key in row['proposal'][side]:
                    self.assertIn(key, owned)
                    if owned[key].kind == 'pick':
                        self.assertEqual(owned[key].current_owner_id, rid)
                        self.assertNotEqual(owned[key].original_roster_id, rid)
        self.assertEqual(f.data, before)
