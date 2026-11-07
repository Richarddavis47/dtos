"""Enforced-container evidence for completed resident-refresh task ownership.

Pinned public disposable inputs only. No provider acquisition, admission override,
active-context eviction or production cache access. This is not live acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import gc
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import weakref

LIMIT = 2 * 1024**3
MIB = 1024**2
FIXTURES = {
    "oneqb.json": "98d76b8452431ff3e6f961b6bddd9a654f7b6d23129d96cce60e52cbf79cb11b",
    "superflex.json": "49915270f727cd3eb6a3a792b8531a487d7da96a06c031ee0e5a176887f69c81",
    "projections.sqlite3": "43541f6a3c738d0ebeac0794cdfd7c009bd27f450816919315b824b512a7b708",
}


class Publication(dict):
    """A normal JSON-compatible dictionary with an observable weak owner."""


class IntervalGate:
    def __init__(self):
        self.arrivals = asyncio.Queue()
        self.permits = asyncio.Queue()
        self.count = 0

    async def sleep(self, _):
        self.count += 1
        self.arrivals.put_nowait(self.count)
        await self.permits.get()

    async def parked(self, expected):
        assert await asyncio.wait_for(self.arrivals.get(), 10) == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = dict(
        schema="resident-refresh-ownership-v1",
        passed=False,
        cases=[],
        samples=[],
        liveness=[],
    )
    scratch = tempfile.TemporaryDirectory(prefix="resident-refresh-ownership-")
    root = Path(scratch.name)
    try:
        for name, sha in FIXTURES.items():
            assert (
                hashlib.file_digest(
                    (args.fixtures / name).open("rb"), "sha256"
                ).hexdigest()
                == sha
            )
        shutil.copyfile(
            args.fixtures / "projections.sqlite3", root / "projections.sqlite3"
        )
        paths, identities = {}, {}
        fixture_time = datetime.now(timezone.utc).isoformat()
        result['fixture_cache_last_sync'] = fixture_time
        for name in ("oneqb", "superflex"):
            with (args.fixtures / (name + ".json")).open(encoding="utf8") as handle:
                payload = json.load(handle)
            identities[name] = (
                str(payload["data"]["league"]["league_id"]),
                int(payload["data"]["league"]["season"]),
            )
            # Refresh only disposable cache-retrieval time, not native observation
            # clocks or facts. Actual admission uses each full written file size.
            payload["last_sync"] = fixture_time
            for generation in ("first", "next", "foreign"):
                path = root / (name + "-" + generation + ".json")
                league = payload["data"]["league"]
                league["name"] = "Disposable " + name + " " + generation
                league["league_id"] = (
                    "foreign-identity"
                    if generation == "foreign"
                    else identities[name][0]
                )
                with path.open("w", encoding="utf8") as handle:
                    for chunk in json.JSONEncoder(
                        separators=(",", ":"), ensure_ascii=False
                    ).iterencode(payload):
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                paths[name, generation] = path
            del payload
        result["inputs"] = {
            name: dict(source_sha256=sha) for name, sha in FIXTURES.items()
        }
        result["written_files"] = {
            path.name: dict(
                bytes=path.stat().st_size,
                sha256=hashlib.file_digest(path.open("rb"), "sha256").hexdigest(),
            )
            for path in paths.values()
        }
        for key in (
            "CACHE",
            "METADATA_DB",
            "INTELLIGENCE_CHECKPOINT",
            "FOIS_DB",
            "HISTORY_DB",
            "ACCOUNT_DB",
        ):
            os.environ["DTOS_" + key + "_FILE"] = str(root / (key.lower() + ".sqlite3"))
        os.environ.update(
            DTOS_PROJECTION_DB_FILE=str(root / "projections.sqlite3"),
            DTOS_DURABLE_HISTORY_REQUIRED="0",
            DTOS_HISTORY_STORAGE_ROOT=str(root),
            DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root / "seasons"),
            SLEEPER_BASE_URL="http://127.0.0.1:9/v1",
        )
        import dtos_app
        import psutil
        from fastapi.testclient import TestClient
        from services import (
            league_maintenance as maintenance,
            league_preparation as prep,
        )
        from src.core.league_runtime import LeagueRuntime, RuntimeState
        from src.platform.lifecycle import (
            lifecycle_coordinator,
            memory_snapshot,
            HeavyWorkDeferred,
        )
        from src.platform.memory_reclamation import release_unused_allocator_pages

        result.update(
            head=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            tree=subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], text=True
            ).strip(),
            working_tree_clean=not subprocess.check_output(
                ["git", "status", "--porcelain"], text=True
            ).strip(),
        )
        if os.environ.get("DTOS_EXPECTED_HEAD"):
            assert (
                result["head"] == os.environ["DTOS_EXPECTED_HEAD"]
                and result["working_tree_clean"]
            )
        assert memory_snapshot()["cgroup_limit_bytes"] == LIMIT
        assert Path("/sys/fs/cgroup/memory.swap.max").read_text().strip() == "0"
        result.update(cgroup_limit=LIMIT, swap_limit=0, cpus=2, network="none")
        timings = []

        class Timing(logging.Handler):
            def emit(self, record):
                if (
                    getattr(record, "event", None) == "request_complete"
                    and getattr(record, "path", None) == "/health/live"
                ):
                    timings.append(record.duration_ms)

        handler = Timing()
        logging.getLogger("dtos.request").addHandler(handler)
        client = TestClient(dtos_app.app)

        def live(label):
            count = len(timings)
            start = time.monotonic()
            assert (
                client.get("/health/live").status_code == 200
                and len(timings) == count + 1
                and timings[-1] < 500
            )
            result["liveness"].append(
                dict(
                    label=label,
                    server_ms=timings[-1],
                    client_ms=(time.monotonic() - start) * 1000,
                )
            )

        def sample(label):
            stat = dict(
                line.split()
                for line in Path("/sys/fs/cgroup/memory.stat").read_text().splitlines()
            )
            row = dict(
                label=label,
                **memory_snapshot(),
                anon=int(stat["anon"]),
                file=int(stat["file"]),
                inactive_file=int(stat["inactive_file"]),
                kernel_peak=int(Path("/sys/fs/cgroup/memory.peak").read_text()),
                child_pids=[p.pid for p in psutil.Process().children(recursive=True)],
            )
            result["samples"].append(row)
            assert (
                row["cgroup_current_bytes"] < LIMIT
                and not row["cgroup_memory_events"]["oom_kill"]
            )
            return row

        def publish(runtime):
            runtime.apply_data(Publication(runtime.state["data"]))
            service = dtos_app.ProjectionService(
                league_id=runtime.league_id, scoring_profile_id=runtime.scoring_profile
            )
            service.restore_into(runtime.state["data"])
            dtos_app._publish_runtime_context(runtime, service)

        def restore(runtime, path, season):
            with patch.object(prep, "league_cache_file", return_value=path):
                return prep.restore_cached_runtime(
                    runtime, publish, expected_season=season
                )

        def source_digest(runtime):
            data = runtime.state["data"]
            h = hashlib.sha256()
            facts = {
                key: data[key]
                for key in ("season_matchups", "canonical_player_production")
            }
            for chunk in json.JSONEncoder(
                sort_keys=True, separators=(",", ":"), default=str
            ).iterencode(facts):
                h.update(chunk.encode())
            return h.hexdigest()

        def admission(path, fois=False):
            return prep.restoration_admission(
                path.stat().st_size,
                memory_snapshot(),
                fois,
                fois_working_bytes=prep.FOIS_WORKING,
                fois_safety_bytes=prep.FOIS_SAFETY,
                expansion_factor=prep.CACHE_EXPANSION_FACTOR,
                minimum_working_bytes=prep.CACHE_MINIMUM_WORKING,
                cache_safety_bytes=prep.CACHE_SAFETY,
                service_limit_bytes=prep.SERVICE_LIMIT,
            )

        async def settle():
            for _ in range(3):
                await asyncio.sleep(0)

        async def run_case(name, failed=False, reader=False):
            runtime = LeagueRuntime(identities[name][0], status=RuntimeState.WARM)
            assert restore(runtime, paths[name, "first"], identities[name][1])
            old = weakref.ref(runtime.state["data"])
            before_digest = source_digest(runtime)
            gate = IntervalGate()

            async def refresh(selected):
                source = selected.state["data"]
                if failed:
                    raise OSError("Disposable refresh failure")
                return source

            api = SimpleNamespace(
                sleep=gate.sleep,
                create_task=asyncio.create_task,
                shield=asyncio.shield,
                gather=asyncio.gather,
                to_thread=asyncio.to_thread,
                CancelledError=asyncio.CancelledError,
            )
            pressure = []
            cold = None
            owned_reader = None
            with patch.object(maintenance, "asyncio", api):
                maintenance.ensure_periodic_refresh(
                    runtime, refresh, interval_seconds=900
                )
                await gate.parked(1)
                gate.permits.put_nowait(None)
                await gate.parked(2)
                if failed:
                    assert (
                        runtime.state["data"] is old()
                        and runtime.lifecycle["refresh_state"] == "failed"
                    )
                if reader:
                    owned_reader = runtime.brain_context
                    runtime.active_requests = 1
                before = sample(name + " before replacement")
                assert restore(runtime, paths[name, "next"], identities[name][1])
                await settle()
                after = sample(name + " replacement settled")
                assert (old() is not None) is reader
                # Verify only after capturing publication counters.
                assert source_digest(runtime) == before_digest
                current = runtime.state["data"]
                assert (
                    restore(runtime, paths[name, "foreign"], identities[name][1])
                    is False
                )
                assert runtime.state["data"] is current
                del current
                row = dict(
                    name=name,
                    failed_refresh=failed,
                    reader=reader,
                    completed=True,
                    old_released_without_reader=old() is None,
                    source_digest=before_digest,
                    invalid_restore_preserved_current=True,
                    before_bytes=before["cgroup_current_bytes"],
                    after_bytes=after["cgroup_current_bytes"],
                )
                if reader:
                    assert owned_reader._data is old() and runtime.active_requests == 1
                    cold = LeagueRuntime(identities["oneqb"][0])
                    path = paths["oneqb", "first"]
                    required = admission(path)["required_bytes"]
                    target = LIMIT - required + 32 * MIB
                    while memory_snapshot()["cgroup_current_bytes"] < target:
                        assert (
                            memory_snapshot()["cgroup_current_bytes"]
                            < LIMIT - 512 * MIB
                        )
                        chunk = bytearray(8 * MIB)
                        for offset in range(0, len(chunk), 4096):
                            chunk[offset] = 1
                        pressure.append(chunk)
                    del chunk
                    unsafe = sample("legitimate reader under pressure")
                    live("unsafe pressure")
                    try:
                        restore(cold, path, identities["oneqb"][1])
                    except HeavyWorkDeferred:
                        pass
                    else:
                        raise AssertionError(
                            "Unsafe pressure must defer before allocating a cold publication"
                        )
                    assert not cold.state["data"] and runtime.active_requests == 1
                    runtime.active_requests = 0
                    del owned_reader
                    await settle()
                    assert old() is None
                    released = sample("obsolete generation released; current runtime retained")
                    lifecycle_coordinator.reserve_fois_generation()
                    try:
                        protected = admission(path, True)
                        assert protected["would_admit"] is False
                        try:
                            restore(cold, path, identities["oneqb"][1])
                        except HeavyWorkDeferred:
                            pass
                        else:
                            raise AssertionError(
                                "Outstanding FOIS demand must stay protected"
                            )
                    finally:
                        lifecycle_coordinator.release_fois_generation()
                    recovery_plan = admission(path)
                    assert restore(cold, path, identities["oneqb"][1])
                    recovered = sample("cold one-QB completed after real owner release")
                    live("recovered capacity")
                    row.update(
                        pressure_deferred=True,
                        fois_protected=True,
                        recovery_completed=True,
                        required_bytes=required,
                        unsafe_bytes=unsafe["cgroup_current_bytes"],
                        released_bytes=released["cgroup_current_bytes"],
                        recovery_plan=recovery_plan,
                        recovery_bytes=recovered["cgroup_current_bytes"],
                    )
                    pressure.clear()
                    release_unused_allocator_pages()
                for cycle in range(3):
                    previous = weakref.ref(runtime.state["data"])
                    gate.permits.put_nowait(None)
                    await gate.parked(cycle + 3)
                    assert restore(
                        runtime,
                        paths[name, "first" if cycle % 2 == 0 else "next"],
                        identities[name][1],
                    )
                    await settle()
                    assert previous() is None
                # Actual pending off-loop writer, not a deferred completion.
                started, release, finished = (
                    threading.Event(),
                    threading.Event(),
                    threading.Event(),
                )

                async def blocked(selected):
                    def work():
                        started.set()
                        release.wait(5)
                        finished.set()

                    await asyncio.to_thread(work)
                    return selected.state["data"]

                await runtime.close()
                runtime.status = RuntimeState.WARM
                runtime.apply_data(
                    Publication(
                        league={
                            "league_id": runtime.league_id,
                            "season": str(identities[name][1]),
                        }
                    )
                )
                maintenance.ensure_periodic_refresh(
                    runtime, blocked, interval_seconds=900
                )
                await gate.parked(6)
                gate.permits.put_nowait(None)
                assert await asyncio.to_thread(started.wait, 5)
                task = next(iter(runtime.background_tasks))
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await settle()
                assert not task.done() and not finished.is_set()
                release.set()
                await asyncio.gather(task, return_exceptions=True)
                assert finished.is_set()
                row.update(repeated_switches=3, cancellation_writer_drained=True)
                await runtime.close()
            if cold is not None:
                await cold.close()
            await settle()
            assert not runtime.background_tasks
            result["cases"].append(row)

        async def run():
            gc.collect()
            release_unused_allocator_pages()
            sample("initial")
            live("initial")
            await run_case("oneqb")
            await run_case("oneqb", failed=True)
            await run_case("superflex", reader=True)
            assert not dtos_app.canonical_history_store._current
            assert lifecycle_coordinator.snapshot()["phase"] == "idle"
            assert not psutil.Process().children(recursive=True)
            sample("completed")
            live("completed")

        asyncio.run(run())
        result.update(
            passed=True,
            children_after=[],
            source_values_preserved=True,
            scope="Three source-compatible disposable ownership cases; current/active contexts preserved. Not liveGranite or independent liveSleeper parity.",
            limitations=[
                "Fixture clocks normalized only on copies; no source facts changed.",
                "Kernel lifetime peak includes fixture preparation,verification and bounded pressure. Stage samples distinguish publication and pressure; no decoder-only comparison claimed.",
                "Three repeated publications per case are finite cleanup evidence,not long-term leak freedom.",
            ],
        )
    finally:
        scratch.cleanup()
        result["scratch_removed"] = not root.exists()
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    assert result["passed"] and result["scratch_removed"]
    print(
        json.dumps(
            {"passed": True, "cases": len(result["cases"]), "scratch_removed": True}
        )
    )


if __name__ == "__main__":
    main()
