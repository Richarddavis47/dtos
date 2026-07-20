"""Targeted tests for deterministic Team Headquarters intelligence."""
from __future__ import annotations

import unittest

from services.team_headquarters import build_team_headquarters, calculate_team_grades


class TeamHeadquartersTests(unittest.TestCase):
    def setUp(self) -> None:
        players = [
            {"id": "qb1", "name": "Young QB", "position": "QB", "team": "BUF", "roster_slot": "Starter"},
            {"id": "qb2", "name": "Reserve QB", "position": "QB", "team": "MIA", "roster_slot": "Bench"},
            {"id": "rb1", "name": "Lead Back", "position": "RB", "team": "NYJ", "roster_slot": "Starter"},
            {"id": "rb2", "name": "Old Back", "position": "RB", "team": "NE", "roster_slot": "Bench"},
            {"id": "wr1", "name": "Wide One", "position": "WR", "team": "DAL", "roster_slot": "Starter"},
            {"id": "wr2", "name": "Wide Two", "position": "WR", "team": "PHI", "roster_slot": "Bench"},
            {"id": "te1", "name": "Tight One", "position": "TE", "team": "KC", "roster_slot": "Starter"},
            {"id": "k1", "name": "Kicker", "position": "K", "team": "BAL", "roster_slot": "Bench"},
        ]
        self.data = {
            "players": {
                "qb1": {"age": 23}, "qb2": {"age": 27}, "rb1": {"age": 24},
                "rb2": {"age": 29}, "wr1": {"age": 25}, "wr2": {"age": 22},
                "te1": {"age": 30}, "k1": {"age": 31},
            },
            "teams": [
                {
                    "roster_id": 1, "team_name": "Alpha", "owner": "Alice", "avatar": "avatar",
                    "wins": 5, "losses": 2, "ties": 0, "points_for": 700,
                    "points_against": 650, "max_points": 820, "players": players,
                    "picks_owned": [
                        {"season": 2027, "round": 1, "original_team": "Alpha", "is_traded": False},
                        {"season": 2027, "round": 1, "original_team": "Bravo", "is_traded": True},
                        {"season": 2028, "round": 2, "original_team": "Alpha", "is_traded": False},
                    ],
                },
                {
                    "roster_id": 2, "team_name": "Bravo", "owner": "Bob", "wins": 4,
                    "losses": 3, "ties": 0, "players": [], "picks_owned": [],
                },
            ],
            "transactions": [
                {"transaction_id": "older", "type": "free_agent", "status": "complete", "created": 1000,
                 "roster_ids": [1], "adds": {"wr2": 1}, "drops": None, "draft_picks": []},
                {"transaction_id": "newer", "type": "trade", "status": "complete", "created": 2000,
                 "roster_ids": [1, 2], "adds": {"qb1": 2}, "drops": {"qb1": 1}, "draft_picks": []},
            ],
        }

    def test_builds_complete_objective_headquarters_model(self) -> None:
        view = build_team_headquarters(self.data, 1, "2026-07-20T12:00:00+00:00")
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view["rank"], 1)
        self.assertEqual(view["snapshot"]["total_players"], 8)
        self.assertEqual(view["snapshot"]["total_picks"], 3)
        self.assertEqual(view["snapshot"]["first_round_picks"], 2)
        self.assertEqual(view["snapshot"]["young_players"], 3)
        self.assertEqual(view["snapshot"]["veteran_players"], 3)
        self.assertEqual(view["performance"]["streak"], "Unavailable")
        self.assertEqual(view["timeline"][0]["id"], "newer")
        self.assertEqual(len(view["picks_by_year"][2027]), 2)

    def test_every_grade_is_bounded_and_explainable(self) -> None:
        view = build_team_headquarters(self.data, 1)
        assert view is not None
        self.assertEqual(
            set(view["grades"]),
            {"QB", "RB", "WR", "TE", "Youth", "Depth", "Draft Capital", "Flexibility", "Roster Construction"},
        )
        for grade in view["grades"].values():
            self.assertIn(grade["grade"], "ABCDF")
            self.assertGreaterEqual(grade["score"], 0)
            self.assertLessEqual(grade["score"], 100)
            self.assertTrue(grade["data"])
            self.assertTrue(grade["calculation"])
            self.assertTrue(grade["why"])

    def test_summary_discloses_model_limits(self) -> None:
        view = build_team_headquarters(self.data, 1)
        assert view is not None
        combined = " ".join(view["summary"].values())
        self.assertIn("Current Championship Outlook", combined)
        self.assertIn("evaluated independently from future assets", combined)
        self.assertIn("independently calculated future horizon", combined)

    def test_missing_ages_use_neutral_explainable_baseline(self) -> None:
        players = [{"id": "unknown", "position": "QB", "roster_slot": "Starter"}]
        grades = calculate_team_grades(players, {"picks_owned": []})
        self.assertEqual(grades["Youth"]["score"], 50)
        self.assertIn("No player ages are available", grades["Youth"]["why"])

    def test_unknown_team_returns_none(self) -> None:
        self.assertIsNone(build_team_headquarters(self.data, 999))


if __name__ == "__main__":
    unittest.main()
