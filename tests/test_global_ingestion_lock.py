import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.core.data_platform.ingestion_lock import ingestion_lock


class GlobalIngestionLockTests(unittest.TestCase):
    def test_competing_process_defers_then_lock_is_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'global.sqlite3'
            code = ('from pathlib import Path; import sys; '
                    'from src.core.data_platform.ingestion_lock import ingestion_lock; '
                    'guard=ingestion_lock(Path(sys.argv[1])); '
                    'print(guard.__enter__()); guard.__exit__(None,None,None)')
            with ingestion_lock(database) as acquired:
                self.assertTrue(acquired)
                child = subprocess.run([sys.executable, '-c', code, str(database)],
                                       capture_output=True, text=True, timeout=10)
                self.assertEqual(child.returncode, 0, child.stderr)
                self.assertEqual(child.stdout.strip(), 'False')
            child = subprocess.run([sys.executable, '-c', code, str(database)],
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertEqual(child.stdout.strip(), 'True')
            self.assertEqual(database.with_name(database.name + '.ingestion-lock').stat().st_size, 1)
