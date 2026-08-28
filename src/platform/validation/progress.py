"""Atomic, sanitized progress evidence for bounded validation workers."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from time import monotonic
from typing import Any

PROGRESS_FILE_ENVIRONMENT = "DTOS_VALIDATION_PROGRESS_FILE"
PROGRESS_RUN_ENVIRONMENT = "DTOS_VALIDATION_PROGRESS_RUN_ID"
_FORBIDDEN_FIELD_PARTS = (
    "password", "secret", "token", "cookie", "csrf", "ssh", "credential",
)


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
            # A validation worker and its smoke subprocess write sequentially to
            # the same run-scoped artifact. Reload the last atomic snapshot so a
            # stale writer cannot erase progress produced by the other process.
            existing = read_progress(self.path)
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
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
            temporary.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
            return entry


def read_progress(path: Path) -> dict[str, Any] | None:
    """Read one complete atomic snapshot; malformed evidence fails closed."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return None
    return payload


def progress_from_environment() -> ValidationProgress | None:
    path = os.environ.get(PROGRESS_FILE_ENVIRONMENT)
    run_id = os.environ.get(PROGRESS_RUN_ENVIRONMENT)
    if not path or not run_id:
        return None
    return ValidationProgress(Path(path), run_id)
