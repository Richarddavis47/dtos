"""Targeted tests for Commissioner Desk context and intelligence."""
from __future__ import annotations

import unittest

from components.commissioner import commissioner_desk
from models.commissioner import ConfidenceScore, RecommendationPriority
from services.commissioner import build_commissioner_desk


class CommissionerDeskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = {
            "league": {"league_id": "league-1", "name": "Example Dynasty", "season": "2026"},
            "nfl_state": {"week": 4, "season_type": "regular"},
            "week": 4,
            "players": {
                "a-qb": {"age": 23}, "a-rb": {"age": 29}, "a-wr": {"age": 24}, "a-te": {"age": 27},
                "b-qb": {"age": 31}, "b-rb": {"age": 30}, "b-wr": {"age": 28}, "b-te": {"age": 29},
            },
            "teams": [
                {
                    "roster_id": 1, "owner_id": "owner-a", "owner": "Alice", "team_name": "Alpha Office",
                    "wins": 4, "losses": 0, "ties": 0, "points_for": 500.0, "points_against": 400.0,
                    "max_points": 550.0, "players": self._players("a"), "picks_owned": self._picks("Alpha Office", 1),
                },
                {
                    "roster_id": 2, "owner_id": "owner-b", "owner": "Bob", "team_name": "Bravo Office",
                    "wins": 1, "losses": 3, "ties": 0, "points_for": 350.0, "points_against": 470.0,
                    "max_points": 420.0, "players": self._players("b"), "picks_owned": [],
                },
            ],
            "transactions": [
                {
                    "transaction_id": "recent-trade", "type": "trade", "status": "complete",
                    "created": 1_767_225_600_000, "roster_ids": [1, 2], "adds": {"a-qb": 2},
                    "drops": {"a-qb": 1}, "draft_picks": [{"season": "2028", "round": 1, "roster_id": 2, "previous_owner_id": 2, "owner_id": 1}],
                },
                {
                    "transaction_id": "old-waiver", "type": "waiver", "status": "complete",
                    "created": 1_700_000_000_000, "roster_ids": [1], "adds": {"a-wr": 1}, "drops": None, "draft_picks": [],
                },
            ],
            "matchups": {"1": [{"team": "Alpha Office", "points": 100}, {"team": "Bravo Office", "points": 90}]},
        }

    @staticmethod
    def _players(prefix: str) -> list[dict[str, object]]:
        return [
            {"id": f"{prefix}-qb", "name": f"{prefix.upper()} QB", "position": "QB", "team": "BUF", "roster_slot": "Starter"},
            {"id": f"{prefix}-rb", "name": f"{prefix.upper()} RB", "position": "RB", "team": "MIA", "roster_slot": "Starter"},
            {"id": f"{prefix}-wr", "name": f"{prefix.upper()} WR", "position": "WR", "team": "NYJ", "roster_slot": "Starter"},
            {"id": f"{prefix}-te", "name": f"{prefix.upper()} TE", "position": "TE", "team": "NE", "roster_slot": "Starter"},
        ]

    @staticmethod
    def _picks(team: str, roster_id: int) -> list[dict[str, object]]:
        return [
            {"season": 2027, "round": round_number, "original_team": team, "original_roster_id": roster_id, "current_owner_id": roster_id, "is_traded": False}
            for round_number in (1, 2, 3, 4)
        ]

    def build(self, **changes: object) -> dict[str, object]:
        arguments = {
            "data": self.data,
            "configured_league_id": "league-1",
            "since": "2025-12-31T00:00:00+00:00",
            "last_sync": "2026-01-02T00:00:00+00:00",
        }
        arguments.update(changes)
        return build_commissioner_desk(**arguments)

    def test_active_context_defaults_and_switches_front_office(self) -> None:
        default = self.build()
        selected = self.build(active_roster_id=2)
        self.assertEqual(default["active_league"].name, "Example Dynasty")
        self.assertEqual(default["active_front_office"].owner_name, "Alice")
        self.assertEqual(selected["active_front_office"].owner_name, "Bob")
        self.assertNotEqual(default["front_office_summary"]["record"], selected["front_office_summary"]["record"])
        self.assertEqual(len(default["front_offices"]), 2)

    def test_briefing_respects_since_and_discloses_unavailable_history(self) -> None:
        view = self.build(since="2026-01-01T00:00:00+00:00")
        ids = {event.source_id for event in view["briefing"].events}
        self.assertEqual(ids, {"recent-trade"})
        self.assertEqual(view["briefing"].counts["Trade"], 1)
        self.assertEqual(view["briefing"].counts["Draft Pick Movement"], 1)
        self.assertTrue(any("historical" in item.lower() for item in view["briefing"].unavailable))

    def test_recommendations_are_prioritized_and_explainable(self) -> None:
        view = self.build(active_roster_id=2)
        recommendations = view["recommendations"]
        priority_order = {RecommendationPriority.HIGH: 0, RecommendationPriority.MEDIUM: 1, RecommendationPriority.LOW: 2}
        self.assertEqual(
            [priority_order[item.priority] for item in recommendations],
            sorted(priority_order[item.priority] for item in recommendations),
        )
        for recommendation in recommendations:
            self.assertGreater(recommendation.confidence.value, 0)
            self.assertTrue(recommendation.reasoning)
            self.assertTrue(recommendation.supporting_metrics)
            self.assertIn("engine", recommendation.future_explanation_hook)

    def test_headlines_are_evidence_backed_and_league_neutral(self) -> None:
        view = self.build()
        self.assertGreaterEqual(len(view["headlines"]), 3)
        for headline in view["headlines"]:
            self.assertTrue(headline.evidence)
        rendered = commissioner_desk(view)
        self.assertIn("Example Dynasty", rendered)
        self.assertNotIn("Day Traders", rendered)

    def test_headlines_disclose_ties_instead_of_inventing_a_leader(self) -> None:
        self.data["teams"][1].update(
            {"wins": 4, "losses": 0, "ties": 0, "points_for": 500.0}
        )
        self.data["teams"][1]["picks_owned"] = self._picks("Bravo Office", 2)
        for player_id in ("b-qb", "b-rb", "b-wr", "b-te"):
            self.data["players"][player_id]["age"] = 26
        for player_id in ("a-qb", "a-rb", "a-wr", "a-te"):
            self.data["players"][player_id]["age"] = 26
        titles = [headline.title for headline in self.build()["headlines"]]
        self.assertTrue(any("level" in title for title in titles))
        self.assertTrue(any("tied for" in title for title in titles))

    def test_component_hierarchy_persistence_responsiveness_and_dark_mode(self) -> None:
        rendered = commissioner_desk(self.build())
        for label in (
            "Commissioner Desk", "Active League", "Active Front Office", "What changed?", "What matters?",
            "What should I do?", "Your Front Office", "League Intelligence", "League Snapshot", "League Personality",
            "Show Reasoning",
        ):
            self.assertIn(label, rendered)
        self.assertIn("localStorage", rendered)
        self.assertIn("dtos.activeFrontOffice", rendered)
        self.assertIn("dtos.lastCommissionerVisit", rendered)
        self.assertIn("fetch('/sync'", rendered)
        self.assertIn("@media(max-width:650px)", rendered)
        self.assertIn("color-scheme:dark", rendered)

    def test_confidence_score_is_bounded(self) -> None:
        self.assertEqual(ConfidenceScore(150).value, 100)
        self.assertEqual(ConfidenceScore(-5).value, 0)


if __name__ == "__main__":
    unittest.main()
