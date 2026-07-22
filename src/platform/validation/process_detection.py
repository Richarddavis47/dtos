"""Process inventory and run-scoped DTOS validation-server detection."""
from __future__ import annotations

import json
import shutil
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


class ProcessInventoryError(RuntimeError):
    """Raised when no Windows inventory source can provide trustworthy data."""


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


def _parse_process_json(output: str, context: str) -> list[ProcessRecord]:
    try:
        payload = json.loads(output.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise ProcessInventoryError(f"{context} returned malformed JSON: {exc}; stdout={output!r}") from exc
    rows = payload if isinstance(payload, list) else [payload]
    if rows == [None]:
        rows = []
    return [
        ProcessRecord(
            int(row.get("ProcessId") or 0), int(row.get("ParentProcessId") or 0),
            str(row.get("Name") or ""), str(row.get("ExecutablePath") or ""),
            str(row.get("CommandLine") or ""),
        )
        for row in rows
        if isinstance(row, dict)
    ]


def _powershell_inventory(executable: str, command_name: str) -> list[ProcessRecord]:
    query = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
        f"@({command_name} Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine) | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    command = [executable, "-NoProfile", "-NonInteractive", "-Command", query]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessInventoryError(f"PowerShell inventory invocation failed; executable={executable!r}; command={command!r}; error={exc}") from exc
    if result.returncode:
        raise ProcessInventoryError(
            "PowerShell process inventory failed; "
            f"executable={executable!r}; method={command_name}; exit_code={result.returncode}; "
            f"stdout={result.stdout.strip()!r}; stderr={result.stderr.strip()!r}; command={command!r}"
        )
    return _parse_process_json(result.stdout, f"{executable} {command_name}")


def _psutil_inventory() -> list[ProcessRecord]:
    try:
        import psutil
    except ImportError as exc:
        raise ProcessInventoryError("psutil fallback is unavailable; install repository dependencies") from exc
    records: list[ProcessRecord] = []
    for process in psutil.process_iter(("pid", "ppid", "name", "exe", "cmdline")):
        try:
            info = process.info
            records.append(ProcessRecord(int(info.get("pid") or 0), int(info.get("ppid") or 0), str(info.get("name") or ""), str(info.get("exe") or ""), subprocess.list2cmdline(info.get("cmdline") or [])))
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return records


def windows_process_inventory() -> list[ProcessRecord]:
    errors: list[str] = []
    executables = tuple(dict.fromkeys(item for item in (shutil.which("powershell.exe"), shutil.which("pwsh.exe")) if item))
    for executable in executables:
        for method in ("Get-CimInstance", "Get-WmiObject"):
            try:
                return _powershell_inventory(executable, method)
            except ProcessInventoryError as exc:
                errors.append(str(exc))
    try:
        return _psutil_inventory()
    except ProcessInventoryError as exc:
        errors.append(str(exc))
    raise ProcessInventoryError("All Windows process inventory methods failed:\n- " + "\n- ".join(errors))


__all__ = [
    "ProcessInventoryError", "ProcessRecord", "descendants", "genuine_dtos_servers", "is_dtos_server",
    "processes_for_run", "validation_run_id", "windows_process_inventory",
]
