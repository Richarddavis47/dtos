from contextlib import closing
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.fois import state_storage
from tools.recovery_backup import encrypt_stream, verify_local, receipt_verifier, write_all
from tools.recovery_guard import RecoveryGuard, ADMISSION, TMP_CEILING, allocated_tree
from tools.retained_storage_recovery import RetainedRecovery, admit_build
from tools.staged_fois_cutover import sha256, proof
from tools.storage_migration import migrate
from tools.recovery_build import build_fois
from tools.recovery_stream import pipe_sender, encrypted_length, SizedPipe


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                                 serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.tmp = self.root / 'tmp'
        self.tmp.mkdir()
        self.guard = RecoveryGuard(self.root, rehearsal=True, temporary_root=self.tmp)
        self.live = self.root / 'live.sqlite3'
        self.new = self.root / 'compact.sqlite3'
        repo = FOISRepository(self.live)
        FOISService(repo)._generate_sync({
            'league': {'league_id': 'A', 'season': '2026'},
            'teams': [{'roster_id': 1, 'owner_id': 'gm', 'players': []}], 'fois_history': {}})
        with repo._connection() as db:
            row = db.execute('SELECT snapshot_id,payload FROM fois_snapshot_history').fetchone()
            db.execute('UPDATE fois_snapshot_history SET payload=? WHERE snapshot_id=?',
                       (json.dumps(state_storage.decode(db, row[1])), row[0]))
            db.commit()
        self.old_hash = sha256(self.live)
        shutil.copyfile(self.live, self.new)
        migrate(self.new, 'fois', maximum_bytes=4 * 1024**2, reserve_bytes=0)
        self.new_hash = sha256(self.new)
        stream = io.BytesIO()
        encrypt_stream(self.live, stream, self.public, self.guard)
        self.package = self.root / 'backup.enc'
        self.package.write_bytes(stream.getvalue())
        self.signed = verify_local(self.package, self.private, self.root / 'verify.sqlite3')
        self.tool = RetainedRecovery(self.live, 'fois', self.guard, receipt_verifier(self.public))

    def prepare(self):
        return self.tool.prepare(self.new, self.signed, source_sha256=self.old_hash,
                                 candidate_sha256=self.new_hash)

    def accept(self):
        def reader(kind, old, active):
            self.assertEqual(proof(old), proof(active))
            return {'passed': True, 'kind': kind}
        return self.tool.accept(reader)

    def test_stream_exact_receipt_and_no_remote_scratch(self):
        self.assertEqual(list(self.tmp.iterdir()), [])
        self.assertFalse((self.root / 'verify.sqlite3').exists())
        self.assertEqual(self.signed['receipt']['destination_sha256'], self.old_hash)
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_partial_transport_writes_are_not_truncated(self):
        class ShortWriter(io.BytesIO):
            def write(self, chunk):
                return super().write(chunk[:7])
        sink = ShortWriter()
        write_all(sink, b'example' * 100)
        self.assertEqual(sink.getvalue(), b'example' * 100)

    def test_pipe_transport_exact_length_and_independent_receipt(self):
        reader, finish = pipe_sender(self.live, self.public, self.guard)
        target = self.root / 'pipe.enc'
        size = encrypted_length(self.live.stat().st_size, self.old_hash, self.public)
        sized = SizedPipe(reader, size)
        sized.seek(0, 2)
        self.assertEqual(sized.tell(), size)
        sized.seek(0)
        try:
            with target.open('xb') as output:
                shutil.copyfileobj(sized, output, length=65536)
            with self.assertRaisesRegex(OSError, 'cannot rewind'):
                sized.seek(0)
        finally:
            finish()
        self.assertEqual(target.stat().st_size,
                         encrypted_length(self.live.stat().st_size, self.old_hash, self.public))
        signed = verify_local(target, self.private, self.root / 'pipe-verify.sqlite3')
        receipt_verifier(self.public)(signed, self.old_hash, self.live.stat().st_size)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_fresh_builder_preserves_source_and_restore_delete_journal(self):
        target = self.root / 'fresh.sqlite3'
        result = build_fois(self.live, target, self.guard, self.signed, receipt_verifier(self.public))
        self.assertEqual(result['source_sha256'], self.old_hash)
        self.assertEqual(sha256(self.live), self.old_hash)
        self.assertEqual(proof(target), proof(self.live))
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0], 'delete')

    def test_failed_builder_preserves_source_and_never_activates_candidate(self):
        target = self.root / 'failed.sqlite3'
        with patch('tools.recovery_build.codec.encode', side_effect=RuntimeError('injected build')):
            with self.assertRaisesRegex(RuntimeError, 'injected build'):
                build_fois(self.live, target, self.guard, self.signed, receipt_verifier(self.public))
        self.assertEqual(sha256(self.live), self.old_hash)
        self.assertFalse(self.tool.record.exists())

    def test_builder_requires_verified_backup_before_creating_target(self):
        target = self.root / 'denied.sqlite3'
        with self.assertRaises(Exception):
            build_fois(self.live, target, self.guard, {}, receipt_verifier(self.public))
        self.assertFalse(target.exists())

    def test_ciphertext_corruption_refuses_receipt_and_cleans_owned_scratch(self):
        content = bytearray(self.package.read_bytes())
        content[-32] ^= 1
        self.package.write_bytes(content)
        with self.assertRaises(Exception):
            verify_local(self.package, self.private, self.root / 'bad.sqlite3')
        self.assertFalse((self.root / 'bad.sqlite3').exists())

    def test_backup_receipt_tampering_refused(self):
        self.signed['receipt']['destination_sha256'] = '0' * 64
        with self.assertRaises(Exception):
            self.prepare()
        self.assertFalse(self.tool.record.exists())
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_valid_receipt_for_different_database_refused(self):
        stream = io.BytesIO()
        encrypt_stream(self.new, stream, self.public, self.guard)
        other = self.root / 'other.enc'
        other.write_bytes(stream.getvalue())
        self.signed = verify_local(other, self.private, self.root / 'other-verify.sqlite3')
        with self.assertRaisesRegex(ValueError, 'verification mismatch'):
            self.prepare()
        self.assertFalse(self.tool.record.exists())

    def test_unrelated_database_is_not_exported(self):
        unrelated = self.root / 'unrelated.sqlite3'
        with closing(sqlite3.connect(unrelated)) as db:
            db.execute('CREATE TABLE accounts (id INTEGER PRIMARY KEY)')
        output = io.BytesIO()
        with self.assertRaisesRegex(ValueError, 'Only reviewed'):
            encrypt_stream(unrelated, output, self.public, self.guard)
        self.assertEqual(output.getvalue(), b'')

    def test_wrong_source_checksum_refused(self):
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.tool.prepare(self.new, self.signed, source_sha256='0' * 64,
                              candidate_sha256=self.new_hash)

    def test_success_retains_old_then_explicitly_removes_after_acceptance(self):
        state = self.prepare()
        before = allocated_tree(self.root)
        self.tool.activate()
        self.assertEqual(sha256(Path(state['old'])), self.old_hash)
        self.assertEqual(sha256(self.live), self.new_hash)
        self.assertFalse(self.new.exists())
        self.assertLess(allocated_tree(self.root) - before, 64 * 1024)
        self.accept()
        self.tool.remove_old(state['old'])
        self.assertFalse(Path(state['old']).exists())
        self.assertEqual(sha256(self.live), self.new_hash)
        with self.assertRaisesRegex(RuntimeError, 'acceptance'):
            self.tool.remove_old(state['old'])

    def test_exact_rollback_and_restart_uses_retained_old(self):
        self.prepare()
        state = self.tool.activate()
        # New controller instance simulates reopening durable recovery state.
        restarted = RetainedRecovery(self.live, 'fois', self.guard, receipt_verifier(self.public))
        restarted.rollback()
        self.assertEqual(sha256(self.live), self.old_hash)
        self.assertTrue(Path(state['old']).exists())
        self.assertEqual(sha256(self.new), self.new_hash)
        with self.assertRaises(RuntimeError):
            restarted.remove_old(state['old'])

    def test_acceptance_does_not_remove_rollback_option(self):
        self.prepare()
        self.tool.activate()
        self.accept()
        self.tool.rollback()
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_no_removal_before_acceptance(self):
        self.prepare()
        state = self.tool.activate()
        with self.assertRaisesRegex(RuntimeError, 'acceptance'):
            self.tool.remove_old(state['old'])
        self.assertEqual(sha256(Path(state['old'])), self.old_hash)

    def test_no_active_or_unknown_removal(self):
        self.prepare()
        self.tool.activate()
        self.accept()
        for path in (self.live, self.package):
            with self.assertRaisesRegex(ValueError, 'Unknown or active'):
                self.tool.remove_old(path)

    def test_failed_post_read_keeps_old_and_allows_rollback(self):
        self.prepare()
        state = self.tool.activate()
        with self.assertRaisesRegex(RuntimeError, 'reads failed'):
            self.tool.accept(lambda *args: {'passed': False})
        self.assertEqual(self.tool.read_record()['phase'], 'active')
        self.assertEqual(sha256(Path(state['old'])), self.old_hash)
        self.tool.rollback()
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_failed_switch_retains_old_and_original_active(self):
        state = self.prepare()
        original = os.replace
        def fail_live(a, b):
            if Path(b) == self.live:
                raise OSError('injected switch')
            return original(a, b)
        with patch('tools.retained_storage_recovery.os.replace', side_effect=fail_live):
            with self.assertRaisesRegex(OSError, 'injected switch'):
                self.tool.activate()
        self.assertEqual(sha256(self.live), self.old_hash)
        self.assertEqual(sha256(Path(state['old'])), self.old_hash)
        self.tool.rollback()
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_bad_compact_equivalence_rejected(self):
        with closing(sqlite3.connect(self.new)) as db:
            db.execute('DELETE FROM fois_snapshot_history')
            db.commit()
        self.new_hash = sha256(self.new)
        with self.assertRaisesRegex(ValueError, 'equivalence'):
            self.prepare()
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_insufficient_headroom_gate_exact(self):
        usage = shutil.disk_usage(self.root)
        with patch('tools.recovery_guard.shutil.disk_usage',
                   return_value=type(usage)(usage.total, usage.used, ADMISSION - 1)):
            with self.assertRaisesRegex(RuntimeError, 'headroom'):
                admit_build(self.guard)
        self.assertEqual(ADMISSION, 243269632)

    def test_tmp_ceiling_independent_of_host_free(self):
        with patch('tools.recovery_guard.allocated_tree', return_value=TMP_CEILING):
            with self.assertRaisesRegex(RuntimeError, 'Temporary-storage'):
                admit_build(self.guard)
        with self.assertRaisesRegex(RuntimeError, 'Large temporary'):
            self.guard.check(temporary_output=self.live.stat().st_size + 10 * 1024**2)

    def test_repeated_activation_and_prepare_refused(self):
        self.prepare()
        with self.assertRaisesRegex(RuntimeError, 'Existing recovery'):
            self.prepare()
        self.tool.activate()
        with self.assertRaisesRegex(RuntimeError, 'already attempted'):
            self.tool.activate()

    def test_changed_generation_blocks_removal(self):
        self.prepare()
        state = self.tool.activate()
        self.accept()
        with self.live.open('ab') as out:
            out.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'generation changed'):
            self.tool.remove_old(state['old'])
        self.assertTrue(Path(state['old']).exists())

    def test_maintenance_required_before_every_stage(self):
        with patch.object(self.guard, 'check', side_effect=RuntimeError('maintenance required')):
            with self.assertRaisesRegex(RuntimeError, 'maintenance'):
                self.prepare()
        self.assertEqual(sha256(self.live), self.old_hash)

    def test_rehearsal_refused_on_render(self):
        with patch.dict(os.environ, {'RENDER': 'true'}):
            with self.assertRaisesRegex(ValueError, 'production'):
                RecoveryGuard(self.root, rehearsal=True)

    def test_legacy_replacement_paths_are_disabled_on_render(self):
        from tools.staged_fois_cutover import publish as fois_publish
        from tools.staged_projection_cutover import publish as projection_publish
        with patch.dict(os.environ, {'RENDER': 'true'}):
            for publish in (fois_publish, projection_publish):
                with self.assertRaisesRegex(RuntimeError, 'Legacy replacement'):
                    publish(self.live, self.new, self.live,
                            source_sha256=self.old_hash, candidate_sha256=self.new_hash)
            with self.assertRaisesRegex(RuntimeError, 'In-place migration'):
                migrate(self.live, 'fois', maximum_bytes=72 * 1024**2, reserve_bytes=128 * 1024**2)


if __name__ == '__main__':
    unittest.main()
