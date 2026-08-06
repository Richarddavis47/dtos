"""Production-scale historical import/read concurrency memory gate."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

import psutil

from config import CACHE_FILE, HISTORY_DATABASE_FILE, LEAGUE_ID
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.historical_memory.store import HistoricalStore

TARGET_RSS_BYTES = 400 * 1024 * 1024
FAIL_RSS_BYTES = 450 * 1024 * 1024
SCENARIOS = (
    "import_alone",
    "coverage_alone",
    "import_plus_coverage",
    "import_plus_player",
    "import_plus_assets",
    "full_post_import_reads",
)


class PeakMonitor:
    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())
        self.peak = self.process.memory_info().rss
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(0.01):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __enter__(self) -> PeakMonitor:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        self.peak = max(self.peak, self.process.memory_info().rss)


def _load_data(cache_file: Path) -> dict[str, Any]:
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    return payload.get("data") or payload


def _append_bounded_import(store: HistoricalStore, league_id: str) -> None:
    observed = "2030-09-01T00:00:00+00:00"
    for batch_number in range(40):
        records = []
        for index in range(50):
            sequence = batch_number * 50 + index
            records.append({
                "record_key": f"memory-gate:{sequence}",
                "entity_type": "player_week", "league_id": league_id,
                "season": 2030, "week": sequence % 18 + 1,
                "franchise_id": f"{league_id}:franchise:{sequence % 10 + 1}",
                "player_id": f"memory-player-{sequence % 200}",
                "source_record_id": str(sequence), "observed_at": observed,
                "retrieved_at": observed, "provider": "fixture",
                "availability": "observed", "confidence": 100,
                "calculation_method": "memory_gate",
                "schema_version": "1.0",
                "payload": {
                    "fantasy_points": float(sequence % 30),
                    "starter": sequence % 2 == 0,
                    "source_league_id": league_id,
                },
            })
        store.append_many(records)
        del records
        time.sleep(0)


def _concurrent(
    writer: Callable[[], None], reader: Callable[[], Any],
) -> None:
    failure: list[BaseException] = []

    def run_writer() -> None:
        try:
            writer()
        except BaseException as exc:  # pragma: no cover - surfaced below
            failure.append(exc)

    thread = threading.Thread(target=run_writer, name="bounded-history-import")
    thread.start()
    while thread.is_alive():
        reader()
        time.sleep(0.01)
    thread.join()
    if failure:
        raise failure[0]


def run_scenario(
    scenario: str, database: Path, cache_file: Path, league_id: str,
    player_id: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dtos-memory-gate-") as directory:
        working_database = Path(directory) / "history.sqlite3"
        shutil.copy2(database, working_database)
        store = HistoricalStore(working_database)
        data = _load_data(cache_file)
        cache = HistoricalReadModelCache()
        graph = cache.get(store, league_id, data)
        started = time.perf_counter()
        with PeakMonitor() as monitor:
            if scenario == "import_alone":
                _append_bounded_import(store, league_id)
            elif scenario == "coverage_alone":
                for _ in range(10):
                    graph.coverage()
            elif scenario == "import_plus_coverage":
                _concurrent(
                    lambda: _append_bounded_import(store, league_id),
                    lambda: cache.get(store, league_id, data).coverage(),
                )
            elif scenario == "import_plus_player":
                _concurrent(
                    lambda: _append_bounded_import(store, league_id),
                    lambda: cache.get(store, league_id, data).player_dossier(player_id),
                )
            elif scenario == "import_plus_assets":
                _concurrent(
                    lambda: _append_bounded_import(store, league_id),
                    lambda: cache.get(store, league_id, data).asset_directory_page(limit=100),
                )
            elif scenario == "full_post_import_reads":
                _append_bounded_import(store, league_id)
                current = cache.get(store, league_id, data)
                current.coverage()
                current.player_dossier(player_id)
                current.asset_directory_page(limit=100)
                current.search(player_id, limit=10)
            else:  # pragma: no cover - argparse constrains values
                raise ValueError(f"Unknown scenario: {scenario}")
        elapsed = round(time.perf_counter() - started, 3)
        return {
            "scenario": scenario, "elapsed_seconds": elapsed,
            "peak_rss_bytes": monitor.peak,
            "peak_rss_mib": round(monitor.peak / 1024 / 1024, 2),
            "target_under_400_mib": monitor.peak < TARGET_RSS_BYTES,
            "hard_gate_under_450_mib": monitor.peak < FAIL_RSS_BYTES,
            "cache_entries": cache.metadata().get("entry_count"),
            "cache_max_entries": cache.metadata().get("max_entries"),
        }


def benchmark(
    database: Path, cache_file: Path, league_id: str, player_id: str,
) -> dict[str, Any]:
    results = []
    for scenario in SCENARIOS:
        command = [
            os.fspath(Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"),
            "-m", "tools.validation.benchmark_historical_memory_stability",
            "--worker-scenario", scenario, "--database", os.fspath(database),
            "--cache-file", os.fspath(cache_file), "--league", league_id,
            "--player", player_id,
        ]
        completed = subprocess.run(
            command, cwd=Path(__file__).resolve().parents[2], capture_output=True,
            text=True, check=False, timeout=300,
        )
        if completed.returncode:
            raise RuntimeError(
                f"Scenario {scenario} failed ({completed.returncode}): "
                f"{completed.stderr or completed.stdout}"
            )
        results.append(json.loads(completed.stdout))
    peak = max(item["peak_rss_bytes"] for item in results)
    return {
        "database": os.fspath(database), "database_bytes": database.stat().st_size,
        "league_id": league_id, "player_id": player_id, "scenarios": results,
        "peak_rss_bytes": peak, "peak_rss_mib": round(peak / 1024 / 1024, 2),
        "target_under_400_mib": peak < TARGET_RSS_BYTES,
        "hard_gate_under_450_mib": peak < FAIL_RSS_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=HISTORY_DATABASE_FILE)
    parser.add_argument("--cache-file", type=Path, default=CACHE_FILE)
    parser.add_argument("--league", default=LEAGUE_ID)
    parser.add_argument("--player", default="10213")
    parser.add_argument("--worker-scenario", choices=SCENARIOS)
    arguments = parser.parse_args()
    result = (
        run_scenario(
            arguments.worker_scenario, arguments.database, arguments.cache_file,
            arguments.league, arguments.player,
        )
        if arguments.worker_scenario
        else benchmark(
            arguments.database, arguments.cache_file, arguments.league,
            arguments.player,
        )
    )
    print(json.dumps(result, indent=None if arguments.worker_scenario else 2, sort_keys=True))
    return 0 if result["hard_gate_under_450_mib"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
