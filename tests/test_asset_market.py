"""Asset Market canonical contracts, ranking, search, and read isolation."""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory.store import HistoricalStore


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
        self.temp.cleanup()

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

    def test_cache_is_single_flight_and_invalidates_by_dataset(self) -> None:
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
        self._append("player_week", "new-evidence", "10213", {"fantasy_points": 20.0})
        self.assertIsNot(
            self.cache.get(self.data, self.state, self.store, self.league_id),
            self.market,
        )

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
                self.assertEqual(client.get("/").status_code, 200)
                self.assertIn("Asset Market", client.get("/market").text)
                self.assertEqual(client.get("/api/market").status_code, 200)
                self.assertEqual(client.get("/api/market/assets?limit=2").json()["limit"], 2)
                self.assertEqual(client.get("/api/market/assets/player:10213").status_code, 200)
                self.assertEqual(client.get("/api/market/search?q=Josh%20Allen").status_code, 200)
                self.assertEqual(client.get("/api/market/trending").status_code, 200)
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
            payload = client.get("/api/market/assets/player:10213").json()
            html = client.get(
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
        path.unlink()
        with self.assertRaisesRegex(RuntimeError, "backing database is unavailable"):
            self.cache.get(self.data, self.state, first_store, self.league_id)
        recreated_store = HistoricalStore(path)
        recreated_market = self.cache.get(
            self.data, self.state, recreated_store, self.league_id,
        )
        self.assertIsNot(recreated_market, first_market)
        self.assertIs(
            self.cache.get(self.data, self.state, recreated_store, self.league_id),
            recreated_market,
        )


if __name__ == "__main__":
    unittest.main()
