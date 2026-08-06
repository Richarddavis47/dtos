"""Benchmark the Historical Asset Graph cold build and bounded warm reads."""
from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

from config import CACHE_FILE, HISTORY_DATABASE_FILE, LEAGUE_ID
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.historical_memory.store import HistoricalStore


def _timed(operation: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = operation()
    return result, round(time.perf_counter() - started, 6)


def benchmark(
    database: Path, cache_file: Path, league_id: str, player_id: str,
) -> dict[str, Any]:
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    data = payload.get("data") or payload
    store = HistoricalStore(database)
    cache = HistoricalReadModelCache()
    tracemalloc.start()
    graph, cold_seconds = _timed(lambda: cache.get(store, league_id, data))
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    (asset_count, first_asset), asset_cold = _timed(
        lambda: graph.asset_directory_page(limit=1),
    )
    (_, repeated_asset), asset_warm = _timed(
        lambda: cache.get(store, league_id, data).asset_directory_page(limit=1),
    )
    player, player_cold = _timed(lambda: graph.player_dossier(player_id))
    repeated_player, player_warm = _timed(
        lambda: cache.get(store, league_id, data).player_dossier(player_id),
    )
    coverage, coverage_seconds = _timed(lambda: graph.coverage())
    return {
        "league_id": league_id,
        "player_id": player_id,
        "cold_build_seconds": cold_seconds,
        "warm_assets_limit_1_seconds": asset_warm,
        "first_assets_limit_1_seconds_after_build": asset_cold,
        "warm_player_seconds": player_warm,
        "first_player_seconds_after_build": player_cold,
        "coverage_seconds": coverage_seconds,
        "asset_count": asset_count,
        "event_count": coverage["asset_event_count"],
        "player_season_summary_count": len(player["season_summaries"]),
        "peak_build_bytes": peak_bytes,
        "outputs_identical": {
            "assets": first_asset == repeated_asset,
            "player": player == repeated_player,
        },
        "read_model": cache.metadata(store.dataset_version(league_id)),
        "targets": {
            "assets_limit_1_under_1_second": asset_warm < 1,
            "player_under_2_seconds": player_warm < 2,
            "coverage_under_30_seconds": coverage_seconds < 30,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=HISTORY_DATABASE_FILE)
    parser.add_argument("--cache-file", type=Path, default=CACHE_FILE)
    parser.add_argument("--league", default=LEAGUE_ID)
    parser.add_argument("--player", default="10213")
    arguments = parser.parse_args()
    result = benchmark(
        arguments.database, arguments.cache_file, arguments.league,
        arguments.player,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if not all(result["targets"].values()) or not all(result["outputs_identical"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
