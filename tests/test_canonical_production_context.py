"""Batch 3 production consumer boundaries, without provider/storage access."""
import unittest
from copy import deepcopy

from src.core.player_value_projection.canonical_production import canonical_production_context


def evidence(points, season=2026):
    return {"league_id": "A", "player_id": "1", "season": season,
            "scoring_fingerprint": "ppr", "production": {"as_of": "2026-09-09T00:00:00Z", "games": [
                {"season": season, "week": week, "game_id": str(week),
                 "availability": "calculated", "fantasy_points": value,
                 "knowledge_boundary": "2026-09-01T00:00:00Z",
                 "raw_stats": {"rec_tgt": 5, "rush_att": 0, "rec": 3,
                               "pass_td": 0, "rush_td": 0, "rec_td": 0}}
                for week, value in enumerate(points, 1)]}}


class CanonicalProductionContextTests(unittest.TestCase):
    def test_missing_current_does_not_replace_it_with_previous(self):
        result = canonical_production_context(evidence([]), evidence([18, 20], 2025))
        self.assertIsNone(result.windows[0].fantasy_points)
        self.assertIsNone(result.windows[3].fantasy_points)
        self.assertEqual(result.windows[4].fantasy_points, 19)
        self.assertEqual(result.status.value, "cached")
        self.assertEqual(result.trend, "Unavailable")

    def test_real_zero_is_retained(self):
        result = canonical_production_context(evidence([0, 0, 0]))
        self.assertEqual(result.windows[3].fantasy_points, 0)
        self.assertEqual(result.windows[0].carries, 0)
        self.assertEqual(result.windows[0].touchdowns, 0)
        self.assertEqual(result.consistency, 100)

    def test_incomplete_scoring_is_not_a_zero_or_complete_average(self):
        rows = evidence([10, None, 20])
        rows["production"]["games"][1]["availability"] = "incomplete"
        result = canonical_production_context(rows)
        self.assertIsNone(result.windows[1].fantasy_points)
        self.assertIsNone(result.windows[3].fantasy_points)
        self.assertEqual(result.windows[0].fantasy_points, 20)
        self.assertIsNone(result.volatility)

    def test_chronological_order_not_observation_order(self):
        source = evidence([1, 2, 3, 4, 5, 6])
        expected = canonical_production_context(source)
        source["production"]["games"].reverse()
        self.assertEqual(canonical_production_context(source), expected)
        self.assertEqual(expected.windows[0].fantasy_points, 6)
        self.assertEqual(expected.trend, "Rising")

    def test_small_sample_is_not_trend(self):
        self.assertEqual(canonical_production_context(evidence([1, 20])).trend, "Unavailable")

    def test_context_and_knowledge_mismatch_rejected(self):
        for key, value in (("league_id", "B"), ("player_id", "2"),
                           ("scoring_fingerprint", "half-ppr"), ("season", 2024)):
            old = evidence([10], 2025)
            old[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                canonical_production_context(evidence([20]), old)
        old = evidence([10], 2025)
        old["production"]["as_of"] = "2027-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            canonical_production_context(evidence([20]), old)

    def test_no_mutation_and_missing_usage_not_zero(self):
        source = evidence([10])
        del source["production"]["games"][0]["raw_stats"]["rec_tgt"]
        before = deepcopy(source)
        result = canonical_production_context(source)
        self.assertEqual(source, before)
        self.assertIsNone(result.windows[0].targets)
        self.assertIsNone(result.windows[0].opportunities)

    def test_invalid_number_rejected(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_production_context(evidence([value]))
