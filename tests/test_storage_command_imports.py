"""Operator commands cannot open application stores before explicit invocation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class StorageCommandImportTests(unittest.TestCase):
    def test_command_imports_do_not_initialize_any_database(self):
        with tempfile.TemporaryDirectory() as folder:
            environment = os.environ.copy()
            root = Path(folder)
            environment['DTOS_HISTORY_STORAGE_ROOT'] = folder
            for name in ('PROJECTION_DB_FILE', 'FOIS_DB_FILE', 'METADATA_DB_FILE',
                         'ACCOUNT_DB_FILE', 'GLOBAL_EVIDENCE_FILE', 'HISTORY_DB_FILE',
                         'INTELLIGENCE_CHECKPOINT_FILE', 'CACHE_FILE', 'DATA_WAREHOUSE_FILE'):
                environment['DTOS_' + name] = str(root / (name.lower() + '.sqlite3'))
            script = '''
import sqlite3
from unittest.mock import patch
with patch.object(sqlite3, 'connect', side_effect=AssertionError('Import opened a database')):
    import tools.storage_migration
    import tools.projection_retention_migration
    import tools.staged_fois_cutover
    import tools.staged_projection_cutover
    import tools.storage_maintenance
import sys
assert 'src.core.projection_intelligence.service' not in sys.modules
assert 'dtos_app' not in sys.modules
'''
            subprocess.run([sys.executable, '-c', script], env=environment, check=True, timeout=20)
            self.assertEqual(list(root.iterdir()), [])

    def test_package_service_export_remains_the_same_runtime_instance(self):
        # Run independently from the import-isolation proof. Explicit service
        # consumption is allowed to initialize its isolated configured store.
        with tempfile.TemporaryDirectory() as folder:
            environment = os.environ.copy()
            environment['DTOS_PROJECTION_DB_FILE'] = str(Path(folder) / 'projection.sqlite3')
            script = '''
from src.core.projection_intelligence import projection_service
from src.core.projection_intelligence.service import projection_service as direct
assert projection_service is direct
'''
            subprocess.run([sys.executable, '-c', script], env=environment, check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
