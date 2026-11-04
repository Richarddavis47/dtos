import unittest
from types import SimpleNamespace
from src.core.trade_intelligence.market_balance import market_balance
from src.core.trade_intelligence.bilateral import evaluate_bilateral
from src.core.trade_intelligence.models import TradeAsset, TradeProposal


class TradeMarketBalanceTests(unittest.TestCase):
    def asset(self, identity, value, kind='player', owner=1):
        return TradeAsset(identity, kind, identity, 'QB' if kind == 'player' else None,
                          999, 999, 999, 999, 0, owner, trade_value=value)

    def test_package_counts_do_not_discount_market(self):
        sent = tuple(self.asset(str(i), 100.25) for i in range(3))
        result = market_balance(sent, (self.asset('target', 300.75),))
        self.assertEqual(result['difference'], 0)
        self.assertEqual(result['ratio'], 1)
        self.assertEqual(result['sent']['total'], 300.75)
        self.assertFalse(result['package_adjustments'])

    def test_missing_never_uses_other_scalar_and_true_zero_survives(self):
        for kind in ('player', 'pick'):
            result = market_balance((self.asset('missing', None, kind), self.asset('zero', 0)),
                                    (self.asset('priced', 100),))
            self.assertEqual(result['availability'], 'partial')
            self.assertIsNone(result['sent']['total'])
            self.assertEqual(result['sent']['known_subtotal'], 0)
            self.assertIsNone(result['difference'])
            self.assertIsNone(result['ratio'])
        self.assertEqual(market_balance((self.asset('a', None),), (self.asset('b', None),))['availability'], 'unavailable')

    def test_partial_evaluator_retains_independent_projection_evidence(self):
        proposal = TradeProposal(1, 2, (self.asset('a', None),), (self.asset('b', 100, owner=2),), 'Manual')
        impact = {'availability': 'supported', 'sides': {'active': {'horizons': {}}}}
        result = evaluate_bilateral(proposal, active_team={}, partner_team={}, league={}, horizon_impact=impact)
        self.assertTrue(result['legal'])
        self.assertIsNone(result['recommendation'])
        self.assertEqual(result['multi_horizon_impact'], impact)
        self.assertFalse(result['generated_trade_eligible'])

    def test_invalid_prices_are_not_unknown_or_zero(self):
        for value in (True, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                market_balance((SimpleNamespace(asset_id='a', trade_value=value),), ())
