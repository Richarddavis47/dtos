"""Contract tests for deterministic Trade Intelligence v1."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.trades import create_trades_router
from src.core.asset_intelligence import evaluate_pick, evaluate_player
from src.core.trade_intelligence import TradeAsset, TradePriority, trade_intelligence
from src.core.trade_intelligence.engine.trade_generator import generate_proposals
from src.core.valuation import packages


def fixture_data() -> dict:
    database = {}
    teams = []
    positions = ("QB", "QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "TE")
    for roster_id in (1, 2, 3):
        players = []
        for index, position in enumerate(positions):
            player_id = f"{roster_id}-{position}-{index}"
            database[player_id] = {"full_name": f"Player {player_id}", "position": position, "team": "BUF", "age": 22 + index % 8}
            players.append({"id": player_id, "name": f"Player {player_id}", "position": position, "team": "BUF", "roster_slot": "Starter" if index < 5 else "Bench"})
        teams.append({
            "roster_id": roster_id,
            "owner": f"Owner {roster_id}",
            "team_name": f"Team {roster_id}",
            "wins": 7 - roster_id,
            "losses": 3 + roster_id,
            "ties": 0,
            "points_for": 1100 - roster_id * 50,
            "points_against": 900,
            "max_points": 1250 - roster_id * 40,
            "players": players,
            "picks_owned": [
                {"season": 2027, "round": round_number, "original_team": f"Team {roster_id}", "original_roster_id": roster_id, "current_owner_id": roster_id}
                for round_number in (1, 2, 3, 4)
            ],
        })
    return {
        "league": {"league_id": "league-1", "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "SUPER_FLEX"]},
        "players": database,
        "teams": teams,
        "transactions": [{"type": "trade", "roster_ids": [1, 2]}],
        "traded_picks": [],
    }


def asset(asset_id: str, kind: str, value: int, source: int = 1) -> TradeAsset:
    return TradeAsset(asset_id, kind, asset_id, "WR" if kind == "player" else None, value, value, 50, value, 25, source)


class TradeGeneratorTests(unittest.TestCase):
    def test_generator_supports_every_documented_package_shape_with_balance(self) -> None:
        outgoing = (
            asset("out-p50", "player", 50), asset("out-p25a", "player", 25), asset("out-p25b", "player", 25),
            asset("out-k25a", "pick", 25), asset("out-k25b", "pick", 25),
        )
        incoming = (
            asset("in-p50", "player", 50, 2), asset("in-p25a", "player", 25, 2), asset("in-p25b", "player", 25, 2),
            asset("in-k25a", "pick", 25, 2), asset("in-k25b", "pick", 25, 2),
        )
        proposals = generate_proposals(1, 2, outgoing, incoming)
        self.assertEqual(
            {proposal.package_type for proposal in proposals},
            {"1-for-1", "2-for-1", "3-for-2", "Player + Pick", "Pick Package", "Multi-Asset"},
        )
        for proposal in proposals:
            sent = sum((item.dynasty_value + item.team_fit_value) / 2 for item in proposal.assets_sent)
            received = sum((item.dynasty_value + item.team_fit_value) / 2 for item in proposal.assets_received)
            self.assertGreaterEqual(received / sent, 0.80)
            self.assertLessEqual(received / sent, 1.25)

    def test_generator_reuses_package_values_without_changing_output(self) -> None:
        outgoing = tuple(
            asset(f"out-{index}", "player" if index < 8 else "pick", 20 + index)
            for index in range(12)
        )
        incoming = tuple(
            asset(
                f"in-{index}",
                "player" if index < 8 else "pick",
                20 + index,
                2,
            )
            for index in range(12)
        )
        with patch(
            "src.core.trade_intelligence.engine.trade_generator.adjusted_package_value",
            wraps=packages.adjusted_package_value,
        ) as package_value:
            first = generate_proposals(1, 2, outgoing, incoming)
        second = generate_proposals(1, 2, outgoing, incoming)
        self.assertEqual(first, second)
        self.assertLess(package_value.call_count, 10_000)


class TradeIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()

    def test_engine_produces_contextual_explainable_dossiers(self) -> None:
        dossiers = trade_intelligence.opportunities(self.data, 1)
        self.assertTrue(dossiers)
        for dossier in dossiers:
            self.assertNotEqual(dossier.proposal.active_roster_id, dossier.proposal.partner_roster_id)
            self.assertIn(dossier.recommendation.priority, set(TradePriority))
            self.assertTrue(dossier.recommendation.evidence)
            self.assertTrue(dossier.partner.evidence)
            self.assertTrue(dossier.impact.evidence)
            self.assertIsNone(dossier.recommendation.acceptance_likelihood)
            self.assertTrue(dossier.negotiation.opening_offer)
            self.assertTrue(dossier.negotiation.minimum_offer)
            self.assertIn("1.25", dossier.negotiation.maximum_offer)
            self.assertTrue(dossier.negotiation.walk_away_point)
            self.assertIn("Active", dossier.why_active_improves)
            self.assertIn("context", dossier.why_partner_improves)

    def test_current_and_future_impacts_remain_independent(self) -> None:
        dossier = trade_intelligence.opportunities(self.data, 1)[0]
        self.assertIsInstance(dossier.impact.current_outlook, int)
        self.assertIsInstance(dossier.impact.future_outlook, int)
        self.assertIn("not a probability", " ".join(dossier.impact.limitations))

    def test_recommendations_are_unique_non_contradictory_and_explainable(self) -> None:
        dossiers = trade_intelligence.opportunities(self.data, 1)
        signatures = {
            (
                dossier.proposal.partner_roster_id,
                tuple(asset.asset_id for asset in dossier.proposal.assets_sent),
                tuple(asset.asset_id for asset in dossier.proposal.assets_received),
            )
            for dossier in dossiers
        }
        self.assertEqual(len(signatures), len(dossiers))
        for dossier in dossiers:
            sent = {asset.asset_id for asset in dossier.proposal.assets_sent}
            received = {asset.asset_id for asset in dossier.proposal.assets_received}
            self.assertTrue(sent.isdisjoint(received))
            self.assertTrue(dossier.recommendation.summary)
            self.assertTrue(dossier.recommendation.evidence)
            self.assertGreaterEqual(dossier.recommendation.confidence, 0)
            self.assertLessEqual(dossier.recommendation.confidence, 100)

    def test_engine_consumes_asset_intelligence_evaluators(self) -> None:
        with patch("src.core.trade_intelligence.market.trade_market.evaluate_player", wraps=evaluate_player) as players, patch("src.core.trade_intelligence.market.trade_market.evaluate_pick", wraps=evaluate_pick) as picks:
            trade_intelligence.opportunities(self.data, 1)
        self.assertGreater(players.call_count, 0)
        self.assertGreater(picks.call_count, 0)

    def test_invalid_front_office_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "not available"):
            trade_intelligence.opportunities(self.data, 999)

    def test_api_and_page_use_same_opportunity_contract(self) -> None:
        async def noop() -> None:
            return None

        from fastapi.responses import HTMLResponse
        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=noop, require_data=lambda: self.data, page=lambda _, body: HTMLResponse(body)))
        client = TestClient(app)
        api = client.get("/api/trades?front_office=1")
        page = client.get("/trades?front_office=1")
        self.assertEqual(api.status_code, 200)
        self.assertGreater(api.json()["count"], 0)
        self.assertIsNotNone(api.json()["decision_confidence"])
        self.assertEqual(api.json()["availability"], "available")
        self.assertTrue(api.json()["brain_snapshot_id"])
        self.assertTrue(api.json()["decision_provenance"])
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-dtos-component="recommendation"', page.text)
        self.assertIn("Active Front Office", page.text)
        self.assertIn("Open Trade Dossier", page.text)
        self.assertNotIn("<details open", page.text)

    def test_trade_center_exposes_four_shared_workflows_and_manual_evaluation(self) -> None:
        async def noop() -> None:
            return None

        from fastapi.responses import HTMLResponse
        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=noop, require_data=lambda: self.data, page=lambda _, body: HTMLResponse(body)))
        client = TestClient(app)
        workspace = client.get("/api/trades/workspace?front_office=1")
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual({item["id"] for item in workspace.json()["workflows"]}, {"create", "trade_for", "shop", "recommended"})
        teams = {team["roster_id"]: team for team in workspace.json()["teams"]}
        sent = teams[1]["assets"][0]["asset_id"]
        received = teams[2]["assets"][0]["asset_id"]
        response = client.post("/api/trades/evaluate", json={"workflow": "create", "active_roster_id": 1, "partner_roster_id": 2, "assets_sent": [sent], "assets_received": [received]})
        self.assertEqual(response.status_code, 200)
        evaluation = response.json()["evaluation"]
        self.assertTrue(evaluation["provenance"]["workflow_independent"])
        self.assertIn(evaluation["recommendation"], {"SMASH ACCEPT", "WORTH PURSUING", "FAIR / OPTIONAL", "NOT WORTH IT", "REJECT"})
        self.assertIn(evaluation["dimensions"]["confidence"]["assessment"], {"HIGH", "MEDIUM", "LOW"})
        page = client.get("/trades?front_office=1")
        self.assertIn("Create Trade", page.text)
        self.assertIn("Trade For", page.text)
        self.assertIn("Shop Asset", page.text)
        self.assertIn("Recommended Trades", page.text)
        for route, marker in (("/trades/create", "create"), ("/trades/trade-for", "trade-for"), ("/trades/shop", "shop"), ("/trades/recommended", "recommended")):
            workflow_page = client.get(f"{route}?front_office=1")
            self.assertEqual(workflow_page.status_code, 200)
            self.assertIn(f'data-trade-workflow="{marker}"', workflow_page.text)
            self.assertIn("does not submit offers", workflow_page.text)
        autocomplete = client.get("/api/trades/assets?q=Player&front_office=1")
        self.assertEqual(autocomplete.status_code, 200)
        self.assertTrue(autocomplete.json()["results"])
        self.assertIn("owner_roster_id", autocomplete.json()["results"][0])
        comparison = client.post("/api/trades/compare", json={"proposals": [
            {"workflow": "create", "active_roster_id": 1, "partner_roster_id": 2, "assets_sent": [sent], "assets_received": [received]},
            {"workflow": "trade_for", "active_roster_id": 1, "partner_roster_id": 2, "assets_sent": [sent], "assets_received": [received]},
        ]})
        self.assertEqual(comparison.status_code, 200)
        identities = {row["evaluation"]["provenance"]["evaluation_id"] for row in comparison.json()["comparisons"]}
        self.assertEqual(len(identities), 1)


if __name__ == "__main__":
    unittest.main()
