"""v1.10.53 Trade Builder and target-preserving repair regressions."""
from __future__ import annotations

import unittest

from components.trade_intelligence import trade_workflow

from services.trade_intelligence import (
    assist_trade_request,
    autocomplete_trade_assets,
    build_trade_workspace,
    create_trade_alternatives,
    evaluate_trade_request,
    generate_trade_workflow,
)
from tests.test_trade_intelligence import fixture_data


class TradeRepairContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.workspace = build_trade_workspace(self.data, 1)
        self.sent = self.workspace["pools"][1][0].asset_id
        self.target = self.workspace["pools"][2][0].asset_id
        self.payload = {
            "active_roster_id": 1,
            "partner_roster_id": 2,
            "assets_sent": [self.sent],
            "assets_received": [self.target],
        }

    def test_make_this_trade_work_never_drops_the_requested_target(self) -> None:
        result = assist_trade_request(self.data, {
            **self.payload, "instruction": "make this trade work",
        })
        self.assertTrue(result["target_preserved"])
        for row in result["results"]:
            if row["repair_type"] != "ALTERNATIVE TARGET":
                self.assertIn(self.target, row["proposal"]["assets_received"])

    def test_aj_brown_for_justin_jefferson_repair_cannot_degrade_to_brown_for_a_pick(self) -> None:
        data = fixture_data()
        data["teams"][0]["players"][0].update(name="A.J. Brown", position="WR")
        data["players"]["1-QB-0"].update(full_name="A.J. Brown", position="WR")
        data["teams"][1]["players"][0].update(name="Justin Jefferson", position="WR")
        data["players"]["2-QB-0"].update(full_name="Justin Jefferson", position="WR")
        result = assist_trade_request(data, {
            "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": ["1-QB-0"], "assets_received": ["2-QB-0"],
            "instruction": "make this trade work",
        })
        for row in result["results"]:
            if row["repair_type"] != "ALTERNATIVE TARGET":
                self.assertIn("2-QB-0", row["proposal"]["assets_received"])
                self.assertFalse(
                    tuple(row["proposal"]["assets_sent"]) == ("1-QB-0",)
                    and all(asset.startswith("2027-") for asset in row["proposal"]["assets_received"]),
                )

    def test_alternative_construction_preserves_target_and_only_named_mode_may_change_it(self) -> None:
        result = assist_trade_request(self.data, {
            **self.payload, "instruction": "alternative construction",
        })
        for row in result["results"]:
            if row["repair_type"] in {"MAKE THIS TRADE WORK", "ALTERNATIVE CONSTRUCTION"}:
                self.assertIn(self.target, row["proposal"]["assets_received"])
            elif row["repair_type"] == "ALTERNATIVE TARGET":
                self.assertNotEqual(set(row["proposal"]["assets_received"]), {self.target})

    def test_create_alternatives_preserve_the_declared_target(self) -> None:
        result = create_trade_alternatives(self.data, self.payload)
        self.assertEqual(result["target_asset_id"], self.target)
        self.assertTrue(all(self.target in row["proposal"]["assets_received"] for row in result["results"]))

    def test_proposal_presentation_contains_actual_construction_and_manager_context(self) -> None:
        result = evaluate_trade_request(self.data, self.payload)
        presentation = result["proposal_presentation"]
        self.assertEqual(presentation["send"][0]["asset_id"], self.sent)
        self.assertEqual(presentation["receive"][0]["asset_id"], self.target)
        self.assertTrue(presentation["partner_team_name"])
        self.assertIn("best_for", presentation)
        self.assertIn("confidence", presentation)

    def test_generated_and_alternative_cards_show_construction_before_opening(self) -> None:
        html = trade_workflow({
            "active_team": self.data["teams"][0], "teams": self.data["teams"],
        }, "trade-for")
        self.assertGreaterEqual(html.count("row.proposal_presentation"), 2)
        self.assertIn("'Send '+send+' → Receive '+receive", html)

    def test_player_picker_uses_one_neutral_market_positional_rank_contract(self) -> None:
        players = [asset for pool in self.workspace["pools"].values() for asset in pool if asset.kind == "player"]
        ranks = [asset.positional_rank for asset in players]
        self.assertTrue(all(rank and rank[:2] in {"QB", "RB", "WR", "TE"} and rank[2:].isdigit() for rank in ranks))
        self.assertEqual(len(ranks), len(set(ranks)))
        search = autocomplete_trade_assets(self.data, players[0].label, 1)
        row = next(item for item in search["results"] if item["asset_id"] == players[0].asset_id)
        self.assertEqual(row["positional_rank"], players[0].positional_rank)
        self.assertEqual(row["market_value"], players[0].trade_value)

    def test_no_path_trade_for_is_honest_and_actionable(self) -> None:
        result = generate_trade_workflow(self.data, {
            "workflow": "trade_for", "active_roster_id": 1,
            "asset_id": self.target, "protected_assets": [asset.asset_id for asset in self.workspace["pools"][1]],
        })
        self.assertEqual(result["count"], 0)
        self.assertEqual(len(result["next_paths"]), 3)
        self.assertIn("No legitimate", result["quiet_state"])
        self.assertEqual(result["provider_requests"] if "provider_requests" in result else 0, 0)


if __name__ == "__main__":
    unittest.main()
