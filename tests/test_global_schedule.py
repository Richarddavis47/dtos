import tempfile
import unittest
from pathlib import Path

from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact
from src.core.data_platform.global_schedule import team_schedule


class GlobalScheduleTests(unittest.TestCase):
    def test_bye_requires_full_season_shape_not_a_partial_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            facts = []
            for week in range(1, 19):
                for pair in range(16):
                    if week == (7 if pair < 8 else 8):
                        continue
                    key = f'{week}-{pair}'
                    facts.append(GlobalFact('schedule', f'nfl-game:{key}', 'fixture', key,
                        '2027-09-01T00:00:00Z', None, {'game_id': key,
                        'home_team': f'T{pair * 2}', 'away_team': f'T{pair * 2 + 1}',
                        'game_type': 'REG'}, season=2027, week=week))
            store.publish(facts, retrieved_at='2027-05-01T00:00:00Z')
            report = team_schedule(store, 'T0', season=2027, as_of='2027-06-01T00:00:00Z')
            self.assertEqual(report['bye_week'], 7)
            self.assertEqual(report['bye_availability'], 'derived')
            self.assertEqual(len(report['games']), 17)

    def test_schedule_is_season_and_knowledge_scoped_without_invented_bye(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            store.publish([GlobalFact('schedule', 'nfl-game:x', 'fixture', 'x',
                '2027-09-01T00:00:00Z', None, {'game_id': 'x', 'kickoff': '2027-09-01T00:00:00Z',
                'home_team': 'BUF', 'away_team': 'NYJ', 'game_type': 'REG'}, season=2027, week=1)],
                retrieved_at='2027-05-01T00:00:00Z')
            report = team_schedule(store, 'BUF', season=2027, as_of='2027-06-01T00:00:00Z')
            self.assertEqual(report['games'][0]['opponent'], 'NYJ')
            self.assertIsNone(report['bye_week'])
            self.assertEqual(team_schedule(store, 'BUF', season=2026,
                as_of='2027-06-01T00:00:00Z')['games'], [])
            self.assertEqual(team_schedule(store, 'BUF', season=2027,
                as_of='2027-04-01T00:00:00Z')['games'], [])

    def test_unbounded_family_scan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            with self.assertRaises(ValueError):
                store.read('production', None, as_of='2027-01-01T00:00:00Z')
