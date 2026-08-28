"""Atomic, sanitized progress evidence for bounded validation workers."""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

PROGRESS_FILE_ENVIRONMENT = "DTOS_VALIDATION_PROGRESS_FILE"
PROGRESS_RUN_ENVIRONMENT = "DTOS_VALIDATION_PROGRESS_RUN_ID"
_FORBIDDEN_FIELD_PARTS = (
    "password", "secret", "token", "cookie", "csrf", "ssh", "credential",
)


@contextmanager
def _progress_file_lock(path: Path):
    """Serialize progress readers and writers across processes."""
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_progress_unlocked(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return None
    return payload


class ValidationProgress:
    """Persist bounded validation progress so watchdog termination keeps evidence."""

    def __init__(self, path: Path, run_id: str, *, maximum_events: int = 1000):
        self.path = path
        self.run_id = run_id
        self.maximum_events = maximum_events
        existing = read_progress(path)
        self._events = list(existing.get("events", [])) if existing else []
        self._sequence = max(
            (int(item.get("sequence") or 0) for item in self._events), default=0,
        )
        self._lock = threading.Lock()

    def record(self, event: str, **fields: Any) -> dict[str, Any]:
        unsafe = [
            name for name in fields
            if any(part in name.casefold() for part in _FORBIDDEN_FIELD_PARTS)
        ]
        if unsafe:
            raise ValueError(
                "Validation progress refuses sensitive fields: " + ", ".join(unsafe)
            )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with _progress_file_lock(self.path):
                # The worker, smoke process, and diagnostic subprocesses share
                # this run-scoped artifact. Reload only while holding the
                # inter-process lock so no writer can erase another's event.
                existing = _read_progress_unlocked(self.path)
                if existing:
                    self._events = list(existing.get("events", []))
                    self._sequence = max(
                        (int(item.get("sequence") or 0) for item in self._events),
                        default=self._sequence,
                    )
                self._sequence += 1
                entry = {
                    "sequence": self._sequence,
                    "event": event,
                    "monotonic": round(monotonic(), 6),
                    "pid": os.getpid(),
                    **fields,
                }
                self._events.append(entry)
                if len(self._events) > self.maximum_events:
                    self._events = self._events[-self.maximum_events:]
                payload = {
                    "schema_version": 1,
                    "run_id": self.run_id,
                    "last_event": entry,
                    "events": self._events,
                }
                temporary = self.path.with_name(
                    f"{self.path.name}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
                )
                try:
                    temporary.write_text(
                        json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    os.replace(temporary, self.path)
                finally:
                    temporary.unlink(missing_ok=True)
                return entry


def read_progress(path: Path) -> dict[str, Any] | None:
    """Read one complete atomic snapshot; malformed evidence fails closed."""
    if not path.exists():
        return None
    with _progress_file_lock(path):
        return _read_progress_unlocked(path)


def cleanup_progress_temporary_files(path: Path) -> int:
    """Remove only unpublished temporary snapshots after all writers exit."""
    removed = 0
    with _progress_file_lock(path):
        for temporary in path.parent.glob(f"{path.name}.*.tmp"):
            temporary.unlink(missing_ok=True)
            removed += 1
    return removed


def progress_from_environment() -> ValidationProgress | None:
    path = os.environ.get(PROGRESS_FILE_ENVIRONMENT)
    run_id = os.environ.get(PROGRESS_RUN_ENVIRONMENT)
    if not path or not run_id:
        return None
    return ValidationProgress(Path(path), run_id)
