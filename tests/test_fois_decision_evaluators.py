import unittest
from src.core.fois.decision_evaluators import evaluate_decision


class DecisionEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(draft_id='d', transaction_id='t', player_id='p', pick_number=3,
                        owner_id='gm', league_id='L', occurred_at='2024-08-01T00:00:00Z',
                        adds=('p',), drops=('q',), faab_bid=0)
        self.market = [dict(asset_id=p, value=v, reference=p, context='same-format-v1',
                            observed_at='2024-07-01T00:00:00Z') for p,v in [('p',500),('q',400)]]

    def test_draft_requires_known_alternative_not_later_selection(self):
        alternative = dict(asset_id='q', available_at_decision=True, reference='pool', known_at='2024-07-01T00:00:00Z')
        result = evaluate_decision(self.row,'drafting',market=self.market,alternatives=[alternative])
        self.assertEqual(result['process']['evaluability'],'partially_evaluable')
        self.assertIsNone(result['process']['quality'])
        alternative['known_at']='2025-01-01T00:00:00Z'
        self.assertEqual(evaluate_decision(self.row,'drafting',market=self.market,alternatives=[alternative])['process']['evaluability'],'insufficient')

    def test_waiver_missing_zero_and_future_prices(self):
        result=evaluate_decision(self.row,'waivers',market=self.market)
        self.assertEqual(result['process']['assessment'][0]['difference'],100)
        self.assertNotIn('FAAB_UNAVAILABLE_OR_NOT_APPLICABLE',result['process']['reasons'])
        self.market[0]['observed_at']='2025-01-01T00:00:00Z'
        self.assertEqual(evaluate_decision(self.row,'waivers',market=self.market)['process']['evaluability'],'insufficient')

    def test_nonmarket_context_and_outcome_are_independent(self):
        context=dict(reference='roster',as_of='2024-07-01T00:00:00Z',owner_id='gm',league_id='L',assessment='supported_need_addressed')
        before=evaluate_decision(self.row,'drafting',roster_assessment=context)
        after=evaluate_decision(self.row,'drafting',roster_assessment=context,
            outcome=dict(reference='later',as_of='2025-01-01T00:00:00Z',decision_id='t',league_id='L',assessment='later_production_available'))
        self.assertEqual(before['process'],after['process'])
        self.assertEqual(after['outcome']['evaluability'],'partially_evaluable')
        context['league_id']='other'
        self.assertEqual(evaluate_decision(self.row,'drafting',roster_assessment=context)['process']['evaluability'],'insufficient')
