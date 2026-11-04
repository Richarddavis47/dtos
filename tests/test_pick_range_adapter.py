import unittest

from src.core.trade_intelligence.market.trade_market import _pick_context


class PickRangeAdapterTests(unittest.TestCase):
    def test_team_rank_cannot_invent_range(self):
        pick = dict(season=2027, round=1, original_roster_id=1, current_owner_id=4)
        data = {'teams': [dict(roster_id=i, points_for=i * 100, wins=i, losses=0)
                          for i in range(1, 11)]}
        result = _pick_context(pick, data)
        self.assertEqual(result['projected_range'], 'UNKNOWN')
        self.assertNotIn('projected_range', pick)

    def test_unsupported_range_and_exact_slot_do_not_survive_adapter(self):
        result = _pick_context(dict(projected_range='EARLY', exact_slot='1.03'), {})
        self.assertEqual(result['projected_range'], 'UNKNOWN')
        self.assertNotIn('exact_slot', result)

    def test_prepared_evidence_is_not_recomputed_from_current_owner(self):
        pick = dict(year=2027, round=1, original_roster_id=1, current_owner_id=4,
                    range_evidence=dict(league_id='A', year=2027, original_roster_id=1,
                        reference='canonical-draft-order', generation='g', earliest_slot=9,
                        latest_slot=9, league_size=10, draft_order_rules_supported=True,
                        data_complete=True, concept='draft_order_interval',
                        season_stage='complete', result_locked=True,
                        all_round_components_complete=True))
        data = {'league': {'league_id': 'A'}, 'teams': []}
        result = _pick_context(pick, data)
        self.assertEqual(result['projected_range'], 'LATE')
        self.assertEqual(result['exact_slot'], '1.09')
        self.assertEqual(result['projected_range_confidence'], 'HIGH')
        moved = _pick_context({**pick, 'current_owner_id': 7}, data)
        for field in ('projected_range', 'exact_slot', 'projected_range_confidence'):
            self.assertEqual(result[field], moved[field])


if __name__ == '__main__':
    unittest.main()
