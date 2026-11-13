"""Reproducible Trade execution/deferral/recovery proof in an enforced 2 GiB cgroup.

Preparation runs in a separate container. Anonymous/file ballast is identified
as harness memory, never subtracted to claim production capacity. No network or
production account data is used. Run via the Product validation workflow.
"""

import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    FIXTURE = args.fixture
    OUTPUT = args.output
    # Isolate all stores before importing any application module.
    os.environ.setdefault("DTOS_CACHE_FILE", "/tmp/trade-proof-cache.json")
    os.environ.setdefault(
        "DTOS_PROJECTION_DB_FILE", "/tmp/trade-proof-projections.sqlite3"
    )
    if args.prepare:
        import json
        from tests.trade_performance_fixture import prepare_fixture

        prepare_fixture(FIXTURE)
        path = FIXTURE / "data.json"
        data = json.loads(path.read_text())
        for i in range(len(data["players"]), 12229):
            pid = f"unowned-{i}"
            data["players"][pid] = dict(
                id=pid,
                full_name=f"Disposable identity {i}",
                position="WR",
                age=25,
                team="BUF",
                metadata={
                    f"field{j}": "fixture-source-shape-value-012345" for j in range(25)
                },
            )
            data.setdefault("normalized_players", {})[pid] = dict(
                player_id=pid,
                name=f"Disposable identity {i}",
                position="WR",
                nfl_team="BUF",
                availability="active",
            )
        path.write_text(json.dumps(data, sort_keys=True))
        print(
            json.dumps(
                dict(
                    phase="fixture preparation before application observation",
                    identities=len(data["players"]),
                    json_bytes=path.stat().st_size,
                )
            )
        )
        raise SystemExit(0)
    if OUTPUT is None:
        parser.error("--output is required for execution")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    TREE = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    working_tree_clean = not subprocess.check_output(
        ["git", "status", "--porcelain"], text=True
    ).strip()
    if os.environ.get("DTOS_EXPECTED_HEAD"):
        assert HEAD == os.environ["DTOS_EXPECTED_HEAD"], "Wrong candidate"
        assert working_tree_clean, "Tracked source differs from the candidate"
    import asyncio
    import hashlib
    import logging
    import json
    import threading
    import time
    import tempfile
    from unittest.mock import patch
    import psutil
    from fastapi.testclient import TestClient
    import dtos_app
    from services import trade_intelligence as trade
    from tests.test_trade_performance import business
    from src.core.projection_intelligence.service import ProjectionService
    from src.core.data_platform import data_platform
    from src.core.data_platform.storage import SnapshotWarehouse
    from src.platform import trade_execution as execution
    from src.platform.lifecycle import lifecycle_coordinator
    from src.platform.memory_reclamation import release_unused_allocator_pages

    root = OUTPUT
    fixture = FIXTURE
    data = json.loads((fixture / "data.json").read_text())
    for row in data["team_strength"]["teams"].values():
        row["weekly"] = {int(k): v for k, v in row["weekly"].items()}
    reader = ProjectionService(fixture / "projections.sqlite3")
    client = TestClient(dtos_app.app)
    client.get("/health/live")
    live_timings = []

    class LiveTiming(logging.Handler):
        def emit(self, record):
            if getattr(record, 'event', None) == 'request_complete' and getattr(record, 'path', None) == '/health/live':
                live_timings.append(record.duration_ms)

    timing_handler = LiveTiming()
    logging.getLogger('dtos.request').addHandler(timing_handler)
    report = {
        "scope": "Actually enforced2GiB disposable source-compatible workloads. File/anonymous ballast is test harness memory, not claimed production headroom. No production Trade invoked.",
        "states": [],
        "operations": [],
        "head": HEAD,
        "tree": TREE,
        "working_tree_clean": working_tree_clean,
    }

    def observe(label):
        s = execution.observe_memory()
        s.update(
            label=label,
            at=time.monotonic(),
            processes=[
                {"pid": p.pid, "ppid": p.ppid(), "rss": p.memory_info().rss}
                for p in [psutil.Process(), *psutil.Process().children(recursive=True)]
            ],
            threads=psutil.Process().num_threads(),
            capacity=execution.assess_memory(s),
        )
        report["states"].append(s)
        return s

    samples = []
    stop = threading.Event()

    def sample_loop():
        while not stop.wait(0.025):
            m = execution.observe_memory()
            samples.append(
                {
                    "at": time.monotonic(),
                    "current": m["cgroup_current_bytes"],
                    "anon": m.get("file_accounting", {}).get("anon"),
                    "file": m.get("file_accounting", {}).get("file"),
                }
            )

    thread = threading.Thread(target=sample_loop, daemon=True)
    thread.start()
    proposal = dict(active_roster_id=1, workflow="recommended", strategy="REBUILD")

    def digest(result):
        return hashlib.sha256(
            json.dumps(business(result), sort_keys=True, default=str).encode()
        ).hexdigest()

    async def run_search(label):
        stop_health = asyncio.Event()

        async def heartbeat():
            while not stop_health.is_set():
                await health(label + "_during_work")
                try:
                    await asyncio.wait_for(stop_health.wait(), timeout=0.5)
                except TimeoutError:
                    pass

        heartbeat_task = asyncio.create_task(heartbeat())
        started = time.monotonic()
        idx = len(samples)

        def work():
            result = trade.generate_trade_workflow(data, proposal)
            encoded = json.dumps(result, default=str)
            return result, encoded

        try:
            result, encoded = await execution.run_trade_operation(work)
        finally:
            stop_health.set()
            await heartbeat_task
        r = {
            "label": label,
            "seconds": time.monotonic() - started,
            "full_evaluations": result["search_evidence"]["full_evaluations"],
            "qualified": result["count"],
            "state": result["result_state"],
            "business_digest": digest(result),
            "response_bytes": len(encoded),
            "peak_raw_current": max((x["current"] for x in samples[idx:]), default=0),
        }
        assert r["full_evaluations"] == 180
        report["operations"].append(r)
        print(json.dumps(r), flush=True)
        return r["business_digest"]

    def allocate_to_raw_headroom(mib):
        current = execution.observe_memory()["cgroup_current_bytes"]
        count = max(0, 2147483648 - current - mib * execution.MIB)
        # Separate harness-owned buffers can be dropped without copying a
        # large bytearray while the container is already under pressure.
        padding = []
        while count:
            chunk = bytearray(min(count, 8 * execution.MIB))
            for offset in range(0, len(chunk), 4096):
                chunk[offset] = 1
            padding.append(chunk)
            count -= len(chunk)
        return padding

    async def health(label):
        observed = len(live_timings)
        started = time.monotonic()
        r = await asyncio.to_thread(client.get, "/health/live")
        elapsed = (time.monotonic() - started) * 1000
        assert len(live_timings) == observed + 1, 'Missing server timing evidence'
        server_ms = live_timings[-1]
        assert r.status_code == 200 and server_ms < 500
        report.setdefault("liveness", []).append(
            {"label": label, "milliseconds": server_ms, "server_duration_ms": server_ms,
             "client_elapsed_ms": elapsed, "measurement": "ASGI acceptance through response completion; client thread/portal waiting is separate"}
        )

    async def scenarios():
        assert execution.observe_memory()["cgroup_limit_bytes"] == 2147483648
        observe("prepared_and_server_imported")
        from tests.test_trade_resource_admission import TradeResourceHTTPTests

        control = TradeResourceHTTPTests(
            methodName="test_one_qb_supported_legal_pre_post_and_unchanged_source"
        )
        try:
            control.setUp()
            control.test_one_qb_supported_legal_pre_post_and_unchanged_source()
            report["one_qb_http_evaluation"] = {
                "passed": True,
                "required_positions": ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"],
                "source": "disposable league-specific projection publication; no K/DEF Market quotes required",
            }
        finally:
            control.doCleanups()
        reference = await run_search("healthy_real_180_candidate_search")
        release_unused_allocator_pages()
        observe("healthy_after_allocator_trim")
        # Unsafe anonymous pressure must not enter the supplied operation at all.
        ballast = allocate_to_raw_headroom(192)
        observe("unsafe_anonymous_pressure")
        called = []
        try:
            await execution.run_trade_operation(lambda: called.append(1))
            raise AssertionError("Unsafe work admitted")
        except execution.TradeSearchDeferred:
            pass
        assert not called and lifecycle_coordinator.trade_search_available()
        await health("unsafe_pressure")
        observe("unsafe_deferred_no_worker_started")
        del ballast
        release_unused_allocator_pages()
        observe("pressure_relieved")
        assert await run_search("real_search_after_pressure_relief") == reference
        # Check true cancellation after a bilateral evaluation has actually begun.
        count = 0
        original = trade.evaluate_trade_request
        entered = threading.Event()

        def evaluate(*args, **kwargs):
            nonlocal count
            count += 1
            entered.set()
            return original(*args, **kwargs)

        with patch.object(trade, "evaluate_trade_request", side_effect=evaluate):
            task = asyncio.create_task(
                execution.run_trade_operation(
                    lambda: trade.generate_trade_workflow(data, proposal)
                )
            )
            while not entered.is_set():
                await asyncio.sleep(0.005)
            began = time.monotonic()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Cancelled work reported completion")
            finished = count
            await asyncio.sleep(0.15)
            assert count == finished and lifecycle_coordinator.trade_search_available()
            report["actual_cancel"] = {
                "evaluations_started": finished,
                "drained_ms": (time.monotonic() - began) * 1000,
            }
        observe("real_cancel_drained")
        with patch.object(execution, "TRADE_TIMEOUT_SECONDS", 0.3):
            try:
                await execution.run_trade_operation(
                    lambda: trade.generate_trade_workflow(data, proposal)
                )
            except execution.TradeSearchTimedOut:
                pass
            else:
                raise AssertionError("Timeout did not execute")
        assert lifecycle_coordinator.trade_search_available()
        observe("real_timeout_drained")

        def fail():
            raise RuntimeError("Synthetic failure")

        try:
            await execution.run_trade_operation(fail)
        except RuntimeError:
            pass
        assert lifecycle_coordinator.trade_search_available()
        observe("failure_released")
        # Conditional file-cache allowance: dirty/writeback must be zero first.
        release_unused_allocator_pages()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clean-cache.bin"
            chunk = b"z" * 1024**2
            with path.open("wb") as f:
                for _ in range(768):
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
            del chunk
            await asyncio.sleep(0.25)
            ballast = allocate_to_raw_headroom(64)
            initial = observe("clean_file_cache_fixture_initial")
            required = execution.WORKING_BYTES + execution.SAFETY_BYTES
            # Kernel reclamation and prior real operations change the amount
            # of file credit. Establish this normal-execution fixture from
            # measured admission, rather than assuming 768MiB stays resident.
            # This is one bounded pre-work calibration, not an operation retry.
            target = required + 32 * execution.MIB
            deficit = max(0, target - initial["capacity"]["admission_headroom_bytes"])
            # Use full buffers first; the last allocated buffer may be short.
            # One extra quantum covers the measured charge/uncharge overhead.
            chunks = ((deficit + 8 * execution.MIB - 1) // (8 * execution.MIB)
                      + bool(deficit))
            assert chunks <= 8 and chunks <= len(ballast), initial["capacity"]
            released = sum(len(ballast.pop(0)) for _ in range(chunks))
            assert deficit <= released <= 64 * execution.MIB
            # Returning Python objects alone may leave their pages in libc.
            # Reuse the existing cleanup boundary and then measure actual
            # container capacity; never credit the requested release itself.
            unused_pages_released = release_unused_allocator_pages()
            before = observe("clean_file_cache_pressure")
            report["file_cache_fixture_calibration"] = {
                "initial_capacity": initial["capacity"],
                "required_bytes": required,
                "fixture_margin_bytes": 32 * execution.MIB,
                "released_harness_bytes": released,
                "maximum_release_bytes": 64 * execution.MIB,
                "buffer_quantum_bytes": 8 * execution.MIB,
                "unused_pages_released": unused_pages_released,
                "admitted_capacity": before["capacity"],
                "operation_retries": 0,
            }
            assert before["capacity"]["admitted"], before["capacity"]
            assert before["capacity"]["admission_headroom_bytes"] >= target
            assert before["capacity"]["conditional_file_credit_bytes"] > 0
            assert before["capacity"]["raw_headroom_bytes"] < required
            index = len(samples)

            def work():
                # Separate model-demand ballast exercises kernel reclaim within the measured
                # 256MiB work allowance; this is not represented as actual engine allocation.
                model_ballast = bytearray(140 * execution.MIB)
                for i in range(0, len(model_ballast), 4096):
                    model_ballast[i] = 1
                result = trade.generate_trade_workflow(data, proposal)
                return digest(result), result["search_evidence"]["full_evaluations"]

            (value, evaluations) = await execution.run_trade_operation(work)
            assert value == reference and evaluations == 180
            await health("file_cache_pressure")
            observe("file_cache_search_complete")
            during = samples[index:]
            min_file = min(x["file"] for x in during)
            assert before["file_accounting"]["file"] > min_file
            report["file_cache_recovery"] = {
                "model_harness_ballast_bytes": 140 * execution.MIB,
                "other_harness_ballast_bytes": sum(map(len, ballast)),
                "file_before": before["file_accounting"]["file"],
                "minimum_file_during": min_file,
                "raw_peak": max(x["current"] for x in during),
                "completed_evaluations": evaluations,
                "content_still_valid": None,
            }
            with path.open("rb") as f:
                assert f.read(16) == b"z" * 16
            report["file_cache_recovery"]["content_still_valid"] = True
            del ballast
            release_unused_allocator_pages()
        assert not path.exists(), "Harness scratch file survived cleanup"
        assert lifecycle_coordinator.trade_search_available()
        report["cleanup"] = {
            "harness_scratch_exists_after": path.exists(),
            "trade_lease_available": lifecycle_coordinator.trade_search_available(),
            "trade_model": "in-process thread; no dedicated Trade subprocess or scratch database",
        }
        observe("all_ballast_released")
        assert not any(
            execution.observe_memory()["cgroup_memory_events"].get(k)
            for k in ["oom", "oom_kill"]
        )
        report["kernel_peak"] = int(Path("/sys/fs/cgroup/memory.peak").read_text())
        report["samples"] = samples
        report["complete"] = True
        report["passed"] = True

    try:
        with (
            patch(
                "services.trade_intelligence._trade_projection_service",
                return_value=reader,
            ),
            patch.object(data_platform, "warehouse", SnapshotWarehouse()),
        ):
            asyncio.run(scenarios())
    finally:
        logging.getLogger('dtos.request').removeHandler(timing_handler)
        stop.set()
        thread.join()
        root.joinpath("result.json").write_text(
            json.dumps(report, indent=2, default=str)
        )
        print(
            json.dumps(
                {
                    "complete": report.get("complete", False),
                    "operations": report["operations"],
                    "last_phase": report["states"][-1]["label"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
