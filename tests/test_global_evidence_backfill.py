import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.global_evidence_backfill import execute


class GlobalEvidenceBackfillTests(unittest.TestCase):
    def test_default_dry_run_does_not_create_database_or_call_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'global.sqlite3'
            with patch('tools.global_evidence_backfill.run_ingestion') as worker:
                result = execute(database, [2025, 2024, 2025])
            self.assertEqual(result['status'], 'dry_run')
            self.assertEqual(result['admission']['seasons'], [2024, 2025])
            worker.assert_not_called()
            self.assertFalse(database.exists())

    def test_missing_source_stops_without_skipping_forward_or_retrying(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'global.sqlite3'
            with patch('tools.global_evidence_backfill.run_ingestion',
                       side_effect=[{'status': 'complete'}, {'status': 'partial'}]) as worker:
                result = execute(database, [2024, 2025, 2026], apply=True)
            self.assertEqual(result['status'], 'incomplete')
            self.assertEqual(worker.call_count, 2)

    def test_low_disk_admission_never_launches_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('tools.global_evidence_backfill.shutil.disk_usage') as disk, \
                 patch('tools.global_evidence_backfill.run_ingestion') as worker:
                disk.return_value.free = 1
                result = execute(Path(directory) / 'global.sqlite3', [2025], apply=True)
            self.assertEqual(result['status'], 'not_admitted')
            worker.assert_not_called()
