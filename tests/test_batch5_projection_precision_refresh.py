import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from src.core.projection_intelligence.scoring import fantasy_points
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import parse_projection_feed, source_update_time


class ProjectionFoundationTests(unittest.TestCase):
    def test_source_coefficient_normalization_removes_float32_noise_only(self):
        from decimal import Decimal
        from src.core.projection_intelligence.scoring import scoring_coefficient
        self.assertEqual(scoring_coefficient(.10000000149011612), Decimal('.1'))
        self.assertEqual(scoring_coefficient('0.12345'), Decimal('.1235'))
        self.assertEqual(scoring_coefficient('-0.12345'), Decimal('-.1234'))
        self.assertEqual(fantasy_points({'pass_cmp': 20.29, 'pass_fd': 23.09},
                         {'pass_cmp': .10000000149011612, 'pass_fd': .10000000149011612}), 4.338)
        self.assertEqual(fantasy_points({'pass_yd': 230.851234}, {'pass_yd': .04}), 9.23404936)

    def test_precision_and_bonus_evidence_not_threshold_invention(self):
        self.assertEqual(fantasy_points({'pass_yd': 230.85, 'pass_cmp': 20.29, 'pass_fd': 23.09},
                                      {'pass_yd': .04, 'pass_cmp': .1, 'pass_fd': .1}), 13.572)
        self.assertEqual(fantasy_points({'pass_yd': 350}, {'pass_yd': .04, 'bonus_pass_yd_300': 5}), 14)
        self.assertEqual(fantasy_points({'rec': 4.1, 'bonus_rec_te': 4.1},
                                      {'rec': 1, 'bonus_rec_te': .5}, 'TE'), 6.15)

    def test_millisecond_provider_time(self):
        self.assertEqual(source_update_time(1789343163527), '2026-09-13T23:46:03.527000+00:00')

    def test_empty_weeks_have_distinct_identity(self):
        a = parse_projection_feed([], season=2026, week=2, scoring={})[1]
        b = parse_projection_feed([], season=2026, week=3, scoring={})[1]
        self.assertNotEqual(a, b)

    def test_refresh_withdrawal_return_and_replay_preserve_observation_history(self):
        data = {'league': {'season': 2026, 'scoring_settings': {'pass_yd': .04}},
                'week': 1, 'players': [{'id': 'q', 'position': 'QB'}]}
        def feed(week, yards):
            return [{'player_id': 'q', 'season': 2026, 'week': week, 'stats': {'pass_yd': yards}}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projections.sqlite3'
            service = ProjectionService(path, league_id='a')
            service.ingest_sleeper(feed(1, 200), data=data, league_id='a', season=2026, week=1)
            for day, payload, expected in ((1, feed(2, 230.85), 9.234), (2, feed(2, 240.15), 9.606),
                                          (3, [], None), (4, feed(2, 230.85), 9.234)):
                with patch('src.core.projection_intelligence.service._now', return_value=f'2026-09-{day:02}T00:00:00+00:00'):
                    service.cache_sleeper_week(payload, scoring={}, season=2026, week=2)
                self.assertEqual(service.week_snapshot(2)['players']['q']['canonical_projection'], expected)
            historical = service.source_as_of(season=2026, week=2, observed_as_of='2026-09-02T12:00:00+00:00')
            self.assertEqual(historical['players']['q']['projected_stats']['pass_yd'], 240.15)
            self.assertIsNone(service.source_as_of(season=2026, week=2, observed_as_of='2026-08-01T00:00:00+00:00'))
            with closing(sqlite3.connect(path)) as db:
                before = db.execute('SELECT COUNT(*) FROM projection_source_history').fetchone()[0]
                states = db.execute('SELECT COUNT(*) FROM projection_player_states').fetchone()[0]
            size = path.stat().st_size
            for _ in range(100):
                service.cache_sleeper_week(feed(2, 230.85), scoring={}, season=2026, week=2)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM projection_source_history').fetchone()[0], before)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM projection_player_states').fetchone()[0], states)
            self.assertEqual(path.stat().st_size, size)
            restored = ProjectionService(path, league_id='a')
            self.assertEqual(restored.week_snapshot(2)['players']['q']['canonical_projection'], 9.234)
            restored.cache_sleeper_week(None, scoring={}, season=2026, week=2)
            self.assertIsNone(restored.week_snapshot(2)['players']['q']['canonical_projection'])
            self.assertEqual(restored._external_snapshot(season=2026, week=2)['availability_state'], 'fetch_unavailable')
