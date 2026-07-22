"""Regression coverage for canonical valuation calibration and trade safety."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from src.core.market_intelligence import ProviderQuote
from src.core.market_intelligence.aggregation import build_consensus
from src.core.trade_intelligence import TradeAsset
from src.core.valuation import (
    CalibrationStatus,
    NORMALIZATION_VERSION,
    adjusted_package_value,
    build_canonical_consensus,
    evaluate_trade_guardrails,
    normalize_internal,
    normalize_pick,
    normalize_value,
)


def asset(asset_id: str, value: int, *, kind: str = "player", position: str | None = "WR", confidence: int = 85) -> TradeAsset:
    return TradeAsset(asset_id, kind, asset_id, position, value, value, value, value, 20, 1, value, 80, confidence, "calibrated")


class NormalizationTests(unittest.TestCase):
    def test_provider_specific_raw_scales_normalize_to_canonical_range(self) -> None:
        fantasycalc = normalize_value("FantasyCalc", 7200)
        dynastyprocess = normalize_value("DynastyProcess", 7200)
        self.assertEqual(fantasycalc.normalized_value, 600)
        self.assertEqual(dynastyprocess.normalized_value, 720)
        self.assertTrue(all(0 <= item.normalized_value <= 1000 for item in (fantasycalc, dynastyprocess)))

    def test_distribution_method_is_deterministic_and_preserves_raw_value(self) -> None:
        population = tuple(range(0, 10_001, 500))
        first = normalize_value("DynastyProcess", 7500, distribution=population)
        second = normalize_value("DynastyProcess", 7500, distribution=population)
        self.assertEqual(first, second)
        self.assertEqual(first.raw_value, 7500)
        self.assertIn("percentile", first.method)

    def test_internal_50_and_external_7500_are_compared_only_after_normalization(self) -> None:
        intrinsic = normalize_internal(50)
        market = normalize_value("DynastyProcess", 7500).normalized_value
        self.assertEqual(intrinsic, 500)
        self.assertEqual(market, 750)
        self.assertEqual(intrinsic - market, -250)

    def test_pick_rounds_are_normalized_with_explicit_tiers(self) -> None:
        first = normalize_pick(82, 1)
        second = normalize_pick(64, 2)
        third = normalize_pick(48, 3)
        self.assertGreater(first, second)
        self.assertGreater(second, third)
        self.assertTrue(all(0 <= item <= 1000 for item in (first, second, third)))

    def test_unknown_provider_is_uncalibrated_not_raw_passthrough(self) -> None:
        result = normalize_value("Unknown", 9000)
        self.assertEqual(result.normalized_value, 0)
        self.assertEqual(result.confidence_score, 0)


class ConsensusTests(unittest.TestCase):
    def test_consensus_uses_normalized_values_and_records_weights(self) -> None:
        values = (normalize_value("FantasyCalc", 9000), normalize_value("DynastyProcess", 7500))
        result = build_canonical_consensus(values)
        self.assertLessEqual(result.market_consensus, 1000)
        self.assertEqual(len(result.providers_used), 2)
        self.assertAlmostEqual(sum(item.weight for item in result.providers_used), 1.0, places=3)

    def test_missing_provider_is_safe_and_partial(self) -> None:
        result = build_canonical_consensus((normalize_value("FantasyCalc", 8000),))
        self.assertEqual(result.calibration_status, CalibrationStatus.PARTIALLY_CALIBRATED)
        self.assertIsNotNone(result.warning)

    def test_stale_data_lowers_confidence_and_status(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        fresh = build_canonical_consensus((normalize_value("FantasyCalc", 8000, updated_at=now), normalize_value("DynastyProcess", 7000, updated_at=now)))
        stale = build_canonical_consensus((normalize_value("FantasyCalc", 8000, updated_at=old), normalize_value("DynastyProcess", 7000, updated_at=old)))
        self.assertLess(stale.confidence_score, fresh.confidence_score)
        self.assertEqual(stale.calibration_status, CalibrationStatus.STALE)

    def test_provider_disagreement_reduces_confidence(self) -> None:
        close = build_canonical_consensus((normalize_value("FantasyCalc", 8000), normalize_value("DynastyProcess", 6800)))
        wide = build_canonical_consensus((normalize_value("FantasyCalc", 11_000), normalize_value("DynastyProcess", 1000)))
        self.assertLess(wide.confidence_score, close.confidence_score)

    def test_legacy_quote_contract_never_compares_thousands_to_internal_scores(self) -> None:
        quote = ProviderQuote("FantasyCalc", "p1", 7500, 90, None, "test", True, "raw", normalized_value=625, raw_scale=(0, 12000), normalization_version=NORMALIZATION_VERSION, normalization_method="provider_range_linear")
        result = build_consensus("p1", (quote,), ("FantasyCalc",))
        self.assertEqual(result.value, 625)


class TradeSafetyTests(unittest.TestCase):
    def test_packages_use_canonical_trade_values(self) -> None:
        package = adjusted_package_value((asset("a", 500), asset("b", 300)))
        self.assertEqual(package.raw_total, 800)
        self.assertLess(package.adjusted_value, package.raw_total)

    def test_multi_asset_consolidation_penalty_and_low_value_discount(self) -> None:
        two = adjusted_package_value((asset("a", 250), asset("b", 250)))
        four = adjusted_package_value(tuple(asset(str(index), 125) for index in range(4)))
        self.assertLess(four.adjusted_value, two.adjusted_value)
        self.assertTrue(four.reasons)

    def test_two_thirds_cannot_purchase_jj_mccarthy(self) -> None:
        thirds = (asset("2027-third", 180, kind="pick", position=None), asset("2028-third", 160, kind="pick", position=None))
        result = evaluate_trade_guardrails(thirds, (asset("jj-mccarthy", 820, position="QB"),), superflex=True)
        self.assertEqual(result.recommendation_status, "rejected")
        self.assertEqual(result.reason_code, "SUPERFLEX_QB_SCARCITY")

    def test_superflex_qb_premium_raises_market_floor(self) -> None:
        offered = (asset("offer", 610),)
        requested = (asset("qb", 800, position="QB"),)
        normal = evaluate_trade_guardrails(offered, requested, superflex=False)
        superflex = evaluate_trade_guardrails(offered, requested, superflex=True)
        self.assertEqual(normal.recommendation_status, "accepted")
        self.assertEqual(superflex.recommendation_status, "rejected")

    def test_market_floor_rejects_severe_imbalance(self) -> None:
        result = evaluate_trade_guardrails((asset("offer", 400),), (asset("request", 650),))
        self.assertEqual(result.reason_code, "BELOW_MARKET_FLOOR")

    def test_uncalibrated_and_low_confidence_packages_are_suppressed(self) -> None:
        uncalibrated = evaluate_trade_guardrails((asset("a", 600),), (asset("b", 600),), calibration_status=CalibrationStatus.UNCALIBRATED)
        low = evaluate_trade_guardrails((asset("a", 600),), (asset("b", 600),), confidence=40)
        self.assertEqual(uncalibrated.reason_code, "UNCALIBRATED_VALUES")
        self.assertEqual(low.reason_code, "LOW_CONFIDENCE")

    def test_explicit_supporting_values_can_justify_pick_package(self) -> None:
        offered = (asset("first", 650, kind="pick", position=None), asset("second", 300, kind="pick", position=None))
        result = evaluate_trade_guardrails(offered, (asset("premium", 800, position="WR"),))
        self.assertEqual(result.recommendation_status, "accepted")

    def test_guardrail_result_is_machine_readable_and_explainable(self) -> None:
        result = evaluate_trade_guardrails((asset("offer", 300),), (asset("request", 800),))
        self.assertTrue(result.reason_code)
        self.assertTrue(result.message)
        self.assertGreater(result.requested_value, result.offered_value)


class ConfigurationTests(unittest.TestCase):
    def test_normalization_version_is_explicit_for_cache_namespacing(self) -> None:
        value = normalize_value("FantasyCalc", 5000)
        self.assertEqual(value.normalization_version, NORMALIZATION_VERSION)

    def test_raw_quotes_remain_available_for_transparency(self) -> None:
        value = normalize_value("FantasyCalc", 7421)
        changed = replace(value, normalized_value=742)
        self.assertEqual(changed.raw_value, 7421)
        self.assertEqual(changed.raw_max, 12_000)


if __name__ == "__main__":
    unittest.main()
