"""Process inventory and run-scoped DTOS validation-server detection."""
from __future__ import annotations

import json
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
    return (
        ("dtos_app:app" in arguments and ("-m uvicorn" in arguments or executable_name.startswith("uvicorn")))
        or "-m tools.validation.server_host" in arguments
    )


def validation_run_id(record: ProcessRecord) -> str | None:
    parts = record.arguments.split()
    try:
        return parts[parts.index("--validation-run-id") + 1]
    except (ValueError, IndexError):
        return None


def processes_for_run(records: list[ProcessRecord], run_id: str) -> tuple[ProcessRecord, ...]:
    return tuple(item for item in records if is_dtos_server(item) and validation_run_id(item) == run_id)


def descendants(records: list[ProcessRecord], root_pid: int) -> tuple[ProcessRecord, ...]:
    found: list[ProcessRecord] = []
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        children = [item for item in records if item.parent_pid == parent and item not in found]
        found.extend(children)
        pending.extend(item.pid for item in children)
    return tuple(found)


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
        capture_output=True, text=True, check=True, timeout=30,
    )
    payload = json.loads(result.stdout or "[]")
    rows = payload if isinstance(payload, list) else [payload]
    return [
        ProcessRecord(
            int(row.get("ProcessId") or 0), int(row.get("ParentProcessId") or 0),
            str(row.get("Name") or ""), str(row.get("ExecutablePath") or ""),
            str(row.get("CommandLine") or ""),
        )
        for row in rows
    ]


__all__ = [
    "ProcessRecord", "descendants", "genuine_dtos_servers", "is_dtos_server",
    "processes_for_run", "validation_run_id", "windows_process_inventory",
]
