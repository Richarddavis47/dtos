"""Missing weekly evidence must not masquerade as a genuine zero valuation input."""
import unittest
from unittest.mock import patch

from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from tests.test_trade_intelligence import fixture_data


class ProjectionValueMissingnessTests(unittest.TestCase):
    def test_missing_and_zero_projection_remain_distinct_end_to_end(self):
        data = fixture_data()
        data['week'] = 1
        def evaluate(points):
            players = {} if points is None else {
                player["id"]: {"weekly_projected_points": points, "provider": "Sleeper",
                    "projection_confidence": 90, "week": data.get("week")}
                for team in data["teams"] for player in team["players"]}
            with patch("src.core.player_value_projection.providers.projection_service.snapshot", return_value={
                "league_id": data["league"]["league_id"], "week": data.get("week"), "players": players}):
                return IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache()).analyze(data, 1).player_values
        missing, zero = evaluate(None), evaluate(0)
        for key, profile in missing.items():
            self.assertIsNone(profile.projection.projected_points)
            self.assertEqual(zero[key].projection.projected_points, 0)
            self.assertIsNone(profile.dtos_dynasty.value)
            self.assertIsNone(zero[key].dtos_dynasty.value)
            self.assertIsNone(profile.lineup.points_above_replacement)
            self.assertEqual(zero[key].lineup.points_above_replacement, 0)
            self.assertIsNone(profile.positional.weekly_rank)
            self.assertIsNotNone(zero[key].positional.weekly_rank)
