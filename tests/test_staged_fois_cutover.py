from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.fois import state_storage
from tools.storage_migration import migrate
from tools.staged_fois_cutover import publish, sha256, proof, ADMISSION


class StagedFOISTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.live = self.root / 'live.sqlite3'
        self.candidate = self.root / 'candidate.sqlite3'
        self.backup = self.root / 'backup.sqlite3'
        repo = FOISRepository(self.live)
        FOISService(repo)._generate_sync({
            'league': {'league_id': 'A', 'season': '2026'},
            'teams': [{'roster_id': 1, 'owner_id': 'gm', 'players': []}],
            'fois_history': {},
        })
        with repo._connection() as conn:
            row = conn.execute('SELECT snapshot_id,payload FROM fois_snapshot_history').fetchone()
            conn.execute('UPDATE fois_snapshot_history SET payload=? WHERE snapshot_id=?',
                         (json.dumps(state_storage.decode(conn, row[1])), row[0]))
            conn.commit()
        shutil.copyfile(self.live, self.backup)
        shutil.copyfile(self.live, self.candidate)
        migrate(self.candidate, 'fois', maximum_bytes=4*1024**2, reserve_bytes=0)
        self.old = sha256(self.live)
        self.new = sha256(self.candidate)

    def run_publish(self):
        return publish(self.live, self.candidate, self.backup,
                       source_sha256=self.old, candidate_sha256=self.new)

    def test_publish_reopen_rerun_denied_and_exact_rollback(self):
        self.assertTrue(self.run_publish()['logical_equivalence'])
        self.assertEqual(sha256(self.live), self.new)
        FOISRepository(self.live)
        with self.assertRaisesRegex(ValueError, 'Source generation'):
            self.run_publish()
        compact_backup = self.root / 'compact-backup.sqlite3'
        shutil.copyfile(self.live, compact_backup)
        publish(self.live, self.backup, compact_backup, source_sha256=self.new,
                candidate_sha256=self.old, rollback=True)
        self.assertEqual(sha256(self.live), self.old)

    def test_headroom_failure_preserves_source(self):
        usage = shutil.disk_usage(self.root)
        with patch('tools.staged_fois_cutover.shutil.disk_usage',
                   return_value=type(usage)(usage.total, usage.used, ADMISSION-1)):
            with self.assertRaisesRegex(RuntimeError, 'headroom'):
                self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_pending_file_never_automatically_deleted(self):
        pending = self.live.with_name(self.live.name + '.staged-fois-pending')
        pending.write_bytes(b'interrupted')
        with self.assertRaisesRegex(RuntimeError, 'explicit review'):
            self.run_publish()
        self.assertEqual(pending.read_bytes(), b'interrupted')

    def test_bad_backup_fails_before_publication(self):
        self.backup.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'Rollback backup'):
            self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_changed_logical_evidence_rejected_even_with_valid_checksum(self):
        with closing(sqlite3.connect(self.candidate)) as conn:
            conn.execute('DELETE FROM fois_snapshot_history')
            conn.commit()
        self.new = sha256(self.candidate)
        with self.assertRaisesRegex(ValueError, 'equivalence'):
            self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_failed_atomic_replace_leaves_source_and_backup(self):
        with patch('tools.staged_fois_cutover.os.replace', side_effect=OSError('injected')):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.run_publish()
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(sha256(self.backup), self.old)
        self.assertFalse(self.live.with_name(self.live.name + '.staged-fois-pending').exists())

    def test_wrong_source_or_candidate_identity_denied(self):
        for key in ('source_sha256', 'candidate_sha256'):
            args = {'source_sha256': self.old, 'candidate_sha256': self.new}
            args[key] = '0'*64
            with self.assertRaises(ValueError):
                publish(self.live, self.candidate, self.backup, **args)
        self.assertEqual(sha256(self.live), self.old)

    def test_sidecar_boundary_rejected(self):
        self.live.with_name(self.live.name + '-wal').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'sidecar'):
            self.run_publish()

    def test_noop_and_malformed_identities_rejected(self):
        for source, target in ((self.old, self.old), ('', self.new), (self.old, 'not-a-hash')):
            with self.assertRaises(ValueError):
                publish(self.live, self.candidate, self.backup,
                        source_sha256=source, candidate_sha256=target)
        self.assertEqual(sha256(self.live), self.old)

    def test_wrong_format_source_refused(self):
        wrong = self.root / 'wrong.sqlite3'
        with closing(sqlite3.connect(wrong)) as conn:
            conn.execute('CREATE TABLE unrelated(id INTEGER PRIMARY KEY)')
            conn.commit()
        wrong_backup = self.root / 'wrong-backup.sqlite3'
        shutil.copyfile(wrong, wrong_backup)
        original = sha256(wrong)
        with self.assertRaisesRegex(ValueError, 'expected FOIS'):
            publish(wrong, self.candidate, wrong_backup,
                    source_sha256=original, candidate_sha256=self.new)
        self.assertEqual(sha256(wrong), original)

    def test_incomplete_target_refused(self):
        self.candidate.write_bytes(b'incomplete sqlite file')
        self.new = sha256(self.candidate)
        with self.assertRaises(sqlite3.DatabaseError):
            self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_headroom_loss_during_verification_refused(self):
        usage = shutil.disk_usage(self.root)
        low = type(usage)(usage.total, usage.used, ADMISSION-1)
        with patch('tools.staged_fois_cutover.shutil.disk_usage', side_effect=[usage, low]):
            with self.assertRaisesRegex(RuntimeError, 'Headroom changed'):
                self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_same_inode_backup_is_not_independent(self):
        with self.assertRaisesRegex(ValueError, 'distinct files'):
            publish(self.live, self.candidate, self.live,
                    source_sha256=self.old, candidate_sha256=self.new)

    def test_new_sidecar_during_verification_blocks_publication(self):
        def checked(path):
            result = proof(path)
            if path == self.backup:
                self.live.with_name(self.live.name + '-wal').write_bytes(b'late writer')
            return result
        with patch('tools.staged_fois_cutover.proof', side_effect=checked):
            with self.assertRaisesRegex(ValueError, 'sidecar'):
                self.run_publish()
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(sha256(self.backup), self.old)

    def test_abrupt_exit_before_replace_preserves_source_and_requires_review(self):
        script = '''
import os, sys
from unittest.mock import patch
from tools.staged_fois_cutover import publish
with patch('tools.staged_fois_cutover.os.replace', side_effect=lambda *a: os._exit(86)):
    publish(*sys.argv[1:4], source_sha256=sys.argv[4], candidate_sha256=sys.argv[5])
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.live),
                                 str(self.candidate), str(self.backup), self.old, self.new], timeout=20)
        self.assertEqual(result.returncode, 86)
        pending = self.live.with_name(self.live.name + '.staged-fois-pending')
        self.assertEqual(sha256(pending), self.new)
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(sha256(self.backup), self.old)
        with self.assertRaisesRegex(RuntimeError, 'explicit review'):
            self.run_publish()
        self.assertTrue(pending.exists())


if __name__ == '__main__':
    unittest.main()
