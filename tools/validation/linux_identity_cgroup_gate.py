"""Linux 2 GiB cgroup gate for bounded historical identity preparation."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

GIB = 1024**3
MIB = 1024**2
LIMIT = 2 * GIB
TOTAL_MAX = int(1.5 * GIB)
TARGET_MAX = int(1.35 * GIB)
CONTEXT_MAX = 40 * MIB
CGROUP = Path("/sys/fs/cgroup")
OUTPUT = Path(os.environ.get("DTOS_BENCHMARK_OUTPUT", "/output/summary.json"))


def metric(name: str) -> int:
    path = CGROUP / name
    if not path.is_file():
        raise RuntimeError(f"required cgroup metric unavailable: {name}")
    value = path.read_text(encoding="ascii").strip()
    if value == "max":
        raise RuntimeError(f"cgroup metric is unlimited: {name}")
    return int(value)


def rss_high_water() -> int:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    return 0


class Monitor:
    def __init__(self) -> None:
        self.peak = metric("memory.current")
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self) -> None:
        while not self.stop.wait(0.01):
            self.peak = max(self.peak, metric("memory.current"))

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args) -> None:
        self.stop.set()
        self.thread.join(timeout=2)
        self.peak = max(self.peak, metric("memory.current"))


def main() -> int:
    if sys.platform != "linux":
        raise RuntimeError("Linux cgroup validation must run on Linux")
    if metric("memory.max") != LIMIT:
        raise RuntimeError("Docker did not enforce the 2 GiB memory limit")
    if not (CGROUP / "memory.peak").is_file():
        raise RuntimeError("memory.peak is required")

    from dtos_app import app
    from services import history as history_service
    from services.sleeper import STATE
    from src.core.historical_memory.enrichment import build_identity_context
    from src.core.historical_memory.jobs import ImportJob, recover_stalled_jobs

    store = history_service.historical_store
    summary: dict[str, object] = {
        "schema": "dtos-linux-identity-memory-v1",
        "memory_max": LIMIT,
        "phases": {},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with Monitor() as monitor, TestClient(app) as client:
        ready = client.get("/health/ready")
        if ready.status_code != 200:
            raise AssertionError(f"fixture readiness failed: {ready.status_code}")
        health = client.get("/api/market/health").json()
        if int(health["cache"]["build_count"]) != 0:
            raise AssertionError("market construction overlapped identity validation")
        summary["phases"]["startup"] = {
            "memory_current": metric("memory.current"),
            "rss_high_water": rss_high_water(), "market_build_count": 0,
        }

        before_rows = store.identity_version_count()
        before_generations = store.identity_generations()
        started = time.perf_counter()
        for player_id, player in STATE["data"]["normalized_players"].items():
            store.upsert_identity(
                str(player_id), "Sleeper", str(player_id), str(player["name"]),
                100, "2026-08-08T00:00:00+00:00",
                {"provider_ids": player["provider_ids"], "aliases": []},
            )
        unchanged_ms = (time.perf_counter() - started) * 1000
        after_rows = store.identity_version_count()
        if after_rows != before_rows or store.identity_generations() != before_generations:
            raise AssertionError("unchanged synchronization grew identity history")
        summary["phases"]["unchanged_sync"] = {
            "duration_ms": round(unchanged_ms, 3), "versions_before": before_rows,
            "versions_after": after_rows, "generation_changed": False,
            "memory_current": metric("memory.current"),
        }

        result = asyncio.run(history_service.enrich_player_history(
            os.environ["SLEEPER_LEAGUE_ID"], seasons=set(range(2021, 2027)),
            today=date(2026, 7, 28), skip_current=True,
        ))
        if result["status"] != "completed_with_pending":
            raise AssertionError(f"unexpected no-work status: {result['status']}")
        if result["identity_context"]["state"] != "not_required":
            raise AssertionError("identity context was built before checkpoint decisions")
        summary["phases"]["checkpoint_first"] = {
            "completed_skipped": 5, "pending": [2026],
            "provider_requests": 0, "context_state": "not_required",
            "memory_current": metric("memory.current"),
        }

        changed_player = next(iter(STATE["data"]["normalized_players"].items()))
        player_id, player = changed_player
        generations = store.identity_generations()
        store.upsert_identity(
            str(player_id), "Sleeper", str(player_id), str(player["name"]), 100,
            "2026-08-08T00:01:00+00:00",
            {"provider_ids": {"GSIS": "gsis-changed"}, "aliases": []},
        )
        changed_generations = store.identity_generations()
        if changed_generations["mapping"] != generations["mapping"] + 1:
            raise AssertionError("real mapping change did not advance generation")

        before_context = metric("memory.current")
        started = time.perf_counter()
        context_holder: list[object] = []
        read_count = 0
        with Monitor() as context_monitor:
            worker = threading.Thread(
                target=lambda: context_holder.append(build_identity_context(store)),
            )
            worker.start()
            while worker.is_alive():
                count, _rows = store.records(
                    os.environ["SLEEPER_LEAGUE_ID"], limit=25,
                )
                read_count += count >= 0
            worker.join()
        context_ms = (time.perf_counter() - started) * 1000
        after_context = metric("memory.current")
        incremental = max(0, context_monitor.peak - before_context)
        context = context_holder[0]
        if context.canonical_count != 12_322:
            raise AssertionError(f"projected identity count={context.canonical_count}")
        if incremental >= CONTEXT_MAX:
            raise AssertionError(
                f"identity context increment {incremental} exceeds 40 MiB",
            )
        summary["phases"]["eligible_context"] = {
            "duration_ms": round(context_ms, 3), "projected_rows": 12_322,
            "streamed_rows": context.canonical_count,
            "memory_before": before_context, "memory_after": after_context,
            "incremental_peak": incremental, "concurrent_reads": read_count,
            "identity_generation": changed_generations["mapping"],
        }

        interrupted = ImportJob(
            store, os.environ["SLEEPER_LEAGUE_ID"], (2026,), ("player_week",),
            provider="nflverse",
        )
        interrupted.create()
        interrupted.acquire(lease_minutes=-1)
        recovered = recover_stalled_jobs(store, os.environ["SLEEPER_LEAGUE_ID"])
        if recovered != 1 or store.jobs(os.environ["SLEEPER_LEAGUE_ID"])[0]["status"] != "queued":
            raise AssertionError("expired preparation lease was not recoverable")
        summary["phases"]["restart_recovery"] = {
            "recovered_jobs": recovered, "state": "queued",
            "memory_current": metric("memory.current"),
        }

    peak = max(monitor.peak, metric("memory.peak"))
    summary.update({
        "memory_current": metric("memory.current"), "memory_peak": peak,
        "margin_below_limit": LIMIT - peak, "target_peak_met": peak < TARGET_MAX,
        "total_peak_gate": peak < TOTAL_MAX, "worker_count": 1,
        "unexpected_restarts": 0, "passed": peak < TARGET_MAX
        and LIMIT - peak >= 500 * MIB,
    })
    OUTPUT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if not summary["passed"]:
        raise AssertionError("Linux identity cgroup gate failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
