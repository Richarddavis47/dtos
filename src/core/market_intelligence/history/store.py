"""Thread-safe JSON snapshot history with an in-memory default."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock


@dataclass(frozen=True)
class MarketSnapshot:
    asset_id: str
    timestamp: str
    provider: str
    value: float
    confidence: int


class MarketHistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._rows: list[MarketSnapshot] = []
        self._lock = RLock()
        if path and path.exists():
            try:
                self._rows = [MarketSnapshot(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
            except (OSError, ValueError, TypeError):
                self._rows = []

    def append(self, rows: tuple[MarketSnapshot, ...]) -> None:
        if not rows:
            return
        with self._lock:
            known = {(row.asset_id, row.timestamp, row.provider) for row in self._rows}
            self._rows.extend(row for row in rows if (row.asset_id, row.timestamp, row.provider) not in known)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                temporary.write_text(json.dumps([asdict(row) for row in self._rows], indent=2), encoding="utf-8")
                temporary.replace(self.path)

    def for_asset(self, asset_id: str) -> tuple[MarketSnapshot, ...]:
        with self._lock:
            return tuple(sorted((row for row in self._rows if row.asset_id == asset_id), key=lambda row: row.timestamp))
