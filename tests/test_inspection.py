"""DINS read-only inspection contract tests."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_metadata import VERSION
from routes.inspect import create_inspection_router
from src.core.inspection import INSPECTION_SCHEMA_VERSION, InspectionEngine


def fixture_state() -> dict:
    return {
        "last_sync": "2026-08-02T12:00:00+00:00",
        "last_error": None,
        "syncing": False,
        "data": {
            "league": {"league_id": "league-1", "name": "Inspection League"},
            "players": {
                "p1": {
                    "full_name": "Example Quarterback",
                    "position": "QB",
                    "team": "BUF",
                    "age": 27,
                    "status": "Active",
                    "bye_week": 7,
                }
            },
            "teams": [{
                "roster_id": 1,
                "team_name": "Front Office One",
                "owner": "Owner One",
                "avatar": "avatar-1",
                "wins": 9,
                "losses": 5,
                "ties": 0,
                "points_for": 1800.5,
                "points_against": 1600.25,
                "max_points": 1950.75,
                "players": [{
                    "id": "p1",
                    "name": "Example Quarterback",
                    "position": "QB",
                    "team": "BUF",
                    "roster_slot": "Starter",
                    "age": 27,
                }],
                "picks_owned": [{
                    "season": "2027",
                    "round": 1,
                    "original_team": "Front Office One",
                    "is_traded": False,
                }],
            }],
            "transactions": [{
                "transaction_id": "trade-1",
                "type": "trade",
                "status": "complete",
                "created": 1770000000000,
                "roster_ids": [1, 2],
            }],
            "market_data": {
                "providers": {
                    "FantasyCalc": {
                        "p1": {
                            "value": 9000,
                            "rank": 3,
                            "updated_at": "2026-08-02T11:00:00+00:00",
                        }
                    }
                }
            },
            "trending": {
                "adds": [{"player_id": "p1", "count": 12}],
                "drops": [],
            },
        },
    }


class InspectionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = fixture_state()
        app = FastAPI()
        app.include_router(create_inspection_router(state=self.state))
        self.client = TestClient(app)

    def test_every_endpoint_uses_the_complete_versioned_contract(self) -> None:
        routes = (
            "/api/inspect",
            "/api/inspect/pages",
            "/api/inspect/team/1",
            "/api/inspect/player/p1",
            "/api/inspect/front-office/1",
            "/api/inspect/trades",
        )
        required = {
            "application_version", "inspection_schema_version", "page_name",
            "route", "sections", "cards", "tables", "charts", "buttons",
            "navigation", "links", "empty_states", "placeholder_actions",
            "warnings", "page_metrics", "last_updated",
        }
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(set(payload), required)
                self.assertEqual(payload["application_version"], VERSION)
                self.assertEqual(
                    payload["inspection_schema_version"],
                    INSPECTION_SCHEMA_VERSION,
                )
                self.assertNotIn("<html", response.text.casefold())

    def test_inspection_is_deterministic_and_does_not_mutate_state(self) -> None:
        before = copy.deepcopy(self.state)
        first = self.client.get("/api/inspect/team/1").json()
        second = self.client.get("/api/inspect/team/1").json()
        self.assertEqual(first, second)
        self.assertEqual(self.state, before)

    def test_inspection_never_synchronizes_or_runs_intelligence(self) -> None:
        with patch(
            "services.sleeper.sync_sleeper",
            side_effect=AssertionError("sync must not execute"),
        ) as sync, patch(
            "src.core.intelligence.intelligence_orchestrator.analyze",
            side_effect=AssertionError("intelligence must not execute"),
        ) as intelligence:
            for route in (
                "/api/inspect",
                "/api/inspect/team/1",
                "/api/inspect/player/p1",
                "/api/inspect/front-office/1",
                "/api/inspect/trades",
            ):
                self.assertEqual(self.client.get(route).status_code, 200)
        sync.assert_not_called()
        intelligence.assert_not_called()

    def test_page_metrics_match_rendered_contract_elements(self) -> None:
        payload = self.client.get("/api/inspect/team/1").json()
        metrics = payload["page_metrics"]
        self.assertEqual(metrics["section_count"], len(payload["sections"]))
        self.assertEqual(metrics["card_count"], len(payload["cards"]))
        self.assertEqual(metrics["table_count"], len(payload["tables"]))
        self.assertEqual(metrics["button_count"], len(payload["buttons"]))
        self.assertEqual(metrics["link_count"], len(payload["links"]))
        self.assertEqual(
            metrics["table_row_count"],
            sum(len(table["rows"]) for table in payload["tables"]),
        )

    def test_team_inspection_includes_links_and_placeholder_actions(self) -> None:
        payload = self.client.get("/api/inspect/team/1").json()
        self.assertEqual(payload["route"], "/teams/1")
        self.assertIn("/players/p1", [link["route"] for link in payload["links"]])
        self.assertEqual(payload["page_metrics"]["placeholder_action_count"], 2)
        self.assertTrue(all(action["placeholder"] for action in payload["placeholder_actions"]))

    def test_player_inspection_uses_cached_provider_data(self) -> None:
        payload = self.client.get("/api/inspect/player/p1").json()
        table = next(row for row in payload["tables"] if row["key"] == "provider_values")
        self.assertEqual(table["rows"][0]["provider"], "FantasyCalc")
        self.assertEqual(table["rows"][0]["value"], 9000)
        self.assertEqual(payload["last_updated"], self.state["last_sync"])

    def test_trade_inspection_reads_only_cached_trade_rows(self) -> None:
        self.state["data"]["transactions"].append({
            "transaction_id": "waiver-1",
            "type": "waiver",
            "status": "complete",
            "created": 1770000001000,
            "roster_ids": [1],
        })
        payload = self.client.get("/api/inspect/trades").json()
        rows = payload["tables"][0]["rows"]
        self.assertEqual([row["transaction_id"] for row in rows], ["trade-1"])

    def test_missing_cached_entities_return_explicit_404(self) -> None:
        self.assertEqual(self.client.get("/api/inspect/team/999").status_code, 404)
        self.assertEqual(self.client.get("/api/inspect/player/missing").status_code, 404)
        self.assertEqual(
            self.client.get("/api/inspect/front-office/999").status_code,
            404,
        )

    def test_empty_cache_has_meaningful_empty_states_and_warning(self) -> None:
        engine = InspectionEngine({"data": {}, "last_sync": None})
        result = engine.trades()
        self.assertEqual(result.empty_states, ("No cached trades are available.",))
        self.assertIn(
            "No successful synchronization timestamp is cached.",
            result.warnings,
        )


if __name__ == "__main__":
    unittest.main()
