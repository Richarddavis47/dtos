"""Regression coverage for run-scoped validation server ownership."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from src.platform.validation.lifecycle import TrackedServer
from src.platform.validation.process_detection import ProcessRecord
from src.platform.validation.worker import validate_worker_result


RUN_ID = "run-123"


def record(pid: int, parent: int = 1, run_id: str = RUN_ID) -> ProcessRecord:
    return ProcessRecord(pid, parent, "python.exe", "python.exe", f"python -m tools.validation.server_host --validation-run-id {run_id}")


def server(tmp: Path, owners, inventories) -> TrackedServer:
    launcher = Mock(pid=100)
    launcher.poll.return_value = None
    return TrackedServer(
        launcher, 9001, RUN_ID, tmp / "stop", owner_lookup=Mock(side_effect=owners),
        inventory=Mock(side_effect=inventories),
    )


def worker_payload(**updates) -> dict:
    started = datetime.now(timezone.utc)
    payload = {
        "run_id": RUN_ID, "started_at": started.isoformat(),
        "completed_at": (started + timedelta(seconds=1)).isoformat(), "completed": True,
        "startup": "PASS", "http_smoke": "PASS", "cleanup": "PASS", "process_cleanup": "PASS",
        "pid": 321, "port": 9001, "shutdown_method": "graceful", "timings": {}, "errors": [], "passed": True,
    }
    payload.update(updates)
    return payload


class ServerLifecycleTests(unittest.TestCase):
    def test_runtime_pid_is_discovered_from_port_owner_and_run_tag(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            tracked = server(Path(folder), [{321}], [[record(100), record(321, 100)]])
            tracked.wait_until_ready(timeout=.1)
        self.assertEqual(tracked.runtime_pid, 321)

    def test_runtime_pid_must_belong_to_current_run(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            tracked = server(Path(folder), [{321}], [[record(321, run_id="other")]])
            with self.assertRaises(TimeoutError):
                tracked.wait_until_ready(timeout=.01)

    def test_graceful_cleanup_verifies_run_and_port_release(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            tracked = server(Path(folder), [{321}, set(), set()], [[record(321)], [], []])
            tracked.runtime_pid = 321
            result = tracked.cleanup(graceful_timeout=.1)
        self.assertEqual(result.outcome, "graceful")

    def test_cleanup_refuses_unrelated_port_owner(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            tracked = server(Path(folder), [{999}], [[record(321)]])
            tracked.runtime_pid = 321
            with self.assertRaisesRegex(RuntimeError, "Refusing cleanup"):
                tracked.cleanup()

    def test_forced_cleanup_targets_run_owned_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            tracked = server(Path(folder), [{321}, set(), set()], [[record(321)], [], []])
            tracked.runtime_pid = 321
            with patch.object(tracked, "_force_process_tree") as force:
                result = tracked.cleanup(graceful_timeout=0, force_timeout=.1)
        force.assert_called_once()
        self.assertEqual(result.outcome, "forced")

    def test_result_schema_rejects_run_id_mismatch(self) -> None:
        self.assertEqual(validate_worker_result(worker_payload(), RUN_ID), ())
        self.assertTrue(any("mismatch" in item for item in validate_worker_result(worker_payload(), "other")))

    def test_result_schema_rejects_incomplete_or_invalid_timestamp(self) -> None:
        errors = validate_worker_result(worker_payload(completed=False, completed_at="invalid"), RUN_ID)
        self.assertTrue(any("incomplete" in item for item in errors))
        self.assertTrue(any("timestamp" in item for item in errors))

    def test_parent_uses_run_scoped_artifact_and_rejects_stale_duplicate(self) -> None:
        from tools.validation import run_http_validation
        with tempfile.TemporaryDirectory() as folder, patch.object(run_http_validation, "RESULTS_DIRECTORY", Path(folder)), patch.dict("os.environ", {"DTOS_VALIDATION_RUN_ID": RUN_ID}):
            run_http_validation.result_file_for(RUN_ID).write_text("{}", encoding="utf-8")
            with patch("builtins.print"):
                self.assertEqual(run_http_validation.main(), 1)

    def test_parent_rejects_missing_artifact(self) -> None:
        from tools.validation import run_http_validation
        worker = Mock()
        worker.wait.return_value = 1
        with tempfile.TemporaryDirectory() as folder, patch.object(run_http_validation, "RESULTS_DIRECTORY", Path(folder)), patch.dict("os.environ", {"DTOS_VALIDATION_RUN_ID": RUN_ID}), patch.object(subprocess, "Popen", return_value=worker), patch("builtins.print"):
            self.assertEqual(run_http_validation.main(), 1)

    def test_worker_writes_artifact_in_finally(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "tools" / "validation" / "http_worker.py").read_text(encoding="utf-8")
        self.assertIn("finally:", source)
        self.assertIn("temporary.replace(args.result_file)", source)

    def test_repeated_standalone_runs_generate_unique_ids(self) -> None:
        from tools.validation.run_http_validation import result_file_for
        self.assertNotEqual(result_file_for("one"), result_file_for("two"))


if __name__ == "__main__":
    unittest.main()
