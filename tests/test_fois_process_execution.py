"""Spawn-safe FOIS compute isolation and semantic-equivalence regressions."""
from __future__ import annotations

import asyncio
import copy
import os
import tempfile
import time
import unittest
from unittest import mock
from dataclasses import asdict
from functools import partial
from pathlib import Path
import json

import psutil

from src.core.fois.process_execution import (
    compact_fois_input, generate_fois_isolated, shutdown_fois_executor,
    shutdown_fois_executor_sync, warm_fois_executor, warm_fois_executor_sync,
)
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


def fixture() -> dict:
    return {
        "league": {"league_id": "fois-process-fixture", "season": "2026"},
        "league_settings": {"playoff_teams": 6},
        "teams": [
            {"roster_id": 1, "owner_id": "owner-1", "owner": "One", "players": [
                {"id": "101", "historical_evidence": {"weekly_record_count": 4}},
            ]},
            {"roster_id": 2, "owner_id": "owner-2", "owner": "Two", "players": [
                {"id": "202", "historical_evidence": {"weekly_record_count": 2}},
            ]},
        ],
        "fois_history": {
            "1": {"seasons": [], "trades": [], "drafts": [], "waivers": []},
            "2": {"seasons": [], "trades": [], "drafts": [], "waivers": []},
        },
        "valuation_intelligence": {
            "generated_at": "2026-08-28T00:00:00+00:00",
            "semantic_generation": "semantic-fixture",
            "availability": "available",
            "assets": {
                "player:101": {"scores": {"confidence": 80, "agreement": 70, "coverage": 60}},
                "player:202": {"scores": {"confidence": 65, "agreement": 55, "coverage": 45}},
                "player:unowned": {"scores": {"confidence": 99, "agreement": 99, "coverage": 99}},
            },
            "timeline": {
                "player:101": [{"value": 1}],
                "player:202": [{"value": 2}],
                "player:unowned": [{"value": 3}],
            },
            "safety": {"unsafe_adjustments": 0},
        },
    }


def semantic(score: object) -> dict:
    payload = asdict(score)
    payload.pop("generated_at", None)
    return payload


def cache_input(root: Path, data: dict, name: str = "cache.json") -> Path:
    path = root / name
    path.write_text(json.dumps({"data": data}), encoding="utf-8")
    return path


class FOISProcessExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_progress_io_cannot_block_request_event_loop(self) -> None:
        class SlowProgress:
            @staticmethod
            def record(*_args, **_kwargs) -> None:
                time.sleep(.15)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = FOISRepository(root / "fois.sqlite3")
            ticks = 0
            active = True

            async def heartbeat() -> None:
                nonlocal ticks
                while active:
                    await asyncio.sleep(.01)
                    ticks += 1

            task = asyncio.create_task(heartbeat())
            try:
                with mock.patch(
                    "src.core.fois.process_execution.progress_from_environment",
                    return_value=SlowProgress(),
                ), self.assertRaisesRegex(RuntimeError, "cache input is unavailable"):
                    await generate_fois_isolated(
                        fixture(), repository, cache_file=root / "missing.json",
                    )
            finally:
                active = False
                await task

        self.assertGreaterEqual(ticks, 5)

    def test_idle_worker_can_be_reaped_and_restored_around_visual_work(self) -> None:
        from src.core.fois import process_execution

        executor = mock.Mock()
        future = mock.Mock()
        future.result.return_value = {"pid": 12_345, "rss_bytes": 75_000_000}
        executor.submit.return_value = future
        with mock.patch.object(process_execution, "_EXECUTOR", executor):
            self.assertTrue(shutdown_fois_executor_sync())
            executor.shutdown.assert_called_once_with(
                wait=True, cancel_futures=True,
            )
            self.assertIsNone(process_execution._EXECUTOR)
        with mock.patch.object(
            process_execution, "_executor", return_value=executor,
        ):
            self.assertEqual(
                warm_fois_executor_sync(),
                {"pid": 12_345, "rss_bytes": 75_000_000},
            )
        future.result.assert_called_once_with(
            timeout=process_execution.FOIS_PROCESS_TIMEOUT_SECONDS,
        )

    def test_compact_input_retains_only_owned_brain_assets(self) -> None:
        data = fixture()
        data["players"] = {str(index): {"player_id": str(index)} for index in range(5000)}
        compact = compact_fois_input(data)

        report = compact["valuation_intelligence"]
        self.assertEqual(set(report["assets"]), {"player:101", "player:202"})
        self.assertEqual(set(report["timeline"]), {"player:101", "player:202"})
        self.assertNotIn("players", compact)
        self.assertEqual(compact["fois_history"], data["fois_history"])

    async def test_persistent_worker_matches_thread_semantics_and_is_reaped_on_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thread_service = FOISService(FOISRepository(root / "thread.sqlite3"))
            process_service = FOISService(
                FOISRepository(root / "process.sqlite3"),
                isolated_executor=partial(
                    generate_fois_isolated,
                    cache_file=cache_input(root, fixture()),
                ),
            )
            thread_scores = await thread_service.generate(copy.deepcopy(fixture()))
            process_scores = await process_service.generate(copy.deepcopy(fixture()))
            repeated_scores = await process_service.generate(copy.deepcopy(fixture()))

            self.assertEqual(
                [semantic(score) for score in process_scores],
                [semantic(score) for score in thread_scores],
            )
            self.assertEqual(
                [semantic(score) for score in repeated_scores],
                [semantic(score) for score in thread_scores],
            )
            execution = process_service.status()["execution"]
            self.assertEqual(execution["execution"], "spawned_subprocess")
            self.assertEqual(execution["input_contract"], "canonical_cache_fois_v2")
            self.assertEqual(execution["exit_status"], 0)
            self.assertEqual(execution["process_model"], "persistent_spawn_pool")
            self.assertFalse(execution["reaped"])
            self.assertGreater(execution["input_bytes"], 0)
            self.assertGreater(execution["child_peak_rss_bytes"], 0)
            worker_pid = int(execution["worker_pid"])
            self.assertTrue(psutil.pid_exists(worker_pid))
            await shutdown_fois_executor()
            self.assertFalse(psutil.pid_exists(worker_pid))

    async def test_prewarmed_worker_keeps_event_loop_responsive_with_large_irrelevant_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = FOISService(
                FOISRepository(root / "fois.sqlite3"),
                isolated_executor=partial(
                    generate_fois_isolated,
                    cache_file=cache_input(root, fixture()),
                ),
            )
            data = fixture()
            data["players"] = {
                str(index): {"player_id": str(index), "metadata": "x" * 300}
                for index in range(50_000)
            }
            await warm_fois_executor()
            gaps: list[float] = []
            stopped = asyncio.Event()

            async def heartbeat() -> None:
                prior = time.perf_counter()
                while not stopped.is_set():
                    await asyncio.sleep(.01)
                    now = time.perf_counter()
                    gaps.append((now - prior) * 1000)
                    prior = now

            task = asyncio.create_task(heartbeat())
            try:
                await service.generate(data)
            finally:
                stopped.set()
                await task
                await shutdown_fois_executor()

            self.assertTrue(gaps)
            self.assertLess(max(gaps), 500)
            self.assertLess(service.status()["execution"]["input_bytes"], 1_000_000)
            self.assertGreater(service.status()["execution"]["source_bytes"], 0)

    async def test_parent_sends_only_bounded_cache_control_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = fixture()
            data["players"] = {
                str(index): {"player_id": str(index), "metadata": "x" * 300}
                for index in range(50_000)
            }
            cache = cache_input(root, data)
            service = FOISService(
                FOISRepository(root / "fois.sqlite3"),
                isolated_executor=partial(generate_fois_isolated, cache_file=cache),
            )
            await service.generate(data)
            execution = service.status()["execution"]
            await shutdown_fois_executor()
            self.assertEqual(execution["input_contract"], "canonical_cache_fois_v2")
            self.assertLess(execution["input_bytes"], 2_000)
            self.assertGreater(execution["source_bytes"], execution["input_bytes"])
            self.assertLess(execution["compact_input_bytes"], 1_000_000)

    async def test_missing_or_cross_league_cache_fails_without_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = FOISRepository(root / "fois.sqlite3")
            missing_service = FOISService(
                repository,
                isolated_executor=partial(
                    generate_fois_isolated, cache_file=root / "missing.json",
                ),
            )
            with self.assertRaisesRegex(RuntimeError, "cache input is unavailable"):
                await missing_service.generate(fixture())

            wrong = fixture()
            wrong["league"]["league_id"] = "other-league"
            mismatch_service = FOISService(
                repository,
                isolated_executor=partial(
                    generate_fois_isolated,
                    cache_file=cache_input(root, wrong, "wrong.json"),
                ),
            )
            with self.assertRaisesRegex(RuntimeError, "league identity mismatch"):
                await mismatch_service.generate(fixture())
            self.assertEqual(repository.league("fois-process-fixture", "4.0"), ())
            await shutdown_fois_executor()

    async def test_process_failure_preserves_failed_state(self) -> None:
        async def broken(_data, _repository):
            raise RuntimeError("isolated failure")

        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(
                FOISRepository(Path(directory) / "fois.sqlite3"),
                isolated_executor=broken,
            )
            with self.assertRaisesRegex(RuntimeError, "isolated failure"):
                await service.generate(fixture())
            self.assertEqual(service.status()["state"], "failed")
            self.assertEqual(service.status()["last_error"], "isolated failure")

    async def test_membership_count_does_not_create_compute_processes(self) -> None:
        calls = 0

        async def observed(_data, repository):
            nonlocal calls
            calls += 1
            return (), await asyncio.to_thread(
                repository.canonical_health, "fois-process-fixture", "4.0",
            ), {"execution": "test", "worker_pid": os.getpid()}

        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(
                FOISRepository(Path(directory) / "fois.sqlite3"),
                isolated_executor=observed,
            )
            data = fixture()
            data["account_memberships"] = [
                {"league_id": f"league-{index}"} for index in range(500)
            ]
            await service.generate(data)
            self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
