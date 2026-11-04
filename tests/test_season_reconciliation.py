import unittest
from src.core.history_context.reconciliation import reconcile_season


class SeasonReconciliationTests(unittest.TestCase):
    def test_missing_regular_season_boundary_is_not_zero_record(self):
        result = reconcile_season({'league': {}, 'rosters': [
            {'roster_id': 1, 'settings': {'wins': 7}}]})
        row = result['standings'][0]
        self.assertIsNone(row['head_to_head'])
        self.assertEqual(row['comparison_availability'], 'unavailable')
        self.assertEqual(row['differences'], [])

    def test_regular_results_do_not_include_playoffs_and_discrepancies_remain(self):
        facts = {'league': {'season': '2025', 'settings': {'playoff_week_start': 2}},
                 'rosters': [{'roster_id': 1, 'settings': {'wins': 1, 'losses': 0, 'ties': 0, 'fpts': 100, 'fpts_decimal': 25}},
                             {'roster_id': 2, 'settings': {'wins': 1, 'losses': 0}}],
                 'matchups': {'1': [{'roster_id': 1, 'matchup_id': 1, 'points': 100.25},
                                   {'roster_id': 2, 'matchup_id': 1, 'points': 90}],
                              '2': [{'roster_id': 1, 'matchup_id': 2, 'points': 0},
                                    {'roster_id': 2, 'matchup_id': 2, 'points': 100}]}}
        result = reconcile_season(facts)
        self.assertEqual(result['standings'][0]['differences'], [])
        self.assertEqual(result['standings'][1]['differences'], ['wins', 'losses'])
        self.assertEqual(result['standings'][0]['head_to_head']['games'], 1)

    def test_duplicate_transactions_are_not_hidden_and_failed_attempts_retained(self):
        transaction = {'transaction_id': 'x', 'type': 'waiver', 'status': 'failed'}
        result = reconcile_season({'league': {}, 'transactions': {'1': [transaction], '2': [transaction]}})
        self.assertEqual(result['duplicate_transaction_ids'], 1)
        self.assertEqual(result['transaction_statuses']['failed'], 2)
