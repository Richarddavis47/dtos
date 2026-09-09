import unittest

from src.core.history_context.ownership import reconcile_ownership


class HistoryOwnershipTests(unittest.TestCase):
    def season(self, league, year, previous, owner):
        return {'league': {'league_id': league, 'season': str(year), 'name': 'Same name',
                           'previous_league_id': previous},
                'rosters': [{'roster_id': 1, 'owner_id': owner, 'co_owners': ['co']} ]}

    def test_changed_and_returning_owner_are_observations_not_invented_dates(self):
        facts = [self.season('a', 2021, None, 'one'), self.season('b', 2022, 'a', 'two'),
                 self.season('c', 2023, 'b', 'one')]
        result = reconcile_ownership(facts)
        self.assertEqual(len(result['ownership_changes']), 2)
        self.assertTrue(all(row['occurred_at'] is None for row in result['ownership_changes']))
        self.assertEqual(result, reconcile_ownership(reversed(facts)))
        self.assertEqual(result['observations'][-1]['co_owners'], ['co'])

    def test_same_name_or_missing_link_never_joins_franchises(self):
        result = reconcile_ownership([self.season('a', 2021, None, 'one'),
                                      self.season('b', 2022, 'missing', 'two')])
        self.assertEqual(result['ownership_changes'], [])
        self.assertEqual(result['observations'][-1]['franchise_continuity'], 'unproven')
        self.assertEqual(len(result['gaps']), 1)

    def test_invalid_chain_and_duplicate_identity_fail_closed(self):
        a = self.season('a', 2021, 'b', 'one')
        b = self.season('b', 2022, 'a', 'two')
        with self.assertRaises(ValueError):
            reconcile_ownership([a, b])
        with self.assertRaises(ValueError):
            reconcile_ownership([a, a])
