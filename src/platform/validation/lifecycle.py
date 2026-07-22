"""Cross-platform, run-scoped validation-server lifecycle management."""
from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

from src.platform.validation.process_detection import (
    ProcessRecord, descendants, processes_for_run, windows_process_inventory,
)


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def listening_pids(port: int) -> set[int]:
    result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=True)
    suffix = f":{port}"
    return {
        int(columns[4]) for line in result.stdout.splitlines()
        if len(columns := line.split()) >= 5 and columns[0].upper() == "TCP"
        and columns[1].endswith(suffix) and columns[3].upper() == "LISTENING"
        and columns[4].isdigit()
    }


@dataclass(frozen=True)
class CleanupResult:
    outcome: str
    pid: int
    port: int


class TrackedServer:
    """Own one run-tagged server and its actual listening runtime process."""

    def __init__(
        self, process: subprocess.Popen[bytes], port: int, run_id: str, control_file: Path,
        *, owner_lookup: Callable[[int], set[int]] = listening_pids,
        inventory: Callable[[], list[ProcessRecord]] = windows_process_inventory,
    ):
        self.process = process
        self.port = port
        self.run_id = run_id
        self.control_file = control_file
        self.owner_lookup = owner_lookup
        self.inventory = inventory
        self.runtime_pid: int | None = None

    @classmethod
    def start(cls, repository_root: Path, log: BinaryIO, run_id: str, port: int | None = None) -> "TrackedServer":
        selected_port = port or available_port()
        control_file = repository_root / ".validation" / "control" / f"{run_id}.stop"
        control_file.parent.mkdir(parents=True, exist_ok=True)
        control_file.unlink(missing_ok=True)
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            [str(repository_root / ".venv" / "Scripts" / "python.exe"), "-B", "-m", "tools.validation.server_host",
             "--port", str(selected_port), "--validation-run-id", run_id, "--shutdown-file", str(control_file)],
            cwd=repository_root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
        )
        return cls(process, selected_port, run_id, control_file)

    def wait_until_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            owners = self.owner_lookup(self.port)
            tagged = {item.pid for item in processes_for_run(self.inventory(), self.run_id)}
            matches = owners & tagged
            if len(matches) == 1:
                self.runtime_pid = matches.pop()
                return
            if len(matches) > 1:
                raise RuntimeError(f"Multiple run-owned processes own validation port {self.port}: {sorted(matches)}")
            if self.process.poll() is not None and not tagged:
                raise RuntimeError(f"Validation launcher PID {self.process.pid} exited before runtime startup completed.")
            time.sleep(.1)
        raise TimeoutError(f"No runtime for run {self.run_id} owned port {self.port} within {timeout} seconds.")

    def _request_graceful_shutdown(self) -> None:
        self.control_file.write_text(self.run_id, encoding="utf-8")

    def _runtime_alive(self) -> bool:
        return self.runtime_pid is not None and any(item.pid == self.runtime_pid for item in self.inventory())

    def _wait_for_exit(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._runtime_alive() and not self.owner_lookup(self.port):
                return True
            time.sleep(.1)
        return False

    def _force_process_tree(self) -> None:
        if self.runtime_pid is None:
            raise RuntimeError("Runtime PID was never established.")
        records = self.inventory()
        run_records = {item.pid: item for item in processes_for_run(records, self.run_id)}
        targets = [item.pid for item in descendants(records, self.runtime_pid) if item.pid in run_records]
        targets.append(self.runtime_pid)
        if os.name == "nt":
            for pid in targets:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=False)
        else:
            for pid in targets:
                os.kill(pid, 9)

    def cleanup(self, graceful_timeout: float = 10, force_timeout: float = 10) -> CleanupResult:
        if self.runtime_pid is None:
            raise RuntimeError("Refusing cleanup: runtime PID was not verified.")
        try:
            run_pids = {item.pid for item in processes_for_run(self.inventory(), self.run_id)}
            owners = self.owner_lookup(self.port)
            if self.runtime_pid not in run_pids or self.runtime_pid not in owners:
                raise RuntimeError(
                    f"Refusing cleanup: runtime PID {self.runtime_pid} is not the run-owned port owner; "
                    f"run_pids={sorted(run_pids)}, owners={sorted(owners)}"
                )
            self._request_graceful_shutdown()
            if self._wait_for_exit(graceful_timeout):
                outcome = "graceful"
            else:
                self._force_process_tree()
                if not self._wait_for_exit(force_timeout):
                    raise RuntimeError(f"Run-owned process tree rooted at PID {self.runtime_pid} survived forced termination.")
                outcome = "forced"
            remaining = processes_for_run(self.inventory(), self.run_id)
            owners = self.owner_lookup(self.port)
            if remaining or owners:
                raise RuntimeError(
                    f"Cleanup incomplete; run processes={[item.pid for item in remaining]}, port owners={sorted(owners)}"
                )
            return CleanupResult(outcome, self.runtime_pid, self.port)
        finally:
            self.control_file.unlink(missing_ok=True)
