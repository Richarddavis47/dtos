"""Personal valuation controls through the actual canonical Trade evaluator.

These disposable controls install an already-authorized server context.  HTTP
authentication/revision controls are exercised separately by the editor tests.
"""
from __future__ import annotations

import copy
import unittest

from services.trade_intelligence import TradeInputError, build_trade_workspace, evaluate_trade_request


class PersonalTradeIntegrationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_capital_strategy_reconciliation import CapitalStrategyTests
        self.fixture = CapitalStrategyTests('test_strategy_changes_fit_never_market_or_lineups')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.data = self.fixture.data

    def evaluate(self, *, values=None, mode=None, preferences=None, sent=None, received=None):
        workspace = build_trade_workspace(self.data, 1)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': sent or ['a'], 'assets_received': received or ['2028-R1-4'],
                   'strategy': 'REBUILD', 'workflow': 'create'}
        if mode:
            original = {asset.asset_id: asset.trade_value
                        for pool in workspace['pools'].values() for asset in pool}
            payload['_personal_context'] = {
                'mode': mode, 'revision': 2, 'baseline_generation': 'seed-A',
                'market_generation': 'current-A', 'method': 'rank-slot-curve-v1',
                'values': {**original, **(values or {})}, 'neutral_values': original,
                'preferences': preferences or {},
                'scope': {'league_id': 'league-1', 'roster_id': 1},
            }
        return evaluate_trade_request(self.data, payload, workspace=workspace,
                                      projection_reader=self.fixture.reader)

    def test_zero_edit_custom_preserves_objective_lineups_market_and_opponent(self):
        neutral = self.evaluate()['evaluation']
        custom = self.evaluate(mode='custom')['evaluation']
        self.assertEqual(custom['recommendation'], neutral['recommendation'])
        self.assertEqual(custom['generated_trade_eligible'], neutral['generated_trade_eligible'])
        for field in ('market_evidence', 'lineup_impact', 'multi_horizon_impact', 'player_facts'):
            self.assertEqual(custom[field], neutral[field], field)
        for dimension in ('strategic_fit', 'package_quality'):
            self.assertEqual(custom['dimensions'][dimension]['partner'],
                             neutral['dimensions'][dimension]['partner'], dimension)
        for dimension in ('counterparty_plausibility', 'confidence', 'value_fairness'):
            self.assertEqual(custom['dimensions'][dimension], neutral['dimensions'][dimension], dimension)

    def test_personal_cost_changes_decision_without_repricing_opponent_or_market(self):
        before = copy.deepcopy(self.data)
        neutral = self.evaluate()['evaluation']
        custom = self.evaluate(mode='custom', values={'a': 500})['evaluation']
        self.assertEqual(neutral['recommendation'], 'WORTH PURSUING')
        self.assertNotEqual(custom['recommendation'], neutral['recommendation'])
        self.assertEqual(custom['market_evidence'], neutral['market_evidence'])
        self.assertEqual(custom['personal_value_evidence']['sent']['total'], 500)
        self.assertEqual(custom['personal_value_evidence']['received']['total'], 250)
        self.assertEqual(custom['dimensions']['counterparty_plausibility'],
                         neutral['dimensions']['counterparty_plausibility'])
        self.assertEqual(custom['dimensions']['strategic_fit']['partner'],
                         neutral['dimensions']['strategic_fit']['partner'])
        self.assertEqual(custom['counterparty_summary'], neutral['counterparty_summary'])
        self.assertEqual(self.data, before)

    def test_neutral_mode_ignores_personal_numeric_opinions(self):
        plain = self.evaluate()['evaluation']
        selected = self.evaluate(mode='neutral', values={'a': 999, '2028-R1-4': 0})['evaluation']
        for field in ('recommendation', 'generated_trade_eligible', 'market_evidence',
                      'values', 'lineup_impact', 'multi_horizon_impact'):
            self.assertEqual(selected[field], plain[field], field)
        self.assertNotIn('personal_value_evidence', selected)

    def test_neutral_severe_overpay_is_not_hidden_by_a_custom_favorite(self):
        self.fixture.prices(a=995, c=75)
        neutral = self.evaluate(sent=['a'], received=['c'])['evaluation']
        custom = self.evaluate(mode='custom', values={'a': 75, 'c': 995},
                               sent=['a'], received=['c'])['evaluation']
        self.assertEqual(neutral['recommendation'], 'REJECT')
        self.assertIn('SEVERE_MARKET_LOSS', neutral['reason_codes'])
        self.assertEqual(custom['recommendation'], 'REJECT')
        self.assertFalse(custom['generated_trade_eligible'])
        self.assertEqual(custom['neutral_assessment']['recommendation'], 'REJECT')
        self.assertEqual(custom['market_evidence'], neutral['market_evidence'])

    def test_saved_protect_and_avoid_warn_without_rewriting_manual_package(self):
        result = self.evaluate(mode='custom', preferences={
            'a': {'protect': True}, '2028-R1-4': {'avoid': True}})
        self.assertEqual(tuple(result['proposal']['assets_sent']), ('a',))
        self.assertEqual(tuple(result['proposal']['assets_received']), ('2028-R1-4',))
        warnings = result['evaluation'].get('personal_preference_warnings') or []
        self.assertEqual(len(warnings), 2)
        self.assertTrue(any('protection' in warning.lower() for warning in warnings))
        self.assertTrue(any('avoid' in warning.lower() for warning in warnings))

    def test_missing_personal_price_cannot_receive_generated_endorsement(self):
        with self.assertRaises(TradeInputError) as unavailable:
            self.evaluate(mode='custom', values={'2028-R1-4': None})
        self.assertEqual(unavailable.exception.code, 'personal_evidence_unavailable')


if __name__ == '__main__':
    unittest.main()
