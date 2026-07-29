"""Thread-safe snapshot warehouse with optional durable JSON storage."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from threading import RLock

from src.core.data_platform.models import DataEnvelope, DataQuality


class SnapshotWarehouse:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._rows: list[DataEnvelope] = []
        self._identities: set[tuple[str, str, str, str]] = set()
        self._lock = RLock()
        if path and path.exists():
            try:
                for row in json.loads(path.read_text(encoding="utf-8")):
                    row["quality"] = DataQuality(**row["quality"])
                    row["limitations"] = tuple(row.get("limitations") or ())
                    envelope = DataEnvelope(**row)
                    self._rows.append(envelope)
                    self._identities.add(self._identity(envelope))
            except (OSError, TypeError, ValueError):
                self._rows = []
                self._identities = set()

    @staticmethod
    def _identity(envelope: DataEnvelope) -> tuple[str, str, str, str]:
        return (
            envelope.key,
            envelope.provider,
            envelope.timestamp,
            envelope.category,
        )

    def append(self, envelope: DataEnvelope) -> None:
        with self._lock:
            identity = self._identity(envelope)
            if identity in self._identities:
                return
            self._rows.append(envelope)
            self._identities.add(identity)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                temporary.write_text(json.dumps([asdict(row) for row in self._rows], indent=2), encoding="utf-8")
                temporary.replace(self.path)

    def history(self, key: str, category: str | None = None) -> tuple[DataEnvelope, ...]:
        with self._lock:
            return tuple(sorted((row for row in self._rows if row.key == key and (category is None or row.category == category)), key=lambda row: row.timestamp))

    def latest(self, provider: str, key: str) -> DataEnvelope | None:
        rows = [row for row in self._rows if row.provider == provider and row.key == key]
        return max(rows, key=lambda row: row.timestamp, default=None)
