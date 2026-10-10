"""Supported exploration stays separate from recommendation admission and prices."""

import copy
import unittest
from unittest.mock import patch

from services.trade_search_policy import SearchFunnel, supported_exploration, rank_key
from services.trade_intelligence import evaluate_trade_request, build_trade_workspace
from tests import test_trade_discovery_repair as fixtures
from services.trade_calculator import market_verdict
from dataclasses import replace


class SimpleDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DiscoveryRepairTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.row = self.f.search("trade_for", asset_id="2w")["results"][0]

    def test_supported_costly_trade_remains_rejected_but_explorable(self):
        e = self.row["evaluation"]
        e["recommendation"] = "NOT WORTH IT"
        e["generated_trade_eligible"] = False
        funnel = SearchFunnel(5)
        self.assertFalse(funnel.assessed(self.row))
        self.assertTrue(supported_exploration(e))
        assets = {
            a.asset_id: a
            for p in build_trade_workspace(self.f.data, 1)["pools"].values()
            for a in p
        }
        rows = funnel.explore(assets)
        self.assertEqual(rows[0]["evaluation"]["recommendation"], "NOT WORTH IT")
        self.assertEqual(funnel.counts["eligible"], 0)
        self.assertEqual(rows[0]["proposal"], self.row["proposal"])

    def test_hard_invalid_and_incomplete_evidence_cannot_be_exploration(self):
        for field, value in (
            ("legal", False),
            ("recommendation", None),
            ("market_evidence", {"availability": "partial"}),
            ("legality", {"execution_status": "REQUIRES ROSTER RESOLUTION"}),
            (
                "recommendation_trace",
                {"rule_reasons": ["FUTURE_CAPITAL_TRADEOFF_UNRESOLVED"]},
            ),
        ):
            with self.subTest(field=field):
                e = copy.deepcopy(self.row["evaluation"])
                e[field] = value
                self.assertFalse(supported_exploration(e))
        for side in ("active", "partner"):
            e = copy.deepcopy(self.row["evaluation"])
            e["dimensions"]["strategic_fit"][side]["projection_coverage_complete"] = (
                False
            )
            self.assertFalse(supported_exploration(e))

    def test_filtered_intent_does_not_reappear_as_exploration(self):
        row = copy.deepcopy(self.row)
        row["evaluation"]["recommendation"] = "REJECT"
        row["evaluation"]["generated_trade_eligible"] = False
        f = SearchFunnel(5)
        f.assessed(row, filtered=True)
        self.assertEqual(f.explorations, [])

    def test_actual_costly_acquisition_with_counterparty_support_is_visible(self):
        # Current engine and actual bounded candidate generation, no label patch.
        r = self.f.search("trade_for", asset_id="2w")
        rows = r["exploratory_results"]
        self.assertTrue(rows)
        first = rows[0]["evaluation"]
        self.assertEqual(first["recommendation"], "NOT WORTH IT")
        self.assertIn(
            first["dimensions"]["counterparty_plausibility"]["assessment"],
            ("STRONG", "PLAUSIBLE"),
        )
        self.assertTrue(
            any(
                row["evaluation"]["values"]["sent"]
                > row["evaluation"]["values"]["received"]
                for row in rows
            )
        )
        self.assertLessEqual(len(rows), 3)
        for row in rows:
            self.assertTrue(supported_exploration(row["evaluation"]))
            self.assertTrue(row["exploration"])
            self.assertIn("2w", row["proposal"]["assets_received"])
        self.assertLessEqual(r["search_evidence"]["full_evaluations"], 240)

    def test_recommended_empty_can_explore_supported_rows_without_new_evaluations(self):
        original = evaluate_trade_request
        calls = []

        def costly(*args, **kwargs):
            row = original(*args, **kwargs)
            calls.append(row)
            if supported_exploration(row["evaluation"]):
                row["evaluation"]["recommendation"] = "NOT WORTH IT"
                row["evaluation"]["generated_trade_eligible"] = False
            return row

        with patch(
            "services.trade_intelligence.evaluate_trade_request", side_effect=costly
        ):
            r = self.f.search("recommended")
        self.assertEqual(r["results"], [])
        self.assertTrue(r["exploratory_results"])
        self.assertLessEqual(len(r["exploratory_results"]), 3)
        self.assertEqual(r["search_evidence"]["full_evaluations"], len(calls))
        self.assertTrue(r["search_evidence"]["bounded"])
        for row in r["exploratory_results"]:
            self.assertEqual(row["evaluation"]["recommendation"], "NOT WORTH IT")

    def test_unfavorable_actual_trade_for_packages_use_existing_bounded_assessments(
        self,
    ):
        original = evaluate_trade_request

        def costly(*args, **kwargs):
            row = original(*args, **kwargs)
            if supported_exploration(row["evaluation"]):
                row["evaluation"]["recommendation"] = "NOT WORTH IT"
                row["evaluation"]["generated_trade_eligible"] = False
            return row

        with patch(
            "services.trade_intelligence.evaluate_trade_request", side_effect=costly
        ):
            r = self.f.search("trade_for", asset_id="2w", protected_assets=["1wb"])
        self.assertEqual(r["results"], [])
        self.assertTrue(r["exploratory_results"])
        for row in r["exploratory_results"]:
            self.assertIn("2w", row["proposal"]["assets_received"])
            self.assertNotIn("1wb", row["proposal"]["assets_sent"])
            self.assertTrue(supported_exploration(row["evaluation"]))
            self.assertEqual(row["evaluation"]["recommendation"], "NOT WORTH IT")
        self.assertLessEqual(r["search_evidence"]["full_evaluations"], 240)
        self.assertEqual(r["provider_requests"], 0)

    def test_price_scale_absolute_tolerances_do_not_override_exact_truth(self):
        a = build_trade_workspace(self.f.data, 1, market_only=True)["pools"][1][0]
        for sent, received in (
            (1000, 900),
            (100, 20),
            (400, 300),
            (180, 100),
            (60, 20),
        ):
            result = market_verdict(
                [replace(a, trade_value=sent)], [replace(a, trade_value=received)]
            )
            self.assertEqual(result["verdict"], "SIDE_B_FAVORED")
            self.assertEqual(result["absolute_gap"], sent - received)
        self.assertEqual(market_verdict([a], [a])["verdict"], "APPROXIMATELY_BALANCED")
        self.assertEqual(
            market_verdict([replace(a, trade_value=None)], [a])["verdict"],
            "UNAVAILABLE",
        )

    def test_strategy_first_rank_does_not_reprice_a_supported_overpay(self):
        better = copy.deepcopy(self.row)
        worse = copy.deepcopy(self.row)
        better["evaluation"]["recommendation"] = "WORTH PURSUING"
        worse["evaluation"]["recommendation"] = "FAIR / OPTIONAL"
        better["evaluation"]["values"]["ratio"] = 0.8
        before = copy.deepcopy(better["evaluation"]["values"])
        self.assertLess(rank_key(better), rank_key(worse))
        self.assertEqual(better["evaluation"]["values"], before)
