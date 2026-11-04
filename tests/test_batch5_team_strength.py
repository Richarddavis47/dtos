import copy
import tempfile
import unittest
from pathlib import Path

from src.core.intelligence.team_strength import prepare_team_strength
from src.core.projection_intelligence.service import ProjectionService


class TeamStrengthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = ProjectionService(Path(self.tmp.name) / 'projection.sqlite3')
        self.data = {'league': {'league_id': 'A', 'season': 2026, 'scoring_settings': {'pass_yd': 1}},
                     'players': [{'id': pid, 'position': 'QB'} for pid in ('a', 'b', 'c', 'd')], 'week': 2}
        self.payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week,
                                 'stats': {'pass_yd': points}, 'player': {'position': 'QB'}}
                                for pid, points in [('a', 10), ('b', 5), ('c', 8), ('d', 3)]]
                         for week in (2, 3, 4, 5)}
        self.service.publish_horizon(self.payloads, data=self.data, league_id='A', season=2026, current_week=2)
        self.rosters = [{'roster_id': 1, 'players': ['a', 'b'], 'starters': ['b']},
                        {'roster_id': 2, 'players': ['c', 'd'], 'starters': ['c']}]

    def prepare(self, **overrides):
        args = dict(league_id='A', season=2026, current_week=2, rosters=self.rosters,
                    roster_positions=['QB', 'BN'], regular_season_weeks=[1, 2, 3],
                    playoff_rounds=[[4, 5]], calendar_reference='canonical-season-A', next_n=3)
        args.update(overrides)
        return prepare_team_strength(self.service, **args)

    def test_complete_horizons_preserve_actual_and_round_components(self):
        original = copy.deepcopy(self.rosters)
        result = self.prepare()
        team = result['teams']['1']
        self.assertEqual(team['actual_submitted_starter_ids'], ['b'])
        self.assertEqual(team['weekly'][2]['optimal']['entries'][0]['asset_id'], 'a')
        self.assertEqual(team['horizons']['next_n']['total'], 30)
        self.assertEqual(team['horizons']['rest_of_regular_season']['total'], 20)
        self.assertEqual(team['horizons']['playoff_window']['weeks_requested'], [4, 5])
        self.assertEqual(result['playoff_round_weeks'], [[4, 5]])
        self.assertIsNone(result['playoff_opponent'])
        self.assertEqual(team['horizons']['current_week']['league_rank'], 1)
        self.assertEqual(self.rosters, original)

    def test_unsupported_week_is_not_extrapolated(self):
        result = self.prepare(playoff_rounds=[[4, 5], [6]])['teams']['1']['horizons']['playoff_window']
        self.assertEqual(result['weeks_missing'], [6])
        self.assertIsNone(result['total'])
        self.assertEqual(result['supported_week_subtotal'], 20)
        self.assertEqual(result['availability'], 'partial')
        self.assertIsNone(result['league_rank'])

    def test_unknown_lineup_does_not_rank_as_zero(self):
        self.rosters[1]['players'] = ['unknown']
        self.rosters[1]['starters'] = []
        result = self.prepare()
        self.assertIsNone(result['teams']['2']['horizons']['current_week']['total'])
        self.assertIsNone(result['teams']['1']['horizons']['current_week']['league_rank'])

    def test_zero_supported_and_reserves_are_week_specific(self):
        self.payloads[3][0]['stats'] = {'pass_yd': 0}
        self.payloads[3][1]['stats'] = {'pass_yd': 0}
        self.service.publish_horizon(self.payloads, data=self.data, league_id='A', season=2026, current_week=2)
        result = self.prepare()['teams']['1']
        self.assertEqual(result['weekly'][3]['optimal']['projected_points'], 0)
        self.assertEqual(result['weekly'][3]['reserve_capacity']['known_subtotal'], 0)
        self.assertEqual(result['weekly'][2]['reserve_capacity']['known_subtotal'], 5)

    def test_generation_is_pinned_even_if_publication_changes_during_read(self):
        before = self.prepare()
        read = self.service.week_snapshot
        published = False

        def racing_read(week, *, generation_snapshot):
            nonlocal published
            if not published:
                published = True
                self.payloads[3][0]['stats'] = {'pass_yd': 100}
                self.service.publish_horizon(self.payloads, data=self.data, league_id='A', season=2026, current_week=2)
            return read(week, generation_snapshot=generation_snapshot)
        self.service.week_snapshot = racing_read
        during = self.prepare()
        self.assertEqual(before, during)
        self.assertNotEqual(self.prepare()['semantic_generation'], before['semantic_generation'])

    def test_known_bye_uses_week_specific_replacement_without_injury_forecast(self):
        result = self.prepare(bye_evidence={'season': 2026, 'reference': 'canonical-nfl-schedule',
                                          'player_weeks': {'a': 3}})['teams']['1']
        self.assertEqual(result['weekly'][2]['optimal']['projected_points'], 10)
        self.assertEqual(result['weekly'][3]['optimal']['projected_points'], 5)
        self.assertEqual(result['weekly'][3]['known_bye_player_ids'], ['a'])
        with self.assertRaises(ValueError):
            self.prepare(bye_evidence={'season': 2025, 'reference': 'old', 'player_weeks': {'a': 3}})

    def test_scope_and_calendar_fail_closed(self):
        with self.assertRaises(ValueError):
            self.prepare(league_id='B')
        with self.assertRaises(ValueError):
            self.prepare(playoff_rounds=[[3, 4]])
        with self.assertRaises(ValueError):
            self.prepare(playoff_rounds=[[4, 5], [5]])
        with self.assertRaises(ValueError):
            self.prepare(calendar_reference=None)
        profile = self.prepare(regular_season_weeks=None, playoff_rounds=None, calendar_reference=None)
        self.assertEqual(profile['teams']['1']['horizons']['playoff_window']['reason'], 'LEAGUE_CALENDAR_UNAVAILABLE')

    def test_replay_and_restart_are_deterministic_without_writes(self):
        before = self.prepare()
        size = self.service._database_file.stat().st_size
        for _ in range(20):
            self.assertEqual(self.prepare(), before)
        self.assertEqual(self.service._database_file.stat().st_size, size)
        self.service = ProjectionService(self.service._database_file)
        self.assertEqual(self.prepare(), before)
        self.assertEqual(before['durable_writes'], 0)
