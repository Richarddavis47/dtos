"""Spawn-safe FOIS compute isolation and semantic-equivalence regressions."""
from __future__ import annotations

import asyncio
import copy
import os
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path

import psutil

from src.core.fois.process_execution import (
    compact_fois_input, generate_fois_isolated, shutdown_fois_executor,
    warm_fois_executor,
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


class FOISProcessExecutionTests(unittest.IsolatedAsyncioTestCase):
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
                isolated_executor=generate_fois_isolated,
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
            self.assertEqual(execution["input_contract"], "compact_fois_v1")
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
            service = FOISService(
                FOISRepository(Path(directory) / "fois.sqlite3"),
                isolated_executor=generate_fois_isolated,
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
