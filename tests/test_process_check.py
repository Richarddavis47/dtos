"""Regression tests for genuine DTOS server process detection."""
from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from tools.validation.process_check import ProcessRecord, genuine_dtos_servers, is_dtos_server
from src.platform.validation.process_detection import ProcessInventoryError, _parse_process_json, _powershell_inventory, windows_process_inventory


def record(pid: int, name: str, arguments: str, parent: int = 1, executable: str = "") -> ProcessRecord:
    return ProcessRecord(pid, parent, name, executable or name, arguments)


class ProcessCheckTests(unittest.TestCase):
    def test_get_cim_instance_parses_one_process(self) -> None:
        payload = '{"ProcessId":10,"ParentProcessId":1,"Name":"python.exe","ExecutablePath":"C:\\\\python.exe","CommandLine":"python -m uvicorn dtos_app:app"}'
        with patch("src.platform.validation.process_detection.subprocess.run", return_value=CompletedProcess([], 0, payload, "")):
            records = _powershell_inventory("powershell.exe", "Get-CimInstance")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].pid, 10)

    def test_get_cim_instance_parses_multiple_processes(self) -> None:
        payload = '[{"ProcessId":10,"ParentProcessId":1,"Name":"python.exe"},{"ProcessId":11,"ParentProcessId":1,"Name":"pwsh.exe"}]'
        self.assertEqual(len(_parse_process_json(payload, "test")), 2)

    def test_empty_process_result_is_supported(self) -> None:
        self.assertEqual(_parse_process_json("", "test"), [])
        self.assertEqual(_parse_process_json("null", "test"), [])

    def test_nonzero_powershell_exit_reports_stderr_and_context(self) -> None:
        result = CompletedProcess([], 1, "partial", "Get-CimInstance: Access denied")
        with patch("src.platform.validation.process_detection.subprocess.run", return_value=result):
            with self.assertRaisesRegex(ProcessInventoryError, "Access denied") as raised:
                _powershell_inventory("powershell.exe", "Get-CimInstance")
        self.assertIn("exit_code=1", str(raised.exception))
        self.assertIn("powershell.exe", str(raised.exception))

    def test_malformed_json_is_explicit(self) -> None:
        with self.assertRaisesRegex(ProcessInventoryError, "malformed JSON"):
            _parse_process_json("warning before json", "Get-CimInstance")

    def test_cim_failure_falls_back_to_wmi_success(self) -> None:
        denied = CompletedProcess([], 1, "", "CIM denied")
        success = CompletedProcess([], 0, "[]", "")
        with patch("src.platform.validation.process_detection.shutil.which", side_effect=lambda name: "powershell.exe" if name == "powershell.exe" else None), patch("src.platform.validation.process_detection.subprocess.run", side_effect=(denied, success)), patch("src.platform.validation.process_detection._psutil_inventory") as psutil:
            self.assertEqual(windows_process_inventory(), [])
        psutil.assert_not_called()

    def test_powershell_failures_fall_back_to_psutil(self) -> None:
        denied = CompletedProcess([], 1, "", "Access denied")
        expected = [record(12, "python.exe", "python -m uvicorn dtos_app:app")]
        with patch("src.platform.validation.process_detection.shutil.which", side_effect=lambda name: "powershell.exe" if name == "powershell.exe" else None), patch("src.platform.validation.process_detection.subprocess.run", return_value=denied), patch("src.platform.validation.process_detection._psutil_inventory", return_value=expected):
            self.assertEqual(windows_process_inventory(), expected)

    def test_all_inventory_methods_failing_is_not_treated_as_empty(self) -> None:
        denied = CompletedProcess([], 1, "", "Access denied")
        with patch("src.platform.validation.process_detection.shutil.which", side_effect=lambda name: "powershell.exe" if name == "powershell.exe" else None), patch("src.platform.validation.process_detection.subprocess.run", return_value=denied), patch("src.platform.validation.process_detection._psutil_inventory", side_effect=ProcessInventoryError("psutil blocked")):
            with self.assertRaisesRegex(ProcessInventoryError, "All Windows process inventory methods failed") as raised:
                windows_process_inventory()
        self.assertIn("Get-CimInstance", str(raised.exception))
        self.assertIn("Get-WmiObject", str(raised.exception))
        self.assertIn("psutil blocked", str(raised.exception))

    def test_real_python_uvicorn_dtos_server_is_detected(self) -> None:
        item = record(10, "python.exe", "python.exe -m uvicorn dtos_app:app --port 8123")
        self.assertTrue(is_dtos_server(item))

    def test_validation_server_host_is_detected(self) -> None:
        item = record(12, "python.exe", "python.exe -m tools.validation.server_host --port 8123")
        self.assertTrue(is_dtos_server(item))

    def test_powershell_query_text_is_not_a_server(self) -> None:
        item = record(11, "powershell.exe", "powershell -Command search uvicorn dtos_app:app")
        self.assertFalse(is_dtos_server(item))

    def test_checker_excludes_itself_and_parent_shell(self) -> None:
        records = [
            record(20, "python.exe", "python -m uvicorn dtos_app:app"),
            record(21, "python.exe", "python -m uvicorn dtos_app:app"),
        ]
        self.assertEqual(genuine_dtos_servers(records, 20, 21), ())

    def test_exited_tracked_process_and_released_port_are_clean(self) -> None:
        self.assertEqual(genuine_dtos_servers([], 30, 29), ())

    def test_unrelated_python_is_not_reported(self) -> None:
        item = record(31, "python.exe", "python -m http.server 8000")
        self.assertFalse(is_dtos_server(item))

    def test_genuine_orphaned_child_is_detected(self) -> None:
        orphan = record(41, "python.exe", "python -B -m uvicorn dtos_app:app --port 8767", parent=999)
        self.assertEqual(genuine_dtos_servers([orphan], 40, 39), (orphan,))

    def test_direct_uvicorn_executable_is_detected(self) -> None:
        item = record(42, "uvicorn.exe", "uvicorn.exe dtos_app:app --port 8767")
        self.assertTrue(is_dtos_server(item))


if __name__ == "__main__":
    unittest.main()
