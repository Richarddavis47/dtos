"""Remaining session constraint boundaries, not real-market offer evidence."""
import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from services.trade_intelligence import assist_trade_request, build_trade_workspace, _bounded_adjustment_candidates
from src.core.trade_intelligence.models import TradeProposal
from tests.test_trade_intelligence import fixture_data


class AdjustmentConstraintTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture_data()
        self.workspace = build_trade_workspace(self.data, 1)
        self.assets = {a.asset_id: a for pool in self.workspace['pools'].values() for a in pool}
        self.payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                        'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}

    def assess(self, data, payload, **kwargs):
        return {'proposal': deepcopy(payload), 'evaluation': {'generated_trade_eligible': True,
            'values': {'ratio': 1}, 'provenance': {'evaluation_id': str(payload)},
            'dimensions': {'package_quality': {
                'active': {'incoming_lineup_contributors': [i for i in payload['assets_received'] if self.assets[i].kind == 'player']},
                'partner': {'incoming_lineup_contributors': [i for i in payload['assets_sent'] if self.assets[i].kind == 'player']}}}}}

    def test_named_clauses_do_not_protect_or_exclude_the_other_name(self):
        a, b = self.assets['1-QB-0'], self.assets['1-QB-1']
        with patch('services.trade_intelligence._bounded_adjustment_candidates', return_value=()) as build:
            assist_trade_request(self.data, dict(self.payload, instruction=f'keep {a.label}; replace {b.label}'))
        constraints = build.call_args.args[1]
        self.assertEqual(constraints['protected_assets'], [a.asset_id])
        self.assertEqual(constraints['excluded_assets'], [b.asset_id])

    def test_meaningful_conflicts_stop_before_search(self):
        a = self.assets['1-QB-0']
        for text in (f'keep {a.label}; replace {a.label}', 'do not trade picks; add outgoing pick'):
            with self.subTest(text=text), patch('services.trade_intelligence._bounded_adjustment_candidates', side_effect=AssertionError('conflicting search')):
                result = assist_trade_request(self.data, dict(self.payload, instruction=text))
                self.assertEqual(result['state'], 'CONSTRAINT_CONFLICT')

    def test_use_wrs_filters_the_generator_pool_not_just_results(self):
        payload = dict(self.payload, replacement_position='WR')
        with patch('services.trade_intelligence.generate_proposals', return_value=()) as generate:
            rows = _bounded_adjustment_candidates(self.workspace, payload)
        self.assertTrue(all(a.kind == 'pick' or a.position == 'WR' for a in generate.call_args.args[2]))
        self.assertTrue(all(a.kind == 'pick' or a.position == 'WR' for row in rows for a in row.assets_sent))

    def test_replace_asset_is_absent_from_positive_construction(self):
        a = self.assets['1-QB-0']
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, instruction=f'replace {a.label}'))
        self.assertEqual(result['count'], 1)
        self.assertNotIn(a.asset_id, result['results'][0]['proposal']['assets_sent'])

    def test_add_pick_preserves_owned_identity_and_does_not_alias(self):
        # Explicit priced-pick fixture: the base fixture deliberately has no
        # external pick quotes, so it cannot demonstrate a positive priced offer.
        self.workspace['pools'][1] = tuple(replace(a, trade_value=200) if a.kind == 'pick' else a
                                           for a in self.workspace['pools'][1])
        self.assets.update({a.asset_id: a for a in self.workspace['pools'][1]})
        with patch('services.trade_intelligence.build_trade_workspace', return_value=self.workspace), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, instruction='add outgoing pick'))
        self.assertEqual(result['count'], 1)
        picks = [self.assets[i] for i in result['results'][0]['proposal']['assets_sent'] if self.assets[i].kind == 'pick']
        self.assertTrue(picks)
        for pick in picks:
            self.assertEqual(pick.source_roster_id, 1)
            self.assertIn(pick, self.workspace['pools'][1])

    def test_cheaper_uses_supported_price_not_asset_count(self):
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, assets_sent=['1-QB-0', '1-QB-1'], instruction='cheaper'))
        self.assertEqual(result['count'], 1)
        cost = sum(self.assets[i].trade_value for i in result['results'][0]['proposal']['assets_sent'])
        self.assertLess(cost, self.assets['1-QB-0'].trade_value + self.assets['1-QB-1'].trade_value)

    def test_expand_requires_actual_added_player_contribution(self):
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, instruction='expand trade'))
        self.assertEqual(result['count'], 1)
        proposal = result['results'][0]['proposal']
        self.assertGreater(len(proposal['assets_sent']) + len(proposal['assets_received']), 2)
        def no_contribution(*args, **kwargs):
            row = self.assess(*args, **kwargs)
            row['evaluation']['dimensions']['package_quality'] = {}
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=no_contribution):
            result = assist_trade_request(self.data, dict(self.payload, instruction='expand trade'))
        self.assertEqual(result['state'], 'NO_CREDIBLE_ADJUSTMENT')

    def test_younger_is_supported_age_direction_not_better_quality(self):
        self.workspace['pools'][2] = tuple(replace(a, age=18) if a.asset_id == '2-QB-1' else a
                                          for a in self.workspace['pools'][2])
        self.assets.update({a.asset_id: a for a in self.workspace['pools'][2]})
        with patch('services.trade_intelligence.build_trade_workspace', return_value=self.workspace), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, instruction='younger'))
        self.assertEqual(result['count'], 1)
        self.assertIn('2-QB-1', result['results'][0]['proposal']['assets_received'])
        def rejected(*args, **kwargs):
            row = self.assess(*args, **kwargs)
            row['evaluation']['generated_trade_eligible'] = False
            return row
        with patch('services.trade_intelligence.build_trade_workspace', return_value=self.workspace), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=rejected):
            self.assertEqual(assist_trade_request(self.data, dict(self.payload, instruction='younger'))['count'], 0)

    def test_win_now_rejects_supported_later_horizon_regression(self):
        def assessed(*args, **kwargs):
            row = self.assess(*args, **kwargs)
            changed = row['proposal']['assets_sent'] != self.payload['assets_sent'] or row['proposal']['assets_received'] != self.payload['assets_received']
            row['evaluation']['dimensions']['strategic_fit'] = {'active': {'horizons': {
                name: {'availability': 'complete', 'delta': (delta if changed else 0)} for name, delta in
                [('current_week', 2), ('next_n', 4), ('rest_of_regular_season', -10), ('playoff_window', 0)]}}}
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=assessed):
            result = assist_trade_request(self.data, dict(self.payload, instruction='win-now'))
        self.assertEqual(result['state'], 'NO_CREDIBLE_ADJUSTMENT')
        def supported_gain(*args, **kwargs):
            row = assessed(*args, **kwargs)
            row['evaluation']['dimensions']['strategic_fit']['active']['horizons']['rest_of_regular_season']['delta'] = 0
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=supported_gain):
            result = assist_trade_request(self.data, dict(self.payload, instruction='win-now'))
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['adjustment_evidence']['unavailable_horizons'], [])

    def test_alternative_target_not_used_when_original_is_credible(self):
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, instruction='alternative target'))
        self.assertEqual(result['count'], 0)
        self.assertIn('credible original-target', result['quiet_state'])

    def test_alternative_target_requires_supported_same_role_and_explicit_change(self):
        outgoing = self.assets['1-QB-0']
        replacement = self.assets['2-QB-1']
        candidate = TradeProposal(1, 2, (outgoing,), (replacement,), 'Alternative Target')
        def assessed(*args, **kwargs):
            result = self.assess(*args, **kwargs)
            result['evaluation']['generated_trade_eligible'] = replacement.asset_id in result['proposal']['assets_received']
            return result
        with patch('services.trade_intelligence._bounded_adjustment_candidates', return_value=(candidate,)), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=assessed):
            result = assist_trade_request(self.data, dict(self.payload, instruction='alternative target'))
        self.assertEqual(result['count'], 1)
        self.assertFalse(result['target_preserved'])
        self.assertTrue(result['results'][0]['objective_evidence']['target_changed'])

    def test_nominal_same_concept_pick_swap_is_not_alternative_construction(self):
        original = replace(self.assets['2027-R1-1'], trade_value=200)
        other = replace(original, asset_id='2027-R1-other-original-franchise')
        self.workspace['pools'][1] = tuple(a for a in self.workspace['pools'][1] if a.asset_id != original.asset_id) + (original, other)
        self.assets.update({a.asset_id: a for a in (original, other)})
        candidate = TradeProposal(1, 2, (self.assets['1-QB-0'], other), (self.assets['2-QB-0'],), 'Alternate')
        with patch('services.trade_intelligence.build_trade_workspace', return_value=self.workspace), \
                patch('services.trade_intelligence._bounded_adjustment_candidates', return_value=(candidate,)), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=self.assess):
            result = assist_trade_request(self.data, dict(self.payload, assets_sent=['1-QB-0', original.asset_id],
                                                        instruction='alternative construction'))
        self.assertEqual(result['state'], 'NO_CREDIBLE_ADJUSTMENT')
