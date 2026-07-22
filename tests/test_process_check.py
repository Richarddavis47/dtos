"""Regression tests for genuine DTOS server process detection."""
from __future__ import annotations

import unittest

from tools.validation.process_check import ProcessRecord, genuine_dtos_servers, is_dtos_server


def record(pid: int, name: str, arguments: str, parent: int = 1, executable: str = "") -> ProcessRecord:
    return ProcessRecord(pid, parent, name, executable or name, arguments)


class ProcessCheckTests(unittest.TestCase):
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
