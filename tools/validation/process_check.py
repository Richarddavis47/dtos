"""Detect genuine orphaned DTOS server hosts without self-matching shell text."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    parent_pid: int
    name: str
    executable: str
    arguments: str


def is_dtos_server(record: ProcessRecord, excluded_pids: set[int] | None = None) -> bool:
    if record.pid in (excluded_pids or set()):
        return False
    executable_name = (Path(record.executable).name or record.name).lower()
    if executable_name not in {"python", "python.exe", "python3", "python3.exe", "uvicorn", "uvicorn.exe"}:
        return False
    arguments = record.arguments.lower()
    has_target = "dtos_app:app" in arguments
    python_host = executable_name.startswith("python") and "-m uvicorn" in arguments
    uvicorn_host = executable_name.startswith("uvicorn")
    return has_target and (python_host or uvicorn_host)


def genuine_dtos_servers(records: list[ProcessRecord], current_pid: int, parent_pid: int) -> tuple[ProcessRecord, ...]:
    excluded = {current_pid, parent_pid}
    return tuple(record for record in records if is_dtos_server(record, excluded))


def windows_process_inventory() -> list[ProcessRecord]:
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout or "[]")
    rows = payload if isinstance(payload, list) else [payload]
    return [
        ProcessRecord(
            int(row.get("ProcessId") or 0),
            int(row.get("ParentProcessId") or 0),
            str(row.get("Name") or ""),
            str(row.get("ExecutablePath") or ""),
            str(row.get("CommandLine") or ""),
        )
        for row in rows
    ]


def main() -> int:
    current_pid = os.getpid()
    parent_pid = os.getppid()
    matches = genuine_dtos_servers(windows_process_inventory(), current_pid, parent_pid)
    if matches:
        detail = "\n".join(
            f"name={item.name} pid={item.pid} parent={item.parent_pid} executable={item.executable} arguments={item.arguments}"
            for item in matches
        )
        raise RuntimeError("Genuine DTOS server process remains:\n" + detail)
    print("Process cleanup passed: no genuine DTOS Python/Uvicorn server remains.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
