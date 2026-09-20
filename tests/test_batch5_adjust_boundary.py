"""Adjust must assess the exact proposal with the accepted shared semantics."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request, assist_trade_request, _bounded_adjustment_candidates
from tests.test_trade_intelligence import fixture_data
from tests.test_batch5_trade_strategy import side


class AdjustBoundaryTests(unittest.TestCase):
    def test_positive_keep_and_add_return_are_material_and_target_preserving(self):
        data = fixture_data()
        before = deepcopy(data)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        readers = []
        def assessed(source, candidate, **kwargs):
            readers.append(kwargs['projection_reader'])
            return {'proposal': deepcopy(candidate), 'evaluation': {'generated_trade_eligible': True,
                    'values': {'ratio': 1}, 'provenance': {'evaluation_id': '|'.join(candidate['assets_sent'] + candidate['assets_received'])}}}
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=assessed):
            kept = assist_trade_request(data, dict(payload, protected_assets=['1-QB-0']))
            self.assertEqual(kept['count'], 1)
            self.assertNotIn('1-QB-0', kept['results'][0]['proposal']['assets_sent'])
            self.assertTrue(kept['target_preserved'])
            self.assertTrue(all(reader is readers[0] for reader in readers))
            added = assist_trade_request(data, dict(payload, instruction='get another player back'))
            self.assertEqual(added['count'], 1)
            self.assertGreater(len(added['results'][0]['proposal']['assets_received']), 1)
            self.assertTrue(added['target_preserved'])
        self.assertEqual(data, before)

    def test_constraints_reach_constructor_before_selection(self):
        workspace = build_trade_workspace(fixture_data(), 1)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0'],
                   'protected_assets': ['1-QB-0']}
        with patch('services.trade_intelligence.generate_proposals', return_value=()) as generate:
            proposals = _bounded_adjustment_candidates(workspace, payload)
        self.assertTrue(generate.call_args.kwargs['construction_only'])
        self.assertNotIn('1-QB-0', {a.asset_id for a in generate.call_args.args[2]})
        self.assertTrue(proposals)
        self.assertTrue(all('1-QB-0' not in {a.asset_id for a in p.assets_sent} for p in proposals))
        self.assertTrue(all('2-QB-0' in {a.asset_id for a in p.assets_received} for p in proposals))

    def test_protecting_shopped_objective_is_explicit_conflict(self):
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0'],
                   'protected_assets': ['1-QB-0'], 'origin_workflow': 'shop', 'origin_asset_id': '1-QB-0'}
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('evaluation during conflict')):
            result = assist_trade_request(fixture_data(), payload)
        self.assertEqual(result['state'], 'CONSTRAINT_CONFLICT')
        self.assertFalse(result['search_completed'])

    def test_no_outgoing_picks_constraint_is_interpreted_before_construction(self):
        data = fixture_data()
        workspace = build_trade_workspace(data, 1)
        picks = {a.asset_id for a in workspace['pools'][1] if a.kind == 'pick'}
        self.assertTrue(picks)
        with patch('services.trade_intelligence._bounded_adjustment_candidates', return_value=()) as candidates:
            result = assist_trade_request(data, {'active_roster_id': 1, 'partner_roster_id': 2,
                'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0'], 'instruction': 'do not trade picks'})
        self.assertTrue(picks.issubset(candidates.call_args.args[1]['protected_assets']))
        self.assertEqual(result['state'], 'NO_CREDIBLE_ADJUSTMENT')

    def test_midsearch_change_is_rejected(self):
        data = fixture_data()
        def changed(*args, **kwargs):
            data['teams'][0]['players'].pop()
            return ()
        with patch('services.trade_intelligence._bounded_adjustment_candidates', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Canonical evidence changed'):
                assist_trade_request(data, {'active_roster_id': 1, 'partner_roster_id': 2,
                    'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']})

    def test_adjust_matches_manual_for_supported_and_missing_horizons(self):
        data = fixture_data()
        before = deepcopy(data)
        workspace = build_trade_workspace(data, 1)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        for impact in ({'sides': {'active': side(1, 5), 'partner': side(2, -5)}},
                       {'availability': 'unavailable'}):
            with self.subTest(impact=impact), patch(
                    'src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value=impact) as horizon:
                manual = evaluate_trade_request(data, dict(payload, workflow='create'), workspace=workspace)
                for workflow in ('adjust', 'trade_for', 'shop', 'recommended', 'create_alternative'):
                    adjusted = evaluate_trade_request(data, dict(payload, workflow=workflow), workspace=workspace)
                    self.assertEqual(manual['evaluation'], adjusted['evaluation'])
                self.assertEqual(horizon.call_count, 6)
        self.assertEqual(data, before)
