import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact


class GlobalSourceCheckTests(unittest.TestCase):
    def test_refresh_receipts_are_bounded_and_separate_from_semantic_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            store = GlobalEvidenceStore(Path(root) / 'global.sqlite3')
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            store.publish([GlobalFact('production', 'sleeper:1', 'nflverse', 'g1:1',
                '2025-09-01T00:00:00Z', None, {'rec': 1})], retrieved_at=start.isoformat())
            before = store.read('production', 'sleeper:1', as_of='2026-02-01T00:00:00Z')
            for index in range(20):
                store.record_source_check('nflverse/production/2025', source_identity='same',
                    checked_at=(start + timedelta(seconds=index)).isoformat(), status='complete',
                    details={'records': 1})
                if index == 0:
                    initial_size = store.path.stat().st_size
            self.assertEqual(store.path.stat().st_size, initial_size)
            self.assertEqual(store.read('production', 'sleeper:1', as_of='2026-02-01T00:00:00Z'), before)
            store.record_source_check('nflverse/production/2025', source_identity='older',
                checked_at=start.isoformat(), status='failed', details={})
            receipt = store.source_check('nflverse/production/2025')
            self.assertEqual(receipt['source_identity'], 'same')
            self.assertEqual(receipt['status'], 'complete')
