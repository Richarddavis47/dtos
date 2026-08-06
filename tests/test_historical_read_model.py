"""Historical graph cache, invalidation, equivalence, and query-bound contracts."""
from __future__ import annotations

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.historical_memory.store import HistoricalStore


class HistoricalReadModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.data = {
            "players": {
                "p1": {"full_name": "Player One", "position": "RB"},
                "p2": {"full_name": "Player Two", "position": "WR"},
            },
        }
        self._append("league_season", "L", {"scoring_settings": {"rec": 1}}, season=2025)
        self._append(
            "draft_pick", "draft:1",
            {"draft_id": "draft", "round": 1, "roster_id": 1, "picked_by": 1, "player_id": "p1"},
            season=2025, player_id="p1",
        )
        self._append(
            "trade", "trade-1",
            {"type": "trade", "status": "complete", "roster_ids": [1, 2], "drops": {"p1": 1}, "adds": {"p1": 2}},
            season=2025, week=2,
        )
        self._append(
            "transaction", "failed-1",
            {"type": "waiver", "status": "failed", "roster_ids": [3], "adds": {"p1": 3}},
            season=2025, week=3,
        )
        self._append(
            "player_week", "p1:1", {"fantasy_points": 10, "starter": True},
            season=2025, week=1, player_id="p1", franchise_id="L:franchise:1",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _append(
        self, entity_type: str, source_id: str, payload: dict[str, object],
        *, season: int, week: int | None = None, player_id: str | None = None,
        franchise_id: str | None = None,
    ) -> None:
        observed = f"{season}-09-{week or 1:02d}T00:00:00+00:00"
        self.store.append(
            record_key=f"{entity_type}:{source_id}", entity_type=entity_type,
            league_id="L", source_record_id=source_id, season=season, week=week,
            player_id=player_id, franchise_id=franchise_id,
            observed_at=observed, retrieved_at=observed, provider="Sleeper",
            availability="observed", confidence=100,
            calculation_method="provider_observation", schema_version="1.0",
            payload={**payload, "source_league_id": "L"},
        )

    def test_repeated_and_concurrent_reads_build_once(self) -> None:
        cache = HistoricalReadModelCache()
        with ThreadPoolExecutor(max_workers=8) as pool:
            graphs = list(pool.map(
                lambda _: cache.get(self.store, "L", self.data), range(20),
            ))
        self.assertEqual(len({id(graph) for graph in graphs}), 1)
        self.assertEqual(cache.metadata()["build_count"], 1)
        self.assertEqual(cache.metadata()["cache_misses"], 1)
        self.assertEqual(cache.metadata()["cache_hits"], 19)

    def test_dataset_change_invalidates_without_cross_league_leak(self) -> None:
        cache = HistoricalReadModelCache()
        first = cache.get(self.store, "L", self.data)
        first_key = cache.metadata()["cache_key"]
        self._append(
            "transaction", "add-2",
            {"type": "free_agent", "status": "complete", "adds": {"p2": 1}},
            season=2025, week=4,
        )
        second = cache.get(self.store, "L", self.data)
        self.assertIsNot(first, second)
        self.assertNotEqual(first_key, cache.metadata()["cache_key"])
        other = cache.get(self.store, "OTHER", self.data)
        self.assertIsNot(second, other)
        self.assertEqual(other.league_id, "OTHER")

    def test_failed_rebuild_retains_last_valid_model_and_reports_error(self) -> None:
        cache = HistoricalReadModelCache()
        first = cache.get(self.store, "L", self.data)
        self._append(
            "transaction", "add-3",
            {"type": "free_agent", "status": "complete", "adds": {"p2": 1}},
            season=2025, week=5,
        )
        with patch(
            "src.core.historical_memory.read_model.HistoricalAssetGraph",
            side_effect=RuntimeError("controlled rebuild failure"),
        ):
            fallback = cache.get(self.store, "L", self.data)
        self.assertIs(fallback, first)
        self.assertIn("controlled rebuild failure", cache.metadata()["last_build_error"])

    def test_pagination_hydrates_only_requested_record_and_is_deterministic(self) -> None:
        graph = HistoricalReadModelCache().get(self.store, "L", self.data)
        total, first = graph.asset_directory_page(limit=1)
        _, repeated = graph.asset_directory_page(limit=1)
        _, second = graph.asset_directory_page(limit=1, offset=1)
        self.assertGreaterEqual(total, 3)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first[0]["canonical_id"], second[0]["canonical_id"])
        self.assertEqual(graph.query_metrics()["records_hydrated"], 1)

    def test_cached_and_reference_outputs_are_semantically_identical(self) -> None:
        reference = HistoricalAssetGraph(self.store, "L", self.data)
        optimized = HistoricalReadModelCache().get(self.store, "L", self.data)
        self.assertEqual(reference.player_dossier("p1"), optimized.player_dossier("p1"))
        self.assertEqual(reference.trade_dossiers(), optimized.trade_dossiers())
        self.assertEqual(reference.asset_directory(), optimized.asset_directory())
        self.assertEqual(reference.search("Player One"), optimized.search("Player One"))
        intervals = optimized.ownership_intervals("DTOS-P-p1")
        self.assertNotIn("L:franchise:3", {row["franchise_id"] for row in intervals})

    def test_reads_are_provider_free_and_expose_cache_health(self) -> None:
        cache = HistoricalReadModelCache()
        with patch(
            "services.sleeper.sleeper_get",
            side_effect=AssertionError("historical read attempted provider I/O"),
        ):
            graph = cache.get(self.store, "L", self.data)
            graph.player_dossier("p1")
            coverage = graph.coverage()
        self.assertEqual(coverage["read_model"]["build_count"], 1)
        self.assertEqual(coverage["read_model"]["status"], "ready")
        self.assertGreater(coverage["read_model"]["event_count"], 0)

    def test_production_scale_indexes_keep_warm_reads_bounded(self) -> None:
        database = Path(self.temp.name) / "production-scale.sqlite3"
        store = HistoricalStore(database)
        observed = "2025-09-01T00:00:00+00:00"
        records = []
        for snapshot in range(3_000):
            players = [f"p{snapshot % 1_000}-{index}" for index in range(10)]
            records.append({
                "record_key": f"weekly:{snapshot}", "entity_type": "weekly_roster",
                "league_id": "SCALE", "season": 2025, "week": snapshot % 18 + 1,
                "franchise_id": f"SCALE:franchise:{snapshot % 10 + 1}",
                "player_id": None, "source_record_id": str(snapshot),
                "observed_at": observed, "retrieved_at": observed,
                "provider": "Sleeper", "availability": "observed",
                "confidence": 100, "calculation_method": "provider_observation",
                "schema_version": "1.0", "payload": {
                    "starters": players[:5], "bench": players[5:],
                    "source_league_id": "SCALE",
                },
            })
            for player_id in players:
                records.append({
                    "record_key": f"player:{snapshot}:{player_id}",
                    "entity_type": "player_week", "league_id": "SCALE",
                    "season": 2025, "week": snapshot % 18 + 1,
                    "franchise_id": f"SCALE:franchise:{snapshot % 10 + 1}",
                    "player_id": player_id,
                    "source_record_id": f"{snapshot}:{player_id}",
                    "observed_at": observed, "retrieved_at": observed,
                    "provider": "Sleeper", "availability": "observed",
                    "confidence": 100, "calculation_method": "provider_observation",
                    "schema_version": "1.0", "payload": {
                        "fantasy_points": 10.0, "starter": player_id in players[:5],
                        "source_league_id": "SCALE",
                    },
                })
        store.append_many(records)
        data = {"players": {f"p0-{index}": {"full_name": f"Player {index}", "position": "WR"} for index in range(10)}}
        cache = HistoricalReadModelCache()
        cold_started = time.perf_counter()
        graph = cache.get(store, "SCALE", data)
        cold_duration = time.perf_counter() - cold_started
        asset_started = time.perf_counter()
        graph.asset_directory_page(limit=1)
        asset_duration = time.perf_counter() - asset_started
        player_started = time.perf_counter()
        graph.player_dossier("p0-0")
        player_duration = time.perf_counter() - player_started
        self.assertLess(cold_duration, 30)
        self.assertLess(asset_duration, 1)
        self.assertLess(player_duration, 2)
        self.assertEqual(cache.metadata()["build_count"], 1)
        self.assertEqual(cache.metadata()["event_count"], 30_000)
        self.assertGreater(cache.metadata()["approximate_model_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
