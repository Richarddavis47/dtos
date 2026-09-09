import tempfile
import unittest
from pathlib import Path

from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact
from src.core.data_platform.global_usage import player_usage


class GlobalUsageTests(unittest.TestCase):
    def test_zero_usage_is_real_and_missing_stays_missing_without_storage_growth(self):
        with tempfile.TemporaryDirectory() as root:
            store = GlobalEvidenceStore(Path(root) / 'global.sqlite3')
            store.publish([GlobalFact('production', 'sleeper:1', 'nflverse', 'g1:1',
                '2025-09-07T17:00:00Z', None,
                {'game_id': 'g1', 'rec_tgt': 0, 'rush_att': None}, season=2025, week=1)],
                retrieved_at='2025-09-08T00:00:00Z')
            before = store.path.read_bytes()
            result = player_usage(store, '1', season=2025, as_of='2025-09-09T00:00:00Z')
            self.assertEqual(result['targets'], 0)
            self.assertIsNone(result['carries'])
            self.assertIsNone(result['routes'])
            self.assertIsNone(result['target_share'])
            self.assertEqual(store.path.read_bytes(), before)
            past = player_usage(store, '1', season=2025, as_of='2025-09-07T00:00:00Z')
            self.assertIsNone(past['targets'])
            self.assertEqual(past['availability'], 'unavailable')
