"""Compact audit inputs preserve the entire canonical calibration contract."""
import copy
import gc
import tracemalloc
import unittest
from unittest.mock import patch

from src.core.valuation import automation
from src.core.valuation.universe import ValuationUniverse
from tests.test_market_calibration_dashboard import calibration_fixture


class CalibrationMemoryTests(unittest.TestCase):
    def test_complete_report_and_application_state_match_full_universe(self):
        for healthy in (True, False):
            for apply in (True, False):
                with self.subTest(healthy=healthy, apply=apply):
                    data, state = calibration_fixture(80, healthy=healthy)
                    data["normalized_players"]["1"].update(status="Retired", age=34)
                    data["normalized_players"]["2"].update(position="WR", age=22, rookie_class=2026)
                    data["market_data"]["providers"]["DynastyProcess"].pop("3")
                    original, corrected = copy.deepcopy(data), copy.deepcopy(data)
                    with patch.object(automation, "_now", return_value="2026-09-01T00:00:00+00:00"), patch("src.core.valuation.universe._now", return_value="2026-09-01T00:00:00+00:00"):
                        with patch.object(automation, "_calibration_universe", ValuationUniverse):
                            before = automation.audit_market_calibration(original, state, apply=apply)
                        after = automation.audit_market_calibration(corrected, state, apply=apply)
                    self.assertEqual(before, after)
                    self.assertEqual(original, corrected)

    def test_all_assets_still_evaluated_without_full_display_retention(self):
        data, state = calibration_fixture(200)
        with patch.object(ValuationUniverse, "_build", side_effect=AssertionError("Eager display universe")):
            universe = automation._calibration_universe(data, state)
        self.assertEqual(len(universe.assets), 240)
        self.assertEqual(len({row["asset_id"] for row in universe.assets}), 240)
        self.assertEqual(universe.status()["counts"]["total"], 240)
        self.assertTrue(all(len(row["layers"]) == 4 for row in universe.assets))

    def test_temporary_peak_is_lower_without_sampling_or_new_caches(self):
        data, state = calibration_fixture(300)

        def peak(factory):
            gc.collect()
            tracemalloc.start()
            try:
                universe = factory(data, state)
                count = len(universe.assets)
                return count, tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()

        original_count, original_peak = peak(ValuationUniverse)
        compact_count, compact_peak = peak(automation._calibration_universe)
        self.assertEqual(original_count, compact_count)
        self.assertLess(compact_peak, original_peak * .75)
