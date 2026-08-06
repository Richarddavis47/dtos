"""Canonical Historical Memory discovery and detail-route regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from routes.inspect import create_inspection_router
from src.core.historical_memory.store import HistoricalStore
from src.core.inspection import discover_pages, excluded_current_trade_pages


class TradeHistoryDiscoveryTests(unittest.TestCase):
    REPORTED_IDS = (
        "1320881994665582592",
        "1325505291252400128",
        "1329942612483772416",
    )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.league_id = "league-1"
        self.state = {
            "data": {
                "league": {"league_id": self.league_id},
                "transactions": [
                    *(
                        {"transaction_id": item, "type": "trade", "status": "complete"}
                        for item in self.REPORTED_IDS
                    ),
                    {"transaction_id": "trade-canonical", "type": "trade", "status": "complete"},
                    {"transaction_id": "waiver-current", "type": "waiver", "status": "complete"},
                ],
            },
        }
        self._append_trade("trade-canonical", "complete", 2025)
        self._append_trade("trade-incomplete", "pending", 2026)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _append_trade(self, transaction_id: str, status: str, season: int) -> None:
        timestamp = f"{season}-09-01T12:00:00+00:00"
        self.store.append(
            record_key=f"trade:{transaction_id}", entity_type="trade",
            league_id=self.league_id, source_record_id=transaction_id,
            observed_at=timestamp, retrieved_at=timestamp, provider="Sleeper",
            availability="available", confidence=100,
            calculation_method="provider_observation", schema_version="2.0",
            payload={
                "transaction_id": transaction_id, "type": "trade",
                "status": status, "roster_ids": [1, 2], "adds": {},
                "drops": {}, "draft_picks": [],
                "source_league_id": self.league_id,
            },
            season=season, week=1,
        )

    @staticmethod
    def _page(title: str, body: str) -> HTMLResponse:
        return HTMLResponse(f"<h1>{title}</h1>{body}")

    def _app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(create_historical_assets_router(
            league_id=self.league_id,
            require_data=lambda: self.state["data"],
            page=self._page,
        ))
        app.include_router(create_inspection_router(
            state=self.state,
            route_provider=lambda: app.routes,
            league_id=self.league_id,
        ))
        return app

    def test_store_discovers_only_completed_canonical_trades(self) -> None:
        rows = self.store.discoverable_trade_records(self.league_id)
        self.assertEqual([row["source_record_id"] for row in rows], ["trade-canonical"])
        self.assertEqual(rows[0]["payload"]["status"], "complete")

    def test_discovery_and_detail_share_canonical_identity(self) -> None:
        with (
            patch("routes.inspect.historical_store", self.store),
            patch("routes.historical_assets.historical_store", self.store),
        ):
            client = TestClient(self._app())
            site_map = client.get("/api/inspect/site-map").json()
            included = [row for row in site_map["pages"] if not row["excluded"]]
            historical = [
                row for row in included
                if row["source_route"] == "/trades/history/{transaction_id}"
            ]
            self.assertEqual([row["route"] for row in historical], ["/trades/history/trade-canonical"])
            for page in included:
                self.assertEqual(
                    client.get(page["route"]).status_code,
                    200,
                    f"Discovered route did not resolve: {page['route']}",
                )
            self.assertEqual(client.get("/api/trades/history/trade-canonical").status_code, 200)

    def test_current_only_trade_has_machine_readable_exclusion(self) -> None:
        excluded = excluded_current_trade_pages(self.state, ("trade-canonical",))
        self.assertEqual(len(excluded), 3)
        self.assertEqual(
            {row.route for row in excluded},
            {f"/trades/history/{item}" for item in self.REPORTED_IDS},
        )
        self.assertTrue(all(
            row.exclusion_code == "canonical_historical_trade_unavailable"
            for row in excluded
        ))
        self.assertTrue(all("waiver-current" not in row.route for row in excluded))

    def test_discovery_is_deterministic_and_does_not_mutate_state(self) -> None:
        before = repr(self.state)
        app = self._app()
        first = discover_pages(
            app.routes, self.state, historical_trades=("trade-canonical",),
        )
        second = discover_pages(
            app.routes, self.state, historical_trades=("trade-canonical",),
        )
        self.assertEqual(first, second)
        self.assertEqual(repr(self.state), before)

    def test_dataset_change_and_restart_never_reuse_stale_discovery(self) -> None:
        before = self.store.dataset_version(self.league_id)
        self._append_trade("trade-new", "complete", 2027)
        after = self.store.dataset_version(self.league_id)
        self.assertNotEqual(before, after)
        self.assertEqual(
            self.store.discoverable_trade_records(self.league_id)[0]["source_record_id"],
            "trade-new",
        )
        reopened = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.assertEqual(reopened.dataset_version(self.league_id), after)
        self.assertEqual(
            reopened.discoverable_trade_records(self.league_id)[0]["source_record_id"],
            "trade-new",
        )

    def test_site_map_never_advertises_reported_current_only_ids(self) -> None:
        before_count = self.store.records(self.league_id, limit=1)[0]
        with (
            patch("routes.inspect.historical_store", self.store),
            patch("routes.historical_assets.historical_store", self.store),
        ):
            client = TestClient(self._app())
            site_map = client.get("/api/inspect/site-map").json()
            advertised = {
                row["route"] for row in site_map["pages"] if not row["excluded"]
            }
            exclusions = site_map["dynamic_discovery"]["exclusions"]
            for transaction_id in self.REPORTED_IDS:
                route = f"/trades/history/{transaction_id}"
                self.assertNotIn(route, advertised)
                self.assertEqual(client.get(route).status_code, 404)
                self.assertEqual(
                    client.get(f"/api/history/transactions?q={transaction_id}").json()["count"],
                    0,
                )
                self.assertTrue(any(row["route"] == route for row in exclusions))
        self.assertEqual(self.store.records(self.league_id, limit=1)[0], before_count)


if __name__ == "__main__":
    unittest.main()
