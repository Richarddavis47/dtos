"""Canonical publisher controls for diagnostic evidence, eligibility and bounds."""

from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from tests import test_dynamic_needs as fixtures
from src.core.intelligence import roster_diagnostics as diagnostics
from src.core.trade_intelligence.models import TradeProposal


class DiagnosticAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CanonicalDiagnosticTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def facts(self):
        return diagnostics.team_diagnostics(self.data, 1, self.snapshot)["positions"][
            "QB"
        ]

    def control(self, status="Active"):
        result = self.fixture.publish(
            [
                [("a", "QB", 30), ("b", "QB", 29), ("c", "QB", 28)],
                [("x", "QB", 20), ("y", "QB", 19), ("z", "QB", 18)],
            ],
            ["QB", "SUPER_FLEX", "BN"],
            statuses={"c": {"status": status}},
        )
        self.data, self.snapshot = self.fixture.data, self.fixture.snapshot
        return result

    def test_inactive_and_retired_are_not_usable_cover(self):
        for status in ("Inactive", "Retired", "Out"):
            with self.subTest(status=status):
                self.control(status)
                self.assertTrue(self.facts()["resilience_need"])
                team = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
                self.assertIn("c", team["excluded_player_ids"])

    def test_explicit_stale_projection_is_disclosed(self):
        self.control()
        self.snapshot["players"]["a"]["source_freshness"] = "Stale"
        row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
        self.assertIn("stale", row["positions"]["QB"]["reason"].lower())

    def test_absent_scoring_withholds_numeric_conclusions(self):
        self.control()
        del self.data["league"]["scoring_settings"]
        row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
        self.assertIsNone(row["optimal_points"])
        self.assertFalse(row["positions"]["QB"]["strength"])

    def test_package_bound_precedes_any_optimization(self):
        self.control()
        self.data["league"]["roster_positions"] = ["SUPER_FLEX"] * 15
        proposal = TradeProposal(
            active_roster_id=1,
            partner_roster_id=2,
            assets_sent=(),
            assets_received=(),
            package_type="test",
        )
        with patch.object(
            diagnostics.SearchLineupMemo,
            "solve",
            side_effect=AssertionError("unsupported solver entered"),
        ):
            result = diagnostics.package_diagnostics(
                self.data, proposal, self.snapshot, {}, {}
            )
        self.assertIsNone(result["sides"]["active"]["post_optimal_points"])

    def test_canonical_status_policy_and_identity_are_preserved(self):
        for status in ("Active", "Questionable", "Doubtful", "Unknown", "Unfamiliar"):
            with self.subTest(status=status):
                self.control(status)
                before = deepcopy(self.data)
                row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
                self.assertEqual(before, self.data)
                evidence = next(e for e in row["eligibility"] if e["player_id"] == "c")
                self.assertEqual(evidence["excluded"], status == "Unfamiliar")
                if status in {"Questionable", "Doubtful"}:
                    self.assertEqual(
                        row["positions"]["QB"]["classification"], "Uncertain"
                    )
                if status == "Active":
                    self.assertTrue(row["positions"]["QB"]["strength"])
                if status == "Unknown":
                    self.assertEqual(
                        row["positions"]["QB"]["conclusion_state"], "provisional"
                    )

    def test_reserve_taxi_and_status_cache_invalidation(self):
        self.control()
        initial = diagnostics.diagnostic_identity(self.data, self.snapshot)
        for slot in ("IR", "Taxi"):
            self.data["teams"][0]["players"][2]["roster_slot"] = slot
            row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
            self.assertIn("c", row["excluded_player_ids"])
            self.assertNotEqual(initial, row["generation"])
        self.data["teams"][0]["players"][2].update(
            roster_slot="Bench", status="Retired"
        )
        self.assertTrue(self.facts()["resilience_need"])

    def test_fresh_stale_retained_unknown_and_retrieval_clock(self):
        self.control()
        for row in self.snapshot["players"].values():
            row["source_freshness"] = "Fresh"
            row["source_timestamp"] = datetime.now(timezone.utc).isoformat()
        fresh = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
        self.assertFalse(fresh["evidence"]["retained"])
        self.snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()
        self.assertEqual(
            fresh["generation"],
            diagnostics.diagnostic_identity(self.data, self.snapshot),
        )
        for state in ("Stale", "Retained", "Fallback", "Unavailable"):
            self.snapshot["players"]["c"]["source_freshness"] = state
            if state == "Unavailable":
                self.snapshot["players"]["c"]["source_timestamp"] = None
            row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
            self.assertTrue(row["evidence"]["retained"])
            self.assertIn(state, row["positions"]["QB"]["reason"])
            self.assertNotEqual(fresh["generation"], row["generation"])

    def test_mixed_leaf_generation_is_not_a_compatible_horizon(self):
        self.control()
        self.snapshot["players"]["c"]["projection_snapshot_id"] = "foreign"
        row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
        self.assertIsNone(row["optimal_points"])
        self.assertIn("Mixed", row["limitations"][0])

    def test_actual_missing_scoring_publication_zero_is_withheld(self):
        self.control()
        self.data["league"].pop("scoring_settings")
        self.snapshot = self.fixture.service.publish_horizon(
            {
                1: [
                    {
                        "player_id": p,
                        "season": 2026,
                        "week": 1,
                        "player": {"position": "QB"},
                        "stats": {"pass_yd": 30},
                    }
                    for p in ("a", "b", "c", "x", "y", "z")
                ]
            },
            data=self.data,
            league_id=self.data["league"]["league_id"],
            season=2026,
            current_week=1,
        )
        self.assertEqual(self.snapshot["players"]["a"]["canonical_projection"], 0)
        row = diagnostics.team_diagnostics(self.data, 1, self.snapshot)
        self.assertIsNone(row["optimal_points"])
        self.assertIn("scoring", row["positions"]["QB"]["reason"])
        proposal = TradeProposal(1, 2, (), (), "test")
        with patch.object(
            diagnostics.SearchLineupMemo,
            "solve",
            side_effect=AssertionError("unsupported"),
        ):
            package = diagnostics.package_diagnostics(
                self.data, proposal, self.snapshot, {}, {}
            )
        self.assertIsNone(package["sides"]["active"]["post_optimal_points"])

    def test_valid_zero_incomplete_scoring_and_unsupported_slots(self):
        self.control()
        for row in self.snapshot["players"].values():
            row["canonical_projection"] = 0
        self.assertEqual(
            diagnostics.team_diagnostics(self.data, 1, self.snapshot)["optimal_points"],
            0,
        )
        self.snapshot["players"]["c"]["canonical_projection"] = None
        self.assertFalse(self.facts()["strength"])
        for scoring in ({}, {"pass_yd": None}, {"unknown_rule": 1}):
            self.data["league"]["scoring_settings"] = scoring
            self.assertIsNone(
                diagnostics.team_diagnostics(self.data, 1, self.snapshot)[
                    "optimal_points"
                ]
            )
        self.control()
        self.data["league"]["roster_positions"] = ["UNSUPPORTED_SLOT"]
        self.assertIsNone(
            diagnostics.team_diagnostics(self.data, 1, self.snapshot)["optimal_points"]
        )

    def test_fourteen_supported_fifteen_blocked_repeated_package(self):
        self.control()
        self.data["league"]["roster_positions"] = ["QB"] * 14
        proposal = TradeProposal(1, 2, (), (), "test")
        result = diagnostics.package_diagnostics(
            self.data, proposal, self.snapshot, {}, {}
        )
        self.assertIn("positions", result["sides"]["active"])
        self.assertEqual(len(result["sides"]["active"]["positions"]), 4)
        self.data["league"]["roster_positions"] = ["SUPER_FLEX"] * 15
        with patch.object(
            diagnostics.SearchLineupMemo,
            "solve",
            side_effect=AssertionError("unsupported"),
        ):
            for _ in range(10):
                result = diagnostics.package_diagnostics(
                    self.data, proposal, self.snapshot, {}, {}
                )
                self.assertFalse(result["evidence"]["calculation_supported"])
