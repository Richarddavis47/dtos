"""Asset Market canonical contracts, ranking, search, and read isolation."""
from __future__ import annotations

import gc
import tempfile
import threading
import time
import unittest
import weakref
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from src.core.asset_market import (
    AssetMarketCache, MarketWarmingError, asset_market_cache,
)
from src.core.asset_market.read_model import (
    MarketMemoryBudgetError, build_read_model, enforce_memory_budget,
)
from src.core.historical_memory.store import HistoricalStore
from src.core.historical_memory import historical_graph


def _brain_asset(asset_id: str, market: int, contender: int, rebuilder: int) -> dict:
    return {
        "asset_id": asset_id, "scores": {"coverage": 75, "confidence": 80, "agreement": 70},
        "valuation_layers": {
            "market_value": {"value": market},
            "contender_value": {"value": contender},
            "rebuilder_value": {"value": rebuilder},
        },
        "categories": [{"name": "Market", "available": True}],
        "evidence_sources": [{"provider_id": "fixture", "category": "Market"}],
        "missing_evidence": ["Projection"], "explanation": "Fixture evidence.",
    }


class AssetMarketTests(unittest.TestCase):
    def setUp(self) -> None:
        asset_market_cache.wait_for_background()
        asset_market_cache.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.league_id = "league-1"
        self.data = {
            "league": {"league_id": self.league_id},
            "players": {
                "10213": {"full_name": "Josh Allen", "position": "QB", "team": "BUF", "age": 30, "status": "Active", "years_exp": 8, "dtos_value": 90},
                "2": {"full_name": "Rookie Tight End", "position": "TE", "team": "NYJ", "age": 21, "status": "Active", "years_exp": 0, "dtos_value": 50},
                "3": {"full_name": "Retired Runner", "position": "RB", "age": 38, "status": "Retired", "years_exp": 12},
            },
            "teams": [{
                "roster_id": 1, "team_name": "Puka Cola Quantum", "owner": "Richard",
                "players": [{"id": "10213", "roster_slot": "starter"}],
            }],
            "pick_ledger": [{
                "season": 2028, "round": 1, "original_roster_id": 1,
                "original_team": "Puka Cola Quantum", "current_owner_id": 1,
                "current_owner": "Puka Cola Quantum",
            }],
            "market_data": {"providers": {}, "provider_status": {}},
            "valuation_intelligence": {
                "schema_version": "1.0", "generated_at": "2026-08-06T00:00:00+00:00",
                "availability": "available",
                "assets": {
                    "player:10213": _brain_asset("player:10213", 9200, 9500, 7000),
                    "player:2": _brain_asset("player:2", 5000, 4200, 6800),
                    "player:3": _brain_asset("player:3", 5000, 5500, 1800),
                    "pick:2028:1:1": _brain_asset("pick:2028:1:1", 6000, 5000, 7500),
                },
                "timeline": {}, "summary": {}, "diagnostics": {},
                "safety": {"unsafe_adjustments": 0},
            },
        }
        self.state = {"data": self.data, "last_sync": "2026-08-06T00:00:00+00:00"}
        self._append("player_week", "former-week", "99", {"fantasy_points": 10.0})
        self._append("player_week", "retired-week", "3", {"fantasy_points": 8.0})
        self.store.upsert_identity(
            "DTOS-P-99", "Sleeper", "99", "Former Player", 100,
            "2024-01-01T00:00:00+00:00", {"position": "WR"},
        )
        self._append("trade", "trade-123", None, {
            "transaction_id": "trade-123", "type": "trade", "status": "complete",
            "roster_ids": [1, 2], "adds": {}, "drops": {}, "draft_picks": [],
            "source_league_id": self.league_id,
        })
        self.cache = AssetMarketCache()
        self.market = self.cache.get(self.data, self.state, self.store, self.league_id)

    def tearDown(self) -> None:
        asset_market_cache.wait_for_background()
        asset_market_cache.clear()
        self.temp.cleanup()

    @staticmethod
    def _ready_get(client: TestClient, path: str):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = client.get(path)
            if response.status_code != 503:
                return response
            time.sleep(0.01)
        raise AssertionError(f"Asset Market did not publish for {path}")

    def _append(
        self, entity_type: str, source: str, player_id: str | None,
        payload: dict, *, store: HistoricalStore | None = None,
    ) -> None:
        (store or self.store).append(
            record_key=f"{entity_type}:{source}", entity_type=entity_type,
            league_id=self.league_id, source_record_id=source,
            observed_at="2025-09-01T00:00:00+00:00",
            retrieved_at="2025-09-01T00:00:00+00:00", provider="Sleeper",
            availability="available", confidence=100,
            calculation_method="provider_observation", schema_version="2.0",
            payload=payload, season=2025, week=1, player_id=player_id,
        )

    def test_complete_canonical_asset_discovery_and_classification(self) -> None:
        health = self.market.health()
        self.assertEqual(health["counts"]["total"], 4)
        self.assertEqual(health["duplicate_asset_ids"], 0)
        self.assertEqual(self.market.by_id["player:10213"]["availability"], "rostered")
        self.assertEqual(self.market.by_id["player:2"]["availability"], "day_traders_free_agent")
        self.assertEqual(self.market.by_id["player:3"]["availability"], "retired")

    def test_durable_compatible_generation_survives_process_cache_restart(self) -> None:
        first_path = self.market._artifact_path
        restarted = AssetMarketCache()
        with patch(
            "src.core.asset_market.engine.build_read_model",
            side_effect=AssertionError("compatible durable generation must not rebuild"),
        ):
            loaded = restarted.get(self.data, self.state, self.store, self.league_id)
        self.assertEqual(loaded._artifact_path, first_path)
        self.assertEqual(loaded.directory(limit=4), self.market.directory(limit=4))

    def test_background_generation_preserves_identity_and_serialized_output(self) -> None:
        background = AssetMarketCache()
        with self.assertRaises(MarketWarmingError):
            background.get(
                self.data, self.state, self.store, self.league_id,
                background=True,
            )
        self.assertTrue(background.wait_for_background())
        loaded = background.get(
            self.data, self.state, self.store, self.league_id,
            background=True,
        )
        self.assertEqual(loaded.generated_at, self.market.generated_at)
        self.assertEqual(loaded.directory(limit=4), self.market.directory(limit=4))
        self.assertEqual(loaded.detail("player:10213", 1), self.market.detail("player:10213", 1))

    def test_directory_pages_before_detail_hydration(self) -> None:
        with patch.object(
            self.market._read_model, "canonical",
            side_effect=AssertionError("directory must not hydrate canonical detail"),
        ):
            result = self.market.directory(limit=2)
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["total"], 4)

    def test_search_reads_compact_rows_without_full_universe_iteration(self) -> None:
        with patch(
            "src.core.asset_market.read_model.AssetSequence.__iter__",
            side_effect=AssertionError("search must use the durable index"),
        ):
            result = self.market.search("Josh Allen", 10)
        self.assertEqual(result["results"][0]["asset_id"], "player:10213")

    def test_memory_guard_refuses_unsafe_stage_before_allocation(self) -> None:
        with patch(
            "src.core.asset_market.read_model.memory_snapshot",
            return_value={
                "rss_bytes": 1, "vms_bytes": 1, "system_available_bytes": 1,
                "cgroup_current_bytes": 1500 * 1024 * 1024,
                "cgroup_limit_bytes": 2048 * 1024 * 1024,
            },
        ):
            with self.assertRaises(MarketMemoryBudgetError):
                enforce_memory_budget("fixture", 64 * 1024 * 1024)

    def test_concurrent_cold_requests_share_one_background_build(self) -> None:
        cache = AssetMarketCache()
        changed_state = {**self.state, "last_sync": "background-fixture"}
        entered = threading.Event()
        release = threading.Event()

        def prepare(*_args: object) -> None:
            entered.set()
            release.wait(1)

        with patch.object(cache, "_prepare_generation", side_effect=prepare) as build:
            with self.assertRaises(MarketWarmingError):
                cache.get(
                    self.data, changed_state, self.store, self.league_id,
                    background=True,
                )
            self.assertTrue(entered.wait(1))
            first_thread = cache._build_thread
            with self.assertRaises(MarketWarmingError):
                cache.get(
                    self.data, changed_state, self.store, self.league_id,
                    background=True,
                )
            self.assertIs(cache._build_thread, first_thread)
            self.assertEqual(build.call_count, 1)
            release.set()
            if first_thread:
                first_thread.join(timeout=1)

    def test_front_office_detail_changes_do_not_duplicate_market_generation(self) -> None:
        first = self.market.detail("player:10213", 1)
        second = self.market.detail("player:10213", 2)
        self.assertEqual(first["market_generation"], second["market_generation"])
        self.assertEqual(self.cache.build_count, 1)

    def test_failed_atomic_rebuild_preserves_valid_generation_and_removes_partial(self) -> None:
        target = self.market._artifact_path
        before = target.read_bytes()

        def failed_rows():
            yield self.market.by_id["player:10213"], self.market._read_model.canonical("player:10213")
            raise RuntimeError("fixture build failure")

        with self.assertRaisesRegex(RuntimeError, "fixture build failure"):
            build_read_model(target, "replacement", failed_rows(), {})
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(any(target.parent.glob(f".{target.name}.*.partial")))

    def test_stable_ranking_and_explicit_tie_breaker(self) -> None:
        result = self.market.directory(sort="market")
        tied = [row["asset_id"] for row in result["assets"] if row["values"]["market_value"] == 5000]
        self.assertEqual(tied, sorted(tied, reverse=True))
        self.assertEqual(result["tie_breaker"], "canonical_asset_id")
        self.assertEqual(result, self.market.directory(sort="market"))

    def test_search_spans_players_picks_former_players_teams_and_trades(self) -> None:
        self.assertEqual(self.market.search("Josh Allen")["results"][0]["asset_id"], "player:10213")
        self.assertEqual(self.market.search("2028 1st")["results"][0]["asset_type"], "pick")
        self.assertEqual(self.market.search("free-agent tight ends")["results"][0]["asset_id"], "player:2")
        self.assertTrue(any(row["display_name"] == "Former Player" for row in self.market.search("Former Player")["results"]))
        self.assertTrue(any(row["asset_type"] == "team" for row in self.market.search("Puka Cola Quantum")["results"]))
        self.assertTrue(any(row["asset_type"] == "trade" for row in self.market.search("trade-123")["results"]))

    def test_value_layers_remain_separate_and_missing_market_is_not_substituted(self) -> None:
        detail = self.market.detail("player:10213", 1)
        self.assertEqual(detail["value_layers"]["market_value"]["value"], 9200)
        self.assertEqual(detail["value_layers"]["contender_value"]["value"], 9500)
        retired = self.market.detail("player:3")
        self.assertIsNone(retired["value_layers"]["intrinsic_dtos_value"]["value"])
        self.assertEqual(retired["value_layers"]["intrinsic_dtos_value"]["availability"], "unavailable")
        self.assertTrue(retired["value_layers"]["intrinsic_dtos_value"]["limitations"])

    def test_contender_and_rebuilder_views_diverge_from_canonical_layers(self) -> None:
        contender = self.market.directory(sort="contender")["assets"]
        rebuilder = self.market.directory(sort="rebuilder")["assets"]
        self.assertNotEqual(contender[0]["asset_id"], rebuilder[0]["asset_id"])

    def test_trending_requires_two_timestamped_observations(self) -> None:
        result = self.market.trending()
        self.assertEqual(result["availability"], "unavailable")
        self.assertEqual(result["most_discussed"]["status"], "unsupported")
        self.data["valuation_intelligence"]["timeline"] = {
            "player:10213": [
                {"timestamp": "2026-01-01", "confidence": 60},
                {"timestamp": "2026-02-01", "confidence": 80},
            ],
        }
        refreshed = AssetMarketCache().get(self.data, self.state, self.store, self.league_id)
        self.assertEqual(refreshed.trending()["biggest_risers"][0]["magnitude"], 20)

    def test_cache_is_single_flight_and_history_reads_track_dataset(self) -> None:
        results = []
        threads = [threading.Thread(target=lambda: results.append(
            self.cache.get(self.data, self.state, self.store, self.league_id)
        )) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(result is self.market for result in results))
        self.assertEqual(self.cache.build_count, 1)
        original_store_identity = self.cache.store_identity(self.store)
        self._append("player_week", "new-evidence", "10213", {"fantasy_points": 20.0})
        self.assertEqual(original_store_identity, self.cache.store_identity(self.store))
        self.assertIs(
            self.cache.get(self.data, self.state, self.store, self.league_id),
            self.market,
        )
        self.assertEqual(self.cache.build_count, 1)
        self.assertEqual(
            self.market.detail("player:10213")["historical_dataset_version"],
            self.store.dataset_version(self.league_id),
        )

    def test_generation_replacement_releases_superseded_market(self) -> None:
        cache = AssetMarketCache()
        previous = cache.get(self.data, self.state, self.store, self.league_id)
        expected_assets = previous.directory()["assets"]
        reference = weakref.ref(previous)
        changed_state = {**self.state, "last_sync": "2026-08-07T00:00:00+00:00"}
        current = cache.get(
            self.data, changed_state, self.store, self.league_id,
        )
        del previous
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(current.directory()["assets"], expected_assets)
        self.assertEqual(cache.build_count, 2)

    def test_api_ui_agree_and_reads_never_sync(self) -> None:
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.data, state=self.state,
            league_id=self.league_id,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        with patch("routes.market.historical_store", self.store):
            client = TestClient(app)
            with patch("services.sleeper.sync_sleeper", new=AsyncMock()) as sync:
                self.assertEqual(self._ready_get(client, "/").status_code, 200)
                self.assertIn("Asset Market", self._ready_get(client, "/market").text)
                self.assertEqual(self._ready_get(client, "/api/market").status_code, 200)
                self.assertEqual(self._ready_get(client, "/api/market/assets?limit=2").json()["limit"], 2)
                self.assertEqual(self._ready_get(client, "/api/market/assets/player:10213").status_code, 200)
                self.assertEqual(self._ready_get(client, "/api/market/search?q=Josh%20Allen").status_code, 200)
                self.assertEqual(self._ready_get(client, "/api/market/trending").status_code, 200)
                sync.assert_not_awaited()

    def test_detail_identity_is_canonical_across_asset_types_and_repeated_reads(self) -> None:
        for asset_id in (
            "player:10213", "player:2", "player:3", "pick:2028:1:1",
        ):
            with self.subTest(asset_id=asset_id):
                first = self.market.detail(asset_id, 1)
                second = self.market.detail(asset_id, 1)
                self.assertEqual(
                    first["brain_snapshot_id"],
                    first["recommendation"]["brain_snapshot_id"],
                )
                self.assertEqual(first["brain_snapshot_id"], second["brain_snapshot_id"])
                self.assertEqual(first["market_generation"], second["market_generation"])
                self.assertEqual(
                    first["historical_dataset_version"], self.market.dataset_version,
                )
                self.assertEqual(
                    first["valuation_generation"],
                    self.data["valuation_intelligence"]["generated_at"],
                )
                self.assertNotEqual(
                    first["brain_snapshot_id"], first["historical_dataset_version"],
                )

    def test_cached_fallback_and_expanded_ui_share_detail_identity(self) -> None:
        self.state["last_sync_error"] = "Sleeper unavailable; using cached data."
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.data, state=self.state,
            league_id=self.league_id,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        with patch("routes.market.historical_store", self.store):
            client = TestClient(app)
            payload = self._ready_get(
                client, "/api/market/assets/player:10213",
            ).json()
            html = self._ready_get(
                client,
                "/market?selected=player%3A10213&front_office=1",
            ).text
        snapshot = payload["recommendation"]["brain_snapshot_id"]
        self.assertEqual(payload["brain_snapshot_id"], snapshot)
        self.assertIn(snapshot, html)
        self.assertIn(payload["market_generation"], html)
        self.assertIn(payload["valuation_generation"], html)
        self.assertIn(payload["historical_dataset_version"], html)

    def test_cache_isolates_identical_stores_and_never_discloses_paths(self) -> None:
        other_path = Path(self.temp.name) / "other" / "history.sqlite3"
        other_store = HistoricalStore(other_path)
        self._append(
            "player_week", "former-week", "99", {"fantasy_points": 10.0},
            store=other_store,
        )
        self._append(
            "player_week", "retired-week", "3", {"fantasy_points": 8.0},
            store=other_store,
        )
        other_store.upsert_identity(
            "DTOS-P-99", "Sleeper", "99", "Former Player", 100,
            "2024-01-01T00:00:00+00:00", {"position": "WR"},
        )
        self._append(
            "trade", "trade-123", None,
            {
                "transaction_id": "trade-123", "type": "trade",
                "status": "complete", "roster_ids": [1, 2], "adds": {},
                "drops": {}, "draft_picks": [],
                "source_league_id": self.league_id,
            },
            store=other_store,
        )
        other_market = self.cache.get(
            self.data, self.state, other_store, self.league_id,
        )
        self.assertIsNot(other_market, self.market)
        self.assertEqual(other_market.dataset_version, self.market.dataset_version)
        public = str({**other_market.health(), "cache": self.cache.metrics()})
        self.assertNotIn(str(other_path), public)
        self.assertNotIn(str(other_path.parent), public)

    def test_deleted_store_and_recreated_same_path_cannot_reuse_model(self) -> None:
        path = Path(self.temp.name) / "replace" / "history.sqlite3"
        first_store = HistoricalStore(path)
        first_market = self.cache.get(
            self.data, self.state, first_store, self.league_id,
        )
        first_uuid = first_store.database_uuid()
        path.unlink()
        with self.assertRaisesRegex(RuntimeError, "backing database is unavailable"):
            self.cache.get(self.data, self.state, first_store, self.league_id)
        recreated_store = HistoricalStore(path)
        self.assertNotEqual(recreated_store.database_uuid(), first_uuid)
        recreated_market = self.cache.get(
            self.data, self.state, recreated_store, self.league_id,
        )
        self.assertIsNot(recreated_market, first_market)
        self.assertIs(
            self.cache.get(self.data, self.state, recreated_store, self.league_id),
            recreated_market,
        )

    def test_durable_uuid_survives_writes_checkpoints_and_store_restart(self) -> None:
        database_uuid = self.store.database_uuid()
        namespace = self.cache.store_identity(self.store)
        self._append(
            "player_week", "uuid-stability", "10213",
            {"fantasy_points": 21.0},
        )
        with self.store.connection() as connection:
            connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
        restarted = HistoricalStore(self.store.path)
        self.assertEqual(self.store.database_uuid(), database_uuid)
        self.assertEqual(restarted.database_uuid(), database_uuid)
        self.assertEqual(self.cache.store_identity(self.store), namespace)
        self.assertNotEqual(
            self.cache.store_identity(restarted), namespace,
            "Separate store instances must not share a process-global model.",
        )

    def test_repeated_query_surfaces_do_not_rebuild_market(self) -> None:
        for _ in range(5):
            self.market.directory(limit=1)
            self.market.search("QB", limit=1)
            self.market.detail("player:10213", 1)
            self.market.trending(limit=1)
            self.assertIs(
                self.cache.get(self.data, self.state, self.store, self.league_id),
                self.market,
            )
        self.assertEqual(self.cache.build_count, 1)
        self.assertGreaterEqual(self.cache.hits, 5)

    def test_dataset_identity_is_single_flight_and_commit_invalidated(self) -> None:
        initial = self.store.dataset_version(self.league_id)
        computations = self.store.dataset_version_metrics()["computations"]
        versions: list[str] = []
        threads = [threading.Thread(target=lambda: versions.append(
            self.store.dataset_version(self.league_id)
        )) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(versions, [initial] * 8)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"], computations,
        )
        self._append(
            "player_week", "identity-invalidation", "10213",
            {"fantasy_points": 22.0},
        )
        changed = self.store.dataset_version(self.league_id)
        self.assertNotEqual(changed, initial)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"],
            computations + 1,
        )
        self.assertFalse(self.store.append(
            record_key="player_week:identity-invalidation",
            entity_type="player_week", league_id=self.league_id,
            source_record_id="identity-invalidation",
            observed_at="2025-09-01T00:00:00+00:00",
            retrieved_at="2025-09-01T00:00:00+00:00", provider="Sleeper",
            availability="available", confidence=100,
            calculation_method="provider_observation", schema_version="2.0",
            payload={"fantasy_points": 22.0}, season=2025, week=1,
            player_id="10213",
        ))
        self.assertEqual(self.store.dataset_version(self.league_id), changed)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"],
            computations + 1,
        )

    def test_search_routes_only_true_historical_queries_to_retained_aliases(self) -> None:
        with patch("src.core.asset_market.engine.historical_graph") as graph:
            self.assertEqual(
                self.market.search("Josh Allen")["results"][0]["asset_id"],
                "player:10213",
            )
            self.assertEqual(self.market.search("no-such-player")["count"], 0)
            self.assertEqual(
                self.market.search("Former Player")["results"][0]["asset_id"],
                "DTOS-P-99",
            )
            graph.assert_not_called()
        with patch.object(self.market._brain, "asset") as asset, patch.object(
            self.market._brain, "decision",
        ) as decision:
            self.market.search("QB")
            asset.assert_not_called()
            decision.assert_not_called()

    def test_request_layers_resolve_dataset_identity_once(self) -> None:
        with patch.object(
            self.store, "dataset_version",
            wraps=self.store.dataset_version,
        ) as version:
            self.market.search("Josh Allen")
            self.assertEqual(version.call_count, 1)
        with patch.object(
            self.store, "dataset_version",
            wraps=self.store.dataset_version,
        ) as version:
            self.market.detail("player:10213", 1)
            self.assertEqual(version.call_count, 1)

    def test_player_dossier_cache_is_single_flight_and_bounded(self) -> None:
        dataset_version = self.store.dataset_version(self.league_id)
        graph = historical_graph(
            self.store, self.league_id, self.data, dataset_version,
        )
        first = graph.player_dossier("10213")
        results: list[dict] = []
        threads = [threading.Thread(target=lambda: results.append(
            graph.player_dossier("10213")
        )) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(result == first for result in results))
        metrics = graph.query_metrics()
        self.assertEqual(metrics["player_summary_build_count"], 1)
        self.assertEqual(metrics["player_summary_cache_hits"], 6)
        self.assertLessEqual(
            metrics["player_summary_cache_entries"],
            metrics["player_summary_cache_limit"],
        )

    def test_player_dossier_cache_eviction_is_bounded_and_failures_are_not_cached(self) -> None:
        dataset_version = self.store.dataset_version(self.league_id)
        graph = historical_graph(
            self.store, self.league_id, self.data, dataset_version,
        )
        graph._player_dossiers.clear()
        with patch.object(
            graph, "_build_player_dossier",
            side_effect=lambda player_id, canonical_id: {
                "identity": canonical_id, "player_id": player_id,
            },
        ) as build:
            for player_id in range(130):
                graph.player_dossier(str(player_id))
            self.assertEqual(len(graph._player_dossiers), 128)
            retained = [key[-1] for key in graph._player_dossiers]
            self.assertNotIn("DTOS-P-0", retained)
            self.assertNotIn("DTOS-P-1", retained)
            self.assertEqual(retained[-1], "DTOS-P-129")
            self.assertEqual(build.call_count, 130)
        graph._player_dossiers.clear()
        with patch.object(
            graph, "_build_player_dossier",
            side_effect=RuntimeError("incomplete summary"),
        ):
            with self.assertRaisesRegex(RuntimeError, "incomplete summary"):
                graph.player_dossier("failed")
        self.assertFalse(any(key[-1] == "DTOS-P-failed" for key in graph._player_dossiers))

    def test_warm_market_reads_do_not_repeat_dataset_aggregate_queries(self) -> None:
        self.store.dataset_version(self.league_id)
        statements: list[str] = []
        original_connection = self.store.connection

        @contextmanager
        def traced_connection():
            with original_connection() as connection:
                connection.set_trace_callback(statements.append)
                yield connection

        with patch.object(self.store, "connection", traced_connection):
            for _ in range(5):
                self.market.search("QB")
                self.market.detail("player:10213", 1)
        aggregates = [
            statement for statement in statements
            if "coalesce(max(id)" in statement
            or "coalesce(max(rowid)" in statement
            or "SELECT issue_key, resolved" in statement
        ]
        self.assertEqual(aggregates, [])

    def test_dataset_identity_cache_is_cross_league_and_rollback_safe(self) -> None:
        first = self.store.dataset_version(self.league_id)
        other = self.store.dataset_version("league-2")
        computations = self.store.dataset_version_metrics()["computations"]
        with self.assertRaises(RuntimeError):
            with self.store.connection() as connection:
                connection.execute(
                    """INSERT INTO historical_records(
                    record_key,entity_type,league_id,source_record_id,
                    observed_at,retrieved_at,provider,availability,confidence,
                    calculation_method,schema_version,payload)
                    VALUES ('rolled-back','player_week',?,'rolled-back',
                    '2025-01-01','2025-01-01','fixture','available',100,
                    'fixture','2.0','{}')""",
                    (self.league_id,),
                )
                raise RuntimeError("rollback")
        self.assertEqual(self.store.dataset_version(self.league_id), first)
        self.assertEqual(self.store.dataset_version("league-2"), other)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"], computations,
        )
        self._append(
            "player_week", "cross-league-change", "10213",
            {"fantasy_points": 23.0},
        )
        self.assertEqual(self.store.dataset_version("league-2"), other)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"], computations,
        )
        self.assertNotEqual(self.store.dataset_version(self.league_id), first)


if __name__ == "__main__":
    unittest.main()
