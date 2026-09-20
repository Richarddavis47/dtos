import tempfile
import unittest
from pathlib import Path

from src.core.projection_intelligence.scoring import fantasy_points, sleeper_web_display
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import parse_projection_feed


# Ordered source scoring fields, 2026 W2. Non-scoring fields do not contribute.
ALLEN = {'fum': .43, 'fum_lost': .19, 'pass_2pt': .1, 'pass_att': 30.6,
         'pass_cmp': 20.29, 'pass_cmp_40p': .44, 'pass_fd': 23.09, 'pass_inc': 10.31,
         'pass_int': .45, 'pass_int_td': 0, 'pass_sack': 2.68, 'pass_td': 1.68,
         'pass_yd': 230.85, 'rush_2pt': .04, 'rush_40p': .07, 'rush_att': 6,
         'rush_fd': 2.69, 'rush_td': .55, 'rush_yd': 26.93}
SCORING = {'pass_int': -1, 'pass_2pt': 2, 'rush_td': 6, 'rush_fd': .5,
           'fum_lost': -2, 'pass_cmp': .10000000149011612, 'rush_2pt': 2,
           'pass_cmp_40p': .5, 'pass_fd': .10000000149011612, 'pass_yd': .04,
           'pass_td': 4, 'rush_yd': .1, 'rush_40p': .5, 'rec': 1, 'rec_yd': .1,
           'rec_td': 6, 'rec_2pt': 2, 'rec_fd': .5, 'rec_40p': .5}
GIBBS = {'fum': .21, 'fum_lost': .09, 'rec': 3.89, 'rec_2pt': .01,
         'rec_40p': .39, 'rec_fd': 2.42, 'rec_td': .15, 'rec_yd': 24.16,
         'rush_2pt': .06, 'rush_40p': .19, 'rush_att': 18.5, 'rush_fd': 10.74,
         'rush_td': 1.26, 'rush_yd': 107.39}


class SleeperDisplayTests(unittest.TestCase):
    def test_binary_surface_rounding_does_not_contaminate_canonical(self):
        self.assertEqual(fantasy_points(ALLEN, SCORING), 27.335)
        self.assertEqual(sleeper_web_display(ALLEN, SCORING, list(ALLEN)), '27.33')
        self.assertEqual(fantasy_points(GIBBS, SCORING), 32.335)
        self.assertEqual(sleeper_web_display(GIBBS, SCORING, list(GIBBS)), '32.34')

    def test_order_is_provenance_not_a_new_projection_universe(self):
        reverse = dict(reversed(list(ALLEN.items())))
        self.assertEqual(fantasy_points(reverse, SCORING), fantasy_points(ALLEN, SCORING))
        self.assertEqual(sleeper_web_display(reverse, SCORING, list(ALLEN)), '27.33')
        self.assertIsNone(sleeper_web_display(reverse, SCORING, None))
        self.assertIsNone(sleeper_web_display(reverse, SCORING, ['pass_yd']))

    def test_missing_is_not_zero(self):
        self.assertIsNone(sleeper_web_display({}, SCORING, []))
        self.assertEqual(sleeper_web_display({'rush_yd': 0}, SCORING, ['rush_yd']), '0.00')

    def test_active_matchup_presentation_keeps_source_display_separate(self):
        from routes.matchups import _starter_projection_html
        row = {'canonical_projection': 27.335, 'sleeper_web_display_projection': '27.33'}
        html = _starter_projection_html(row)
        self.assertIn('<b>27.33</b>', html)
        self.assertIn('data-dtos-value="27.33"', html)
        self.assertEqual(row['canonical_projection'], 27.335)
        self.assertIn('Projection unavailable', _starter_projection_html({
            'canonical_projection': None, 'sleeper_web_display_projection': '0.00'}))

    def test_active_publication_and_restart_preserve_display_and_exact_value(self):
        payload=[{'player_id': 'q', 'season': 2026, 'week': 2, 'stats': ALLEN,
                  'player': {'position': 'QB'}}]
        rows, _, _ = parse_projection_feed(payload, season=2026, week=2, scoring=SCORING)
        self.assertEqual(rows['q']['source_stat_order'], list(ALLEN))
        data={'league': {'league_id': 'a', 'season': 2026, 'scoring_settings': SCORING},
              'players': [{'id': 'q', 'position': 'QB'}], 'week': 2}
        with tempfile.TemporaryDirectory() as directory:
            service=ProjectionService(Path(directory)/'projection.sqlite3')
            result=service.publish_horizon({2: payload}, data=data, league_id='a', season=2026, current_week=2)
            row=result['players']['q']
            self.assertEqual(row['canonical_projection'], 27.335)
            self.assertEqual(row['sleeper_web_display_projection'], '27.33')
            again=service.publish_horizon({2: payload}, data=data, league_id='a', season=2026, current_week=2)
            self.assertEqual(result['projection_snapshot_id'], again['projection_snapshot_id'])
            restarted=ProjectionService(Path(directory)/'projection.sqlite3')
            self.assertEqual(restarted.week_snapshot(2)['players']['q']['sleeper_web_display_projection'], '27.33')
