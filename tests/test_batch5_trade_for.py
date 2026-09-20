import unittest
from copy import deepcopy
from unittest.mock import patch

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request, generate_trade_workflow
from src.core.trade_intelligence.engine.trade_generator import generate_proposals
from tests.test_batch5_trade_strategy import asset, side
from tests.test_trade_intelligence import fixture_data


class TradeForTests(unittest.TestCase):
    def test_positive_workflow_keeps_fair_and_fewer_than_three(self):
        from src.core.trade_intelligence.models import TradeProposal
        data = fixture_data()
        workspace = build_trade_workspace(data, 1)
        outgoing = [a for a in workspace['pools'][1] if a.kind == 'player'][:2]
        target = next(a for a in workspace['pools'][2] if a.asset_id == '2-QB-0')
        proposals = tuple(TradeProposal(1, 2, (a,), (target,), '1-for-1') for a in outgoing)
        def supported_fixture(data, payload, **kwargs):
            return {'proposal': {'assets_sent': payload['assets_sent'], 'assets_received': payload['assets_received']},
                    'evaluation': {'generated_trade_eligible': False, 'recommendation': 'FAIR / OPTIONAL',
                        'legal': True, 'legality': {'execution_status': 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER'},
                        'dimensions': {'counterparty_plausibility': {'assessment': 'PLAUSIBLE'}, 'confidence': {'assessment': 'MEDIUM'}},
                        'values': {'sent': 100}, 'provenance': {'evaluation_id': payload['assets_sent'][0]}}}
        for count in (1, 2):
            with patch('services.trade_intelligence.generate_proposals', return_value=proposals[:count]), \
                    patch('services.trade_intelligence.evaluate_trade_request', side_effect=supported_fixture):
                result = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': target.asset_id})
            self.assertEqual(result['count'], count)
            self.assertTrue(all(r['evaluation']['recommendation'] == 'FAIR / OPTIONAL' for r in result['results']))
            self.assertTrue(all(r['workflow_eligibility']['eligible'] for r in result['results']))
            self.assertIsNone(result['quiet_state'])

    def test_wrong_league_runtime_rejected_before_construction(self):
        from types import SimpleNamespace
        with patch('src.platform.league_context.current_league_context', return_value=SimpleNamespace(league_id='another-league')), \
                patch('services.trade_intelligence.generate_proposals', side_effect=AssertionError('wrong league search')):
            with self.assertRaisesRegex(ValueError, 'league context changed'):
                generate_trade_workflow(fixture_data(), {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': '2-QB-0'})

    def test_mid_search_evidence_changes_discard_results(self):
        from services.trade_intelligence import TradeInputError
        for field in ('market_data', 'projection_intelligence', 'team_strength', 'fois', 'pick_context', 'methodology'):
            with self.subTest(field=field):
                data = fixture_data()
                def replace_evidence(*args, **kwargs):
                    data[field] = {'generation': 'replacement'}
                    return ()
                with patch('services.trade_intelligence.generate_proposals', side_effect=replace_evidence):
                    with self.assertRaisesRegex(TradeInputError, 'Canonical evidence changed'):
                        generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': '2-QB-0'})

    def test_projection_publication_during_search_discards_results(self):
        from services.trade_intelligence import TradeInputError
        data = fixture_data()
        state = {'horizon_generation': 'before'}
        def publish(*args, **kwargs):
            state['horizon_generation'] = 'after'
            return ()
        with patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=lambda: dict(state)), \
                patch('services.trade_intelligence.generate_proposals', side_effect=publish):
            with self.assertRaisesRegex(TradeInputError, 'Canonical evidence changed'):
                generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': '2-QB-0'})

    def test_target_owner_is_resolved_again_and_old_partner_rejected(self):
        data = fixture_data()
        moved = next(p for p in data['teams'][1]['players'] if p['id'] == '2-QB-0')
        data['teams'][1]['players'].remove(moved)
        data['teams'][2]['players'].append(moved)
        with self.assertRaisesRegex(ValueError, 'counterparty does not own'):
            generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1,
                                         'asset_id': '2-QB-0', 'partner_roster_id': 2})
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value={'availability': 'unavailable'}):
            result = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': '2-QB-0'})
        self.assertEqual(result['search_evidence']['stages'][0]['partner_id'], data['teams'][2]['roster_id'])

    def test_outgoing_ownership_and_constraints_use_current_pool(self):
        data = fixture_data()
        moved = data['teams'][0]['players'].pop(0)
        data['teams'][2]['players'].append(moved)
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value={'availability': 'unavailable'}):
            first = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1,
                'asset_id': '2-QB-0', 'protected_assets': ['1-RB-2']})
            second = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': '2-QB-0'})
        self.assertNotIn(moved['id'], second['search_evidence']['stages'][0]['shortlisted_asset_ids']['sent'])
        self.assertNotIn('1-RB-2', first['search_evidence']['stages'][0]['shortlisted_asset_ids']['sent'])
        self.assertIn('1-RB-2', second['search_evidence']['stages'][0]['shortlisted_asset_ids']['sent'])
        self.assertEqual(second['constraints'], {'protected_assets': [], 'excluded_assets': []})

    def test_excluded_target_is_explicitly_unavailable_not_substituted(self):
        result = generate_trade_workflow(fixture_data(), {'workflow': 'trade_for', 'active_roster_id': 1,
            'asset_id': '2-QB-0', 'excluded_assets': ['2-QB-0']})
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['search_evidence']['full_evaluations'], 0)
        self.assertEqual(result['target_asset_id'], '2-QB-0')

    def test_pick_target_moves_by_exact_identity_not_round(self):
        data = fixture_data()
        pick = data['teams'][1]['picks_owned'].pop(0)
        pick['current_owner_id'] = 3
        data['teams'][2]['picks_owned'].append(pick)
        target = f"{pick['season']}-R{pick['round']}-2"
        with self.assertRaisesRegex(ValueError, 'counterparty does not own'):
            generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1,
                                         'asset_id': target, 'partner_roster_id': 2})
        result = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': target})
        self.assertEqual(result['search_evidence']['stages'][0]['partner_id'], 3)
        self.assertEqual(result['target_asset_id'], target)
        self.assertEqual(result['count'], 0)  # Fixture has no legitimate pick Market quote.

    def test_optional_target_acquisition_preserves_bilateral_safeguards(self):
        from services.trade_intelligence import _trade_for_eligible
        evaluation = {
            'generated_trade_eligible': False, 'recommendation': 'FAIR / OPTIONAL', 'legal': True,
            'legality': {'execution_status': 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER'},
            'dimensions': {'counterparty_plausibility': {'assessment': 'PLAUSIBLE'},
                           'confidence': {'assessment': 'MEDIUM'}},
        }
        original = deepcopy(evaluation)
        self.assertTrue(_trade_for_eligible(evaluation))
        self.assertEqual(evaluation, original)  # Workflow policy cannot rewrite shared judgment.
        for recommendation in ('NOT WORTH IT', 'REJECT', None):
            self.assertFalse(_trade_for_eligible({**evaluation, 'recommendation': recommendation}))
        for confidence in ('LIMITED', None):
            rejected = deepcopy(evaluation)
            rejected['dimensions']['confidence']['assessment'] = confidence
            self.assertFalse(_trade_for_eligible(rejected))
        for plausibility in ('LOW', 'INSUFFICIENT EVIDENCE', None):
            rejected = deepcopy(evaluation)
            rejected['dimensions']['counterparty_plausibility']['assessment'] = plausibility
            self.assertFalse(_trade_for_eligible(rejected))
        self.assertFalse(_trade_for_eligible({**evaluation, 'legal': False}))
        self.assertFalse(_trade_for_eligible({**evaluation, 'legality': {'execution_status': 'REQUIRES ROSTER RESOLUTION'}}))

    def test_target_is_constrained_before_candidate_selection(self):
        outgoing = tuple(asset(str(i), i + 1, 1) for i in range(15))
        incoming = (asset('target', 1000, 2), asset('cheap', 1, 2))
        with patch('src.core.trade_intelligence.engine.trade_generator._value', side_effect=AssertionError('legacy discount')), \
                patch('src.core.trade_intelligence.engine.trade_generator.evaluate_trade_guardrails', side_effect=AssertionError('legacy grading')):
            rows = generate_proposals(1, 2, outgoing, incoming, required_received_asset_id='target', construction_only=True)
        self.assertTrue(rows)  # Price ratio must not veto construction.
        self.assertLessEqual(len(rows), 6)
        self.assertTrue(all('target' in {a.asset_id for a in p.assets_received} for p in rows))
        self.assertEqual(rows, generate_proposals(1, 2, outgoing, incoming, required_received_asset_id='target', construction_only=True))

    def test_trade_for_and_manual_use_identical_shared_result(self):
        data = fixture_data()
        workspace = build_trade_workspace(data, 1)
        before = deepcopy(data)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        impact = {'sides': {'active': side(1, 5), 'partner': side(2, -5)}}
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value=impact) as prepare:
            manual = evaluate_trade_request(data, {**payload, 'workflow': 'create'}, workspace=workspace)
            target = evaluate_trade_request(data, {**payload, 'workflow': 'trade_for'}, workspace=workspace)
        self.assertEqual(prepare.call_count, 2)
        self.assertEqual(manual['evaluation'], target['evaluation'])
        self.assertEqual(data, before)

    def test_constraints_apply_before_search_and_missing_preparation_stays_quiet(self):
        data = fixture_data()
        before = deepcopy(data)
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value={'availability': 'unavailable'}):
            result = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1,
                'asset_id': '2-QB-0', 'protected_assets': ['1-QB-0'], 'excluded_assets': ['1-RB-2']})
        self.assertEqual(result['count'], 0)
        stages = result['search_evidence']['stages'][0]
        self.assertNotIn('1-QB-0', stages['shortlisted_asset_ids']['sent'])
        self.assertNotIn('1-RB-2', stages['shortlisted_asset_ids']['sent'])
        self.assertLessEqual(result['search_evidence']['full_evaluations'], 6)
        self.assertGreaterEqual(result['search_evidence']['timings_seconds']['shared_evaluation'], 0)
        self.assertNotIn('stronger pick', str(result))
        self.assertEqual(data, before)

    def test_position_diversity_survives_price_proximity_pruning(self):
        from dataclasses import replace
        outgoing = tuple(asset('qb' + str(i), 100, 1) for i in range(20))
        # These differently positioned assets must not disappear behind twelve
        # closer-priced quarterbacks before canonical evaluation is possible.
        outgoing += (replace(asset('wr', 1, 1), position='WR'), replace(asset('te', 2, 1), position='TE'))
        diagnostics = {}
        generate_proposals(1, 2, outgoing, (asset('target', 100, 2),), required_received_asset_id='target',
                           construction_only=True, search_diagnostics=diagnostics)
        self.assertIn('wr', diagnostics['shortlisted_asset_ids']['sent'])
        self.assertIn('te', diagnostics['shortlisted_asset_ids']['sent'])
        self.assertLessEqual(diagnostics['shortlisted_outgoing'], 12)
        self.assertTrue(diagnostics['shortlist_excluded_asset_ids']['sent'])
        boundary = diagnostics['package_boundaries'][0]
        self.assertEqual(boundary['candidate_count'], 12)
        self.assertEqual(len(boundary['nearest_constructions']), 3)
        self.assertEqual(boundary['nearest_constructions'][1]['selection'], 'pruned_search_budget')
        self.assertTrue(all(row['quality'] == 'not_assessed' for row in boundary['nearest_constructions']))

    def test_all_protected_performs_no_shared_evaluations(self):
        data = fixture_data()
        protected = [p['id'] for p in data['teams'][0]['players']]
        # Fixture picks are unpriced and cannot fill a fake acquisition offer.
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('must not evaluate')):
            result = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1,
                'asset_id': '2-QB-0', 'protected_assets': protected})
        self.assertEqual(result['search_evidence']['full_evaluations'], 0)
        self.assertEqual(result['count'], 0)

    def test_specific_foreign_target_is_required(self):
        data = fixture_data()
        for target in ('', '1-QB-0', 'not-owned'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': 1, 'asset_id': target})

    def test_equivalent_fourth_swap_does_not_fill_another_offer_slot(self):
        from dataclasses import replace
        from services.trade_intelligence import _distinct_trade_for_offers
        by_id = {pid: asset(pid, 100, 1) for pid in ('a', 'b', 'target')}
        for pid, original in (('pick1', 1), ('pick2', 3)):
            by_id[pid] = replace(asset(pid, 10, 1), kind='pick', position=None, season=2028, round=4,
                                 original_roster_id=original, current_owner_id=1)
        rows = [{'proposal': {'assets_sent': ids, 'assets_received': ['target']}}
                for ids in (['a', 'pick1'], ['a', 'pick2'], ['b', 'pick2'])]
        original = deepcopy(rows)
        self.assertEqual(_distinct_trade_for_offers(rows, by_id), [rows[0], rows[2]])
        self.assertEqual(rows, original)
