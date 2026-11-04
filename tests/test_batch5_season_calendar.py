import unittest

from src.core.intelligence.season_calendar import season_calendar


def league(**settings):
    return {'league_id': 'A', 'season': '2026', 'sport': 'nfl', 'status': 'in_season',
            'settings': {'leg': 2, 'last_scored_leg': 1, 'start_week': 1, 'playoff_week_start': 14,
                         'playoff_teams': 6, 'playoff_round_type': 1, 'playoff_type': 0, **settings}}


class SeasonCalendarTests(unittest.TestCase):
    def test_two_week_final_preserves_components_without_opponent(self):
        result = season_calendar(league())
        self.assertEqual(result['playoff_rounds'], [[14], [15], [16, 17]])
        self.assertEqual(result['remaining_regular_season_weeks'], list(range(2, 14)))
        self.assertEqual(result['first_round_bye_slots'], 2)
        self.assertEqual(result['locked_bye_roster_ids'], [])
        self.assertIsNone(result['playoff_opponent'])

    def test_different_settings_have_different_scoped_calendar(self):
        first = season_calendar(league())
        other = league(playoff_teams=4, playoff_week_start=15, playoff_round_type=2)
        other['league_id'] = 'B'
        result = season_calendar(other)
        self.assertEqual(result['playoff_rounds'], [[15, 16], [17, 18]])
        self.assertEqual(result['first_round_bye_slots'], 0)
        self.assertNotEqual(result['reference'], first['reference'])

    def test_missing_unknown_and_impossible_settings_do_not_default(self):
        for change in ({'playoff_round_type': None}, {'playoff_round_type': 9},
                       {'playoff_week_start': 17}, {'last_scored_leg': 3}, {'playoff_teams': 12}):
            self.assertEqual(season_calendar(league(**change))['availability'], 'unavailable')
