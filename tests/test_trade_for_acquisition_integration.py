"""Existing canonical sources/search/evaluator; cost roles never alter verdicts."""

from copy import deepcopy
import unittest
from unittest.mock import patch
from services import trade_intelligence as trade
from services.trade_for_acquisition import select_offers
from tests import test_trade_discovery_repair as discovery
from tests import test_offer_comparison_browser as comparison


class AcquisitionIntegrationTests(unittest.TestCase):
    def test_actual_bounded_search_keeps_cost_minimum_from_all_eligible_assessments(
        self,
    ):
        fixture = discovery.DiscoveryRepairTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        captured = []

        def select(rows, *args, **kwargs):
            captured.extend(deepcopy(rows))
            return select_offers(rows, *args, **kwargs)

        with patch("services.trade_for_acquisition.select_offers", side_effect=select):
            result = fixture.search(
                "trade_for", asset_id="2w", protected_assets=["1qb"]
            )
        self.assertTrue(result["results"])
        self.assertTrue(captured)
        priced = [
            r
            for r in captured
            if r["evaluation"]["market_evidence"]["availability"] == "full"
        ]
        winner = next(
            r
            for r in result["results"]
            if "lowest_cost" in r["acquisition_comparison"]["roles"]
        )
        self.assertEqual(
            winner["acquisition_comparison"]["cost"]["outgoing"],
            min(r["evaluation"]["market_evidence"]["sent"]["total"] for r in priced),
        )
        best = next(
            r
            for r in result["results"]
            if "best_fit" in r["acquisition_comparison"]["roles"]
        )
        self.assertEqual(best["proposal"], captured[0]["proposal"])
        for row in result["results"]:
            self.assertNotIn("1qb", row["proposal"]["assets_sent"])
            self.assertIn("2w", row["proposal"]["assets_received"])
            manual = trade.evaluate_trade_request(
                fixture.data,
                {**row["proposal"], "workflow": "create"},
                projection_reader=fixture.fixture.reader,
            )
            self.assertEqual(
                row["evaluation"]["recommendation"],
                manual["evaluation"]["recommendation"],
            )
            self.assertEqual(
                row["evaluation"]["market_evidence"],
                manual["evaluation"]["market_evidence"],
            )
        self.assertLessEqual(result["search_evidence"]["full_evaluations"], 240)

    def test_granite_shaped_and_superflex_lineups_keep_shared_evaluator_values(self):
        for sf in (False, True):
            with self.subTest(superflex=sf):
                f = comparison.OfferComparisonBrowserTests()
                source, _, fixture = f.fixture(superflex=sf)
                try:
                    data = fixture.editor.data
                    with patch(
                        "services.trade_intelligence._trade_projection_service",
                        return_value=fixture.capital.reader,
                    ):
                        payload = {
                            "active_roster_id": 1,
                            "partner_roster_id": 2,
                            "assets_sent": ["a"],
                            "assets_received": ["c"],
                            "strategy": "WIN NOW",
                        }
                        manual = trade.evaluate_trade_request(
                            data, {**payload, "workflow": "create"}
                        )
                        targeted = trade.evaluate_trade_request(
                            data, {**payload, "workflow": "trade_for"}
                        )
                    self.assertEqual(
                        manual["evaluation"]["market_evidence"],
                        targeted["evaluation"]["market_evidence"],
                    )
                    self.assertEqual(
                        manual["evaluation"]["recommendation"],
                        targeted["evaluation"]["recommendation"],
                    )
                    self.assertEqual(
                        manual["evaluation"]["decision_context"]["lineup_comparisons"],
                        targeted["evaluation"]["decision_context"][
                            "lineup_comparisons"
                        ],
                    )
                finally:
                    f.doCleanups()
