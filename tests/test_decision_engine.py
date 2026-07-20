"""Contract tests for the reusable Decision Engine v1."""
from __future__ import annotations

import copy
import unittest

from src.core.decision_engine import DecisionContext, DecisionEngine, TeamWindow, evaluate_team
from src.core.decision_engine.models.evaluation import Evaluation, EvaluationHorizon
from src.core.decision_engine.models.recommendation import RecommendationCategory
from src.core.decision_engine.team.competitive_window import classify_competitive_window


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        players = []
        player_db = {}
        for position, count in (("QB", 2), ("RB", 4), ("WR", 5), ("TE", 2)):
            for number in range(count):
                player_id = f"{position.lower()}{number}"
                players.append({
                    "id": player_id,
                    "position": position,
                    "roster_slot": "Starter" if number == 0 else "Bench",
                })
                player_db[player_id] = {"age": 23 + number}
        player_db["rb0"]["injury_status"] = "Questionable"
        self.data = {
            "players": player_db,
            "teams": [{
                "roster_id": 1,
                "team_name": "Architecture FC",
                "owner": "Alex",
                "wins": 8,
                "losses": 2,
                "points_for": 1200,
                "points_against": 900,
                "max_points": 1400,
                "players": players,
                "picks_owned": [
                    {"season": 2027, "round": 1},
                    {"season": 2028, "round": 1},
                    {"season": 2028, "round": 2},
                ],
            }, {
                "roster_id": 2,
                "team_name": "League Baseline",
                "owner": "Blair",
                "wins": 4,
                "losses": 6,
                "points_for": 850,
                "max_points": 1000,
                "players": [],
                "picks_owned": [],
            }],
        }
        self.context = DecisionContext(
            active_front_office_id=1,
            league_id="league-1",
            league_settings={"roster_positions": ["QB", "RB", "WR", "TE"]},
            team_strategy="Compete",
        )

    def test_current_and_future_horizons_are_independent(self) -> None:
        original = evaluate_team(self.data, 1, self.context)
        changed = copy.deepcopy(self.data)
        changed["teams"][0].update(wins=0, losses=10, points_for=200, max_points=300)
        result = evaluate_team(changed, 1, self.context)
        self.assertNotEqual(original.current_outlook.score, result.current_outlook.score)
        self.assertEqual(original.future_outlook.score, result.future_outlook.score)
        self.assertFalse(hasattr(result, "overall_score"))

    def test_context_depth_and_explainability_are_preserved(self) -> None:
        decision = DecisionEngine().evaluate_team(self.data, 1, self.context)
        self.assertEqual(decision.profile.active_front_office_id, 1)
        self.assertEqual(decision.profile.league_settings, self.context.league_settings)
        self.assertEqual(set(decision.position_evaluations), {"QB", "RB", "WR", "TE"})
        self.assertTrue(decision.position_evaluations["RB"].factors)
        self.assertIn("injury", " ".join(
            f"{factor.name} {factor.explanation}"
            for factor in decision.position_evaluations["RB"].factors
        ).lower())

    def test_recommendations_implement_shared_contract(self) -> None:
        decision = evaluate_team(self.data, 1, self.context)
        self.assertTrue(decision.recommendations)
        for recommendation in decision.recommendations:
            self.assertIsInstance(recommendation.category, RecommendationCategory)
            self.assertGreaterEqual(recommendation.confidence.value, 0)
            self.assertLessEqual(recommendation.confidence.value, 100)
            self.assertTrue(recommendation.reasoning)
            self.assertTrue(recommendation.supporting_metrics)
            self.assertTrue(recommendation.future_explanation_hook)

    def test_all_window_classifications_have_deterministic_boundaries(self) -> None:
        def evaluation(score: int) -> Evaluation:
            return Evaluation(EvaluationHorizon.CURRENT, score, "C", 80, "Test", ())

        cases = (
            (80, 70, TeamWindow.CHAMPIONSHIP),
            (70, 40, TeamWindow.PLAYOFF),
            (40, 70, TeamWindow.ASCENSION),
            (40, 40, TeamWindow.REBUILD),
            (55, 60, TeamWindow.TRANSITION),
        )
        for current, future, expected in cases:
            with self.subTest(expected=expected):
                window, explanation = classify_competitive_window(evaluation(current), evaluation(future))
                self.assertEqual(window, expected)
                self.assertTrue(explanation)


if __name__ == "__main__":
    unittest.main()
