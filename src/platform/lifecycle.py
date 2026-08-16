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
    "cache_persistence", "historical_import", "historical_cache", "asset_market_build",
    "historical_market_resolution", "live_visual_capture",
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
        self._startup_epoch = 0
        self._startup_state = "complete"
        self._startup_reason = "Startup coordination has not begun."
        self._startup_started_at: str | None = None
        self._startup_completed_at: str | None = None
        self._market_critical = 0
        self._market_critical_reason: str | None = None
        self._visual_deferrals = 0
        self._visual_overlap_count = 0

    def begin_startup(self, reason: str) -> int:
        """Open a process startup fence before canonical work begins."""
        with self._condition:
            self._startup_epoch += 1
            self._startup_state = "running"
            self._startup_reason = reason
            self._startup_started_at = _utcnow()
            self._startup_completed_at = None
            self._condition.notify_all()
            return self._startup_epoch

    def update_startup(self, epoch: int, reason: str) -> None:
        """Update bounded public-safe startup progress for the active epoch."""
        with self._condition:
            if epoch == self._startup_epoch and self._startup_state == "running":
                self._startup_reason = reason
                self._condition.notify_all()

    def complete_startup(self, epoch: int, reason: str) -> bool:
        """Close the active startup fence exactly once."""
        with self._condition:
            if epoch != self._startup_epoch or self._startup_state != "running":
                return False
            self._startup_state = "complete"
            self._startup_reason = reason
            self._startup_completed_at = _utcnow()
            self._condition.notify_all()
            return True

    def fail_startup(self, epoch: int, reason: str) -> bool:
        """Fail closed when canonical startup cannot reach a terminal state."""
        with self._condition:
            if epoch != self._startup_epoch or self._startup_state != "running":
                return False
            self._startup_state = "failed"
            self._startup_reason = reason
            self._startup_completed_at = _utcnow()
            self._condition.notify_all()
            return True

    def startup_complete(self) -> bool:
        with self._condition:
            return self._startup_state == "complete"

    def reserve_market_critical(self, reason: str) -> None:
        """Prioritize a queued first/replacement Market generation over browsers."""
        with self._condition:
            self._market_critical += 1
            self._market_critical_reason = reason
            self._condition.notify_all()

    def release_market_critical(self) -> None:
        with self._condition:
            self._market_critical = max(0, self._market_critical - 1)
            if self._market_critical == 0:
                self._market_critical_reason = None
            self._condition.notify_all()

    def visual_capture_allowed(self) -> bool:
        with self._condition:
            return self._market_critical == 0 and self._phase not in {
                "asset_market_build", "historical_market_resolution",
            }

    def defer_visual_capture(self) -> None:
        with self._condition:
            self._visual_deferrals += 1

    def wait_for_visual_capture(self, timeout: float = 0.25) -> bool:
        with self._condition:
            if self._market_critical or self._phase in {
                "asset_market_build", "historical_market_resolution",
            }:
                self._condition.wait(timeout)
            return self._market_critical == 0 and self._phase not in {
                "asset_market_build", "historical_market_resolution",
            }

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
            return (
                self._startup_state == "complete"
                and self._phase not in MARKET_BUILD_BLOCKERS
            )

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {
                "phase": self._phase or "idle",
                "market_build_allowed": (
                    self._startup_state == "complete"
                    and self._phase not in MARKET_BUILD_BLOCKERS
                ),
                "startup_fence": {
                    "epoch": self._startup_epoch,
                    "state": self._startup_state,
                    "reason": self._startup_reason,
                    "started_at": self._startup_started_at,
                    "completed_at": self._startup_completed_at,
                },
                "heavy_work": {
                    "state": (
                        "MARKET_CRITICAL" if self._market_critical
                        else "VISUAL_CAPTURE" if self._phase == "live_visual_capture"
                        else "HISTORICAL_HEAVY" if self._phase == "historical_import"
                        else "HISTORICAL_MARKET" if self._phase == "historical_market_resolution"
                        else "PROJECTION_HEAVY" if self._phase == "valuation_intelligence"
                        else "IDLE" if self._phase is None else self._phase.upper()
                    ),
                    "market_critical": bool(self._market_critical),
                    "market_critical_reason": self._market_critical_reason,
                    "visual_deferrals": self._visual_deferrals,
                    "visual_overlap_count": self._visual_overlap_count,
                },
                "recent_phases": list(self._history),
                "memory": memory_snapshot(),
            }

    def reset(self) -> None:
        with self._condition:
            self._phase = None
            self._owner = None
            self._history.clear()
            self._startup_epoch = 0
            self._startup_state = "complete"
            self._startup_reason = "Startup coordination has not begun."
            self._startup_started_at = None
            self._startup_completed_at = None
            self._market_critical = 0
            self._market_critical_reason = None
            self._visual_deferrals = 0
            self._visual_overlap_count = 0
            self._condition.notify_all()


lifecycle_coordinator = LifecycleCoordinator()
