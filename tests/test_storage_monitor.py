import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from src.platform import storage_monitor


class StorageMonitorTests(unittest.TestCase):
    def test_measures_without_writing_and_warns_without_deleting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'private.sqlite3'
            with closing(sqlite3.connect(path)) as db:
                for table in storage_monitor.TABLES['projection']:
                    db.execute(f'CREATE TABLE {table}(value TEXT)')
                db.commit()
                before = path.read_bytes()
                with patch('src.platform.storage_monitor.shutil.disk_usage') as disk:
                    disk.return_value.free = 1
                    with self.assertLogs('dtos.storage', 'WARNING'):
                        report = storage_monitor.observe(db, 'projection')
                self.assertIn('LOW_DISK_HEADROOM', report['reasons'])
                self.assertEqual(before, path.read_bytes())
                self.assertNotIn(str(path), str(storage_monitor.health()))
                db.executemany('INSERT INTO projection_source_history VALUES (?)', [('x',)] * 100)
                db.commit()
                with self.assertLogs('dtos.storage', 'WARNING'):
                    report = storage_monitor.observe(db, 'projection')
                self.assertIn('ROW_GROWTH_ACCELERATION_REVIEW', report['reasons'])
                self.assertEqual(report['rows']['projection_source_history'], 100)
