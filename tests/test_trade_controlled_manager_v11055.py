"""v1.10.55 controlled-manager, discovery, and mobile contracts."""
from __future__ import annotations

import copy
import unittest

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from components.trade_intelligence import trade_center, trade_workflow
from routes.trades import create_trades_router
from services.trade_intelligence import (
    ManagerContextRequired,
    build_trade_center,
    build_trade_workflow_context,
    build_trade_workspace,
    evaluate_trade_request,
    generate_trade_workflow,
)
from tests.test_trade_intelligence import fixture_data


class ControlledManagerContextTests(unittest.TestCase):
    def test_missing_context_never_selects_first_roster(self) -> None:
        with self.assertRaisesRegex(ManagerContextRequired, "Choose the franchise"):
            build_trade_workspace(fixture_data())

    def test_explicit_manager_controls_assets_and_identity(self) -> None:
        data = fixture_data()
        first = build_trade_workspace(data, 1)
        third = build_trade_workspace(data, 3)
        self.assertEqual(first["active_roster_id"], 1)
        self.assertEqual(third["active_roster_id"], 3)
        self.assertNotEqual(
            {asset.asset_id for asset in first["pools"][1]},
            {asset.asset_id for asset in third["pools"][3]},
        )
        self.assertEqual(third["manager_context"].source, "explicit_front_office")

    def test_context_is_league_scoped(self) -> None:
        data = fixture_data()
        other = copy.deepcopy(data)
        other["league"]["league_id"] = "private-league-b"
        self.assertNotEqual(
            build_trade_workspace(data, 2)["manager_context"].league_id,
            build_trade_workspace(other, 2)["manager_context"].league_id,
        )

    def test_missing_context_routes_render_selection_not_another_manager(self) -> None:
        async def noop() -> None:
            return None

        app = FastAPI()
        app.include_router(create_trades_router(
            ensure_fresh=noop,
            require_data=fixture_data,
            page=lambda _, body: HTMLResponse(body),
        ))
        client = TestClient(app)
        page = client.get("/trades")
        api = client.get("/api/trades")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Choose your franchise", page.text)
        self.assertNotIn("Team 1</h2>", page.text)
        self.assertEqual(api.json()["status"], "manager_context_required")
        self.assertIsNone(api.json()["active_front_office"])
        selected = client.get("/api/trades?front_office=2")
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["active_front_office"], 2)


class TradeDiscoveryAndPresentationTests(unittest.TestCase):
    def test_same_target_uses_each_controlled_managers_own_assets(self) -> None:
        data = fixture_data()
        target = build_trade_workspace(data, 1)["pools"][2][0].asset_id
        for manager in (1, 3):
            result = generate_trade_workflow(data, {
                "workflow": "trade_for", "active_roster_id": manager,
                "asset_id": target,
            })
            self.assertGreater(result["count"], 0)
            for row in result["results"]:
                self.assertEqual(row["proposal"]["active_roster_id"], manager)
                self.assertTrue(all(
                    asset_id.startswith(f"{manager}-") or asset_id.endswith(f"-{manager}")
                    for asset_id in row["proposal"]["assets_sent"]
                ))

    def test_honest_no_path_includes_bounded_search_evidence(self) -> None:
        data = fixture_data()
        target = build_trade_workspace(data, 1)["pools"][2][0].asset_id
        excluded = [asset.asset_id for asset in build_trade_workspace(data, 1)["pools"][1]]
        result = generate_trade_workflow(data, {
            "workflow": "trade_for", "active_roster_id": 1,
            "asset_id": target, "excluded_assets": excluded,
        })
        self.assertEqual(result["count"], 0)
        self.assertTrue(result["search_evidence"]["bounded"])
        self.assertEqual(result["search_evidence"]["package_shapes"], 6)
        self.assertEqual(result["closest_path"]["target_asset_id"], target)
        self.assertGreater(len(result["next_paths"]), 0)

    def test_wrong_side_ownership_is_rejected(self) -> None:
        data = fixture_data()
        workspace = build_trade_workspace(data, 1)
        with self.assertRaisesRegex(ValueError, "canonical ownership"):
            evaluate_trade_request(data, {
                "active_roster_id": 1, "partner_roster_id": 2,
                "assets_sent": [workspace["pools"][2][0].asset_id],
                "assets_received": [workspace["pools"][1][0].asset_id],
            }, workspace=workspace)

    def test_mobile_workflow_exposes_asset_first_visual_contract(self) -> None:
        html = trade_workflow(build_trade_workflow_context(fixture_data(), 1), "trade-for")
        for contract in (
            "ti-roster-browser", "ti-asset-tile", "ti-pick-tile",
            "headshot_url", "League assets", "trade_value", "YOUR TEAM",
            "THEIR TEAM", "PICKS", "Market Balance", "NEAR FAIR",
        ):
            self.assertIn(contract, html)
        self.assertIn("@media(max-width:760px)", html)

    def test_recommendation_cards_show_recognizable_assets_before_open(self) -> None:
        html = trade_center(build_trade_center(fixture_data(), 1))
        self.assertIn("ti-proposal-asset", html)
        self.assertIn("You send", html)
        self.assertIn("You receive", html)
        self.assertIn("Why you", html)


if __name__ == "__main__":
    unittest.main()
