"""Spawn-safe FOIS compute isolation and semantic-equivalence regressions."""
from __future__ import annotations

import asyncio
import copy
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import psutil

from src.core.fois.process_execution import generate_fois_isolated
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


def fixture() -> dict:
    return {
        "league": {"league_id": "fois-process-fixture", "season": "2026"},
        "league_settings": {"playoff_teams": 6},
        "teams": [
            {"roster_id": 1, "owner_id": "owner-1", "owner": "One", "players": []},
            {"roster_id": 2, "owner_id": "owner-2", "owner": "Two", "players": []},
        ],
        "fois_history": {
            "1": {"seasons": [], "trades": [], "drafts": [], "waivers": []},
            "2": {"seasons": [], "trades": [], "drafts": [], "waivers": []},
        },
    }


def semantic(score: object) -> dict:
    payload = asdict(score)
    payload.pop("generated_at", None)
    return payload


class FOISProcessExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_spawned_worker_matches_thread_semantics_and_is_reaped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thread_service = FOISService(FOISRepository(root / "thread.sqlite3"))
            process_service = FOISService(
                FOISRepository(root / "process.sqlite3"),
                isolated_executor=generate_fois_isolated,
            )
            thread_scores = await thread_service.generate(copy.deepcopy(fixture()))
            process_scores = await process_service.generate(copy.deepcopy(fixture()))

            self.assertEqual(
                [semantic(score) for score in process_scores],
                [semantic(score) for score in thread_scores],
            )
            execution = process_service.status()["execution"]
            self.assertEqual(execution["execution"], "spawned_subprocess")
            self.assertEqual(execution["exit_status"], 0)
            self.assertTrue(execution["reaped"])
            self.assertGreater(execution["input_bytes"], 0)
            self.assertGreater(execution["child_peak_rss_bytes"], 0)
            self.assertFalse(psutil.pid_exists(int(execution["worker_pid"])))

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
