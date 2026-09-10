"""The universe preparation reader obeys the existing canonical temporal rules."""
import tempfile
import unittest
from pathlib import Path

from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact


def fact(player, value, season=2025):
    return GlobalFact('production', f'sleeper:{player}', 'nflverse', f'game:{player}',
                      f'{season}-09-01T00:00:00Z', None, {'rec': value}, season=season, week=1)


class PlayerProductionStreamTests(unittest.TestCase):
    def test_stream_matches_canonical_reads_and_no_future_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'global.sqlite3', reserve_bytes=0)
            store.publish([fact('1', 5), fact('2', 7)], retrieved_at='2025-09-02T00:00:00Z')
            store.publish([fact('1', 6)], retrieved_at='2025-09-10T00:00:00Z')
            for boundary in ('2025-09-03T00:00:00Z', '2025-09-11T00:00:00Z'):
                rows = list(store.iter_player_production(['2', '1'], seasons=(2025,), as_of=boundary))
                for row in rows:
                    canonical = store.read('production', row['subject_id'], season=2025, as_of=boundary)[0]
                    self.assertEqual(row['values'], canonical['values'])
                    self.assertEqual(row['fingerprint'], canonical['fingerprint'])
                    self.assertEqual(row['knowledge_boundary'], canonical['knowledge_boundary'])
                self.assertEqual(len(rows), 2)
            self.assertEqual(store.counts(), {'production': 3})

    def test_chunking_large_universe_preserves_order_and_selected_seasons(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'global.sqlite3', reserve_bytes=0)
            store.publish([fact(str(i), i) for i in range(500)], retrieved_at='2025-09-02T00:00:00Z')
            ids = [str(i) for i in range(500)]
            rows = list(store.iter_player_production(reversed(ids), seasons=(2025,), as_of='2026-01-01T00:00:00Z'))
            self.assertEqual([row['subject_id'] for row in rows], [f'sleeper:{i}' for i in sorted(ids)])
            self.assertEqual(list(store.iter_player_production(ids, seasons=(2026,), as_of='2026-01-01T00:00:00Z')), [])

    def test_unpublished_facts_and_unrequested_players_absent(self):
        from src.core.data_platform.global_evidence import IngestionCheckpoint
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'global.sqlite3', reserve_bytes=0)
            store.publish([fact('1', 5)], retrieved_at='2025-09-02T00:00:00Z',
                          checkpoint=IngestionCheckpoint('test', 'revision', 0, 1, False))
            self.assertEqual(list(store.iter_player_production(['1'], seasons=(2025,), as_of='2026-01-01T00:00:00Z')), [])
            store.publish([fact('2', 7)], retrieved_at='2025-09-02T00:00:00Z')
            self.assertEqual(list(store.iter_player_production(['1'], seasons=(2025,), as_of='2026-01-01T00:00:00Z')), [])

    def test_excessive_season_scope_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'global.sqlite3', reserve_bytes=0)
            with self.assertRaises(ValueError):
                list(store.iter_player_production(['1'], seasons=(2023, 2024, 2025), as_of='2026-01-01T00:00:00Z'))
