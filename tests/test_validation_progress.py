from __future__ import annotations

import json
import tempfile
import unittest
import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from pathlib import Path

from src.platform.validation.progress import ValidationProgress, read_progress
from tools.validation.smoke_http import _request_group, _route_identity
from src.platform.validation.release import startup_hygiene


class ValidationProgressTests(unittest.TestCase):
    def test_atomic_progress_survives_new_writer_process_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "progress.json"
            parent = ValidationProgress(path, "run")
            child = ValidationProgress(path, "run")
            parent.record("worker_phase", phase="startup")
            child.record(
                "request_started", route="/teams/{id}",
            )
            parent.record("worker_phase", phase="cleanup")
            payload = read_progress(path)
        self.assertEqual([row["sequence"] for row in payload["events"]], [1, 2, 3])
        self.assertEqual(payload["events"][1]["route"], "/teams/{id}")
        self.assertEqual(payload["last_event"]["phase"], "cleanup")

    def test_progress_snapshot_is_complete_json(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "progress.json"
            ValidationProgress(path, "run").record("phase", status="complete")
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["run_id"], "run")

    def test_route_identity_redacts_values_but_preserves_query_keys(self) -> None:
        self.assertEqual(
            _route_identity("/teams/42?league_id=private&front_office=7"),
            "/teams/{id}?front_office={value}&league_id={value}",
        )
        self.assertEqual(
            _route_identity("/api/market/assets/player:secret-id"),
            "/api/market/assets/player:{id}",
        )

    def test_request_groups_are_deterministic(self) -> None:
        self.assertEqual(_request_group("/api/market/health"), "market")
        self.assertEqual(_request_group("/trades?front_office=2"), "trade")
        self.assertEqual(_request_group("/api/inspect/health"), "inspection_health")

    def test_sensitive_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            progress = ValidationProgress(Path(folder) / "progress.json", "run")
            with self.assertRaisesRegex(ValueError, "sensitive fields"):
                progress.record("unsafe", session_token="never-store-this")

    @patch("src.platform.validation.release.windows_process_inventory", return_value=[])
    def test_canonical_hygiene_rejects_results_but_ignores_diagnostics(self, _inventory) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            diagnostics = root / ".validation" / "diagnostics"
            diagnostics.mkdir(parents=True)
            (diagnostics / "retained.progress.json").write_text("{}", encoding="utf-8")
            startup_hygiene(root, "run")
            results = root / ".validation" / "results"
            results.mkdir(parents=True)
            (results / "stale.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Stale validation state"):
                startup_hygiene(root, "run")

    def test_timeout_preserves_diagnostic_without_contaminating_results(self) -> None:
        from tools.validation import run_http_validation

        worker = Mock()
        worker.pid = 44
        worker.poll.return_value = -9
        worker.returncode = -9
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            results = root / "results"
            diagnostics = root / "diagnostics"
            diagnostics.mkdir()
            progress = diagnostics / "timeout.progress.json"
            waits = 0

            def wait(*, timeout):
                nonlocal waits
                waits += 1
                if waits == 1:
                    ValidationProgress(progress, "timeout").record(
                        "request_started", route="/market",
                    )
                    raise subprocess.TimeoutExpired("worker", timeout)
                return 0

            worker.wait.side_effect = wait
            with (
                patch.object(run_http_validation, "RESULTS_DIRECTORY", results),
                patch.object(run_http_validation, "DIAGNOSTICS_DIRECTORY", diagnostics),
                patch.object(run_http_validation, "progress_file_for", return_value=progress),
                patch.object(run_http_validation.subprocess, "Popen", return_value=worker),
                patch.dict("os.environ", {"DTOS_VALIDATION_RUN_ID": "timeout"}, clear=False),
                patch("builtins.print"),
            ):
                self.assertEqual(run_http_validation.main(timeout=1), 1)
            self.assertTrue(progress.exists())
            self.assertFalse(results.exists() and tuple(results.glob("*.json")))

    def test_outer_watchdog_allows_healthy_lifecycle_longer_than_120_seconds(self) -> None:
        from tools.validation import run_http_validation

        worker = Mock(pid=45, returncode=0)
        worker.poll.return_value = 0
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            results = root / "results"
            diagnostics = root / "diagnostics"

            def complete(*, timeout):
                self.assertEqual(timeout, 180.0)
                started = datetime.now(timezone.utc)
                payload = {
                    "run_id": "healthy", "started_at": started.isoformat(),
                    "completed_at": (started + timedelta(seconds=130)).isoformat(),
                    "completed": True, "startup": "PASS", "http_smoke": "PASS",
                    "cleanup": "PASS", "process_cleanup": "PASS", "pid": 1,
                    "port": 1, "shutdown_method": "graceful", "timings": {},
                    "errors": [], "passed": True,
                }
                results.mkdir(parents=True, exist_ok=True)
                (results / "healthy.json").write_text(
                    json.dumps(payload), encoding="utf-8",
                )
                return 0

            worker.wait.side_effect = complete
            with (
                patch.object(run_http_validation, "RESULTS_DIRECTORY", results),
                patch.object(run_http_validation, "DIAGNOSTICS_DIRECTORY", diagnostics),
                patch.object(run_http_validation.subprocess, "Popen", return_value=worker),
                patch.dict("os.environ", {"DTOS_VALIDATION_RUN_ID": "healthy"}, clear=False),
                patch("builtins.print"),
            ):
                self.assertEqual(run_http_validation.main(), 0)
            self.assertFalse((results / "healthy.json").exists())

    def test_outer_watchdog_does_not_change_request_contracts(self) -> None:
        from tools.validation import run_http_validation, smoke_http

        self.assertEqual(run_http_validation.OUTER_VALIDATION_WORKER_WATCHDOG_SECONDS, 180.0)
        self.assertEqual(smoke_http.MARKET_WARMING_RESPONSE_LIMIT_SECONDS, 0.5)
        self.assertEqual(smoke_http.MARKET_WARMING_DEADLINE_SECONDS, 60.0)


if __name__ == "__main__":
    unittest.main()
