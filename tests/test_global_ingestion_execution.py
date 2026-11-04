import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.global_evidence_ingestion import run_ingestion
from src.platform.lifecycle import lifecycle_coordinator


class GlobalIngestionExecutionTests(unittest.TestCase):
    def setUp(self):
        lifecycle_coordinator.reset()

    def tearDown(self):
        lifecycle_coordinator.reset()

    def test_startup_defers_without_process(self):
        lifecycle_coordinator.begin_startup('test')
        with patch('services.global_evidence_ingestion.subprocess.Popen') as launch:
            result = run_ingestion(2025, Path('unused'))
        self.assertEqual(result['status'], 'deferred')
        launch.assert_not_called()

    def test_cancellation_during_source_wait_tears_down_worker(self):
        cancelled = threading.Event()
        process = MagicMock()
        process.pid = os.getpid()
        process.poll.return_value = None

        def communicate(**kwargs):
            if kwargs.get('timeout'):
                cancelled.set()
                raise subprocess.TimeoutExpired('worker', 1)
            return b'', b''

        process.communicate.side_effect = communicate
        with tempfile.TemporaryDirectory() as directory:
            with patch('services.global_evidence_ingestion.subprocess.Popen', return_value=process):
                result = run_ingestion(2025, Path(directory) / 'global.sqlite3', cancelled=cancelled)
            self.assertEqual(result['status'], 'cancelled')
            process.kill.assert_called_once()
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['global.sqlite3.ingestion-lock'])
            self.assertEqual(lifecycle_coordinator.snapshot()['phase'], 'idle')

    def test_timeout_kills_worker_and_parent_removes_temporary_files(self):
        process = MagicMock()
        process.pid = os.getpid()
        process.communicate.side_effect = [subprocess.TimeoutExpired('worker', 1), (b'', b'')]
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            with patch('services.global_evidence_ingestion.subprocess.Popen', return_value=process), \
                 patch('services.global_evidence_ingestion.WORKER_TIMEOUT', -1):
                with self.assertRaises(TimeoutError):
                    run_ingestion(2025, Path(directory) / 'global.sqlite3')
            process.kill.assert_called_once()
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['global.sqlite3.ingestion-lock'])
            self.assertEqual(lifecycle_coordinator.snapshot()['phase'], 'idle')

    def test_child_receives_no_secret_environment_and_no_league_payload(self):
        process = MagicMock()
        process.returncode = 0
        process.poll.return_value = 0
        process.communicate.return_value = (json.dumps({'protocol': 1, 'status': 'complete', 'season': 2025}).encode(), b'')
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict('os.environ', {'DTOS_INSPECTION_TOKEN': 'not-for-child'}), \
                 patch('services.global_evidence_ingestion.subprocess.Popen', return_value=process) as launch:
                self.assertEqual(run_ingestion(2025, Path(directory) / 'global.sqlite3')['status'], 'complete')
            self.assertNotIn('DTOS_INSPECTION_TOKEN', launch.call_args.kwargs['env'])
            payload = json.loads(process.communicate.call_args_list[0].kwargs['input'])
            self.assertEqual(set(payload), {'protocol', 'season', 'database', 'temporary_directory'})
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['global.sqlite3.ingestion-lock'])
