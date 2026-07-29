"""Player Value & Projection Integration v1 regression coverage."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from services.matchup_intelligence import matchup_player_values, matchup_projection
from services.trade_intelligence import build_trade_center
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry, intelligence_orchestrator
from src.core.valuation import packages
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

    def test_matchup_projection_skips_unrelated_trade_intelligence(self) -> None:
        teams = self.data["teams"][:2]
        sides = [
            {
                "roster_id": team["roster_id"],
                "team": team["team_name"],
                "lineup": [
                    {"id": player["id"], "position": player["position"]}
                    for player in team["players"][:2]
                ],
            }
            for team in teams
        ]
        with patch.object(
            self.orchestrator.registry,
            "provider",
            wraps=self.orchestrator.registry.provider,
        ) as provider, patch.object(
            packages,
            "adjusted_package_value",
            wraps=packages.adjusted_package_value,
        ) as package_value:
            values = self.orchestrator.matchup_player_values(
                self.data,
                tuple(side["roster_id"] for side in sides),
            )
            summary = matchup_projection(self.data, sides, values)
        self.assertNotIn("trade", [call.args[0] for call in provider.call_args_list])
        package_value.assert_not_called()
        self.assertEqual(len(summary["sides"]), 2)

    def test_matchup_page_builds_all_roster_values_once(self) -> None:
        fixture_teams = self.data["teams"][:4]
        matchup_groups = {
            "1": [
                {"roster_id": team["roster_id"]}
                for team in fixture_teams[:2]
            ],
            "2": [
                {"roster_id": team["roster_id"]}
                for team in fixture_teams[2:4]
            ],
        }
        expected_ids = {
            int(side["roster_id"])
            for sides in matchup_groups.values()
            for side in sides
        }
        with patch.object(
            intelligence_orchestrator,
            "matchup_player_values",
            wraps=intelligence_orchestrator.matchup_player_values,
        ) as build:
            values = matchup_player_values(self.data, matchup_groups)
        self.assertEqual(build.call_count, 1)
        self.assertEqual(set(values), expected_ids)

    def test_matchup_request_deduplicates_rosters_and_rebuilds_next_request(self) -> None:
        teams = self.data["teams"][:2]
        roster_ids = tuple(int(team["roster_id"]) for team in teams)
        duplicated = roster_ids + roster_ids
        sides = [
            {
                "roster_id": team["roster_id"],
                "team": team["team_name"],
                "lineup": [
                    {"id": player["id"], "position": player["position"]}
                    for player in team["players"][:2]
                ],
            }
            for team in teams
        ]
        with patch.object(
            self.orchestrator.registry,
            "provider",
            wraps=self.orchestrator.registry.provider,
        ) as provider:
            first = self.orchestrator.matchup_player_values(
                self.data,
                duplicated,
            )
            first_calls = provider.call_count
            first_provider_names = [
                call.args[0]
                for call in provider.call_args_list
            ]
            second = self.orchestrator.matchup_player_values(
                self.data,
                duplicated,
            )
            second_provider_names = [
                call.args[0]
                for call in provider.call_args_list[first_calls:]
            ]
        self.assertEqual(set(first), set(roster_ids))
        self.assertEqual(set(second), set(roster_ids))
        self.assertEqual(
            matchup_projection(self.data, sides, first),
            matchup_projection(self.data, sides, second),
        )
        for provider_names in (first_provider_names, second_provider_names):
            self.assertEqual(provider_names.count("decision"), 1)
            self.assertEqual(provider_names.count("asset"), len(roster_ids))
            self.assertEqual(
                provider_names.count("market"),
                len(roster_ids),
            )
            self.assertEqual(
                provider_names.count("player_value"),
                len(roster_ids),
            )
            self.assertNotIn("trade", provider_names)
        first_player = next(iter(first[roster_ids[0]].values()))
        second_player = next(iter(second[roster_ids[0]].values()))
        self.assertNotEqual(
            first_player.dtos_dynasty.updated_at,
            second_player.dtos_dynasty.updated_at,
        )
        self.assertEqual(
            provider.call_count,
            first_calls * 2,
        )

    def test_matchup_fast_path_matches_full_orchestrator_projection(self) -> None:
        teams = self.data["teams"][:2]
        sides = [
            {
                "roster_id": team["roster_id"],
                "team": team["team_name"],
                "lineup": [
                    {"id": player["id"], "position": player["position"]}
                    for player in team["players"][:2]
                ],
            }
            for team in teams
        ]
        full_values = {
            int(side["roster_id"]): self.orchestrator.analyze(
                self.data,
                int(side["roster_id"]),
            ).player_values
            for side in sides
        }
        fast_values = self.orchestrator.matchup_player_values(
            self.data,
            tuple(int(side["roster_id"]) for side in sides),
        )
        self.assertEqual(
            matchup_projection(self.data, sides, fast_values),
            matchup_projection(self.data, sides, full_values),
        )

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
