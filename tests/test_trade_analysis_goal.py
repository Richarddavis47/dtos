"""Matched real prepared packages: analysis choices are not provider gaps."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tests import test_capital_strategy_reconciliation as fixtures
from services.trade_intelligence import evaluate_trade_request
from services.trade_search_policy import (
    analysis_goal_required, classify, SearchFunnel, result_state,
    missing_evidence_guidance,
)
from services.recommended_trade_search import zero_result_guidance
from src.core.intelligence.team_strength import prepare_for_data


class TradeAnalysisGoalTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CapitalStrategyTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.data['teams'][0].pop('strategy')
        self.payload = dict(active_roster_id=1, partner_roster_id=2,
                            assets_sent=['a'], assets_received=['2028-R1-4'])

    def evaluate(self, **updates):
        return evaluate_trade_request(self.f.data, {**self.payload, **updates},
                                      projection_reader=self.f.reader)['evaluation']

    def gap(self, side):
        rows = deepcopy(self.f.payloads)
        ids = {'a', 'b', 'e'} if side == 'active' else {'c', 'd', 'f'}
        rows[3] = [r for r in rows[3] if r['player_id'] not in ids]
        self.f.reader.publish_horizon(rows, data=self.f.data, league_id='league-1',
                                     season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.f.reader, self.f.data)

    def funnel(self, evaluation):
        funnel = SearchFunnel(180)
        self.assertFalse(funnel.assessed({'evaluation': evaluation, 'proposal': self.payload}))
        return funnel

    def test_complete_matched_goal_choice_changes_no_market_or_lineup_facts(self):
        original = deepcopy(self.f.data)
        no_goal = self.evaluate()
        self.assertEqual(classify(no_goal), 'ANALYSIS GOAL REQUIRED')
        self.assertIsNone(no_goal['recommendation'])
        self.assertFalse(no_goal['generated_trade_eligible'])
        self.assertEqual(no_goal['decision_context']['verdict'], 'Choose an analysis goal')
        self.assertTrue(no_goal['decision_context']['strategy']['selection_required'])
        self.assertNotIn('future_capital_tradeoff', {r['cause'] for r in no_goal['evidence_limitations']['blocking_requirements']})
        self.assertEqual(no_goal['evidence_limitations']['analysis_requirements'][0]['input'], 'analysis_strategy')
        for goal in ('REBUILD', 'WIN NOW', 'RETOOL'):
            with self.subTest(goal=goal):
                explicit = self.evaluate(strategy=goal)
                self.assertFalse(analysis_goal_required(explicit))
                self.assertEqual(explicit['market_evidence'], no_goal['market_evidence'])
                self.assertEqual(explicit['multi_horizon_impact'], no_goal['multi_horizon_impact'])
                self.assertEqual(explicit['dimensions']['strategic_fit']['active']['manager_strategy']['strategy'], goal)
        self.assertEqual(self.evaluate(strategy='REBUILD')['recommendation'], 'WORTH PURSUING')
        self.assertEqual(self.evaluate(strategy='WIN NOW')['recommendation'], 'NOT WORTH IT')
        self.assertEqual(self.f.data, original)

    def test_goal_only_funnel_and_guidance_do_not_request_source_recovery(self):
        e = self.evaluate()
        f = self.funnel(e)
        counts = f.result(0)
        self.assertEqual(counts['analysis_goal_required'], 1)
        self.assertEqual(counts['missing_evidence'], 0)
        self.assertEqual(counts['analysis_requirements']['analysis_goal'], 1)
        self.assertEqual(result_state(f, []), 'ANALYSIS GOAL REQUIRED')
        guidance = zero_result_guidance(f, [], {'pools': {}}, projection_available=True)
        self.assertTrue(guidance['analysis_goal']['temporary_only'])
        self.assertEqual(guidance['analysis_goal']['choices'], ['WIN NOW', 'RETOOL', 'REBUILD'])
        for text in (guidance['message'], missing_evidence_guidance(e)):
            self.assertIn('temporary analysis goal', text)
            self.assertNotIn('Review the source gaps', text)
            self.assertNotIn('try again after source data updates', text)
            self.assertIn('cannot choose this goal', text)
        self.assertFalse(guidance['recommendation'])

    def test_real_active_source_gap_does_not_invent_a_strategy_requirement(self):
        self.gap('active')
        e = self.evaluate()
        self.assertEqual(classify(e), 'MISSING REQUIRED EVIDENCE')
        self.assertFalse(analysis_goal_required(e))
        self.assertIn('future_week_lineup', {r['cause'] for r in e['evidence_limitations']['blocking_requirements']})
        g = zero_result_guidance(self.funnel(e), [], {'pools': {}}, projection_available=True)
        self.assertFalse(g['analysis_goal']['selection_required'])
        self.assertIn('Review the source gaps', g['message'])

    def test_mixed_partner_gap_retains_both_independent_causes(self):
        self.gap('partner')
        e = self.evaluate()
        self.assertTrue(analysis_goal_required(e))
        self.assertEqual(classify(e), 'MISSING REQUIRED EVIDENCE')
        self.assertTrue(any(r['cause'] == 'future_week_lineup' and r.get('side') == 'partner'
                            for r in e['evidence_limitations']['blocking_requirements']))
        self.assertTrue(e['evidence_limitations']['analysis_requirements'])
        f = self.funnel(e)
        self.assertEqual(f.result(0)['analysis_requirements'], {
            'analysis_goal': 1, 'also_missing_evidence': 1,
            'meaning': 'Recorded active-franchise analysis input, not missing source data or counterparty intent. Counts may overlap real evidence gaps.'})
        g = zero_result_guidance(f, [], {'pools': {}}, projection_available=True)
        self.assertIn('Review the source gaps', g['message'])
        self.assertTrue(g['analysis_goal']['selection_required'])
        explicit = self.evaluate(strategy='REBUILD')
        self.assertFalse(analysis_goal_required(explicit))
        self.assertEqual(explicit['multi_horizon_impact'], e['multi_horizon_impact'])
        self.assertTrue(any(r['cause'] == 'future_week_lineup' for r in explicit['evidence_limitations']['blocking_requirements']))

    def test_supported_player_only_rejection_needs_no_goal(self):
        e = self.evaluate(assets_received=['c'])
        self.assertFalse(analysis_goal_required(e))
        self.assertIn(e['recommendation'], ('REJECT', 'NOT WORTH IT'))
        self.assertEqual(classify(e), 'STRATEGICALLY POOR')
        self.assertFalse(e['decision_context']['strategy']['selection_required'])

    def test_legacy_ambiguous_capital_reason_stays_unknown(self):
        e = self.evaluate()
        del e['dimensions']['strategic_fit']['active']['capital_strategy_fit']['unresolved_inputs']
        self.assertFalse(analysis_goal_required(e))
        self.assertEqual(classify(e), 'MISSING REQUIRED EVIDENCE')
        self.assertNotIn('temporary analysis goal', missing_evidence_guidance(e))

    def test_primary_counts_and_overlaps_do_not_promote_rejected_packages(self):
        complete = self.evaluate()
        rejected = self.evaluate(strategy='WIN NOW')
        self.gap('partner')
        mixed = self.evaluate()
        f = SearchFunnel(180)
        for e in (complete, rejected, mixed):
            self.assertFalse(f.assessed({'evaluation': e, 'proposal': self.payload}))
        r = f.result(0)
        self.assertEqual((r['evaluated'], r['analysis_goal_required'], r['missing_evidence'], r['strategically_rejected'], r['eligible']), (3, 1, 1, 1, 0))
        self.assertEqual(r['analysis_requirements']['analysis_goal'], 2)
        self.assertEqual(r['analysis_requirements']['also_missing_evidence'], 1)
        self.assertIn('future_week_lineup', r['evidence_limitations']['blocking_requirement_counts'])
        self.assertEqual(len(f.explorations), 1)
        self.assertIs(f.explorations[0]['evaluation'], rejected)
        self.assertFalse(f.explorations[0]['evaluation']['generated_trade_eligible'])
        self.assertEqual(f.explorations[0]['evaluation']['recommendation'], 'NOT WORTH IT')
