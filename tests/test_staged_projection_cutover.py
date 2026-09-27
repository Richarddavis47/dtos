from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.core.projection_intelligence.service import ProjectionService
from tools.projection_retention_migration import build_copy
from tools.staged_projection_cutover import publish, sha256, ADMISSION


class StagedProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.live = self.root / 'live.sqlite3'
        self.candidate = self.root / 'candidate.sqlite3'
        self.backup = self.root / 'backup.sqlite3'
        service = ProjectionService(self.live, league_id='a')
        with closing(sqlite3.connect(self.live)) as db:
            db.execute('DELETE FROM projection_retention_policy')
            db.commit()
        service.publish_horizon({1: [{'player_id': 'q', 'season': 2026, 'week': 1,
                                     'stats': {'pass_yd': 123.45}}]},
                                data={'league': {'league_id': 'a', 'season': 2026,
                                                 'scoring_settings': {'pass_yd': 0.04}},
                                      'week': 1, 'players': [{'id': 'q', 'position': 'QB'}]},
                                league_id='a', season=2026, current_week=1)
        self.snapshot = service.snapshot()
        shutil.copyfile(self.live, self.backup)
        build_copy(self.live, self.candidate, maximum_bytes=4 * 1024**2)
        self.old, self.new = sha256(self.live), sha256(self.candidate)

    def run_publish(self):
        return publish(self.live, self.candidate, self.backup,
                       source_sha256=self.old, candidate_sha256=self.new)

    def test_publish_restart_rerun_and_byte_exact_rollback(self):
        self.assertTrue(self.run_publish()['proof']['retained_evidence_equal'])
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)
        with self.assertRaisesRegex(ValueError, 'Source generation'):
            self.run_publish()
        compact_backup = self.root / 'compact-backup.sqlite3'
        shutil.copyfile(self.live, compact_backup)
        publish(self.live, self.backup, compact_backup,
                source_sha256=self.new, candidate_sha256=self.old, rollback=True)
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)

    def test_identity_guards(self):
        for key in ('source_sha256', 'candidate_sha256'):
            args = {'source_sha256': self.old, 'candidate_sha256': self.new}
            args[key] = '0' * 64
            with self.assertRaises(ValueError):
                publish(self.live, self.candidate, self.backup, **args)
        self.assertEqual(sha256(self.live), self.old)

    def test_headroom_before_and_after_verification(self):
        usage = shutil.disk_usage(self.root)
        low = type(usage)(usage.total, usage.used, ADMISSION - 1)
        for sequence in ([low], [usage, low]):
            with patch('tools.staged_projection_cutover.shutil.disk_usage', side_effect=sequence):
                with self.assertRaises(RuntimeError):
                    self.run_publish()
            self.assertEqual(sha256(self.live), self.old)

    def test_changed_semantics_with_valid_hash_rejected(self):
        with closing(sqlite3.connect(self.candidate)) as db:
            db.execute('DELETE FROM projection_publication_heads')
            db.commit()
        self.new = sha256(self.candidate)
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_interrupted_file_is_preserved(self):
        pending = self.live.with_name(self.live.name + '.staged-projection-pending')
        pending.write_bytes(b'unknown interrupted state')
        with self.assertRaisesRegex(RuntimeError, 'explicit review'):
            self.run_publish()
        self.assertEqual(pending.read_bytes(), b'unknown interrupted state')

    def test_replace_failure_preserves_source_and_backup(self):
        with patch('tools.staged_projection_cutover.os.replace', side_effect=OSError('injected')):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.run_publish()
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(sha256(self.backup), self.old)
        self.assertFalse(self.live.with_name(self.live.name + '.staged-projection-pending').exists())

    def test_sidecar_and_incomplete_target_denied(self):
        self.live.with_name(self.live.name + '-wal').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'sidecar'):
            self.run_publish()
        self.live.with_name(self.live.name + '-wal').unlink()
        self.candidate.write_bytes(b'incomplete')
        self.new = sha256(self.candidate)
        with self.assertRaises(sqlite3.DatabaseError):
            self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_wrong_policy_denied(self):
        with closing(sqlite3.connect(self.candidate)) as db:
            db.execute("UPDATE projection_retention_policy SET version='unknown'")
            db.commit()
        self.new = sha256(self.candidate)
        with self.assertRaisesRegex(ValueError, 'format/policy'):
            self.run_publish()

    def test_explicit_apply_required_and_no_implicit_cli_action(self):
        result = subprocess.run(
            [sys.executable, '-m', 'tools.staged_projection_cutover',
             str(self.live), str(self.candidate), str(self.backup),
             '--source-sha256', self.old, '--candidate-sha256', self.new],
            capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--apply', result.stderr)
        self.assertEqual(sha256(self.live), self.old)

    def test_same_inode_and_noop_denied(self):
        with self.assertRaisesRegex(ValueError, 'distinct'):
            publish(self.live, self.candidate, self.live,
                    source_sha256=self.old, candidate_sha256=self.new)
        with self.assertRaisesRegex(ValueError, 'No-op'):
            publish(self.live, self.candidate, self.backup,
                    source_sha256=self.old, candidate_sha256=self.old)

    def test_writer_sidecar_appearing_during_proof_is_rejected(self):
        from tools.projection_retention_migration import verify_copy
        def checked(source, target):
            result = verify_copy(source, target)
            self.live.with_name(self.live.name + '-wal').write_bytes(b'late writer')
            return result
        with patch('tools.staged_projection_cutover.verify_copy', side_effect=checked):
            with self.assertRaisesRegex(ValueError, 'sidecar'):
                self.run_publish()
        self.assertEqual(sha256(self.live), self.old)

    def test_legacy_schema_without_retention_tables_roundtrips_exactly(self):
        with closing(sqlite3.connect(self.live)) as db:
            for table in ('projection_retention_policy', 'projection_previous_heads',
                          'projection_checkpoint_roots', 'projection_source_roots'):
                db.execute(f'DROP TABLE {table}')
            db.commit()
        shutil.copyfile(self.live, self.backup)
        self.old = sha256(self.live)
        self.run_publish()
        compact_backup = self.root / 'compact-backup.sqlite3'
        shutil.copyfile(self.live, compact_backup)
        publish(self.live, self.backup, compact_backup,
                source_sha256=self.new, candidate_sha256=self.old, rollback=True)
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)
        self.assertEqual(sha256(self.live), self.old)

    def test_abrupt_exit_before_replace_preserves_source_and_requires_review(self):
        script = '''
import os, sys
from unittest.mock import patch
from tools.staged_projection_cutover import publish
with patch('tools.staged_projection_cutover.os.replace', side_effect=lambda *a: os._exit(86)):
    publish(*sys.argv[1:4], source_sha256=sys.argv[4], candidate_sha256=sys.argv[5])
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.live),
                                 str(self.candidate), str(self.backup), self.old, self.new], timeout=20)
        self.assertEqual(result.returncode, 86)
        pending = self.live.with_name(self.live.name + '.staged-projection-pending')
        self.assertEqual(sha256(pending), self.new)
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(sha256(self.backup), self.old)
        with self.assertRaisesRegex(RuntimeError, 'explicit review'):
            self.run_publish()
        self.assertTrue(pending.exists())


if __name__ == '__main__':
    unittest.main()
