"""Measure Asset Market through the production-equivalent cached application path."""
from __future__ import annotations

import json
import os
from statistics import median
from time import perf_counter
from typing import Any, Callable

import psutil

from config import LEAGUE_ID
from services.sleeper import STATE, load_cache
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory import historical_store


def _measure(operation: Callable[[], Any], count: int = 5) -> dict[str, Any]:
    durations = []
    for _ in range(count):
        started = perf_counter()
        operation()
        durations.append(round((perf_counter() - started) * 1000, 3))
    return {
        "runs_ms": durations,
        "median_ms": round(median(durations), 3),
        "maximum_ms": max(durations),
    }


def main() -> int:
    load_cache()
    data = STATE.get("data") or {}
    if not data:
        raise RuntimeError("Production-scale synchronized cache is unavailable.")
    cache = AssetMarketCache()
    cold_started = perf_counter()
    market = cache.get(data, STATE, historical_store, LEAGUE_ID)
    cold_ms = round((perf_counter() - cold_started) * 1000, 3)
    player_id = "10213" if "10213" in (data.get("players") or {}) else next(
        iter(data.get("players") or {}), ""
    )
    results = {
        "asset_count": len(market.assets),
        "cold_build_ms": cold_ms,
        "directory": _measure(lambda: cache.get(
            data, STATE, historical_store, LEAGUE_ID,
        ).directory(limit=50)),
        "search": _measure(lambda: cache.get(
            data, STATE, historical_store, LEAGUE_ID,
        ).search("QB", 50)),
        "expansion": _measure(lambda: cache.get(
            data, STATE, historical_store, LEAGUE_ID,
        ).detail(f"player:{player_id}", 1)),
        "trending": _measure(lambda: cache.get(
            data, STATE, historical_store, LEAGUE_ID,
        ).trending(10)),
        "cache": cache.metrics(),
        "rss_bytes": psutil.Process(os.getpid()).memory_info().rss,
        "provider_synchronization": False,
    }
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
