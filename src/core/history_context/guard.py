"""Fail-closed accounting for dormant HistoricalStore access."""
from __future__ import annotations

import inspect
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock

from app_metadata import VERSION
from config import HISTORY_DATABASE_FILE, HISTORY_STORAGE_ROOT


class LegacyAccessError(RuntimeError):
    pass


@dataclass
class LegacyAccessGuard:
    mode: str = field(default_factory=lambda: os.getenv(
        "DTOS_LEGACY_HISTORY_MODE", "retired",
    ).strip().casefold())
    reads: int = 0
    writes: int = 0
    creates: int = 0
    callers: Counter[str] = field(default_factory=Counter)
    last_attempt_caller: str | None = None
    _lock: RLock = field(default_factory=RLock, repr=False)

    def _record(self, operation: str) -> None:
        frame = next((
            item for item in inspect.stack()[2:]
            if "historical_memory\\store.py" not in item.filename.replace("/", "\\")
        ), None)
        caller = (
            f"{Path(frame.filename).name}:{frame.function}:{frame.lineno}"
            if frame else "unknown"
        )
        with self._lock:
            if operation == "read":
                self.reads += 1
            elif operation == "write":
                self.writes += 1
            else:
                self.creates += 1
            self.last_attempt_caller = caller
            self.callers[f"{operation}:{caller}"] += 1
        if self.mode in {"shadow_forbidden", "retired"}:
            raise LegacyAccessError(
                f"Legacy HistoricalStore {operation} is forbidden in {self.mode} mode."
            )

    def read(self) -> None:
        self._record("read")

    def write(self) -> None:
        self._record("write")

    def create(self) -> None:
        self._record("create")

    @staticmethod
    def targets(path: Path) -> bool:
        """Identify only the configured retired archive, never test databases."""
        try:
            return Path(path).resolve() == Path(HISTORY_DATABASE_FILE).resolve()
        except OSError:
            return Path(path).absolute() == Path(HISTORY_DATABASE_FILE).absolute()

    def guard_constructor(self, path: Path) -> None:
        if self.mode == "retired" and self.targets(path):
            self.create()

    @staticmethod
    def marker_path() -> Path:
        return Path(HISTORY_STORAGE_ROOT) / ".historicalstore-retired.json"

    def _retirement_marker(self) -> dict[str, object]:
        try:
            value = json.loads(self.marker_path().read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def health(self) -> dict[str, object]:
        with self._lock:
            marker = self._retirement_marker()
            present = Path(HISTORY_DATABASE_FILE).exists()
            return {
                "mode": self.mode,
                "historicalstore_retired": self.mode == "retired",
                "legacy_file_present": present,
                "legacy_read_attempts": self.reads,
                "legacy_write_attempts": self.writes,
                "legacy_create_attempts": self.creates,
                "last_attempt_caller": self.last_attempt_caller,
                "retirement_timestamp": marker.get("retired_at"),
                "retirement_version": marker.get("version") or (
                    VERSION if self.mode == "retired" and not present else None
                ),
                "callers": dict(self.callers),
                "status": "healthy" if not (
                    self.reads or self.writes or self.creates
                ) else "failed",
            }

    def reset(self) -> None:
        with self._lock:
            self.reads = self.writes = self.creates = 0
            self.last_attempt_caller = None
            self.callers.clear()


legacy_access_guard = LegacyAccessGuard()
