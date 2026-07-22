"""Player Value & Projection Integration v1 regression coverage."""
from __future__ import annotations

import unittest
from pathlib import Path

from services.matchup_intelligence import matchup_projection
from services.trade_intelligence import build_trade_center
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from src.core.player_value_projection.models import DataStatus
from src.core.player_value_projection.providers import CachedProductionProvider, InternalProjectionProvider, scoring_multiplier
from tests.test_trade_intelligence import fixture_data


class PlayerValueProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60))

    def test_league_scoring_changes_same_player_projection(self) -> None:
        provider = InternalProjectionProvider()
        player = {"position": "TE", "status": "Active"}
        standard = provider.project(player, 65, {"rec": 0}, 1)
        premium = provider.project(player, 65, {"rec": 1, "bonus_rec_te": .5}, 1)
        self.assertGreater(premium.projected_points, standard.projected_points)
        self.assertNotEqual(scoring_multiplier("QB", {"pass_td": 6}), scoring_multiplier("QB", {"pass_td": 4}))

    def test_projection_fallback_is_explicit_and_explainable(self) -> None:
        projection = InternalProjectionProvider().project({"position": "WR"}, 60, {"rec": 1}, 3)
        self.assertEqual(projection.status, DataStatus.FALLBACK)
        self.assertIn("internal", projection.source.lower())
        self.assertTrue(projection.limitations)
        self.assertLess(projection.floor, projection.median)
        self.assertGreater(projection.ceiling, projection.median)

    def test_production_cached_and_unavailable_states_are_distinct(self) -> None:
        provider = CachedProductionProvider()
        cached = provider.production({"recent_points": [10, 12, 18], "season_average": 13})
        unavailable = provider.production({})
        self.assertEqual(cached.status, DataStatus.CACHED)
        self.assertEqual(unavailable.status, DataStatus.UNAVAILABLE)
        self.assertIsNotNone(cached.volatility)
        self.assertTrue(unavailable.limitations)

    def test_unified_profiles_keep_internal_and_market_values_separate(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        profile = next(iter(result.player_values.values()))
        self.assertEqual(profile.dtos_dynasty.source, "DTOS Asset Intelligence")
        self.assertIn(profile.market_consensus.status, set(DataStatus))
        self.assertTrue(profile.evidence)
        self.assertTrue(profile.market_posture)
        self.assertGreaterEqual(profile.lineup.scarcity, 0)

    def test_points_above_replacement_and_roster_marginal_value_are_exposed(self) -> None:
        profiles = self.orchestrator.analyze(self.data, 1).player_values.values()
        self.assertTrue(all(isinstance(item.lineup.points_above_replacement, float) for item in profiles))
        self.assertTrue(all(0 <= item.lineup.marginal_value <= 100 for item in profiles))
        self.assertTrue(any(item.lineup.role for item in profiles))

    def test_contender_and_rebuilder_values_remain_independent(self) -> None:
        profiles = self.orchestrator.analyze(self.data, 1).player_values.values()
        self.assertTrue(any(item.contender.value != item.rebuilder.value for item in profiles))

    def test_portrait_fallback_and_determinism(self) -> None:
        first = self.orchestrator.analyze(self.data, 1)
        second = self.orchestrator.analyze(self.data, 1)
        self.assertEqual(first.player_values, second.player_values)
        player = next(iter(first.player_values.values()))
        self.assertIn(player.image_status, {"available", "fallback"})
        self.assertTrue(player.portrait_url or player.fallback_initials)

    def test_matchup_aggregation_reports_ranges_without_probabilities(self) -> None:
        teams = self.data["teams"][:2]
        sides = []
        for team in teams:
            lineup = [{"id": player["id"], "position": player["position"]} for player in team["players"][:2]]
            sides.append({"roster_id": team["roster_id"], "team": team["team_name"], "lineup": lineup})
        summary = matchup_projection(self.data, sides)
        self.assertEqual(len(summary["sides"]), 2)
        self.assertTrue(all(item["floor"] <= item["projected"] <= item["ceiling"] for item in summary["sides"]))
        self.assertNotIn("probability", summary)

    def test_trade_view_exposes_separate_value_horizons(self) -> None:
        view = build_trade_center(self.data, 1)
        for impact in view["value_impacts"].values():
            self.assertEqual(set(impact), {"dtos_dynasty", "market", "contender", "rebuild", "weekly"})

    def test_application_services_respect_orchestrator_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in ("services/matchup_intelligence.py", "services/trade_intelligence.py", "services/team_headquarters.py"):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertIn("src.core.intelligence", source)
            self.assertNotIn("src.core.player_value_projection", source)
            self.assertNotIn("src.core.roster_intelligence", source)


if __name__ == "__main__":
    unittest.main()
