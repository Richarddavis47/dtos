"""Native team-score controls
expectations are retained source values."""
import copy
import unittest

from services.matchup_season import METHOD
from services.season_performance import season_performance
from src.core.intelligence.season_calendar import season_calendar
from src.core.player_value_projection.sleeper_actuals import scoring_identity
from src.ui.season_performance import season_panel


def fixture():
    league = dict(league_id='A', season='2026', sport='nfl', status='in_season',
                  scoring_settings={'rec': 1}, settings=dict(leg=5, last_scored_leg=4,
                  start_week=1, playoff_week_start=15, playoff_teams=4,
                  playoff_round_type=0, playoff_type=0, num_teams=2))
    weeks = {str(w): dict(availability='available', observed_at='2026-11-01T12:00:00Z',
                          rows=[dict(roster_id=1, points=p), dict(roster_id=2, points=10)])
             for w, p in [(1, 0), (2, -2), (3, 20), (4, 30), (5, 999)]}
    return dict(league=league, teams=[dict(roster_id=1), dict(roster_id=2)],
                season_matchups=dict(league_id='A', season='2026', methodology=METHOD,
                scoring_fingerprint=scoring_identity(league['scoring_settings']),
                calendar_reference=season_calendar(league)['reference'], weeks=weeks,
                semantic_generation='g1', observed_at='2026-11-01T12:00:00Z'))


class SeasonPerformanceTests(unittest.TestCase):
    def test_native_zero_negative_and_live_boundary(self):
        v = season_performance(fixture(), 1)
        self.assertEqual([r['points'] for r in v['weeks']], [0, -2, 20, 30])
        self.assertEqual(v['average'], 12)
        self.assertEqual(v['league_average'], 11)
        self.assertEqual([r['week'] for r in v['recent']], [2, 3, 4])

    def test_custom_override_and_invalid_override(self):
        d = fixture()
        row = d['season_matchups']['weeks']['1']['rows'][0]
        row['custom_points'] = -4
        self.assertEqual(season_performance(d, 1)['weeks'][0]['points'], -4)
        row['custom_points'] = 'invalid'
        self.assertIn(1, season_performance(d, 1)['missing'])

    def test_repeated_doubleheader_dedup_and_conflict(self):
        d = fixture()
        rows = d['season_matchups']['weeks']['4']['rows']
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(season_performance(d, 1)['average'], 12)
        rows[-1]['points'] = 31
        v = season_performance(d, 1)
        self.assertIn(4, v['missing'])
        self.assertIsNone(v['recent'][-1]['points'])

    def test_unequal_coverage_withholds_comparison_not_own_results(self):
        d = fixture()
        d['season_matchups']['weeks']['2']['rows'].pop()
        v = season_performance(d, 1)
        self.assertEqual(v['average'], 12)
        self.assertIsNone(v['league_average'])
        self.assertIn('comparison withheld', season_panel(d, 1))

    def test_missing_latest_week_not_replaced_with_older_week(self):
        d = fixture()
        d['season_matchups']['weeks']['4']['rows'] = []
        v = season_performance(d, 1)
        self.assertEqual([r['week'] for r in v['recent']], [2, 3, 4])
        self.assertIsNone(v['recent'][-1]['points'])

    def test_failed_refresh_retains_qualification(self):
        d = fixture()
        w = d['season_matchups']['weeks']['4']
        w['retained_rows'] = w.pop('rows')
        w['availability'] = 'unavailable'
        self.assertTrue(season_performance(d, 1)['retained'])
        self.assertIn('retained results', season_panel(d, 1, compact=True))

    def test_corrections_and_player_transfers_do_not_reconstruct_scores(self):
        d = fixture()
        d['teams'][0]['players'] = [{'id': 'new-player', 'points': 5000}]
        self.assertEqual(season_performance(d, 1)['average'], 12)
        d['season_matchups']['weeks']['4']['rows'][0]['points'] = 34
        d['season_matchups']['semantic_generation'] = 'g2'
        self.assertEqual(season_performance(d, 1)['average'], 13)
        self.assertIn('g2', season_panel(d, 1))

    def test_identity_scoring_calendar_isolation(self):
        for key, value in [('league_id', 'B'), ('season', '2025'),
                           ('scoring_fingerprint', 'other'), ('calendar_reference', 'other')]:
            d = fixture()
            d['season_matchups'][key] = value
            self.assertIsNone(season_performance(d, 1)['average'])
        self.assertIsNone(season_performance(fixture(), 3)['average'])

    def test_home_and_team_same_values_no_new_action(self):
        d = fixture()
        for compact in [False, True]:
            h = season_panel(d, 1, compact=compact)
            self.assertIn('12.00', h)
            self.assertIn('4/4', h)
            self.assertNotIn('contender', h)
            self.assertNotIn('<form', h)
