"""Roster Intelligence v1 quality-first and explainability regressions."""
from __future__ import annotations

import unittest

from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from src.core.roster_intelligence.engine import _identity, _room_score
from src.core.roster_intelligence.models import PlayerCard
from tests.test_trade_intelligence import fixture_data


def card(score: int, *, risk: str = "Low") -> PlayerCard:
    return PlayerCard(
        str(score), "Cornerstone" if score >= 84 else "Replacement Level", "A" if score >= 84 else "F",
        score, "Prime", "Stable", score, score, score, score, score, 70, risk,
        score, score, "Observable current outlook", "Observable future outlook", "HOLD",
    )


class RosterIntelligenceTests(unittest.TestCase):
    def test_elite_room_with_limited_depth_beats_deep_replacement_room(self) -> None:
        elite, elite_dimensions = _room_score([card(98), card(92), card(45)], "TE")
        deep, deep_dimensions = _room_score([card(48) for _ in range(6)], "TE")
        self.assertGreater(elite, deep)
        self.assertGreater(elite_dimensions["Elite Talent"], deep_dimensions["Elite Talent"])
        self.assertGreater(deep_dimensions["Depth"], elite_dimensions["Depth"])

    def test_grade_consistency_is_order_independent(self) -> None:
        players = [card(90), card(72), card(55), card(44)]
        self.assertEqual(_room_score(players, "WR"), _room_score(list(reversed(players)), "WR"))

    def test_team_identity_distinguishes_young_and_aging_windows(self) -> None:
        young, young_reason = _identity(85, 84, 24.8, 3)
        aging, aging_reason = _identity(80, 55, 29.4, 1)
        rebuild, _ = _identity(45, 70, 24.1, 1)
        self.assertIn(young, {"Championship Favorite", "Young Contender"})
        self.assertEqual(aging, "Aging Contender")
        self.assertEqual(rebuild, "Productive Struggle")
        self.assertIn("average starter age", young_reason)
        self.assertIn("future outlook", aging_reason)

    def test_orchestrator_supplies_explainable_roster_report(self) -> None:
        orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60))
        result = orchestrator.analyze(fixture_data(), 1)
        self.assertIsNotNone(result.roster)
        self.assertEqual(set(result.roster.rooms), {"QB", "RB", "WR", "TE"})
        for room in result.roster.rooms.values():
            self.assertEqual(len(room.dimensions), 6)
            self.assertTrue(room.reasoning)
            self.assertGreaterEqual(room.league_rank, 1)
            self.assertLessEqual(room.league_rank, room.league_size)
        self.assertTrue(result.roster.identity_reasoning)
        self.assertIn("Roster Intelligence", orchestrator.registry.provider("roster").__module__.replace("_", " ").title())

    def test_player_cards_expose_tier_strategy_and_shared_values(self) -> None:
        result = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache()).analyze(fixture_data(), 1)
        self.assertTrue(result.roster.players)
        player = next(iter(result.roster.players.values()))
        self.assertTrue(player.tier)
        self.assertGreaterEqual(player.dynasty_value, 0)
        self.assertGreaterEqual(player.contender_value, 0)
        self.assertGreaterEqual(player.rebuilder_value, 0)
        self.assertTrue(player.recommended_action)


if __name__ == "__main__":
    unittest.main()
