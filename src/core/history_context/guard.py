"""Fail-closed accounting for dormant HistoricalStore access."""
from __future__ import annotations

import inspect
import os
from collections import Counter
from dataclasses import dataclass, field
from threading import RLock


class LegacyAccessError(RuntimeError):
    pass


@dataclass
class LegacyAccessGuard:
    mode: str = field(default_factory=lambda: os.getenv(
        "DTOS_LEGACY_HISTORY_MODE", "shadow_forbidden",
    ).strip().casefold())
    reads: int = 0
    writes: int = 0
    callers: Counter[str] = field(default_factory=Counter)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def _record(self, operation: str) -> None:
        frame = next((
            item for item in inspect.stack()[2:]
            if "historical_memory\\store.py" not in item.filename.replace("/", "\\")
        ), None)
        caller = f"{frame.filename}:{frame.lineno}" if frame else "unknown"
        with self._lock:
            if operation == "read":
                self.reads += 1
            else:
                self.writes += 1
            self.callers[f"{operation}:{caller}"] += 1
        if self.mode in {"shadow_forbidden", "retired"}:
            raise LegacyAccessError(
                f"Legacy HistoricalStore {operation} is forbidden in {self.mode} mode."
            )

    def read(self) -> None:
        self._record("read")

    def write(self) -> None:
        self._record("write")

    def health(self) -> dict[str, object]:
        with self._lock:
            return {
                "mode": self.mode,
                "legacy_read_attempts": self.reads,
                "legacy_write_attempts": self.writes,
                "callers": dict(self.callers),
                "status": "healthy" if not self.reads and not self.writes else "failed",
            }

    def reset(self) -> None:
        with self._lock:
            self.reads = self.writes = 0
            self.callers.clear()


legacy_access_guard = LegacyAccessGuard()
