"""Controlled tests for deterministic validation-server cleanup."""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import Mock, patch

from tools.validation.server_lifecycle import TrackedServer


def process(pid: int = 321) -> Mock:
    item = Mock()
    item.pid = pid
    item.poll.return_value = None
    return item


class ServerLifecycleTests(unittest.TestCase):
    def test_graceful_shutdown_releases_port(self) -> None:
        child = process()
        owners = Mock(side_effect=[{321}, set()])
        server = TrackedServer(child, 9001, owner_lookup=owners)
        with patch.object(server, "_request_graceful_shutdown") as graceful:
            result = server.cleanup()
        graceful.assert_called_once()
        self.assertEqual(result.outcome, "graceful")

    def test_ignored_interrupt_forces_tracked_process_tree(self) -> None:
        child = process()
        child.wait.side_effect = [subprocess.TimeoutExpired("server", 1), 0]
        owners = Mock(side_effect=[{321}, set()])
        server = TrackedServer(child, 9002, owner_lookup=owners)
        with patch.object(server, "_request_graceful_shutdown"), patch.object(server, "_force_process_tree") as force:
            result = server.cleanup(graceful_timeout=.01)
        force.assert_called_once()
        self.assertEqual(result.outcome, "forced")

    def test_force_path_represents_child_process_tree_cleanup(self) -> None:
        child = process()
        server = TrackedServer(child, 9003, owner_lookup=Mock(side_effect=[{321}, set()]))
        child.wait.side_effect = [subprocess.TimeoutExpired("server", 1), 0]
        with patch.object(server, "_request_graceful_shutdown"), patch("tools.validation.server_lifecycle.os.name", "nt"), patch("tools.validation.server_lifecycle.subprocess.run") as run:
            server.cleanup()
        run.assert_called_once_with(["taskkill", "/PID", "321", "/T", "/F"], capture_output=True, check=False)

    def test_port_release_is_required(self) -> None:
        server = TrackedServer(process(), 9004, owner_lookup=Mock(side_effect=[{321}, {999}]))
        with patch.object(server, "_request_graceful_shutdown"):
            with self.assertRaisesRegex(RuntimeError, "remains occupied"):
                server.cleanup()

    def test_refuses_to_terminate_unrelated_owner(self) -> None:
        server = TrackedServer(process(), 9005, owner_lookup=lambda _: {999})
        with patch.object(server, "_request_graceful_shutdown") as graceful:
            with self.assertRaisesRegex(RuntimeError, "Refusing cleanup"):
                server.cleanup()
        graceful.assert_not_called()

    def test_already_exited_server_is_safe(self) -> None:
        child = process()
        child.poll.return_value = 0
        result = TrackedServer(child, 9006, owner_lookup=lambda _: set()).cleanup()
        self.assertEqual(result.outcome, "already exited")

    def test_runner_cleanup_is_in_finally_after_smoke_exception(self) -> None:
        source = (__import__("pathlib").Path(__file__).resolve().parents[1] / "tools" / "validation" / "run_http_validation.py").read_text(encoding="utf-8")
        self.assertIn("finally:", source)
        self.assertIn("server.cleanup()", source)


if __name__ == "__main__":
    unittest.main()
