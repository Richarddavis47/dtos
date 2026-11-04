from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services.history import wait_for_historical_lease
from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.historical_memory.jobs import ImportJob
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.historical_memory.store import HistoricalStore


class HistoricalLifecycleStabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.league_id = "league"

    def tearDown(self) -> None:
        self.temp.cleanup()

    async def test_expired_worker_lease_is_recovered_without_manual_action(self) -> None:
        job = ImportJob(
            self.store, self.league_id, (2025,), ("matchup",),
            worker_identity="terminated-worker",
        )
        job.create()
        self.assertTrue(job.acquire(lease_minutes=0))
        with patch("services.history.historical_store", self.store):
            recovered = await wait_for_historical_lease(
                self.league_id, poll_seconds=0.001,
            )
        self.assertEqual(recovered, 1)
        state = next(row for row in self.store.jobs(self.league_id) if row["job_id"] == job.job_id)
        self.assertEqual(state["status"], "queued")
        self.assertIsNone(state["worker_identity"])
        self.assertEqual(state["last_error_type"], "worker_interrupted")
        self.assertEqual(self.store.locks(), [])

    async def test_live_lease_is_not_taken_over_before_expiration(self) -> None:
        job = ImportJob(
            self.store, self.league_id, (2025,), ("matchup",),
            worker_identity="live-worker",
        )
        job.create()
        self.assertTrue(job.acquire(lease_minutes=0.001))
        started = time.perf_counter()
        with patch("services.history.historical_store", self.store):
            recovered = await wait_for_historical_lease(
                self.league_id, poll_seconds=0.01,
            )
        self.assertGreaterEqual(time.perf_counter() - started, 0.04)
        self.assertEqual(recovered, 1)

    def test_cache_retains_only_one_dataset_generation(self) -> None:
        cache = HistoricalReadModelCache()
        cache.get(self.store, self.league_id, {"players": {}})
        self.store.append(
            record_key="season", entity_type="league_season",
            league_id=self.league_id, season=2025,
            source_record_id="season", observed_at="2025-01-01T00:00:00+00:00",
            retrieved_at="2025-01-01T00:00:00+00:00", provider="Sleeper",
            availability="observed", confidence=100,
            calculation_method="provider_record", schema_version="1.0",
            payload={"season": 2025},
        )
        cache.get(self.store, self.league_id, {"players": {}})
        self.assertEqual(cache.metadata()["entry_count"], 1)
        self.assertEqual(cache.metadata()["max_entries"], 1)

    def test_directory_and_player_reads_do_not_materialize_all_player_weeks(self) -> None:
        graph = HistoricalAssetGraph(
            self.store, self.league_id,
            {"players": {"p1": {"full_name": "Player One"}}},
        )
        with patch.object(self.store, "records", wraps=self.store.records) as records:
            graph.asset_directory_page(limit=1)
            graph.player_dossier("p1")
        player_week_calls = [
            call for call in records.call_args_list
            if len(call.args) > 1 and call.args[1] == "player_week"
        ]
        self.assertTrue(player_week_calls)
        self.assertTrue(all(call.kwargs.get("player_id") == "p1" for call in player_week_calls))

    def test_coverage_uses_compact_sql_counts(self) -> None:
        graph = HistoricalAssetGraph(self.store, self.league_id, {"players": {}})
        with patch.object(
            self.store, "entity_counts_by_season",
            wraps=self.store.entity_counts_by_season,
        ) as counts, patch.object(
            graph, "_ensure_event_indexes",
            side_effect=AssertionError("coverage hydrated the global graph"),
        ):
            result = graph.coverage()
        counts.assert_called_once()
        self.assertEqual(result["status"], "incomplete")

    def test_global_graph_hydration_is_blocked_during_active_import(self) -> None:
        job = ImportJob(self.store, self.league_id, (2025,), ("matchup",))
        job.create()
        self.assertTrue(job.acquire())
        graph = HistoricalAssetGraph(self.store, self.league_id, {"players": {}})
        with self.assertRaisesRegex(RuntimeError, "indexed read path"):
            graph.events()
        self.assertIn("counts_by_season", graph.coverage())

    def test_asset_specific_reads_remain_available_during_import(self) -> None:
        observed = "2025-09-01T00:00:00+00:00"
        self.store.append(
            record_key="roster", entity_type="weekly_roster",
            league_id=self.league_id, season=2025, week=1,
            franchise_id=f"{self.league_id}:franchise:1", player_id=None,
            source_record_id="roster", observed_at=observed,
            retrieved_at=observed, provider="Sleeper", availability="observed",
            confidence=100, calculation_method="provider_record",
            schema_version="1.0", payload={"starters": ["p1"], "bench": []},
        )
        job = ImportJob(self.store, self.league_id, (2025,), ("matchup",))
        job.create()
        self.assertTrue(job.acquire())
        graph = HistoricalAssetGraph(
            self.store, self.league_id,
            {"players": {"p1": {"full_name": "Player One", "position": "WR"}}},
        )
        with patch(
            "services.sleeper.sleeper_get",
            side_effect=AssertionError("historical read attempted provider I/O"),
        ):
            events = graph.events(asset_id="DTOS-P-p1")
            directory = graph.asset_directory_page(limit=1)
        self.assertEqual(len(events), 1)
        self.assertEqual(directory[1][0]["canonical_id"], "DTOS-P-p1")


if __name__ == "__main__":
    unittest.main()
