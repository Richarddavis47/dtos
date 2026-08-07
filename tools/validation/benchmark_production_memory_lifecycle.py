"""Production-scale synchronized-state lifecycle memory and latency gate."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any, Callable

import psutil

from config import LEAGUE_ID
from services import sleeper
from services.history import canonical_history_progress
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory import historical_store
from src.core.provider_network import build_provider_network
from src.core.valuation.automation import audit_market_calibration
from src.core.valuation_intelligence import build_valuation_intelligence
from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot

TARGET_BYTES = 1200 * 1024 * 1024
FAIL_BYTES = 1500 * 1024 * 1024


class MemoryMonitor:
    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())
        self.peak_rss = self.process.memory_info().rss
        self.peak_cgroup = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(0.01):
            snapshot = memory_snapshot()
            self.peak_rss = max(self.peak_rss, int(snapshot["rss_bytes"] or 0))
            self.peak_cgroup = max(
                self.peak_cgroup, int(snapshot["cgroup_current_bytes"] or 0),
            )

    def __enter__(self) -> MemoryMonitor:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._sample_once()

    def _sample_once(self) -> None:
        snapshot = memory_snapshot()
        self.peak_rss = max(self.peak_rss, int(snapshot["rss_bytes"] or 0))
        self.peak_cgroup = max(
            self.peak_cgroup, int(snapshot["cgroup_current_bytes"] or 0),
        )


def measure(operation: Callable[[], Any], count: int = 5) -> dict[str, Any]:
    durations = []
    result = None
    for _ in range(count):
        started = perf_counter()
        result = operation()
        durations.append(round((perf_counter() - started) * 1000, 3))
    return {
        "median_ms": round(median(durations), 3),
        "maximum_ms": max(durations),
        "response_bytes": len(json.dumps(result, default=str, separators=(",", ":"))),
    }


def main() -> int:
    lifecycle_coordinator.reset()
    phases: dict[str, dict[str, int | float | None]] = {}
    process = psutil.Process(os.getpid())

    def phase(name: str, operation: Callable[[], Any]) -> Any:
        before = process.memory_info().rss
        started = perf_counter()
        result = operation()
        after = process.memory_info().rss
        phases[name] = {
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "rss_before_bytes": before, "rss_after_bytes": after,
            "rss_retained_delta_bytes": after - before,
        }
        return result

    with MemoryMonitor() as monitor:
        phase("cache_load", sleeper.load_cache)
        data = sleeper.STATE.get("data") or {}
        if not data:
            raise RuntimeError("Production-scale synchronized cache is unavailable.")
        phase("provider_network", lambda: build_provider_network(data, sleeper.STATE))
        phase(
            "valuation_intelligence",
            lambda: build_valuation_intelligence(data, sleeper.STATE),
        )
        phase(
            "calibration_audit",
            lambda: audit_market_calibration(data, sleeper.STATE, apply=True),
        )
        original_cache_file = sleeper.CACHE_FILE
        with tempfile.TemporaryDirectory(prefix="dtos-lifecycle-") as directory:
            sleeper.CACHE_FILE = Path(directory) / "cache.json"
            try:
                phase("cache_persistence", sleeper.save_cache)
            finally:
                sleeper.CACHE_FILE = original_cache_file
        phase("historical_progress", lambda: canonical_history_progress(LEAGUE_ID))
        phase(
            "historical_coverage",
            lambda: historical_store.compact_identity_coverage(LEAGUE_ID),
        )
        cache = AssetMarketCache()
        market = phase(
            "cold_market",
            lambda: cache.get(data, sleeper.STATE, historical_store, LEAGUE_ID),
        )
        player_id = "10213" if "10213" in (data.get("players") or {}) else next(
            iter(data.get("players") or {}), "",
        )
        performance = {
            "directory": measure(
                lambda active_market=market: active_market.directory(limit=50)
            ),
            "search": measure(
                lambda active_market=market: active_market.search("Bijan", 50)
            ),
            "expansion": measure(
                lambda active_market=market: active_market.detail(
                    f"player:{player_id}", 1,
                )
            ),
            "trending": measure(
                lambda active_market=market: active_market.trending(10)
            ),
            "health": measure(cache.health),
        }
        del market
        sleeper.STATE["last_sync"] = f"{sleeper.STATE.get('last_sync') or ''}:benchmark"
        replacement = phase(
            "generation_replacement",
            lambda: cache.get(data, sleeper.STATE, historical_store, LEAGUE_ID),
        )
        phase("warm_generation_read", lambda: replacement.directory(limit=50))
        monitor._sample_once()

    measured_peak = monitor.peak_cgroup or monitor.peak_rss
    result = {
        "asset_count": len(replacement.assets),
        "platform": os.name,
        "cgroup_available": bool(monitor.peak_cgroup),
        "peak_rss_bytes": monitor.peak_rss,
        "peak_cgroup_bytes": monitor.peak_cgroup or None,
        "measured_peak_bytes": measured_peak,
        "target_under_1_2_gib": measured_peak < TARGET_BYTES,
        "hard_gate_under_1_5_gib": measured_peak < FAIL_BYTES,
        "phases": phases,
        "performance": performance,
        "cache": cache.metrics(),
        "lifecycle": lifecycle_coordinator.snapshot(),
        "provider_synchronization": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["hard_gate_under_1_5_gib"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
