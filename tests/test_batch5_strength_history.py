import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.core.history_context.metadata import MinimalMetadataStore
from src.core.intelligence.strength_history import record_strength_history


class StrengthHistoryTests(unittest.TestCase):
    def profile(self):
        return dict(league_id='A', season=2026, current_week=2, next_n=3,
                    methodology_version='v1', projection_generation='p1', semantic_generation='s1',
                    roster_reference='r1', calendar_reference='c1', teams={'1': {
                        'horizons': {'current_week': {'total': 100, 'availability': 'complete'}},
                        'weekly': {2: {'reserve_capacity': {'supported_slots': 2, 'known_subtotal': 10},
                                       'known_bye_player_ids': [], 'bye_evidence_availability': 'unavailable'}}}})

    def test_100_unchanged_saves_and_source_only_revisions_zero_growth(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'m.sqlite3'
            store = MinimalMetadataStore(path)
            profile = self.profile()
            self.assertEqual(record_strength_history(store, profile, observed_at='first'), 1)
            before = {p.name: p.stat().st_size for p in path.parent.iterdir()}
            for i in range(100):
                profile['projection_generation'] = str(i)
                self.assertEqual(record_strength_history(store, profile, observed_at=str(i)), 0)
            self.assertEqual(before, {p.name: p.stat().st_size for p in path.parent.iterdir()})

    def test_transition_method_boundary_cap_and_league_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory)/'m.sqlite3')
            profile = self.profile()
            for i in range(132):
                profile['teams']['1']['horizons']['current_week']['total'] = 100 + i % 2
                record_strength_history(store, profile, observed_at=str(i))
            profile['methodology_version'] = 'v2'
            record_strength_history(store, profile, observed_at='method')
            other = copy.deepcopy(profile)
            other['league_id'] = 'B'
            record_strength_history(store, other, observed_at='other')
            with store.connection() as connection:
                rows = connection.execute("SELECT value FROM metadata WHERE namespace='team_strength_history' ORDER BY key").fetchall()
            first, second = [json.loads(row[0]) for row in rows]
            self.assertEqual(len(first['events']), 128)
            self.assertEqual(first['discarded_transitions'], 5)
            self.assertEqual(first['events'][-1]['reasons'], ['METHODOLOGY_CHANGED'])
            self.assertEqual(len(second['events']), 1)
            self.assertNotIn('players', json.dumps(first))
