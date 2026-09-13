import unittest
from src.core.fois.decision_evaluators import evaluate_decision
from src.core.history_context.timestamps import canonical_utc_timestamp


class DecisionTimeBoundaryTests(unittest.TestCase):
    def row(self, time):
        return dict(draft_id='d', player_id='p', pick_number=1, owner_id='gm',
                    league_id='L', occurred_at=time)

    def test_missing_is_not_failed_market_lookup(self):
        result=evaluate_decision(self.row(None),'drafting')['process']
        self.assertIn('DECISION_TIME_UNAVAILABLE',result['reasons'])
        self.assertIn('MARKET_LOOKUP_UNAVAILABLE_TIME_BOUNDARY',result['reasons'])
        self.assertNotIn('NO_CONTEMPORANEOUS_MARKET',result['reasons'])

    def test_invalid_time_and_missing_market_distinct(self):
        invalid=evaluate_decision(self.row('2024-draft-1'),'drafting')['process']
        valid=evaluate_decision(self.row('2024-08-01T12:00:00Z'),'drafting')['process']
        self.assertIn('INVALID_TIME_BOUNDARY',invalid['reasons'])
        self.assertIn('NO_CONTEMPORANEOUS_MARKET',valid['reasons'])

    def test_same_day_ordering_and_timezone(self):
        row=self.row(canonical_utc_timestamp('2024-08-01T08:00:00-04:00'))
        alternative=dict(asset_id='q',available_at_decision=True,reference='pool',
                         known_at='2024-08-01T11:00:00Z')
        market=[dict(asset_id=p,value=100,reference=p,context='format',observed_at=t)
                for p,t in [('p','2024-08-01T11:59:59Z'),('q','2024-08-01T11:00:00Z')]]
        self.assertEqual(evaluate_decision(row,'drafting',market=market,alternatives=[alternative])['process']['evaluability'],'partially_evaluable')
        market[0]['observed_at']='2024-08-01T12:00:01Z'
        self.assertEqual(evaluate_decision(row,'drafting',market=market,alternatives=[alternative])['process']['evaluability'],'insufficient')

    def test_unknown_faab_does_not_block_exchange_assessment(self):
        row=dict(transaction_id='t',owner_id='gm',league_id='L',occurred_at='2024-08-01T12:00:00Z',adds=['p'],drops=['q'],faab_bid=None)
        market=[dict(asset_id=p,value=100,reference=p,context='format',observed_at='2024-07-01T00:00:00Z') for p in ('p','q')]
        self.assertEqual(evaluate_decision(row,'waivers',market=market)['process']['evaluability'],'partially_evaluable')

