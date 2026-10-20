"""Platform and failure-mode coverage for development validation tooling."""
from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import psutil

from src.platform.validation.lifecycle import listening_pids
from tools.validation import browser_runtime, setup_cloud
from src.platform.validation.browser_memory import bounded_test_environment


def connection(port=9001, pid=321, status=psutil.CONN_LISTEN, family=socket.AF_INET):
    return SimpleNamespace(laddr=SimpleNamespace(port=port), pid=pid, status=status, family=family)


class ListenerInspectionTests(unittest.TestCase):
    def test_windows_and_linux_use_same_tcp_inventory_without_shell(self):
        for platform in ("win32", "linux"):
            with self.subTest(platform=platform), patch("sys.platform", platform), patch(
                "src.platform.validation.lifecycle.psutil.net_connections", return_value=[
                    connection(), connection(family=socket.AF_INET6),
                    connection(pid=322, family=socket.AF_INET6),
                    connection(port=90010, pid=123),
                    connection(pid=123, status=psutil.CONN_ESTABLISHED),
                    connection(pid=None, status=psutil.CONN_TIME_WAIT),
                ],
            ) as inventory, patch("subprocess.run") as shell:
                self.assertEqual(listening_pids(9001), {321, 322})
                inventory.assert_called_once_with(kind="tcp")
                shell.assert_not_called()

    def test_unknown_owner_is_not_a_released_port(self):
        with patch("psutil.net_connections", return_value=[connection(pid=None)]):
            with self.assertRaisesRegex(RuntimeError, "Cannot determine PID"):
                listening_pids(9001)

    def test_permission_error_is_not_empty_inventory(self):
        with patch("psutil.net_connections", side_effect=psutil.AccessDenied()):
            with self.assertRaises(psutil.AccessDenied):
                listening_pids(9001)

    def test_real_loopback_listener_reports_current_pid_then_releases(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            self.assertIn(os.getpid(), listening_pids(port))
        self.assertEqual(listening_pids(port), set())


class BrowserSelectionTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.pinned = Path(self.folder.name) / "chrome"
        self.playwright = SimpleNamespace(chromium=Mock(executable_path=str(self.pinned)))

    def test_installed_playwright_browser_wins_over_system(self):
        self.pinned.touch()
        with patch("shutil.which") as which:
            self.assertIsNone(browser_runtime.chromium_executable(self.playwright))
        which.assert_not_called()

    def test_linux_system_fallback_is_explicit_at_launch(self):
        with patch("sys.platform", "linux"), patch("shutil.which", return_value="/usr/bin/chromium"):
            browser_runtime.launch_chromium(self.playwright, headless=True)
        self.playwright.chromium.launch.assert_called_once_with(
            headless=True, executable_path="/usr/bin/chromium",
        )

    def test_windows_missing_pinned_browser_requires_setup(self):
        with patch("sys.platform", "win32"), patch("shutil.which", return_value="chromium"):
            with self.assertRaisesRegex(RuntimeError, "No Chromium available"):
                browser_runtime.chromium_executable(self.playwright)

    def test_invalid_override_fails_instead_of_falling_back(self):
        self.pinned.touch()
        with patch.dict(os.environ, {browser_runtime.EXECUTABLE_ENV: str(self.pinned.parent / "missing")}):
            with self.assertRaisesRegex(RuntimeError, "not an executable"):
                browser_runtime.chromium_executable(self.playwright)

    def test_explicit_override_wins_over_pinned(self):
        self.pinned.touch()
        executable = self.pinned.parent / "system-chrome"
        executable.touch()
        executable.chmod(0o755)
        with patch.dict(os.environ, {browser_runtime.EXECUTABLE_ENV: str(executable)}):
            # Path.resolve() can canonicalize the drive/directory case on Windows.
            self.assertEqual(browser_runtime.chromium_executable(self.playwright), str(executable.resolve()))

    def test_relative_override_is_resolved_before_launch(self):
        self.pinned.touch()
        # Stay on the working directory's drive, including on Windows CI.
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            executable = Path(folder) / "system-chrome"
            executable.touch()
            executable.chmod(0o755)
            (Path(folder) / "subdir").mkdir()
            relative = Path(folder).relative_to(Path.cwd()) / "subdir" / ".." / executable.name
            with patch.dict(os.environ, {browser_runtime.EXECUTABLE_ENV: str(relative)}):
                browser_runtime.launch_chromium(self.playwright, headless=True)
            self.playwright.chromium.launch.assert_called_once_with(
                headless=True, executable_path=str(executable.resolve()),
            )

    def test_launch_failure_is_not_retried_with_another_browser(self):
        self.pinned.touch()
        self.playwright.chromium.launch.side_effect = RuntimeError("broken browser")
        with self.assertRaisesRegex(RuntimeError, "broken browser"):
            browser_runtime.launch_chromium(self.playwright, headless=True)
        self.assertEqual(self.playwright.chromium.launch.call_count, 1)


class CloudSetupTests(unittest.TestCase):
    def test_browser_heap_budget_is_scoped_to_child_environment(self):
        supplied = {'DTOS_CACHE_FILE': 'caller-cache', 'HTTPS_PROXY': 'caller-proxy'}
        prepared = bounded_test_environment(supplied)
        self.assertNotIn('NODE_OPTIONS', supplied)
        self.assertEqual(prepared['NODE_OPTIONS'], '--max-old-space-size=256')
        self.assertEqual(prepared['DTOS_CACHE_FILE'], supplied['DTOS_CACHE_FILE'])
        self.assertEqual(prepared['HTTPS_PROXY'], supplied['HTTPS_PROXY'])

    def test_existing_node_options_remain_authoritative(self):
        for value in ('--max-old-space-size=192', '--require caller-bootstrap', ''):
            self.assertEqual(bounded_test_environment({'NODE_OPTIONS': value})['NODE_OPTIONS'], value)

    def test_existing_linux_system_browser_avoids_download_and_checks_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            python = Path(folder) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python.parent.mkdir()
            python.touch()
            with patch.object(setup_cloud.sys, 'version_info', (3, 12, 0)), patch("sys.argv", ["setup_cloud", "--venv", folder]), patch("sys.platform", "linux"), patch(
                "shutil.which", return_value="/usr/bin/chromium",
            ), patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as run:
                self.assertEqual(setup_cloud.main(), 0)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertFalse(any("playwright" in command for command in commands))
        self.assertIn("tools.validation.browser_runtime", commands[-1])
        self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))

    def test_missing_browser_installs_pinned_chromium_before_preflight(self):
        with tempfile.TemporaryDirectory() as folder:
            python = Path(folder) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python.parent.mkdir()
            python.touch()
            with patch.object(setup_cloud.sys, 'version_info', (3, 12, 0)), patch("sys.argv", ["setup_cloud", "--venv", folder]), patch(
                "shutil.which", return_value=None,
            ), patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as run:
                self.assertEqual(setup_cloud.main(), 0)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[1][1:], ["-m", "playwright", "install", "chromium"])
        self.assertIn("tools.validation.browser_runtime", commands[-1])

    def test_unsupported_python_is_rejected_before_setup_or_download(self):
        import io
        for version in ((3, 11, 0), (3, 14, 3)):
            with self.subTest(version=version), patch.object(setup_cloud.sys, 'version_info', version), \
                    patch('sys.argv', ['setup_cloud']), patch('sys.stderr', new_callable=io.StringIO), \
                    patch('subprocess.run') as run, patch('venv.EnvBuilder') as builder:
                with self.assertRaises(SystemExit) as error:
                    setup_cloud.main()
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()
                builder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
