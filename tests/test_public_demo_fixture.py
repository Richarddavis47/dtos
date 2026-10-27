"""The public illustration is a frozen export of one verified football context."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from services.personal_rankings import personal_values, to_trade_id
from src.core.projection_intelligence.scoring import fantasy_points
from tools.validation import public_demo_fixture as fixture


class PublicDemoFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network_attempts = []

        def deny_network(*args, **kwargs):
            cls.network_attempts.append("socket connection")
            raise AssertionError("The offline fixture must never fetch a provider")

        with patch.object(socket.socket, "connect", side_effect=deny_network):
            cls.actual = fixture.generate()
        path = Path(__file__).resolve().parents[1] / "src/ui/public_demo_data.json"
        cls.raw = path.read_bytes()
        cls.frozen = json.loads(cls.raw)

    def test_complete_reviewed_export_matches_authoritative_producers(self):
        # generate() uses the actual published projection reader, legal solver,
        # bilateral evaluator, build_universe and personal rank-slot adapter.
        # It checks Custom parity of complete neutral Market and opponent facts.
        self.assertEqual(self.actual, self.frozen)
        self.assertLessEqual(len(self.raw), 16 * 1024)
        self.assertEqual(self.network_attempts, [])

    def test_named_players_keep_verified_positions_and_hypothetical_labels(self):
        expected = {
            "Josh Allen": "QB", "Lamar Jackson": "QB", "Jalen Hurts": "QB",
            "Bijan Robinson": "RB", "Christian McCaffrey": "RB",
            "DeVonta Smith": "WR", "Ja'Marr Chase": "WR", "CeeDee Lamb": "WR",
            "Brock Bowers": "TE", "George Kittle": "TE", "Justin Jefferson": "WR",
        }
        rows = self.frozen["team"]["lineup"] + self.frozen["team"]["reserve"] + self.frozen["trade"]["receive"]
        self.assertEqual({r["name"]: r["position"] for r in rows}, expected)
        self.assertIn("not actual player assessments", self.frozen["limitations"][0])
        self.assertEqual(self.frozen["trade"]["send"][0]["name"], "Lamar Jackson")
        for row in self.frozen["personal"]["before_order"] + self.frozen["personal"]["after_order"]:
            self.assertIn(row["label"], {"Lamar Jackson", "Justin Jefferson"})

    def test_standard_football_stats_and_full_ppr_context(self):
        data, stats = fixture.fixture_input()
        self.assertEqual(data["league"]["total_rosters"], len(data["teams"]))
        self.assertEqual(data["league"]["settings"]["playoff_teams"], 4)
        self.assertEqual(
            data["league"]["roster_positions"][:6],
            ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX"],
        )
        self.assertEqual(fixture.SCORING["pass_yd"], 0.04)
        self.assertEqual(fixture.SCORING["pass_td"], 4)
        self.assertEqual(fixture.SCORING["rec"], 1)
        self.assertEqual(fantasy_points(stats["harbor-q1"], fixture.SCORING, "QB"), 34)
        self.assertEqual(fantasy_points(stats["harbor-q2"], fixture.SCORING, "QB"), 30)
        self.assertEqual(fantasy_points(stats["harbor-q3"], fixture.SCORING, "QB"), 24)
        self.assertEqual(fantasy_points(stats["summit-w1"], fixture.SCORING, "WR"), 26)
        for pid, production in stats.items():
            if data["players"][pid]["position"] != "QB":
                self.assertFalse(
                    set(production) & {"pass_yd", "pass_td", "pass_int"}, pid
                )

    def test_highest_legal_lineup_and_meaningful_superflex_cover(self):
        team = self.frozen["team"]
        self.assertEqual(team["lineup_points"], 108)
        self.assertEqual(
            (team["comparison_rank"], team["comparison_population"]), (2, 4)
        )
        self.assertEqual(sum(row["points"] for row in team["lineup"]), 108)
        self.assertEqual(len({row["asset_id"] for row in team["lineup"]}), 6)
        self.assertEqual(
            sorted(row["slot"] for row in team["lineup"]), sorted(fixture.STARTERS)
        )
        for row in team["lineup"]:
            if row["slot"] == "FLEX":
                self.assertIn(row["position"], {"RB", "WR", "TE"})
        reserve = next(r for r in team["reserve"] if r["position"] == "QB")
        self.assertEqual((reserve["asset_id"], reserve["points"]), ("harbor-q3", 24))
        self.assertNotIn(reserve["asset_id"], {r["asset_id"] for r in team["lineup"]})

    def test_bilateral_trade_has_real_benefits_and_explicit_depth_cost(self):
        trade = self.frozen["trade"]
        self.assertEqual([a["asset_id"] for a in trade["send"]], ["harbor-q2"])
        self.assertEqual([a["asset_id"] for a in trade["receive"]], ["summit-w1"])
        self.assertEqual((trade["market_sent"], trade["market_received"]), (528, 528))
        self.assertEqual(
            (
                trade["active"]["before"],
                trade["active"]["after"],
                trade["active"]["delta"],
            ),
            (108, 120, 12),
        )
        self.assertEqual(
            (
                trade["partner"]["before"],
                trade["partner"]["after"],
                trade["partner"]["delta"],
            ),
            (112, 116, 4),
        )
        self.assertEqual(
            (
                trade["active"]["reserve_before"],
                trade["active"]["reserve_after"],
                trade["active"]["reserve_delta"],
            ),
            (43, 27, -16),
        )
        self.assertEqual(trade["partner"]["reserve_delta"], 0)
        self.assertIn("no further quarterback replacement", trade["active"]["cost"])
        self.assertIn("highest-projected receiver", trade["partner"]["cost"])
        self.assertEqual(trade["recommendation"], "WORTH PURSUING")
        self.assertTrue(trade["eligible"])
        self.assertIn("not a prediction", trade["qualification"])

    def test_personal_same_package_keeps_market_and_exact_identity_separate(self):
        personal = self.frozen["personal"]
        self.assertEqual(
            (personal["neutral_sent"], personal["neutral_received"]), (528, 528)
        )
        self.assertEqual(
            (personal["personal_sent"], personal["personal_received"]), (528, 785)
        )
        before = {r["asset_id"]: r for r in personal["before_order"]}
        after = {r["asset_id"]: r for r in personal["after_order"]}
        self.assertEqual(before["player:summit-w1"]["rank"], 5)
        self.assertEqual(after["player:summit-w1"]["rank"], 1)
        for row in personal["before_order"] + personal["after_order"]:
            self.assertEqual(to_trade_id(row["asset_id"]), row["trade_asset_id"])
        self.assertEqual(personal["universe_asset_count"], 32)
        self.assertEqual(
            set(personal["unpriced_exact_picks"]), {"pick:2028:1:1", "pick:2028:1:2"}
        )
        self.assertIn("no supplied Market quote", personal["cohort_label"])
        self.assertEqual(
            personal["unchanged"],
            [
                "Neutral Market prices",
                "Both legal-lineup calculations",
                "Opponent neutral valuation",
            ],
        )

    def test_exact_capital_preserves_origin_separate_from_owner(self):
        pick = self.frozen["team"]["capital"][0]
        self.assertEqual(pick["asset_id"], "pick:2028:1:2")
        self.assertEqual(to_trade_id(pick["asset_id"]), "2028-R1-2")
        self.assertEqual((pick["year"], pick["round"]), (2028, 1))
        self.assertEqual(
            (pick["original_franchise_id"], pick["current_owner_id"]), (2, 1)
        )
        self.assertIn("Summit", pick["original_franchise"])
        self.assertIn("Harbor", pick["current_owner"])
        self.assertNotIn("value", pick)

    def test_missing_price_is_not_zero_or_a_frozen_personal_endorsement(self):
        doc = {
            "order": ["player:b", "player:a"],
            "baseline": {"ids": ["player:a", "player:b"]},
        }
        available = personal_values(
            doc,
            {
                "rows": [
                    {"asset_id": "player:a", "market_value": 0},
                    {"asset_id": "player:b", "market_value": 10},
                ]
            },
        )
        self.assertTrue(available["available"])
        self.assertEqual(available["values"]["player:a"], 0)
        missing = personal_values(
            doc, {"rows": [{"asset_id": "player:a", "market_value": 0}]}
        )
        self.assertFalse(missing["available"])
        self.assertEqual(missing["values"], {"player:a": 0})
        self.assertNotIn("player:b", missing["values"])
        self.assertTrue(missing["partial_available"])

    def test_public_export_has_only_fictional_presentation_fields(self):
        data, _ = fixture.fixture_input()
        self.assertEqual(self.frozen["fixture_id"], fixture.FIXTURE_ID)
        self.assertIn("fictional", self.frozen["label"])
        self.assertEqual(
            set(self.frozen),
            {
                "version",
                "fixture_id",
                "input_sha256",
                "label",
                "season",
                "week",
                "league",
                "limitations",
                "team",
                "trade",
                "personal",
            },
        )
        self.assertEqual((self.frozen["season"], self.frozen["week"]), (2026, 5))
        for word in [
            "csrf",
            "cookie",
            "session",
            "authorization",
            "opportunity_token",
            "http://",
            "https://",
        ]:
            self.assertNotIn(word, self.raw.decode().casefold())
        self.assertTrue(all("Front Office" in t["team_name"] for t in data["teams"]))

    def test_failed_regeneration_does_not_replace_the_reviewed_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "reviewed.json"
            path.write_text("previous reviewed artifact")
            with (
                patch.object(
                    fixture, "generate", side_effect=ValueError("incompatible source")
                ),
                patch("sys.argv", ["public_demo_fixture", "--output", str(path)]),
            ):
                with self.assertRaises(ValueError):
                    fixture.main()
            self.assertEqual(path.read_text(), "previous reviewed artifact")


if __name__ == "__main__":
    unittest.main()
