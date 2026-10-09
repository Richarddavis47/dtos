"""Grounded league badges and presentation-only numeric formatting."""

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.core.history_context.season_cache import SleeperSeasonCache
from src.ui.badges import (
    champion_badge,
    defending_champion,
    movement_badge,
    official_ranks,
    position_chip,
    standing_badge,
    streak_badge,
    you_badge,
)
from src.ui.intelligence_presentation import manager_points, numeric_evidence
from services.trade_explanation import render_trade_explanation


class PhoneDesignSemanticTests(unittest.TestCase):
    def test_official_medals_require_complete_source_ranks_not_strength_order(self):
        data = {
            "week": 5,
            "league": {"league_id": "A", "season": "2026"},
            "teams": [
                {"roster_id": rid, "official_standing_rank": rank, "wins": 2}
                for rid, rank in ((1, 3), (2, 1), (3, 2))
            ],
        }
        self.assertEqual(official_ranks(data), {1: 3, 2: 1, 3: 2})
        for rank, meaning in ((1, "Gold"), (2, "Silver"), (3, "Bronze")):
            self.assertIn(meaning, standing_badge(rank))
            self.assertIn("Official Sleeper", standing_badge(rank))
        for mutation in ("missing", "duplicate", "string", "preseason"):
            other = copy.deepcopy(data)
            if mutation == "preseason":
                other["preseason"] = True
            else:
                other["teams"][0]["official_standing_rank"] = {
                    "missing": None,
                    "duplicate": 1,
                    "string": "3",
                }[mutation]
            self.assertEqual(official_ranks(other), {})
        self.assertEqual(standing_badge(None), "")

    def test_champion_is_previous_completed_season_and_league_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SleeperSeasonCache(Path(folder))
            data = {
                "league": {"league_id": "A", "season": "2026"},
                "teams": [{"roster_id": 1}, {"roster_id": 2}],
            }
            facts = {
                "league": {"status": "complete", "season": "2025"},
                "winners_bracket": [
                    {"m": 1, "p": 1, "r": 2, "t1": 1, "t2": 2, "w": 2, "l": 1}
                ],
            }
            cache.write(cache.normalize("A", 2025, facts))
            self.assertEqual(defending_champion(data, cache), (2025, 2))
            self.assertIn("2025", champion_badge((2025, 2), 2))
            self.assertIn("winners-bracket", champion_badge((2025, 2), 2))
            self.assertEqual(champion_badge((2025, 2), 1), "")
            other = copy.deepcopy(data)
            other["league"]["league_id"] = "B"
            self.assertIsNone(defending_champion(other, cache))
            for field, value in (("status", "in_season"), ("season", "2024")):
                bad = copy.deepcopy(facts)
                bad["league"][field] = value
                cache.write(cache.normalize("A", 2025, bad))
                self.assertIsNone(defending_champion(data, cache))
            bad = copy.deepcopy(facts)
            bad["winners_bracket"][0]["w"] = None
            cache.write(cache.normalize("A", 2025, bad))
            self.assertIsNone(defending_champion(data, cache))

    def test_rank_movement_and_completed_streak_are_separate_explained_facts(self):
        move = movement_badge(2, 4, "Week 4 to Week 5")
        self.assertIn("↑2", move)
        self.assertIn("Week 4 to Week 5", move)
        streak = streak_badge(["L", "W", "W", "W"], "completed Weeks 1–4")
        self.assertIn("W3", streak)
        self.assertNotIn("↑3", streak)
        self.assertIn("↓1", movement_badge(3, 2, "Week 4 to Week 5"))
        self.assertIn("L2", streak_badge(["W", "L", "L"], "completed Weeks 1–3"))
        for args in ((None, 2, "Week 5"), (1, 2, None)):
            self.assertEqual(movement_badge(*args), "")
        self.assertEqual(streak_badge(["W", "unknown"], "Weeks 1–2"), "")
        self.assertEqual(streak_badge(["W"], None), "")

    def test_you_uses_authenticated_membership_and_never_team_name(self):
        data = {"league": {"league_id": "A"}}
        account = SimpleNamespace(
            membership=SimpleNamespace(league_id="A", roster_id=2)
        )
        with patch("src.ui.badges.current_account", return_value=account):
            self.assertIn("You", you_badge(data, 2))
            self.assertEqual(you_badge(data, 1), "")
            self.assertEqual(you_badge({"league": {"league_id": "B"}}, 2), "")
        with patch("src.ui.badges.current_account", return_value=None):
            self.assertEqual(you_badge(data, 2), "")
        for position in ("QB", "RB", "WR", "TE"):
            self.assertIn(f'data-position="{position}"', position_chip(position))
        self.assertEqual(position_chip("<script>"), "")

    def test_manager_points_format_without_changing_source_or_weekly_precision(self):
        self.assertEqual(manager_points(5.4318000000001), "5.43")
        self.assertEqual(manager_points(-0.00000000001), "0")
        self.assertEqual(manager_points(None), "Unavailable")
        self.assertEqual(numeric_evidence(5.4318000000001), "5.4318000000001")
        result = {
            "provenance": {
                "evaluation_id": "fixture",
                "evaluator": "accepted-fixture",
                "inputs": {
                    "league_id": "A",
                    "active_roster_id": 1,
                    "partner_roster_id": 2,
                },
            },
            "multi_horizon_impact": {
                "sides": {
                    "active": {
                        "horizons": {
                            "current_week": {
                                "delta": 5.4318000000001,
                                "pre_supported_weeks": [5],
                                "post_supported_weeks": [5],
                                "weeks_requested": [5],
                            }
                        },
                        "weekly": {
                            5: {
                                "pre": {"optimal": {"projected_points": 27.335}},
                                "post": {},
                                "delta": None,
                            }
                        },
                    }
                }
            },
        }
        result["dimensions"] = {
            "strategic_fit": {
                "active": {
                    "horizons": result["multi_horizon_impact"]["sides"]["active"][
                        "horizons"
                    ]
                }
            }
        }
        original = copy.deepcopy(result)
        html = render_trade_explanation(result, league_id="A")
        self.assertIn("5.43", html)
        self.assertNotIn("5.4318000000001", html)
        self.assertIn("27.335", html)
        self.assertEqual(result, original)
