"""Legal dependency closure; presentation findings never relax Trade diagnostics."""

from copy import deepcopy
from datetime import timedelta
import unittest
from unittest.mock import patch
from tests import test_dynamic_needs as fixtures
from src.core.intelligence import roster_diagnostics as d


class PositionalPresentationScopeTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CanonicalDiagnosticTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def control(self, slots=None, status=None, missing=True):
        return self.f.publish(
            [
                [
                    ("a", "QB", 30),
                    ("b", "QB", 20),
                    ("r", "RB", 10),
                    ("gap", "RB", None if missing else 0),
                ],
                [("x", "QB", 15), ("y", "QB", 12), ("s", "RB", 9)],
            ],
            slots or ["QB", "RB", "FLEX", "BN"],
            statuses={"gap": status or {}},
        )

    def test_unrelated_missing_reserve_preserves_qb_comparison_not_trade_strength(self):
        team = self.control()["teams"]["1"]
        self.assertFalse(team["positions"]["QB"]["strength"])
        self.assertEqual(team["positions"]["QB"]["surplus_assets"], [])
        scoped = team["presentation_positions"]["QB"]
        self.assertTrue(scoped["strength"])
        self.assertEqual(scoped["starter_points"], 30)
        self.assertFalse(team["presentation_positions"]["RB"]["strength"])
        self.assertEqual(scoped["dependency_scope"]["slots"], ["QB"])

    def test_superflex_makes_rb_gap_relevant_to_qb(self):
        row = self.control(["QB", "RB", "SUPER_FLEX", "BN"])["teams"]["1"][
            "presentation_positions"
        ]["QB"]
        self.assertFalse(row["strength"])
        self.assertIn(
            "gap", [g["player_id"] for g in row["dependency_scope"]["blockers"]]
        )

    def test_questionable_reserve_is_not_dependable_cover(self):
        team = self.control(status={"status": "Questionable"}, missing=False)["teams"][
            "1"
        ]
        self.assertTrue(team["presentation_positions"]["QB"]["strength"])
        self.assertFalse(
            team["presentation_positions"]["RB"]["dependency_scope"]["independent"]
        )
        self.assertFalse(team["positions"]["RB"]["quality_depth_need"])

    def test_explicit_zero_is_supported_dependency(self):
        row = self.control(missing=False)["teams"]["1"]["presentation_positions"]["RB"]
        self.assertEqual(row["dependency_scope"]["blockers"], [])

    def test_excluded_ir_and_bye_do_not_enter_legal_scope(self):
        for status in ({"roster_slot": "IR"}, {"roster_slot": "Taxi"}, {"bye_week": 1}):
            with self.subTest(status=status):
                team = self.control(status=status)["teams"]["1"]
                self.assertIn("gap", team["excluded_player_ids"])
                self.assertEqual(
                    team["presentation_positions"]["RB"]["dependency_scope"][
                        "blockers"
                    ],
                    [],
                )

    def test_multi_position_player_connects_otherwise_separate_slots(self):
        self.control()
        self.f.data["teams"][0]["players"][-1]["fantasy_positions"] = ["RB", "QB"]
        row = d.diagnose_league(self.f.data, self.f.snapshot)["teams"]["1"][
            "presentation_positions"
        ]["QB"]
        self.assertFalse(row["strength"])
        self.assertIn("RB", row["dependency_scope"]["slots"])

        scope = d._presentation_scope('QB', ['QB', 'RB'], {'1': [dict(id='unknown', position='WR', fantasy_positions=[], projected_points=5)]}, {'1': []})
        self.assertFalse(scope['independent'])
        self.assertIn('Unknown eligibility',scope['blockers'][0]['reason'])

    def test_age_and_failed_refresh_keep_provisional_scope(self):
        self.control()
        saved = deepcopy(self.f.data)
        with patch.object(d, "_now", return_value=d._now() + timedelta(days=10)):
            row = d.diagnose_league(self.f.data, self.f.snapshot)["teams"]["1"][
                "presentation_positions"
            ]["QB"]
        self.assertEqual(row["conclusion_state"], "provisional")
        self.assertTrue(row["source_limitations"])
        self.assertEqual(self.f.data, saved)

    def test_incompatible_scoring_withholds_all_presentation_findings(self):
        self.control()
        self.f.data["league"]["scoring_settings"] = {"pass_yd": 2}
        team = d.diagnose_league(self.f.data, self.f.snapshot)["teams"]["1"]
        self.assertNotIn("presentation_positions", team)
