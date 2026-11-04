import itertools
import unittest

from src.core.trade_intelligence.lineup import optimal_legal_lineup


class LegalLineupTests(unittest.TestCase):
    def test_partial_is_not_complete_team_total(self):
        result = optimal_legal_lineup([{'id': 'q', 'position': 'QB', 'projected_points': 21.123}], ['QB', 'WR'])
        self.assertFalse(result.available)
        self.assertIsNone(result.projected_points)
        self.assertEqual(result.unsupported_slots, ('WR',))
        self.assertEqual(result.known_starters_subtotal, 21.123)

    def test_unknown_does_not_override_true_zero_or_block_supported_lineup(self):
        players = [{'id': 'unknown', 'position': 'QB', 'projected_points': None, 'dtos_projection': 100},
                   {'id': 'zero', 'position': 'QB', 'projection': {'projected_points': 0, 'value': 100}}]
        result = optimal_legal_lineup(players, ['QB'])
        self.assertTrue(result.available)
        self.assertEqual(result.projected_points, 0)
        self.assertEqual(result.entries[0].asset_id, 'zero')
        self.assertEqual(result.missing_player_ids, ('unknown',))

    def test_reserve_taxi_bye_excluded_without_mutation(self):
        players = [{'id': 'ir', 'position': 'QB', 'projected_points': 100, 'roster_slot': 'IR'},
                   {'id': 'taxi', 'position': 'QB', 'projected_points': 90, 'roster_slot': 'TAXI'},
                   {'id': 'bye', 'position': 'QB', 'projected_points': 80, 'bye_week': 4},
                   {'id': 'ok', 'position': 'QB', 'projected_points': 10, 'roster_slot': 'BN'}]
        result = optimal_legal_lineup(players, ['QB', 'BN', 'IR'], week=4)
        self.assertEqual(result.projected_points, 10)
        self.assertEqual(players[-1]['roster_slot'], 'BN')

    def test_exact_assignment_matches_exhaustive_oracle_and_is_order_stable(self):
        players = [{'id': str(i), 'position': pos, 'projected_points': value}
                   for i, (pos, value) in enumerate([('QB', 23), ('QB', 22), ('QB', 21),
                                                    ('RB', 20), ('WR', 19), ('TE', 18)])]
        slots = ['QB', 'FLEX', 'SUPER_FLEX']
        allowed = [{'QB'}, {'RB', 'WR', 'TE'}, {'QB', 'RB', 'WR', 'TE'}]
        expected = max(sum(p['projected_points'] for p in lineup)
                       for lineup in itertools.permutations(players, 3)
                       if all(p['position'] in legal for p, legal in zip(lineup, allowed)))
        result = optimal_legal_lineup(players, slots)
        self.assertEqual(result.projected_points, expected)
        self.assertEqual(result, optimal_legal_lineup(reversed(players), slots))
        self.assertEqual(len({entry.asset_id for entry in result.entries}), 3)

    def test_duplicate_identity_rejected(self):
        player = {'id': 'q', 'position': 'QB', 'projected_points': 10}
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            optimal_legal_lineup([player, player], ['QB', 'SUPER_FLEX'])

    def test_nonfinite_boolean_are_not_projection_evidence(self):
        for value in (float('nan'), float('inf'), True):
            result = optimal_legal_lineup([{'id': 'q', 'position': 'QB', 'projected_points': value}], ['QB'])
            self.assertIsNone(result.projected_points)
