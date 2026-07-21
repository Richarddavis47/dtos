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
        self.assertEqual(page.status_code, 200)
        self.assertIn("Trade Intelligence v1", page.text)
        self.assertIn("Open Trade Dossier", page.text)
        self.assertNotIn("<details open", page.text)


if __name__ == "__main__":
    unittest.main()
