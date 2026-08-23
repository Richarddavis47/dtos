"""v1.10.50 value-integrity and manager-workflow regressions."""
from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.trades import create_trades_router
from components.trade_intelligence import trade_workflow
from services.trade_intelligence import (
    assist_trade_request,
    build_trade_center,
    build_trade_workspace,
    create_trade_alternatives,
    generate_trade_workflow,
)
from src.core.asset_intelligence import AssetContext, evaluate_player
from src.core.trade_intelligence.bilateral import evaluate_bilateral
from src.core.trade_intelligence.models import TradeAsset, TradeProposal
from tests.test_trade_intelligence import fixture_data


class TradeValueIntegrityTests(unittest.TestCase):
    def test_age_only_intrinsic_signal_cannot_create_premium_prospect_value(self) -> None:
        context = AssetContext("league", 1, {}, "Contender", "Neutral")
        young = evaluate_player({"player_id": "young", "full_name": "Young", "position": "WR", "team": "BUF", "age": 21}, context)
        veteran = evaluate_player({"player_id": "vet", "full_name": "Veteran", "position": "WR", "team": "MIN", "age": 28}, context)
        self.assertLessEqual(young.core_values.dynasty.score, 72)
        self.assertLessEqual(abs(young.core_values.dynasty.score - veteran.core_values.dynasty.score), 20)
        self.assertIn("must not replace neutral market value", young.core_values.dynasty.limitations[0])

    def test_unknown_future_first_does_not_exceed_elite_neutral_market_fixture(self) -> None:
        workspace = build_trade_workspace(fixture_data(), 1)
        unknown_first = next(asset for asset in workspace["pools"][1] if asset.kind == "pick" and asset.round == 1)
        self.assertEqual(unknown_first.projected_range, "UNKNOWN")
        self.assertLess(unknown_first.trade_value, 900)

    def test_projected_range_changes_pick_value_without_exact_slot_fabrication(self) -> None:
        data = fixture_data()
        for roster_id in (1, 2, 3):
            data["teams"][roster_id - 1]["picks_owned"] = []
        data["teams"].append({
            "roster_id": 4, "owner": "Owner 4", "team_name": "Team 4",
            "wins": 0, "losses": 10, "points_for": 400, "max_points": 500,
            "players": [], "picks_owned": [],
        })
        data["teams"][0]["picks_owned"] = [
            {"season": 2027, "round": 1, "original_roster_id": 4, "current_owner_id": 1},
            {"season": 2027, "round": 1, "original_roster_id": 1, "current_owner_id": 1},
        ]
        picks = [asset for asset in build_trade_workspace(data, 1)["pools"][1] if asset.kind == "pick"]
        self.assertEqual({pick.projected_range for pick in picks}, {"EARLY", "LATE"})
        self.assertEqual({pick.projected_range_confidence for pick in picks}, {"MEDIUM"})
        self.assertEqual({pick.exact_slot for pick in picks}, {None})
        self.assertEqual(len({pick.trade_value for pick in picks}), 2)


class TradeWorkflowConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()

    def test_natural_language_protection_is_applied_to_assisted_search(self) -> None:
        workspace = build_trade_workspace(self.data, 1)
        protected = workspace["pools"][1][0]
        received = workspace["pools"][2][0]
        result = assist_trade_request(self.data, {
            "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": [protected.asset_id], "assets_received": [received.asset_id],
            "instruction": f"Don't trade {protected.label}. Use picks instead.",
        })
        self.assertIn(protected.asset_id, result["constraints"]["protected_assets"])
        for row in result["results"]:
            self.assertNotIn(protected.asset_id, row["proposal"]["assets_sent"])

    def test_assist_endpoint_executes_calculated_workflow(self) -> None:
        async def noop() -> None:
            return None

        app = FastAPI()
        app.include_router(create_trades_router(
            ensure_fresh=noop,
            require_data=lambda: self.data,
            page=lambda _, body: HTMLResponse(body),
        ))
        client = TestClient(app)
        workspace = client.get("/api/trades/workspace?front_office=1").json()
        teams = {team["roster_id"]: team for team in workspace["teams"]}
        response = client.post("/api/trades/assist", json={
            "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": [teams[1]["assets"][0]["asset_id"]],
            "assets_received": [teams[2]["assets"][0]["asset_id"]],
            "instruction": "make this trade work",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["calculated"])
        self.assertGreater(response.json()["count"], 0)

    def test_manager_ui_exposes_real_multi_asset_edit_adjust_and_repair_controls(self) -> None:
        async def noop() -> None:
            return None

        app = FastAPI()
        app.include_router(create_trades_router(
            ensure_fresh=noop,
            require_data=lambda: self.data,
            page=lambda _, body: HTMLResponse(body),
        ))
        text = TestClient(app).get("/trades/create?front_office=1").text
        self.assertEqual(text.count("+ Add player or pick"), 2)
        self.assertIn("trade-sent-chips", text)
        self.assertIn("trade-received-chips", text)
        self.assertIn("Generate revised offer", text)
        for label in (
            "Keep this player", "Do not trade this pick", "Replace this asset",
            "Use WRs instead", "Use RBs instead", "Use picks instead", "Add a pick",
            "Get another player back", "Make it cheaper", "Make it younger",
            "Make it more win-now", "Expand the trade",
        ):
            self.assertIn(label, text)
        self.assertIn("runAssist(path)", text)
        self.assertIn("Market fairness uses neutral canonical values", text)
        self.assertNotIn("Use protected and excluded assets to constrain the next generated search.", text)

    def test_ambiguous_structured_reference_fails_safely(self) -> None:
        workspace = build_trade_workspace(self.data, 1)
        result = assist_trade_request(self.data, {
            "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": [workspace["pools"][1][0].asset_id],
            "assets_received": [workspace["pools"][2][0].asset_id],
            "instruction": "Keep this player",
        })
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["interpretation_error"], "specific_asset_required")
        self.assertIn("specific player or pick", result["quiet_state"])

    def test_seller_side_elite_superflex_qb_downgrade_fails_bilateral_gate(self) -> None:
        hurts = TradeAsset("hurts", "player", "Jalen Hurts", "QB", 720, 720, 720, 720, 10, 1, trade_value=720)
        kincaid = TradeAsset("kincaid", "player", "Dalton Kincaid", "TE", 280, 280, 280, 280, 15, 2, trade_value=280)
        unknown_first = TradeAsset(
            "2027-R1-2", "pick", "2027 Round 1", None, 360, 0, 360, 360, 30, 2,
            trade_value=360, projected_range="UNKNOWN", projected_range_confidence="LOW",
        )
        result = evaluate_bilateral(
            TradeProposal(1, 2, (hurts,), (kincaid, unknown_first), "Player + Pick"),
            active_team={"roster_id": 1, "players": [{"id": "hurts", "position": "QB", "projected_points": 22}]},
            partner_team={"roster_id": 2, "players": [{"id": "kincaid", "position": "TE", "projected_points": 10}]},
            league={"roster_positions": ["QB", "RB", "WR", "TE", "SUPER_FLEX"]},
            ownership={"hurts": 1, "kincaid": 2, "2027-R1-2": 2},
        )
        self.assertEqual(result["perspectives"]["bilateral_reality"], "NOT REALISTIC")
        self.assertEqual(result["dimensions"]["confidence"]["assessment"], "LOW")
        self.assertNotEqual(result["recommendation"], "WORTH PURSUING")

    def test_preloaded_workflows_and_picker_use_ownership_aware_auto_run(self) -> None:
        view = build_trade_center(self.data, 1)
        owned = build_trade_workspace(self.data, 1)["pools"][1][0].asset_id
        external = build_trade_workspace(self.data, 1)["pools"][2][0].asset_id
        shop = trade_workflow(view, "shop", owned, 1)
        trade_for = trade_workflow(view, "trade-for", external, 2)
        self.assertIn(f'data-preload-asset="{owned}"', shop)
        self.assertIn(f'data-preload-asset="{external}"', trade_for)
        self.assertIn('data-owner-roster="2"', trade_for)
        self.assertIn("await run()", shop)
        self.assertIn("onchange=()=>add('sent',s)", shop)
        self.assertIn("More adjustment options", shop)

    def test_shop_searches_all_counterparties_and_create_alternatives_are_bounded(self) -> None:
        workspace = build_trade_workspace(self.data, 1)
        owned = workspace["pools"][1][0].asset_id
        shop = generate_trade_workflow(self.data, {
            "workflow": "shop", "active_roster_id": 1, "asset_id": owned,
        })
        self.assertLessEqual(shop["count"], 5)
        self.assertTrue(all(owned in row["proposal"]["assets_sent"] for row in shop["results"]))
        sent, received = workspace["pools"][1][0].asset_id, workspace["pools"][2][0].asset_id
        alternatives = create_trade_alternatives(self.data, {
            "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": [sent], "assets_received": [received],
        })
        self.assertLessEqual(alternatives["count"], 3)
        self.assertEqual(alternatives["provider_requests"], 0)
        self.assertEqual(alternatives["asset_market_constructions"], 0)


if __name__ == "__main__":
    unittest.main()
