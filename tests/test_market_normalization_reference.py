"""Provider normalization survives league relevance without copying populations."""
from copy import deepcopy
import unittest

from src.core.valuation.calibration import cached_market_consensus
from src.core.valuation.normalization import normalize_cached_value, prepare_market_normalization


class MarketNormalizationReferenceTests(unittest.TestCase):
    def fixture(self):
        return {"providers": {"FantasyCalc": {str(i): {"value": i * 100, "confidence": 90}
            for i in range(1, 101)}}}

    def test_two_league_subsets_use_same_full_population(self):
        market = self.fixture()
        prepare_market_normalization(market)
        expected = cached_market_consensus(market, ["50"])["50"]
        for members in (("50",), tuple(str(i) for i in range(30, 70))):
            subset = deepcopy(market)
            subset["providers"]["FantasyCalc"] = {key: row for key, row in subset["providers"]["FantasyCalc"].items() if key in members}
            self.assertEqual(cached_market_consensus(subset, ["50"])["50"], expected)

    def test_unchanged_preparation_is_idempotent(self):
        market = self.fixture()
        prepare_market_normalization(market)
        before = deepcopy(market)
        prepare_market_normalization(market)
        self.assertEqual(market, before)
        reference = market["providers"]["FantasyCalc"]["50"]["normalization_reference"]
        self.assertEqual(reference["population_size"], 100)
        self.assertFalse(any(isinstance(value, (list, dict)) for value in reference.values()))

    def test_material_population_change_invalidates_reference(self):
        market = self.fixture()
        prepare_market_normalization(market)
        before = deepcopy(market["providers"]["FantasyCalc"]["50"]["normalization_reference"])
        market["providers"]["FantasyCalc"]["1"]["value"] = 11000
        prepare_market_normalization(market)
        self.assertNotEqual(before["generation"], market["providers"]["FantasyCalc"]["50"]["normalization_reference"]["generation"])

    def test_stale_raw_value_cannot_reuse_old_normalized_value(self):
        market = self.fixture()
        prepare_market_normalization(market)
        row = market["providers"]["FantasyCalc"]["50"]
        row["value"] = 0
        self.assertEqual(normalize_cached_value("FantasyCalc", row).normalized_value, 0)

    def test_source_version_change_cannot_reuse_reference(self):
        market = self.fixture()
        prepare_market_normalization(market)
        row = market["providers"]["FantasyCalc"]["50"]
        row["normalization_reference"]["version"] = "obsolete"
        self.assertEqual(normalize_cached_value("FantasyCalc", row).method, "provider_range_linear")

    def test_zero_confidence_is_not_replaced_by_default_confidence(self):
        market = self.fixture()
        market["providers"]["FantasyCalc"]["50"]["confidence"] = 0
        prepare_market_normalization(market)
        self.assertEqual(cached_market_consensus(market, ["50"])["50"][1], 0)
