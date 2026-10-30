"""Disposable exact ownership/capacity controls; no trade-quality shortcuts."""
from copy import deepcopy
from dataclasses import replace
from itertools import combinations
import json
import os
from pathlib import Path
from time import perf_counter
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from tests import test_capital_strategy_reconciliation as capital


def evidence(name, value):
    if os.getenv('DTOS_REBUILD_SPACE_EVIDENCE'):
        root = Path(os.environ['DTOS_REBUILD_SPACE_EVIDENCE'])
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + '.json')).write_text(json.dumps(value, indent=2))


class RebuildRosterSpaceTests(unittest.TestCase):
    def fixture(self, slots=3):
        f = capital.CapitalStrategyTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.data['league']['roster_positions'] = ['QB'] + ['BN'] * (slots - 1)
        f.prices(a=350)
        f.publish()
        self.enterContext(patch('services.trade_intelligence._trade_projection_service', return_value=f.reader))
        return f

    def test_known_full_roster_blockers_do_not_consume_bilateral_evaluation_budget(self):
        f = self.fixture()
        original = trade.evaluate_trade_request
        observed = []
        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result
        with patch.object(trade, 'evaluate_trade_request', side_effect=capture):
            result = trade.generate_trade_workflow(f.data, dict(active_roster_id=1, workflow='recommended', strategy='REBUILD'))
        unresolved = [r for r in observed if r['evaluation']['legality']['execution_status'] == 'REQUIRES ROSTER RESOLUTION']
        self.assertEqual(len(unresolved), 0, f'{len(unresolved)} known capacity blockers consumed expensive evaluations')
        self.assertGreater(result['search_evidence']['construction_admission']['roster_capacity_rejected_checks'], 0)
        self.assertLessEqual(result['search_evidence']['full_evaluations'], 180)
        self.assertGreater(result['count'], 0)

    def test_balancing_player_and_exact_acquired_pick_reach_unchanged_evaluator(self):
        f = self.fixture()
        payload = dict(active_roster_id=1, partner_roster_id=2, assets_sent=['a'],
                       assets_received=['d', '2028-R1-4'], strategy='REBUILD')
        manual = trade.evaluate_trade_request(f.data, payload, projection_reader=f.reader)['evaluation']
        self.assertEqual(manual['recommendation'], 'WORTH PURSUING')
        self.assertTrue(manual['generated_trade_eligible'])
        observed = []
        original = trade.evaluate_trade_request
        def capture(*args, **kwargs):
            row = original(*args, **kwargs)
            if set(row['proposal']['assets_sent']) == {'a'} and set(row['proposal']['assets_received']) == {'d', '2028-R1-4'}:
                observed.append(row['evaluation'])
            return row
        before = deepcopy(f.data)
        with patch.object(trade, 'evaluate_trade_request', side_effect=capture):
            result = trade.generate_trade_workflow(f.data, dict(active_roster_id=1, workflow='recommended', strategy='REBUILD'))
        self.assertTrue(observed)
        for row in observed:
            for key in ('market_evidence', 'multi_horizon_impact', 'recommendation', 'generated_trade_eligible', 'legality'):
                self.assertEqual(row[key], manual[key])
        self.assertEqual(f.data, before)
        evidence('balanced-mixed-witness', {'proposal': payload, 'evaluation': manual,
            'reached_evaluation': True, 'search': result['search_evidence'], 'inputs_unchanged': True})

    def test_capacity_preflight_agrees_with_actual_horizon_simulation_for_every_package(self):
        from services.trade_candidate_admission import admit_workspace
        from src.core.trade_intelligence.horizon_impact import evaluate_horizon_impact
        from src.core.trade_intelligence.models import TradeProposal
        f = self.fixture()
        checks = 0
        for positions in (['QB', 'BN', 'BN'], ['QB', 'BN', 'BN', 'BN'], ['QB', 'SUPER_FLEX', 'BN']):
            f.data['league']['roster_positions'] = positions
            # IR and taxi do not consume active capacity; sending one does not
            # free an active spot. An incoming reserve is still hypothetical active.
            f.data['teams'][0]['players'][1]['roster_slot'] = 'IR'
            f.data['teams'][1]['players'][2]['roster_slot'] = 'Taxi'
            f.publish()
            w = admit_workspace(f.data, trade.build_trade_workspace(f.data, 1), f.reader.snapshot())
            admission = w['candidate_admission']
            self.assertTrue(admission.capacity_supported)
            outgoing, incoming = w['pools'][1][:4], w['pools'][2][:4]
            for sent_n, received_n in ((1, 1), (1, 2), (2, 1)):
                for sent in combinations(outgoing, sent_n):
                    for received in combinations(incoming, received_n):
                        impact = evaluate_horizon_impact(f.data, TradeProposal(1, 2, sent, received, 'control'), f.reader)
                        self.assertEqual(impact['availability'], 'supported')
                        executable = all(side['roster_capacity']['additional_spots_to_resolve'] == 0 for side in impact['sides'].values())
                        self.assertEqual(admission.allows(1, 2, sent, received), executable)
                        checks += 1
        evidence('capacity-equivalence', {'actual_horizon_comparisons': checks, 'all_equal': True,
            'ir_taxi_outgoing_and_incoming': True, 'superflex_and_bench_rules': True})

    def test_conflicting_pick_player_and_pool_ownership_are_removed_before_discovery(self):
        from services.trade_candidate_admission import admit_workspace
        f = self.fixture()
        w = trade.build_trade_workspace(f.data, 1)
        wrong = next(a for a in w['pools'][2] if a.kind == 'pick')
        w['pools'][2] = tuple(replace(a, current_owner_id=1) if a is wrong else a for a in w['pools'][2])
        # Conflicting prepared pools must not be resolved by last-write-wins.
        w['pools'][2] += (replace(w['pools'][1][0], source_roster_id=2),)
        admitted = admit_workspace(f.data, w, f.reader.snapshot())
        self.assertNotIn('a', {a.asset_id for pool in admitted['pools'].values() for a in pool})
        self.assertNotIn(wrong.asset_id, {a.asset_id for a in admitted['pools'][2]})
        self.assertGreaterEqual(admitted['candidate_admission'].summary()['ownership_rejected_assets'], 3)
        self.assertEqual(next(a for a in admitted['pools'][1] if a.kind == 'pick').current_owner_id, 1)

    def test_missing_or_changed_projection_scope_never_infers_capacity_readiness(self):
        from services.trade_candidate_admission import admit_workspace
        f = self.fixture()
        for snapshot in (None, {**f.reader.snapshot(), 'league_id': 'foreign'},
                         {**f.reader.snapshot(), 'scoring_profile_id': 'incompatible'}):
            w = admit_workspace(f.data, trade.build_trade_workspace(f.data, 1), snapshot)
            admission = w['candidate_admission']
            self.assertFalse(admission.capacity_supported)
            self.assertTrue(admission.allows(1, 2, (w['pools'][1][3],), (w['pools'][2][0],)))
            self.assertEqual(admission.summary()['roster_capacity_checks'], 0)

    def test_unconfirmed_exact_pick_is_not_replaced_and_zero_is_not_a_missing_price(self):
        from services.trade_candidate_admission import admit_workspace
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        pick = next(a for a in workspace['pools'][2] if a.kind == 'pick')
        for fields in ({'current_owner_id': None}, {'original_roster_id': None}, {'season': None},
                       {'asset_id': '2028-R1-999'}, {'current_owner_id': 1}):
            altered = {**workspace, 'pools': {**workspace['pools'], 2: tuple(replace(a, **fields) if a is pick else a for a in workspace['pools'][2])}}
            admitted = admit_workspace(f.data, altered, f.reader.snapshot())
            self.assertEqual(sum(a.kind == 'pick' for a in admitted['pools'][2]), 2)
            self.assertEqual(admitted['candidate_admission'].summary()['ownership_rejected_assets'], 1)
        for price in (0, None):
            altered = {**workspace, 'pools': {**workspace['pools'], 2: tuple(replace(a, trade_value=price, market_value=price) if a is pick else a for a in workspace['pools'][2])}}
            admitted = admit_workspace(f.data, altered, f.reader.snapshot())
            self.assertEqual(next(a for a in admitted['pools'][2] if a.asset_id == pick.asset_id).trade_value, price)

    def test_genuine_zero_results_name_capacity_without_assuming_drops_or_acceptance(self):
        f = self.fixture()
        w = trade.build_trade_workspace(f.data, 1)
        all_ids = {a.asset_id for pool in w['pools'].values() for a in pool}
        report = trade.generate_trade_workflow(f.data, dict(active_roster_id=1, workflow='recommended',
            strategy='REBUILD', excluded_assets=sorted(all_ids - {'a', '2028-R1-4'})))
        self.assertEqual(report['count'], 0)
        self.assertEqual(report['search_evidence']['full_evaluations'], 0)
        self.assertGreater(report['search_evidence']['construction_admission']['roster_capacity_rejected_checks'], 0)
        self.assertIn('extra roster space', report['quiet_state'])
        self.assertIn('not assume a drop', report['quiet_state'])
        self.assertFalse(report['zero_result_guidance']['recommendation'])
        self.assertIsNone(report['zero_result_guidance']['acceptance_probability'])
        for lead in report['zero_result_guidance']['shop_review_leads']:
            self.assertEqual(lead['assessment'], 'search_lead_not_a_qualified_offer')
        evidence('capacity-zero-result', report)

    def test_full_and_partial_rosters_all_strategies_keep_prices_slots_and_inputs(self):
        f = self.fixture()
        summaries = []
        for slots in (3, 4, 5):
            f.data['league']['roster_positions'] = ['QB'] + ['BN'] * (slots - 1)
            f.publish()
            before = deepcopy(f.data)
            for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
                result = trade.generate_trade_workflow(f.data, dict(active_roster_id=1, workflow='recommended', strategy=strategy))
                for row in result['results']:
                    self.assertEqual(row['evaluation']['legality']['execution_status'], 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER')
                    if row['search_result_type'] == 'CREDIBLE RECOMMENDATION':
                        self.assertTrue(row['evaluation']['generated_trade_eligible'])
                    else:
                        self.assertEqual(row['search_result_type'], 'OPTIONAL / LOWER-RANKED TRADE')
                self.assertLessEqual(result['search_evidence']['full_evaluations'], 180)
                self.assertEqual(f.data, before)
                summaries.append({'slots': slots, 'strategy': strategy, 'count': result['count'], 'search': result['search_evidence']})
        evidence('full-partial-strategies', summaries)

    def test_ordinary_candidate_admission_has_no_provider_solver_history_or_storage_work(self):
        from contextlib import ExitStack
        from services.trade_candidate_admission import admit_workspace
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        guards = ['services.sleeper.sleeper_get', 'src.core.projection_intelligence.service.ProjectionService.generate',
                  'src.core.fois.service.FOISService._generate_sync',
                  'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
                  'src.core.trade_intelligence.lineup.optimal_legal_lineup']
        before = deepcopy(f.data)
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in guards]
            for _ in range(3):
                admission = admit_workspace(f.data, workspace, f.reader.snapshot())['candidate_admission']
                self.assertTrue(admission.capacity_supported)
            self.assertFalse(any(spy.call_count for spy in spies))
        self.assertEqual(f.data, before)
        evidence('admission-call-counts', {'guarded_call_counts': dict.fromkeys(guards, 0), 'source_unchanged': True,
            'persistent_storage_added': 0, 'request_only': True})

    def test_veteran_heavy_and_young_core_mult_position_leagues_remain_bilateral(self):
        from src.core.intelligence.team_strength import prepare_for_data
        f = self.fixture()
        reports = []
        for league_id, age, starters in (
                ('veteran-rebuild', 34, ['QB', 'RB', 'WR', 'TE']),
                ('young-superflex', 23, ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPER_FLEX'])):
            scoring = {'pass_yd': .04, 'rush_yd': .1, 'rec_yd': .1, 'rec': 1}
            f.data['league'].update(league_id=league_id, roster_positions=starters + ['BN'] * (8-len(starters)), scoring_settings=scoring)
            f.data['scoring_settings'] = scoring
            f.data['players'] = {}
            f.points = {}
            for team in f.data['teams']:
                rid = team['roster_id']
                team['strategy'] = 'REBUILD' if rid == 1 else 'WIN NOW'
                team['players'] = []
                for position in ('QB', 'RB', 'WR', 'TE'):
                    for index in (0, 1):
                        pid = f'{rid}-{position}-{index}'
                        f.data['players'][pid] = {'full_name': f'Fixture {pid}', 'position': position,
                            'age': age if rid == 1 else 26}
                        team['players'].append({'id': pid, 'name': f'Fixture {pid}', 'position': position,
                                                'roster_slot': 'Starter' if index == 0 else 'Bench'})
                        f.points[pid] = (24 if position == 'QB' else 16) - index * 4 - (3 if rid == 2 else 0)
            f.prices(**{pid: 350 if pid.endswith('-0') else 180 for pid in f.points})
            payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week,
                        'player': {'position': f.data['players'][pid]['position']},
                        'stats': {('pass_yd' if '-QB-' in pid else 'rush_yd' if '-RB-' in pid else 'rec_yd'):
                                  points / (.04 if '-QB-' in pid else .1)}} for pid, points in f.points.items()]
                        for week in (2, 3, 4, 5)}
            f.reader.publish_horizon(payloads, data=f.data, league_id=league_id, season=2026, current_week=2)
            with patch('services.global_evidence.retained_global_evidence', return_value=None):
                prepare_for_data(f.reader, f.data)
            before = deepcopy(f.data)
            for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
                start = perf_counter()
                result = trade.generate_trade_workflow(f.data, dict(active_roster_id=1, workflow='recommended', strategy=strategy))
                self.assertTrue(result['search_evidence']['construction_admission']['capacity_evidence_supported'])
                self.assertEqual(result['search_evidence']['hard_invalid'], 0)
                self.assertLessEqual(result['search_evidence']['full_evaluations'], 180)
                self.assertEqual(f.data, before)
                reports.append({'league': league_id, 'own_age_control': age, 'strategy': strategy,
                    'seconds': perf_counter()-start, 'count': result['count'], 'search': result['search_evidence']})
        evidence('multi-position-leagues', reports)
