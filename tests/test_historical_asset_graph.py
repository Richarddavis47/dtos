"""Historical Asset Graph identity, chronology, and reconciliation contracts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from src.core.historical_memory.graph import (
    HistoricalAssetGraph,
    canonical_pick_id,
    canonical_player_id,
)
from src.core.historical_memory.store import HistoricalStore


class HistoricalAssetGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.league_id = "ROOT"
        self.current_data = {
            "players": {
                "p1": {"full_name": "Alpha Runner", "position": "RB"},
                "current-only": {"full_name": "Current Only", "position": "WR"},
            },
        }
        self._append(
            "league_season", "season-2025", 2025,
            {"scoring_settings": {"rec": 1.0}, "source_league_id": "L25"},
        )
        self._append(
            "league_season", "season-2026", 2026,
            {"scoring_settings": {"rec": 0.5}, "source_league_id": "L26"},
        )
        self._append(
            "draft", "draft-1", 2025,
            {"draft": {"draft_id": "draft-1", "type": "rookie"}, "source_league_id": "L25"},
        )
        self._append(
            "draft_pick", "pick-1", 2025,
            {
                "draft_id": "draft-1", "round": 1, "pick_no": 1,
                "roster_id": 1, "picked_by": 1, "player_id": "p1",
                "source_league_id": "L25",
            },
            player_id="p1",
        )
        self._append(
            "trade", "trade-1", 2025,
            {
                "transaction_id": "trade-1", "type": "trade", "status": "complete",
                "roster_ids": [1, 2], "adds": {"p1": 2}, "drops": {"p1": 1},
                "draft_picks": [{
                    "season": 2026, "round": 1, "roster_id": 1,
                    "previous_owner_id": 1, "owner_id": 2,
                }],
                "source_league_id": "L25",
            },
            week=4,
        )
        self._append(
            "transaction", "failed-waiver", 2025,
            {
                "transaction_id": "failed-waiver", "type": "waiver", "status": "failed",
                "roster_ids": [3], "adds": {"p1": 3}, "drops": {},
                "source_league_id": "L25",
            },
            week=5,
        )
        for season, points in ((2025, 20.0), (2026, 12.0)):
            self._append(
                "player_week", f"p1-{season}-1", season,
                {"fantasy_points": points, "starter": True, "source_league_id": f"L{str(season)[-2:]}"},
                week=1, franchise_id=f"ROOT:franchise:{1 if season == 2025 else 2}",
                player_id="p1",
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _append(
        self, entity_type: str, source_id: str, season: int,
        payload: dict[str, object], *, week: int | None = None,
        franchise_id: str | None = None, player_id: str | None = None,
    ) -> None:
        timestamp = f"{season}-09-{min(week or 1, 28):02d}T12:00:00+00:00"
        self.store.append(
            record_key=f"{entity_type}:{source_id}", entity_type=entity_type,
            league_id=self.league_id, source_record_id=source_id,
            observed_at=timestamp, retrieved_at=timestamp, provider="Sleeper",
            availability="available", confidence=100,
            calculation_method="provider_observation", schema_version="2.0",
            payload=payload, season=season, week=week,
            franchise_id=franchise_id, player_id=player_id,
        )

    def graph(self) -> HistoricalAssetGraph:
        return HistoricalAssetGraph(self.store, self.league_id, self.current_data)

    def test_stable_ids_and_unresolved_identity_are_honest(self) -> None:
        self.assertEqual(canonical_player_id("p1"), "DTOS-P-p1")
        self.assertEqual(canonical_pick_id(2026, 1, 1), "PICK-2026-R1-ORIG1")
        unresolved = self.graph().player_identity("retired-unknown")
        self.assertEqual(unresolved["resolution_status"], "unresolved")
        self.assertTrue(unresolved["missing_reasons"])

    def test_completed_trade_moves_ownership_but_failed_waiver_does_not(self) -> None:
        graph = self.graph()
        events = graph.events(asset_id="DTOS-P-p1")
        failed = [event for event in events if event["event_status"] == "failed"]
        intervals = graph.ownership_intervals("DTOS-P-p1")
        self.assertEqual(len(failed), 1)
        self.assertEqual([row["franchise_id"] for row in intervals], [
            "ROOT:franchise:1", "ROOT:franchise:2",
        ])
        self.assertNotIn("ROOT:franchise:3", {row["franchise_id"] for row in intervals})

    def test_season_summaries_preserve_scoring_versions_and_in_progress_state(self) -> None:
        summaries = self.graph().player_season_summaries("p1")
        by_season = {row["season"]: row for row in summaries}
        self.assertNotEqual(
            by_season[2025]["scoring_settings_version"],
            by_season[2026]["scoring_settings_version"],
        )
        self.assertEqual(by_season[2026]["status"], "in_progress")
        self.assertEqual(by_season[2025]["fantasy_points"], 20.0)
        self.assertIn(2, by_season[2025]["missing_weeks"])

    def test_pick_and_trade_dossiers_are_bidirectionally_connected(self) -> None:
        graph = self.graph()
        pick = graph.pick_dossier("PICK-2025-R1-ORIG1")
        trade = graph.trade_dossier("trade-1")
        self.assertEqual(pick["selected_player_id"], "DTOS-P-p1")
        self.assertEqual(pick["selected_player_url"], "/players/p1")
        self.assertTrue(any(event["asset_id"] == "DTOS-P-p1" for event in trade["asset_events"]))
        self.assertEqual(trade["value_at_trade_availability"], "unavailable_without_timestamped_valuation")

    def test_search_and_directory_cover_current_historical_pick_and_trade_assets(self) -> None:
        graph = self.graph()
        self.assertEqual(graph.search("Alpha Runner")[0]["canonical_url"], "/players/p1")
        self.assertEqual(graph.search("trade-1")[0]["result_type"], "trade")
        self.assertEqual(graph.search("PICK-2026")[0]["result_type"], "pick")
        directory_ids = {row["canonical_id"] for row in graph.asset_directory()}
        self.assertIn("DTOS-P-current-only", directory_ids)
        self.assertIn("PICK-2026-R1-ORIG1", directory_ids)

    def test_event_ids_are_unique_and_sources_are_auditable(self) -> None:
        graph = self.graph()
        events = graph.events()
        self.assertEqual(len(events), len({event["event_id"] for event in events}))
        self.assertTrue(all(event["source_record_id"] for event in events))
        coverage = graph.coverage()
        self.assertEqual(coverage["asset_event_count"], len(events))
        self.assertEqual(coverage["duplicate_event_ids"], 0)
        self.assertTrue(coverage["source_hashes_available"])

    def test_asset_specific_event_output_matches_full_graph_output(self) -> None:
        full_graph = self.graph()
        full_events = [
            event for event in full_graph.events()
            if event["asset_id"] == "DTOS-P-p1"
        ]
        targeted_events = self.graph().events(asset_id="DTOS-P-p1")
        self.assertEqual(targeted_events, full_events)

    def test_api_and_ui_share_canonical_ids_and_cross_links(self) -> None:
        app = FastAPI()
        app.include_router(create_historical_assets_router(
            league_id=self.league_id,
            require_data=lambda: self.current_data,
            page=lambda _title, body: HTMLResponse(body),
        ))
        with patch("routes.historical_assets.historical_store", self.store):
            client = TestClient(app)
            player = client.get("/api/history/players/p1")
            pick = client.get("/api/picks/PICK-2025-R1-ORIG1")
            pick_page = client.get("/picks/PICK-2025-R1-ORIG1")
            trade_page = client.get("/trades/history/trade-1")
            search = client.get("/api/search", params={"q": "Alpha Runner"})
        self.assertEqual({player.status_code, pick.status_code, pick_page.status_code, trade_page.status_code, search.status_code}, {200})
        self.assertEqual(player.json()["identity"]["canonical_id"], "DTOS-P-p1")
        self.assertEqual(pick.json()["selected_player_id"], "DTOS-P-p1")
        self.assertIn('/players/p1', pick_page.text)
        self.assertIn('/players/p1', trade_page.text)
        self.assertEqual(search.json()["records"][0]["canonical_id"], "DTOS-P-p1")


if __name__ == "__main__":
    unittest.main()
