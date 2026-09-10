"""Scope, missing evidence and stable ordering are part of the rank contract."""
import unittest

from src.core.valuation.ranking import rank_players


class ScopedPlayerRankTests(unittest.TestCase):
    def ranks(self, values, positions, scope="global"):
        return rank_players(values, positions, scope=scope, value_basis="intrinsic", methodology="test-v1")

    def test_overall_and_position_are_not_aliases(self):
        rows = self.ranks({'q1': 700, 'q2': 600, 'w1': 650}, {'q1': 'QB', 'q2': 'QB', 'w1': 'WR'})
        self.assertEqual(rows['q2']['overall'].rank, 3)
        self.assertEqual(rows['q2']['position'].rank, 2)
        self.assertEqual(rows['w1']['position'].rank, 1)
        self.assertEqual(rows['q2']['overall'].universe_size, 3)

    def test_roster_scope_cannot_silently_become_global(self):
        rows = self.ranks({'q2': 600}, {'q2': 'QB'}, "roster")
        self.assertEqual(rows['q2']['position'].rank, 1)
        self.assertEqual(rows['q2']['position'].scope, 'roster')

    def test_missing_unranked_zero_ranked_and_ties_stable(self):
        values = {'b': 10, 'a': 10, 'zero': 0, 'missing': None}
        positions = dict.fromkeys(values, 'WR')
        rows = self.ranks(values, positions)
        self.assertEqual(rows['a']['overall'].rank, 1)
        self.assertEqual(rows['b']['overall'].rank, 2)
        self.assertEqual(rows['zero']['overall'].rank, 3)
        self.assertIsNone(rows['missing']['overall'].rank)
        self.assertEqual(rows, self.ranks(dict(reversed(list(values.items()))), positions))

    def test_generation_changes_for_semantics_not_input_order(self):
        first = self.ranks({'a': 1}, {'a': 'QB'})
        changed = self.ranks({'a': 2}, {'a': 'QB'})
        self.assertNotEqual(first['a']['overall'].generation, changed['a']['overall'].generation)

    def test_bad_identity_or_nonfinite_value_rejected(self):
        with self.assertRaises(ValueError):
            self.ranks({'a': 1}, {'b': 'QB'})
        with self.assertRaises(ValueError):
            self.ranks({'a': float('nan')}, {'a': 'QB'})
