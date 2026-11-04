import unittest
from src.core.intelligence.pick_context import pick_portfolio, assess_pick_range


class PickPortfolioTests(unittest.TestCase):
    def ranged(self):
        return {'year': 2027, 'round': 1, 'original_roster_id': 2, 'current_owner_id': 1,
                'range_evidence': {'league_id': 'A', 'year': 2027, 'original_roster_id': 2,
                    'reference': 'canonical', 'generation': 'g', 'earliest_slot': 1,
                    'latest_slot': 3, 'league_size': 10, 'draft_order_rules_supported': True,
                    'data_complete': True, 'concept': 'draft_order_interval', 'season_stage': 'regular_season'}}

    def test_range_follows_original_not_current_owner(self):
        pick = self.ranged()
        a = assess_pick_range(pick, league_id='A')
        b = assess_pick_range({**pick, 'current_owner_id': 9, 'market_value': 999}, league_id='A')
        self.assertEqual(a['projected_range'], 'EARLY')
        self.assertEqual(a['projected_range'], b['projected_range'])
        self.assertFalse(a.get('exact_slot_established', False))
        self.assertEqual(assess_pick_range(pick, league_id='B')['projected_range'], 'UNKNOWN')

    def test_interval_crossing_and_seed_not_locked(self):
        pick = self.ranged()
        pick['range_evidence']['latest_slot'] = 4
        self.assertEqual(assess_pick_range(pick, league_id='A')['projected_range'], 'UNKNOWN')
        pick['range_evidence'].update(latest_slot=1, earliest_slot=1, concept='playoff_seed')
        self.assertEqual(assess_pick_range(pick, league_id='A')['projected_range'], 'UNKNOWN')

    def test_exact_requires_completed_multiweek_round(self):
        pick = self.ranged()
        pick['range_evidence'].update(latest_slot=1, season_stage='complete', result_locked=True,
                                      all_round_components_complete=False)
        self.assertFalse(assess_pick_range(pick, league_id='A').get('exact_slot_established', False))
        pick['range_evidence']['all_round_components_complete'] = True
        result = assess_pick_range(pick, league_id='A')
        self.assertEqual(result['exact_slot'], '1.01')
        self.assertEqual(result['projected_range_confidence'], 'HIGH')

    def test_traded_original_and_timing_no_scalar(self):
        picks = [{'year': 2027, 'round': 1, 'original_roster_id': 2, 'current_owner_id': 1},
                 {'year': 2028, 'round': 2, 'original_roster_id': 1, 'current_owner_id': 1}]
        result = pick_portfolio(picks, league_id='A', generation='g')
        self.assertEqual(result['original_franchise_exposure'], {'1': 1, '2': 1})
        self.assertEqual(result['years'], {'2027': 1, '2028': 1})
        self.assertIsNone(result['score'])
        self.assertEqual(result, pick_portfolio(list(reversed(picks)), league_id='A', generation='g'))

    def test_market_and_unsupported_range_do_not_forecast(self):
        pick = {'year': 2027, 'round': 1, 'original_roster_id': 2,
                'projected_range': 'EARLY', 'market_value': 999, 'projected_range_confidence': 'HIGH'}
        result = pick_portfolio([pick], league_id='A', generation='g')
        self.assertEqual(result['projected_range_distribution'], {'UNKNOWN': 1})
        self.assertEqual(result['range_confidence_distribution'], {'LOW': 1})

    def test_duplicate_and_cross_league_rejected(self):
        pick = {'year': 2027, 'round': 1, 'original_roster_id': 1, 'league_id': 'A'}
        with self.assertRaises(ValueError):
            pick_portfolio([pick, pick], league_id='A', generation='g')
        with self.assertRaises(ValueError):
            pick_portfolio([pick], league_id='B', generation='g')
