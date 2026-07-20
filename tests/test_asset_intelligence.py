"""Contract tests for deterministic Asset Intelligence v1."""
from __future__ import annotations

import unittest

from components.asset_intelligence import player_dossier
from src.core.asset_intelligence import AssetContext, evaluate_pick, evaluate_player
from src.core.asset_intelligence.portfolio import evaluate_pick_portfolio, evaluate_player_portfolio


class AssetIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.player = {
            "id": "p1", "full_name": "Traceable Player", "position": "RB", "team": "BUF",
            "age": 23, "years_exp": 2, "injury_status": None, "bye_week": 7,
        }
        self.contender = AssetContext(
            "league-1", 1, {"roster_positions": ["QB", "RB", "WR", "TE", "SUPER_FLEX"]},
            "Championship Window", "Compete", ("RB",), {"QB": 3, "RB": 1, "WR": 7, "TE": 2},
        )

    def test_player_dossier_has_four_independent_traceable_values(self) -> None:
        report = evaluate_player(self.player, self.contender)
        values = report.core_values
        self.assertEqual(
            {values.dynasty.name, values.redraft.name, values.market.name, values.team_fit.name},
            {"Dynasty Value", "Redraft Value", "Market Value", "Team Fit Value"},
        )
        self.assertNotEqual(values.dynasty.score, values.redraft.score)
        for value in (values.dynasty, values.redraft, values.market, values.team_fit):
            self.assertGreaterEqual(value.score, 0)
            self.assertLessEqual(value.score, 100)
            self.assertTrue(value.evidence)
            for evidence in value.evidence:
                self.assertTrue(evidence.factor)
                self.assertTrue(evidence.observed_value)
                self.assertTrue(evidence.explanation)
                self.assertTrue(evidence.source)

    def test_team_fit_changes_with_front_office_context(self) -> None:
        contender = evaluate_player(self.player, self.contender)
        rebuilder_context = AssetContext(
            "league-1", 2, self.contender.league_settings, "Rebuild Window", "Rebuild",
            (), {"QB": 2, "RB": 5, "WR": 6, "TE": 2},
        )
        rebuilder = evaluate_player(self.player, rebuilder_context)
        self.assertNotEqual(contender.core_values.team_fit.score, rebuilder.core_values.team_fit.score)
        self.assertIn("Front Office 1", contender.core_values.team_fit.summary)
        self.assertIn("Front Office 2", rebuilder.core_values.team_fit.summary)

    def test_missing_market_and_production_data_are_not_fabricated(self) -> None:
        report = evaluate_player(self.player, self.contender)
        self.assertEqual(report.core_values.market.score, 50)
        self.assertFalse(report.core_values.market.evidence[0].available)
        limitations = " ".join(report.limitations).lower()
        self.assertIn("production", limitations)
        self.assertIn("market", limitations)

    def test_recommendation_and_ui_evidence_are_collapsed(self) -> None:
        report = evaluate_player(self.player, self.contender)
        self.assertIn(report.recommendation.action, {"Buy", "Hold", "Sell", "Shop Aggressively"})
        self.assertTrue(report.recommendation.evidence)
        html = player_dossier(report, {"roster_id": 1, "owner": "Alex"}, [{"roster_id": 1, "owner": "Alex"}])
        self.assertIn("Supporting Evidence", html)
        self.assertIn("<details", html)
        self.assertNotIn("<details open", html)

    def test_pick_report_exposes_value_risk_range_horizon_and_strategy(self) -> None:
        report = evaluate_pick(
            {"season": 2028, "round": 1, "original_team": "Alpha", "owner_id": 1},
            self.contender,
        )
        self.assertEqual(report.round, 1)
        self.assertTrue(report.dynasty_value.evidence)
        self.assertEqual(report.market_value.score, 50)
        self.assertIn("slot unknown", report.expected_range)
        self.assertTrue(report.time_horizon)
        self.assertTrue(report.recommendation.evidence)

    def test_portfolios_aggregate_individual_reports(self) -> None:
        players = evaluate_player_portfolio((self.player,), self.contender)
        picks = evaluate_pick_portfolio(({"season": 2027, "round": 1},), self.contender)
        self.assertIn("individual", players.summary.lower())
        self.assertIn("Individual pick values", {item.factor for item in picks.evidence})


if __name__ == "__main__":
    unittest.main()
