"""Focused Batch 7 lifecycle, recovery, isolation and storage contracts."""
from contextlib import closing
import copy
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.history_context.metadata import MinimalMetadataStore
from src.core.intelligence.season_calendar import season_calendar
from src.core.projection_intelligence.service import ProjectionService


def league(league_id='day', *, teams=6, rounds=4, kind=1, status='in_season',
           leg=1, completed=0, season='2026'):
    return {
        'league_id': league_id, 'name': 'Day Traders' if league_id == 'day' else 'Super Flexxxin',
        'season': season, 'sport': 'nfl', 'status': status,
        'roster_positions': ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPER_FLEX'] if league_id == 'day'
                            else ['QB', 'RB', 'WR', 'TE', 'FLEX'],
        'scoring_settings': {'pass_yd': .04, 'pass_td': 6, 'rec': 1} if league_id == 'day'
                            else {'pass_yd': .04, 'pass_td': 4, 'rec': .5},
        'settings': {'leg': leg, 'last_scored_leg': completed, 'start_week': 1,
                     'playoff_week_start': 14 if teams == 6 else 15,
                     'playoff_teams': teams, 'playoff_round_type': kind,
                     'playoff_type': 0, 'draft_rounds': rounds},
    }


def data_for(source):
    return {'league': copy.deepcopy(source), 'season': int(source['season']), 'week': source['settings']['leg'],
            'scoring_settings': copy.deepcopy(source['scoring_settings']),
            'players': {'zero': {'id': 'zero', 'position': 'RB', 'team': 'A'},
                        'value': {'id': 'value', 'position': 'QB', 'team': 'B'},
                        'missing': {'id': 'missing', 'position': 'WR', 'team': 'C'}}}


def feed(season, week, yards=250):
    return [
        {'player_id': 'zero', 'season': season, 'week': week,
         'player': {'position': 'RB'}, 'stats': {'rush_yd': 0}, 'updated_at': '2026-09-01T12:00:00+00:00'},
        {'player_id': 'value', 'season': season, 'week': week,
         'player': {'position': 'QB'}, 'stats': {'pass_yd': yards}, 'updated_at': '2026-09-01T12:00:00+00:00'},
    ]


class SeasonTransitionMatrixTests(unittest.TestCase):
    def test_preweek_regular_playoff_and_complete_transitions_are_source_backed(self):
        preweek = season_calendar(league())
        self.assertEqual(preweek['availability'], 'supported')
        self.assertEqual(preweek['remaining_regular_season_weeks'][0], 1)

        active = season_calendar(league(leg=8, completed=7))
        self.assertEqual(active['remaining_regular_season_weeks'][0], 8)
        self.assertEqual(active['playoff_rounds'], [[14], [15], [16, 17]])

        postseason = season_calendar(league(leg=15, completed=14))
        self.assertEqual(postseason['remaining_regular_season_weeks'], [])
        self.assertEqual(postseason['round_membership']['16'], 3)
        self.assertEqual(postseason['round_membership']['17'], 3)

        completed = season_calendar(league(status='complete', leg=17, completed=17))
        self.assertEqual(completed['availability'], 'supported')
        # The identical counters are not admitted before the provider marks completion.
        self.assertEqual(season_calendar(league(leg=17, completed=17))['availability'], 'unavailable')

    def test_two_leagues_keep_settings_calendar_and_season_isolated(self):
        day = season_calendar(league())
        flex_league = league('flex', rounds=3)
        flex = season_calendar(flex_league)
        self.assertEqual(day['playoff_rounds'], [[14], [15], [16, 17]])
        self.assertEqual(flex['playoff_rounds'], [[14], [15], [16, 17]])
        self.assertEqual(day['first_round_bye_slots'], 2)
        self.assertEqual(flex['first_round_bye_slots'], 2)
        self.assertNotEqual(day['reference'], flex['reference'])
        self.assertEqual(day['source_fields']['playoff_teams'], 6)
        self.assertEqual(flex['source_fields']['playoff_teams'], 6)
        self.assertEqual(day['source_fields'], flex['source_fields'])
        self.assertNotEqual(league()['scoring_settings'], flex_league['scoring_settings'])
        self.assertEqual(league()['settings']['draft_rounds'], 4)
        self.assertEqual(flex_league['settings']['draft_rounds'], 3)
        self.assertNotEqual(league()['roster_positions'], flex_league['roster_positions'])


class ProjectionTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'projection.sqlite3'

    def service(self, league_id='day'):
        return ProjectionService(self.database, league_id=league_id)

    def test_rollover_preserves_true_zero_missing_and_source_value_identity(self):
        source = league()
        data = data_for(source)
        service = self.service()
        first = service.publish_horizon({1: feed(2026, 1)}, data=data, league_id='day', season=2026, current_week=1)
        players = first['players']
        self.assertEqual(players['zero']['canonical_projection'], 0)
        self.assertEqual(players['zero']['projection_coverage'], 'available')
        self.assertIsNone(players['missing']['canonical_projection'])
        self.assertEqual(players['missing']['projection_coverage'], 'unavailable')
        self.assertEqual(players['value']['canonical_projection'], 10)

        next_source = league(season='2027')
        next_data = data_for(next_source)
        next_data['week'] = 1
        self.assertFalse(service.restore_into(next_data))
        second = service.publish_horizon({1: feed(2027, 1, 300)}, data=next_data,
                                         league_id='day', season=2027, current_week=1)
        self.assertNotEqual(first['horizon_generation'], second['horizon_generation'])
        self.assertEqual(second['players']['value']['canonical_projection'], 12)
        self.assertEqual(first['players']['value']['sleeper_evidence_fingerprint'],
                         service.week_snapshot(1, generation_snapshot=first)['players']['value']['sleeper_evidence_fingerprint'])

    def test_partial_failure_recovery_atomic_restart_and_unchanged_storage(self):
        data = data_for(league())
        service = self.service()
        partial = service.publish_horizon({1: feed(2026, 1), 2: None}, data=data,
                                          league_id='day', season=2026, current_week=1)
        self.assertEqual(partial['weeks_supported'], [1])
        self.assertIsNone(service.week_snapshot(2)['players']['value']['canonical_projection'])
        recovered = service.publish_horizon({1: feed(2026, 1), 2: feed(2026, 2)}, data=data,
                                            league_id='day', season=2026, current_week=1)
        self.assertEqual(recovered['weeks_supported'], [1, 2])
        with closing(sqlite3.connect(self.database)) as connection:
            before = {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                      for table in ('projection_snapshots', 'projection_player_states',
                                    'projection_source_history', 'sleeper_projection_snapshots')}
        size = self.database.stat().st_size
        for _ in range(3):
            same = service.publish_horizon({1: feed(2026, 1), 2: feed(2026, 2)}, data=data,
                                           league_id='day', season=2026, current_week=1)
            self.assertEqual(same['horizon_generation'], recovered['horizon_generation'])
        with closing(sqlite3.connect(self.database)) as connection:
            after = {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                     for table in before}
        self.assertEqual(before, after)
        self.assertEqual(size, self.database.stat().st_size)

        restarted = self.service()
        restart_data = data_for(league())
        self.assertTrue(restarted.restore_into(restart_data))
        self.assertEqual(restart_data['projection_intelligence']['horizon_generation'], recovered['horizon_generation'])
        wrong_week = data_for(league(leg=2, completed=1))
        self.assertFalse(restarted.restore_into(wrong_week))

    def test_interrupted_preparation_and_corrupt_disposable_head_fail_closed(self):
        data = data_for(league())
        service = self.service()
        valid = service.publish_horizon({1: feed(2026, 1)}, data=data,
                                        league_id='day', season=2026, current_week=1)
        with self.assertRaises(Exception):
            service.publish_horizon({1: {'bad': 'shape'}}, data=data,
                                    league_id='day', season=2026, current_week=1)
        self.assertEqual(service.snapshot(), valid)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE projection_snapshots SET payload='not-json' WHERE snapshot_id=?",
                               (valid['horizon_generation'],))
            connection.commit()
        restored = self.service()
        self.assertIsNone(restored.snapshot())
        self.assertEqual(restored.health()['status'], 'warming')

    def test_league_scoring_scope_cannot_cross_even_with_same_players(self):
        day_data = data_for(league())
        flex_data = data_for(league('flex', rounds=3))
        day = self.service('day')
        day_snapshot = day.publish_horizon({1: feed(2026, 1)}, data=day_data,
                                           league_id='day', season=2026, current_week=1)
        flex = self.service('flex')
        self.assertFalse(flex.restore_into(flex_data))
        flex_snapshot = flex.publish_horizon({1: feed(2026, 1)}, data=flex_data,
                                             league_id='flex', season=2026, current_week=1)
        self.assertNotEqual(day_snapshot['scoring_profile_id'], flex_snapshot['scoring_profile_id'])
        self.assertNotEqual(day_snapshot['horizon_generation'], flex_snapshot['horizon_generation'])
        self.assertFalse(day.restore_into(flex_data))

    def test_unchanged_provider_cache_and_sync_marker_do_not_rewrite(self):
        service = self.service()
        payload = feed(2026, 1)
        with patch('src.core.projection_intelligence.service._now', side_effect=['first', 'second']):
            service.cache_sleeper_week(payload, scoring={'pass_yd': .04, 'pass_td': 6, 'rec': 1}, season=2026, week=1)
            service.cache_sleeper_week(payload, scoring={'pass_yd': .04, 'pass_td': 6, 'rec': 1}, season=2026, week=1)
        with closing(sqlite3.connect(self.database)) as connection:
            rows = connection.execute('SELECT retrieved_at FROM sleeper_projection_snapshots').fetchall()
            history = connection.execute('SELECT count(*) FROM projection_source_history').fetchone()[0]
        self.assertEqual(rows, [('first',)])
        self.assertEqual(history, 1)

        metadata_path = Path(self.temporary.name) / 'metadata.sqlite3'
        store = MinimalMetadataStore(metadata_path)
        self.assertTrue(store.record_sync_generation('day', 'g1'))
        first = store.get('sync_generation', 'day')
        size = metadata_path.stat().st_size
        self.assertFalse(store.record_sync_generation('day', 'g1'))
        self.assertEqual(store.get('sync_generation', 'day'), first)
        self.assertEqual(metadata_path.stat().st_size, size)
        self.assertTrue(store.record_sync_generation('day', 'g2'))
        self.assertEqual(store.get('sync_generation', 'day')['generation'], 'g2')
