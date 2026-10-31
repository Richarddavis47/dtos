"""Completed fixture evidence -> visible summaries; preserve policy and numbers."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from tests import test_trade_recommendation_clarity as fixtures
from services.trade_decision import decision_context
from services.trade_decision_summary import decision_summary
from services.trade_explanation import render_trade_explanation
from services.trade_lineup_evidence import completed_lineup_admissions


class ConditionalSummaryTests(unittest.TestCase):
    def fixture(self):
        f = fixtures.RecommendationClarityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def test_supported_partner_loss_is_visible_without_changing_verdict_or_values(self):
        f = self.fixture()
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            e = f.evaluate(strategy=strategy)
            before = deepcopy(e)
            d = decision_context(e)
            self.assertEqual(e, before)
            self.assertIn('-6.31', d['their_side_summary'])
            self.assertIn('strategy is unconfirmed', d['decision_conditions'])
            self.assertIn('They give up supported projected production', d['decision_conditions'])
            self.assertIn('do not establish rebuilding intent', d['decision_conditions'])
            e['decision_context'] = d
            html = render_trade_explanation(e, league_id='league-1')
            self.assertIn(d['decision_conditions'], html)
            self.assertEqual(e['recommendation'], before['recommendation'])
            self.assertEqual(e['generated_trade_eligible'], before['generated_trade_eligible'])

    def test_explicit_direction_and_roster_inference_are_not_conflated(self):
        f = self.fixture()
        for source in ('explicit_manager', 'canonical_competitive_window', 'unavailable'):
            for strategy in ('REBUILD', 'WIN NOW'):
                e = f.evaluate()
                e['dimensions']['counterparty_plausibility']['manager_strategy'] = {'strategy': strategy, 'source': source}
                d = decision_context(e)
                expected = {'explicit_manager':'Their saved direction', 'canonical_competitive_window':'not a confirmed manager intention', 'unavailable':'strategy is unconfirmed'}[source]
                self.assertIn(expected, d['decision_conditions'])
                self.assertIn('do not', d['decision_conditions'])

    def test_missing_partner_comparison_gets_evidence_action_not_add_a_pick(self):
        f = self.fixture()
        e = f.evaluate()
        a = completed_lineup_admissions(e)
        a['partner']['mean_weekly_delta'] = None
        a['partner']['weekly'] = {}
        for h in a['partner']['horizons'].values():
            h['delta'] = None
        d = decision_summary(e, a)
        self.assertIn("Their team's compatible player-week projections", d['evidence_next_action'])
        self.assertIn('adding a pick cannot fix missing projections', d['evidence_next_action'])
        self.assertIn('2, 3, 4, 5', d['their_side_summary'])

    def test_future_capital_qualification_is_distinct_from_balanced_market(self):
        f = self.fixture()
        e = f.evaluate()
        e['dimensions']['strategic_fit']['active']['future_capital']['assessment']['availability'] = 'unavailable'
        d = decision_context(e)
        self.assertIn('Future-capital qualification is incomplete', d['your_side_summary'])
        self.assertIn('future-capital qualification', d['evidence_next_action'])

    def test_zero_and_missing_are_distinct_without_source_work(self):
        f = self.fixture()
        e = f.evaluate()
        a = completed_lineup_admissions(e)
        a['active']['mean_weekly_delta'] = 0
        a['active']['horizons']['current_week']['delta'] = 0
        with patch('services.sleeper.sleeper_get', side_effect=AssertionError('Unexpected provider work')):
            d = decision_summary(e, a)
        self.assertIn('+0.00', d['your_side_summary'])
        self.assertNotIn('current-week legal-lineup change cannot', d['your_side_summary'])

    def test_provenance_conflict_does_not_repeat_a_supported_mean(self):
        f = self.fixture()
        e = f.evaluate()
        e['multi_horizon_impact']['league_id'] = 'foreign'
        d = decision_context(e)
        self.assertNotIn('+6.31', d['your_side_summary'])
        self.assertIn('cannot be verified', d['their_side_summary'])
