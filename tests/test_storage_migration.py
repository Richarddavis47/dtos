from contextlib import closing
import json
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
import threading

from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.fois import state_storage
from tools.storage_migration import migrate, digest
from src.platform.storage_gate import connect, database_gate


class StorageMigrationTests(unittest.TestCase):
    def test_connection_fence_and_abandoned_output_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fois.sqlite3'
            FOISRepository(path)
            started, entered = threading.Event(), threading.Event()
            def reader():
                started.set()
                with closing(connect(path)):
                    entered.set()
            with database_gate(path, exclusive=True):
                worker = threading.Thread(target=reader)
                worker.start()
                self.assertTrue(started.wait(2))
                self.assertFalse(entered.wait(.1))
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertTrue(entered.is_set())
            prefix = '.dtos-storage-migration-' + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12] + '-'
            abandoned = path.parent / (prefix + 'interrupted')
            abandoned.mkdir()
            (abandoned / 'compact.sqlite3').write_bytes(b'incomplete')
            migrate(path, 'fois', maximum_bytes=4*1048576, reserve_bytes=0)
            self.assertFalse(abandoned.exists())

    def test_fois_reversible_idempotent_and_interruption_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'fois.sqlite3'
            repository = FOISRepository(path)
            FOISService(repository)._generate_sync({
                'league': {'league_id': 'A', 'season': '2026'},
                'teams': [{'roster_id': 1, 'owner_id': 'gm', 'players': []}],
                'fois_history': {},
            })
            with repository._connection() as c:
                row = c.execute('SELECT snapshot_id,payload FROM fois_snapshot_history').fetchone()
                c.execute('UPDATE fois_snapshot_history SET payload=? WHERE snapshot_id=?',
                          (json.dumps(state_storage.decode(c, row[1])), row[0]))
                c.commit()
                expected = digest(c, 'fois')
            original = path.read_bytes()
            def interrupt():
                raise RuntimeError('simulated interruption')
            with self.assertRaisesRegex(RuntimeError, 'simulated'):
                migrate(path, 'fois', maximum_bytes=4*1048576, reserve_bytes=0, before_publish=interrupt)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(root.glob('.dtos-storage-migration-*')), [])
            for reverse in (False, False, True):
                report = migrate(path, 'fois', maximum_bytes=4*1048576, reserve_bytes=0, restore_legacy=reverse)
                self.assertEqual(report['tables'], expected)
            with repository._connection() as c:
                self.assertNotIn('$storage', json.loads(c.execute('SELECT payload FROM fois_snapshot_history').fetchone()[0]))

    def test_projection_evidence_actuals_and_missing_values_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'projection.sqlite3'
            with closing(sqlite3.connect(path)) as c:
                c.execute('CREATE TABLE projection_snapshots(snapshot_id TEXT PRIMARY KEY,payload TEXT)')
                c.execute('CREATE TABLE projection_actuals(snapshot_id TEXT,player_id TEXT,actual_points REAL,PRIMARY KEY(snapshot_id,player_id))')
                for index, value in enumerate((None, 0, 19.5)):
                    payload = {'league_id': 'A', 'generated_at': str(index), 'players': {'p': {'weekly_projected_points': value}}}
                    c.execute('INSERT INTO projection_snapshots VALUES (?,?)', (str(index), json.dumps(payload)))
                c.execute("INSERT INTO projection_actuals VALUES ('2','p',7)")
                c.commit()
                expected = digest(c, 'projection')
            for reverse in (False, False, True):
                report = migrate(path, 'projection', maximum_bytes=4*1048576, reserve_bytes=0, restore_legacy=reverse)
                self.assertEqual(report['tables'], expected)

    def test_budget_failure_never_replaces_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fois.sqlite3'
            FOISRepository(path)
            before = path.read_bytes()
            with self.assertRaises(sqlite3.OperationalError):
                migrate(path, 'fois', maximum_bytes=4096, reserve_bytes=0)
            self.assertEqual(path.read_bytes(), before)
