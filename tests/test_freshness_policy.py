from __future__ import annotations

import unittest

from src.core.freshness import (
    FRESHNESS_POLICY_VERSION,
    assess_freshness,
    freshness_policy_manifest,
)


class FreshnessPolicyTests(unittest.TestCase):
    def test_market_age_is_semantically_stable_inside_tier(self) -> None:
        first = assess_freshness(0.0, "fantasycalc_observed_market")
        later = assess_freshness(35.999, "fantasycalc_observed_market")
        self.assertEqual((first.tier, first.semantic_weight), ("Fresh", 100))
        self.assertEqual(
            (later.tier, later.semantic_weight),
            (first.tier, first.semantic_weight),
        )
        self.assertNotEqual(first.age_hours, later.age_hours)

    def test_market_boundary_is_explicit_and_deterministic(self) -> None:
        before = assess_freshness(35.999, "fantasycalc_observed_market")
        after = assess_freshness(36.0, "fantasycalc_observed_market")
        self.assertEqual(before.tier, "Fresh")
        self.assertEqual(after.tier, "Aging")
        self.assertEqual((before.semantic_weight, after.semantic_weight), (100, 90))

    def test_projection_uses_stricter_policy_than_dynasty_market(self) -> None:
        projection = assess_freshness(2, "optional_external_projection")
        market = assess_freshness(2, "fantasycalc_observed_market")
        self.assertEqual(projection.tier, "Aging")
        self.assertEqual(market.tier, "Fresh")

    def test_historical_evidence_does_not_decay(self) -> None:
        assessment = assess_freshness(50000, "dtos_intrinsic")
        self.assertEqual(assessment.tier, "Immutable")
        self.assertEqual(assessment.semantic_weight, 100)
        self.assertIsNone(assessment.next_threshold_hours)

    def test_unavailable_evidence_is_explicit(self) -> None:
        assessment = assess_freshness(None, "fantasycalc_observed_market")
        self.assertEqual(assessment.tier, "Unavailable")
        self.assertEqual(assessment.semantic_weight, 40)

    def test_manifest_is_bounded_and_versioned(self) -> None:
        manifest = freshness_policy_manifest()
        self.assertEqual(manifest["version"], FRESHNESS_POLICY_VERSION)
        self.assertIn("fantasycalc_observed_market", manifest["families"])
        self.assertNotIn("age_hours", str(manifest))


if __name__ == "__main__":
    unittest.main()
