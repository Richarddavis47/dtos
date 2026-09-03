from __future__ import annotations

import unittest

from src.core.trade_intelligence.bilateral import evaluate_bilateral
from src.core.trade_intelligence.lineup import optimal_legal_lineup
from src.core.trade_intelligence.models import TradeAsset, TradeProposal


def player(asset_id: str, value: int, roster: int, position: str = "WR", confidence: int = 80) -> TradeAsset:
    return TradeAsset(asset_id, "player", asset_id, position, value, value, value, value, 20, roster, value, 60, confidence)


class OptimalLegalLineupTests(unittest.TestCase):
    def test_uses_eligible_bench_player_and_limits_superflex_qbs(self) -> None:
        roster = [
            {"id": "qb1", "name": "QB 1", "position": "QB", "projected_points": 25, "roster_slot": "Starter"},
            {"id": "qb2", "name": "QB 2", "position": "QB", "projected_points": 23, "roster_slot": "Bench"},
            {"id": "qb3", "name": "QB 3", "position": "QB", "projected_points": 22, "roster_slot": "Bench"},
            {"id": "wr1", "name": "WR 1", "position": "WR", "projected_points": 9, "roster_slot": "Starter"},
            {"id": "wr2", "name": "WR 2", "position": "WR", "projected_points": 17, "roster_slot": "Bench"},
        ]
        result = optimal_legal_lineup(roster, ["QB", "WR", "SUPER_FLEX", "BN"])
        self.assertTrue(result.available)
        self.assertEqual({entry.asset_id for entry in result.entries}, {"qb1", "qb2", "wr2"})
        self.assertNotIn("qb3", {entry.asset_id for entry in result.entries})

    def test_missing_projections_are_unavailable_not_zero(self) -> None:
        result = optimal_legal_lineup([{"id": "p", "position": "WR"}], ["WR"])
        self.assertFalse(result.available)
        self.assertIsNone(result.projected_points)


class BilateralTradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.active = {"roster_id": 1, "players": [{"id": "a", "name": "A", "position": "WR", "projected_points": 15}]}
        self.partner = {"roster_id": 2, "players": [{"id": "b", "name": "B", "position": "WR", "projected_points": 16}]}
        self.league = {"roster_positions": ["WR"]}

    def evaluate(self, sent=(player("a", 100, 1),), received=(player("b", 100, 2),)):
        proposal = TradeProposal(1, 2, sent, received, "Manual")
        return evaluate_bilateral(proposal, active_team=self.active, partner_team=self.partner, league=self.league, ownership={"a": 1, "b": 2})

    def test_same_construction_has_workflow_independent_bilateral_contract(self) -> None:
        result = self.evaluate()
        self.assertEqual(result["recommendation"], "WORTH PURSUING")
        self.assertTrue(result["generated_trade_eligible"])
        self.assertTrue(result["why_you_would_do_it"])
        self.assertTrue(result["why_they_would_do_it"])
        self.assertEqual(set(result["dimensions"]), {"value_fairness", "strategic_fit", "counterparty_plausibility", "historical_counterparty_evidence", "package_quality", "best_for", "confidence"})
        self.assertEqual(result["lineup_impact"]["comparison"], "optimal_legal_lineup_before_vs_after")

    def test_manual_illegal_trade_is_evaluated_but_not_executable(self) -> None:
        proposal = TradeProposal(1, 2, (player("b", 100, 2),), (player("a", 100, 1),), "Manual")
        result = evaluate_bilateral(proposal, active_team=self.active, partner_team=self.partner, league=self.league, ownership={"a": 1, "b": 2})
        self.assertEqual(result["recommendation"], "REJECT")
        self.assertFalse(result["legal"])
        self.assertFalse(result["generated_trade_eligible"])

    def test_calculator_stuffing_fails_package_quality(self) -> None:
        sent = (player("elite", 1000, 1),)
        received = tuple(player(f"piece-{index}", 250, 2) for index in range(4))
        proposal = TradeProposal(1, 2, sent, received, "Manual")
        result = evaluate_bilateral(proposal, active_team=self.active, partner_team=self.partner, league=self.league)
        self.assertEqual(result["dimensions"]["package_quality"]["active"]["assessment"], "POOR")
        self.assertFalse(result["generated_trade_eligible"])

    def test_confidence_is_qualitative(self) -> None:
        result = self.evaluate(sent=(player("a", 100, 1, confidence=40),))
        self.assertEqual(result["dimensions"]["confidence"]["assessment"], "LOW")

    def test_neutral_market_value_is_not_rewritten_by_team_fit(self) -> None:
        sent = (TradeAsset("hurts", "player", "Jalen Hurts", "QB", 735, 600, 719, 900, 20, 1, 719, 80, 85),)
        received = (TradeAsset("allen", "player", "Josh Allen", "QB", 896, 600, 954, 400, 20, 2, 954, 90, 90),)
        result = self.evaluate(sent=sent, received=received)
        self.assertEqual(result["values"], {"sent": 719.0, "received": 954.0, "ratio": 1.327})
        self.assertEqual(result["dimensions"]["value_fairness"]["assessment"], "ACTIVE ADVANTAGE")
        self.assertEqual(result["recommendation"], "REJECT")
        self.assertFalse(result["generated_trade_eligible"])

    def test_ratio_alone_cannot_create_worth_pursuing(self) -> None:
        active = {"roster_id": 1, "players": [{"id": "a", "position": "WR"}]}
        partner = {"roster_id": 2, "players": [{"id": "b", "position": "WR"}]}
        proposal = TradeProposal(1, 2, (player("a", 500, 1),), (player("b", 500, 2),), "Manual")
        result = evaluate_bilateral(proposal, active_team=active, partner_team=partner, league={"roster_positions": []})
        self.assertEqual(result["recommendation"], "NOT WORTH IT")
        self.assertEqual(result["dimensions"]["counterparty_plausibility"]["assessment"], "DOES NOT CLEAR")

    def test_elite_superflex_qb_downgrade_requires_compensation(self) -> None:
        elite = player("elite", 900, 2, "QB")
        lower = player("lower", 700, 1, "QB")
        proposal = TradeProposal(1, 2, (lower,), (elite,), "Manual")
        result = evaluate_bilateral(proposal, active_team=self.active, partner_team=self.partner, league={"roster_positions": ["QB", "SUPER_FLEX"]})
        self.assertEqual(result["recommendation"], "REJECT")
        self.assertIn(result["dimensions"]["value_fairness"]["assessment"], {"ACTIVE ADVANTAGE", "PARTNER ADVANTAGE"})
        self.assertFalse(result["generated_trade_eligible"])


if __name__ == "__main__":
    unittest.main()
