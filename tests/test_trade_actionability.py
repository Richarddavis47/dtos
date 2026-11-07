"""Prepared, bilateral evidence -> concise presentation; no new trade policy."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from services.trade_decision import decision_context
from services.trade_explanation import REASONS, render_trade_explanation
from tests import test_trade_recommendation_clarity as fixtures
from tests import test_trade_lineup_detail as lineups


class TradeActionabilityTests(unittest.TestCase):
    def fixture(self):
        f = fixtures.RecommendationClarityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def test_recorded_rule_leads_both_views_without_changing_the_evaluation(self):
        f = self.fixture()
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            e = f.evaluate(strategy=strategy)
            original = deepcopy(e)
            with patch('services.sleeper.sleeper_get', side_effect=AssertionError('No presentation acquisition')), \
                 patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('No presentation optimization')):
                d = decision_context(e)
                html = render_trade_explanation(e, league_id='league-1')
            self.assertEqual(e, original)
            self.assertIn(d['decisive_reason'], html)
            self.assertIn(d['decision_next_step'], html)
            self.assertLess(html.index('Why this decision:'), html.index('Neutral Market'))
            self.assertIn('-6.31', d['their_side_summary'])
            self.assertIn('strategy is unconfirmed', d['decision_conditions'])

    def test_expensive_marginal_gain_keeps_the_existing_severe_loss_rejection(self):
        f = self.fixture()
        f.f.f.prices(a=995, c=75)
        f.f.f.points['c'] = 20.01
        f.f.f.publish()
        e = f.evaluate(assets_sent=['a'], assets_received=['c'])
        self.assertEqual(e['recommendation'], 'REJECT')
        self.assertFalse(e['generated_trade_eligible'])
        self.assertEqual(e['decision_context']['decisive_reason'], REASONS['SEVERE_MARKET_LOSS'])
        self.assertIn('Do not pursue', e['decision_context']['decision_next_step'])
        self.assertEqual(e['market_evidence']['sent']['total'], 995)
        self.assertEqual(e['market_evidence']['received']['total'], 75)

    def test_incompatible_lineup_cannot_supply_a_positive_decision_reason(self):
        e = self.fixture().evaluate()
        e['multi_horizon_impact']['projection_generation'] = 'foreign'
        d = decision_context(e)
        self.assertIn('cannot be verified', d['decisive_reason'])
        self.assertIsNone(d['lineup']['delta'])
        self.assertNotIn('supported production gain', d['decisive_reason'])

    def test_counterparty_limit_never_uses_a_positive_reason_as_its_blocker(self):
        f = self.fixture()
        f.test_real_custom_pick_exchange_keeps_neutral_counterparty_veto()
        e = f.limited
        e['dimensions']['counterparty_plausibility']['reason_codes'] = [
            'SUPPORTED_COUNTERPARTY_BENEFIT', 'LOW_COUNTERPARTY_PLAUSIBILITY']
        d = decision_context(e)
        self.assertEqual(d['verdict'], 'COUNTERPARTY LIMITED')
        self.assertEqual(d['decisive_reason'], REASONS['LOW_COUNTERPARTY_PLAUSIBILITY'])
        self.assertIn('confirm their direction', d['decision_next_step'])

    def test_custom_rule_names_personal_cost_without_relabeling_neutral_prices(self):
        f = self.fixture()
        f.f.f.prices(a=995, c=75)
        e = f.evaluate(assets_sent=['a'], assets_received=['c'])
        e['personal_value_evidence'] = {'unit': 'personal_rank_slot_value', 'availability': 'partial'}
        d = decision_context(e)
        self.assertIn('personal valuation', d['decisive_reason'])
        self.assertIn('Neutral Market: 995 sent / 75 received', d['your_side_summary'])

    def test_one_qb_k_def_and_superflex_keep_their_independent_legal_lineups(self):
        f = lineups.TradeLineupDetailTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        from services.trade_lineup_detail import lineup_detail_view
        for superflex in (False, True):
            if superflex:
                f.f.test_superflex_without_dedicated_te_preserves_legal_scoring()
            e = f.evaluate()
            original = deepcopy(e)
            html = render_trade_explanation(e, league_id=e['multi_horizon_impact']['league_id'])
            for side in ('active', 'partner'):
                for phase in ('pre', 'post'):
                    p = lineup_detail_view(e)['sides'][side][8]['phases'][phase]
                    self.assertEqual(p['state'], 'complete')
                    slots = [r['slot'] for r in p['entries']]
                    if superflex:
                        self.assertIn('SUPER_FLEX', slots)
                        self.assertNotIn('TE', slots)
                    else:
                        self.assertIn('K', slots)
                        self.assertIn('DEF', slots)
                        self.assertEqual(slots.count('FLEX'), 2)
                    self.assertAlmostEqual(sum(r['projected_points'] for r in p['entries']), p['total'])
            self.assertIn('not your submitted Sleeper starters', html)
            self.assertEqual(e, original)

    def test_missing_reserve_evidence_remains_a_named_limit_not_a_zero(self):
        f = lineups.TradeLineupDetailTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.f.feed = [r for r in f.f.feed if r['player_id'] != '2-9']
        f.f.publish()
        e = f.evaluate()
        d = e['decision_context']
        self.assertIn('cannot', d['their_side_summary'])
        self.assertIn('adding a pick cannot fix missing projections', d['evidence_next_action'])
        self.assertIn('a missing reserve effect is not zero', d['their_side_summary'])
        self.assertFalse(e['generated_trade_eligible'])
