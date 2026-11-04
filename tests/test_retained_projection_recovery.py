from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from tests.test_staged_projection_cutover import StagedProjectionTests
from tools.recovery_guard import RecoveryGuard
from tools.retained_storage_recovery import RetainedRecovery, equivalence
from tools.recovery_build import build_projection
from tools.staged_fois_cutover import sha256
from src.core.projection_intelligence.service import ProjectionService


class RetainedProjectionTests(unittest.TestCase):
    def setUp(self):
        StagedProjectionTests.setUp(self)
        self.tmp = self.root / 'temporary'
        self.tmp.mkdir()
        self.guard = RecoveryGuard(self.root, rehearsal=True, temporary_root=self.tmp)
        # Cryptographic receipt verification is independently covered by the
        # shared backup/FOIS tests. This fixture pins identity, not coverage.
        self.receipt = {'sha256': self.old, 'bytes': self.live.stat().st_size}

        def verify(receipt, identity, size):
            if receipt != {'sha256': identity, 'bytes': size}:
                raise ValueError('Backup identity mismatch')
        self.verifier = verify
        self.tool = RetainedRecovery(self.live, 'projection', self.guard, verify)

    def prepare(self):
        return self.tool.prepare(self.candidate, self.receipt,
                                 source_sha256=self.old, candidate_sha256=self.new)

    def test_retained_old_success_restart_exact_projection_and_removal(self):
        state = self.prepare()
        self.tool.activate()
        self.assertEqual(sha256(Path(state['old'])), self.old)
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)
        self.assertEqual(sha256(self.live), self.new)
        self.tool.accept(lambda kind, old, new: {
            'passed': equivalence(kind, old, new)['retained_evidence_equal']})
        self.tool.remove_old(state['old'])
        self.assertFalse(Path(state['old']).exists())
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)

    def test_retained_exact_projection_rollback(self):
        self.prepare()
        self.tool.activate()
        self.tool.rollback()
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)

    def test_separate_projection_builder_keeps_old_intact(self):
        target = self.root / 'fresh-projection.sqlite3'
        report = build_projection(self.live, target, self.guard, self.receipt, self.verifier)
        self.assertTrue(report['equivalence']['retained_evidence_equal'])
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_projection_build_keeps_stronger_headroom_gate(self):
        usage = shutil.disk_usage(self.root)
        with patch('tools.recovery_guard.shutil.disk_usage',
                   return_value=type(usage)(usage.total, usage.used, 352 * 1024**2 - 1)):
            with self.assertRaisesRegex(RuntimeError, 'headroom'):
                build_projection(self.live, self.root / 'denied.sqlite3', self.guard,
                                 self.receipt, self.verifier)
        self.assertFalse((self.root / 'denied.sqlite3').exists())

    def test_failed_atomic_switch_old_stays_usable(self):
        state = self.prepare()
        real_replace = __import__('os').replace

        def replace(a, b):
            if Path(b) == self.live:
                raise OSError('injected path switch')
            return real_replace(a, b)

        with patch('tools.retained_storage_recovery.os.replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'injected path switch'):
                self.tool.activate()
        self.assertEqual(sha256(self.live), self.old)
        self.assertEqual(sha256(Path(state['old'])), self.old)
        self.assertEqual(ProjectionService(self.live, league_id='a').snapshot(), self.snapshot)
        with self.assertRaisesRegex(RuntimeError, 'already attempted'):
            self.tool.activate()


if __name__ == '__main__':
    unittest.main()
