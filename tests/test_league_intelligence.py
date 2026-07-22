"""League Intelligence Engine v1 synthesis and explainability regressions."""
from __future__ import annotations

import unittest
from pathlib import Path

from components.commissioner import commissioner_desk
from services.commissioner import build_commissioner_desk
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from tests.test_trade_intelligence import fixture_data


class LeagueIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60))
        self.result = self.orchestrator.analyze(self.data, 1)
        self.league = self.result.league

    def test_every_team_has_quality_based_needs_and_direction(self) -> None:
        self.assertEqual(set(self.league.needs), {1, 2, 3})
        self.assertEqual(set(self.league.directions), {1, 2, 3})
        for roster_id, needs in self.league.needs.items():
            self.assertEqual({item.position for item in needs}, {"QB", "RB", "WR", "TE"})
            self.assertTrue(all(item.reasoning for item in needs))
            self.assertEqual(needs, tuple(sorted(needs, key=lambda item: (-item.score, item.position))))
            self.assertTrue(self.league.directions[roster_id].reasoning)

    def test_surplus_requires_quality_and_liquidity_evidence(self) -> None:
        for rows in self.league.surpluses.values():
            for surplus in rows:
                self.assertGreaterEqual(surplus.score, 62)
                self.assertTrue(surplus.reasoning)
                self.assertTrue(surplus.category)

    def test_pairwise_compatibility_is_complete_explainable_and_deterministic(self) -> None:
        self.assertEqual(len(self.league.compatibilities), 3)
        self.assertTrue(all(item.explanation and 0 <= item.score <= 100 for item in self.league.compatibilities))
        second = self.orchestrator.analyze(self.data, 1).league
        self.assertEqual(self.league, second)

    def test_market_map_and_economy_identify_buyers_sellers_and_premiums(self) -> None:
        self.assertTrue({"QB", "RB", "WR", "TE", "Draft Picks", "Veterans", "Youth"}.issubset(self.league.market_map))
        self.assertEqual(set(self.league.economy), {"QB", "RB", "WR", "TE"})
        for position, market in self.league.market_map.items():
            self.assertEqual(set(market), {"buyers", "sellers"})
            if position in self.league.economy:
                self.assertEqual(self.league.economy[position].demand, len(market["buyers"]))
                self.assertEqual(self.league.economy[position].supply, len(market["sellers"]))
                self.assertTrue(self.league.economy[position].explanation)

    def test_asset_availability_is_neutral_and_evidence_backed(self) -> None:
        allowed = {"Untouchable", "Extremely Difficult", "Available For Premium", "Available", "Actively Shopping"}
        self.assertTrue(self.league.availability)
        self.assertTrue(all(item.status in allowed and item.reasoning for item in self.league.availability.values()))

    def test_gm_profiles_use_observed_front_office_evidence(self) -> None:
        for profile in self.league.gm_profiles.values():
            self.assertTrue(profile.activity)
            self.assertTrue(profile.negotiation_style)
            self.assertTrue(profile.evidence)
            self.assertGreater(profile.confidence, 0)

    def test_opportunities_are_prioritized_and_explainable(self) -> None:
        scores = [item.score for item in self.league.opportunities]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(item.reasoning and item.target_roster_id == 1 for item in self.league.opportunities))

    def test_trade_recommendations_preserve_separate_impacts(self) -> None:
        self.assertTrue(self.league.trade_recommendations)
        for recommendation in self.league.trade_recommendations:
            self.assertTrue(recommendation.offer)
            self.assertTrue(recommendation.receive)
            self.assertIsInstance(recommendation.dtos_value_delta, int)
            self.assertIsInstance(recommendation.lineup_impact, int)
            self.assertTrue(recommendation.explanation)

    def test_dashboard_is_rendered_on_commissioner_home(self) -> None:
        view = build_commissioner_desk(self.data, "league-1", active_roster_id=1)
        html = commissioner_desk(view)
        self.assertIn("League Opportunity Dashboard", html)
        self.assertIn("Best Trade Partners", html)
        self.assertIn("League Economy", html)
        self.assertNotIn("win probability", html.lower())

    def test_application_services_keep_orchestrator_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in ("services/commissioner.py", "services/team_headquarters.py", "services/trade_intelligence.py"):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertIn("src.core.intelligence", source)
            self.assertNotIn("src.core.league_intelligence", source)


if __name__ == "__main__":
    unittest.main()
