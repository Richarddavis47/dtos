"""Process-local coordination and bounded memory telemetry for heavy DTOS work."""
from __future__ import annotations

import os
import threading
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import psutil

HEAVY_PHASES = frozenset({
    "sleeper_sync", "provider_network", "valuation_intelligence",
    "cache_persistence", "historical_import", "asset_market_build",
})
MARKET_BUILD_BLOCKERS = HEAVY_PHASES - {"asset_market_build"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integer_file(*paths: str) -> int | None:
    for raw in paths:
        try:
            value = Path(raw).read_text(encoding="utf-8").strip()
            if value != "max":
                return int(value)
        except (OSError, ValueError):
            continue
    return None


def _key_value_file(path: str) -> dict[str, int] | None:
    try:
        values: dict[str, int] = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            key, raw = line.split(maxsplit=1)
            value = int(raw)
            if value < 0:
                return None
            values[key] = value
        return values or None
    except (OSError, ValueError):
        return None


def memory_snapshot() -> dict[str, Any]:
    """Return numeric process/cgroup telemetry without host path disclosure."""
    process = psutil.Process(os.getpid())
    info = process.memory_info()
    current = _integer_file(
        "/sys/fs/cgroup/memory.current",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes",
    )
    limit = _integer_file(
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    )
    stat = _key_value_file("/sys/fs/cgroup/memory.stat")
    events = _key_value_file("/sys/fs/cgroup/memory.events")
    return {
        "rss_bytes": int(info.rss),
        "vms_bytes": int(info.vms),
        "system_available_bytes": int(psutil.virtual_memory().available),
        "cgroup_current_bytes": current,
        "cgroup_limit_bytes": limit,
        "cgroup_inactive_file_bytes": (
            stat.get("inactive_file") if stat is not None else None
        ),
        "cgroup_memory_events": events,
    }


class LifecycleCoordinator:
    """Serialize memory-heavy phases and retain only bounded diagnostics."""

    def __init__(self, history_limit: int = 32) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._phase: str | None = None
        self._owner: int | None = None
        self._history: deque[dict[str, Any]] = deque(maxlen=history_limit)

    @contextmanager
    def phase(self, name: str) -> Iterator[dict[str, Any]]:
        if name not in HEAVY_PHASES:
            raise ValueError(f"Unsupported lifecycle phase: {name}")
        owner = threading.get_ident()
        with self._condition:
            while self._phase is not None and self._owner != owner:
                self._condition.wait()
            previous = self._phase
            self._phase = name
            self._owner = owner
            started = _utcnow()
            before = memory_snapshot()
        outcome = "complete"
        details: dict[str, Any] = {}
        try:
            yield details
        except BaseException:
            outcome = "failed"
            raise
        finally:
            after = memory_snapshot()
            with self._condition:
                self._history.append({
                    "phase": name, "status": outcome, "started_at": started,
                    "finished_at": _utcnow(), "memory_before": before,
                    "memory_after": after, "details": dict(details),
                })
                self._phase = previous
                self._owner = owner if previous is not None else None
                self._condition.notify_all()

    def market_build_allowed(self) -> bool:
        with self._condition:
            return self._phase not in MARKET_BUILD_BLOCKERS

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {
                "phase": self._phase or "idle",
                "market_build_allowed": self._phase not in MARKET_BUILD_BLOCKERS,
                "recent_phases": list(self._history),
                "memory": memory_snapshot(),
            }

    def reset(self) -> None:
        with self._condition:
            self._phase = None
            self._owner = None
            self._history.clear()
            self._condition.notify_all()


lifecycle_coordinator = LifecycleCoordinator()
