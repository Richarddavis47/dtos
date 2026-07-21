"""Windows-safe lifecycle management for a tracked local validation server."""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def listening_pids(port: int) -> set[int]:
    result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=True)
    suffix = f":{port}"
    owners = set()
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 5 and columns[0].upper() == "TCP" and columns[1].endswith(suffix) and columns[3].upper() == "LISTENING":
            try:
                owners.add(int(columns[4]))
            except ValueError:
                continue
    return owners


@dataclass(frozen=True)
class CleanupResult:
    outcome: str
    pid: int
    port: int


class TrackedServer:
    def __init__(self, process: subprocess.Popen[bytes], port: int, *, owner_lookup: Callable[[int], set[int]] = listening_pids):
        self.process = process
        self.port = port
        self.owner_lookup = owner_lookup

    @classmethod
    def start(cls, repository_root: Path, log: BinaryIO, port: int | None = None) -> "TrackedServer":
        selected_port = port or available_port()
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            [str(repository_root / ".venv" / "Scripts" / "python.exe"), "-B", "-m", "uvicorn", "dtos_app:app", "--host", "127.0.0.1", "--port", str(selected_port)],
            cwd=repository_root,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        return cls(process, selected_port)

    def wait_until_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Validation server PID {self.process.pid} exited before startup completed.")
            owners = self.owner_lookup(self.port)
            if self.process.pid in owners:
                return
            time.sleep(.1)
        raise TimeoutError(f"Validation server PID {self.process.pid} did not own port {self.port} within {timeout} seconds.")

    def _request_graceful_shutdown(self) -> None:
        if os.name == "nt":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.process.terminate()

    def _force_process_tree(self) -> None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            self.process.kill()

    def cleanup(self, graceful_timeout: float = 10, force_timeout: float = 10) -> CleanupResult:
        if self.process.poll() is not None:
            return CleanupResult("already exited", self.process.pid, self.port)
        owners = self.owner_lookup(self.port)
        if self.process.pid not in owners:
            raise RuntimeError(f"Refusing cleanup: tracked PID {self.process.pid} does not own validation port {self.port}; owners={sorted(owners)}")
        self._request_graceful_shutdown()
        try:
            self.process.wait(timeout=graceful_timeout)
            outcome = "graceful"
        except subprocess.TimeoutExpired:
            self._force_process_tree()
            try:
                self.process.wait(timeout=force_timeout)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Tracked server process tree rooted at PID {self.process.pid} survived forced termination.") from exc
            outcome = "forced"
        remaining = self.owner_lookup(self.port)
        if remaining:
            raise RuntimeError(f"Validation port {self.port} remains occupied after {outcome} shutdown; owners={sorted(remaining)}")
        return CleanupResult(outcome, self.process.pid, self.port)
