"""Step 8 historical Trade Intelligence integration regressions."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from services.trade_intelligence import (
    build_trade_workspace, evaluate_trade_request, generate_trade_workflow,
)
from src.core.trade_intelligence.evidence_context import build_trade_evidence_context
from tests.test_trade_intelligence import fixture_data


def _dimension(key: str, tendency: str, confidence: str = "high") -> dict:
    return {
        "key": key, "tendency": tendency, "confidence": confidence,
        "sample_count": 8, "opportunity_count": 8, "coverage": 1.0,
        "supporting_counts": {tendency: 8},
        "explanation": "supported", "evidence_references": [f"event:{key}"],
    }


class TradeHistoricalUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.workspace = build_trade_workspace(self.data, 1)
        self.sent = self.workspace["pools"][1][0].asset_id
        self.received = self.workspace["pools"][2][0].asset_id
        self.payload = {
            "workflow": "create", "active_roster_id": 1,
            "partner_roster_id": 2, "assets_sent": [self.sent],
            "assets_received": [self.received],
        }
        self.data["gm_behavioral_intelligence"] = {
            "2": {
                "overall_confidence": "high", "evidence_completeness": 90,
                "dimensions": [
                    _dimension("asset_direction", "acquire_player"),
                    _dimension("positional", f"acquire_{self.workspace['pools'][1][0].position}"),
                    _dimension("package_preference", "one_for_one"),
                ],
            },
        }
        self.data["front_office_evidence"] = {
            "2": {"partner_counts": {"1": 3}, "evidence_references": ["event:bilateral"]},
        }
        self.data["market_trend_summaries"] = {
            self.received: {"direction": "rising", "confidence": "high"},
        }

    def test_supported_history_enriches_but_does_not_rewrite_value(self) -> None:
        with_history = evaluate_trade_request(self.data, self.payload)
        without = fixture_data()
        baseline = evaluate_trade_request(without, self.payload)
        history = with_history["evaluation"]["dimensions"]["historical_counterparty_evidence"]
        self.assertEqual(history["assessment"], "HIGH")
        self.assertEqual(with_history["evaluation"]["values"], baseline["evaluation"]["values"])
        self.assertEqual(
            with_history["evaluation"]["generated_trade_eligible"],
            baseline["evaluation"]["generated_trade_eligible"],
        )
        self.assertEqual(with_history["evaluation"]["provenance"]["provider_requests"], 0)
        self.assertEqual(with_history["evaluation"]["provenance"]["raw_history_scans"], 0)

    def test_missing_history_is_honest_and_does_not_lower_quality(self) -> None:
        data = fixture_data()
        result = evaluate_trade_request(data, self.payload)["evaluation"]
        history = result["dimensions"]["historical_counterparty_evidence"]
        self.assertEqual(history["assessment"], "LOW")
        self.assertEqual(history["confidence"], "LOW")
        self.assertIn("unavailable", history["reasons"][0])

    def test_behavior_is_league_and_partner_scoped(self) -> None:
        first = evaluate_trade_request(self.data, self.payload)["evaluation"]
        other = fixture_data()
        other["league"]["league_id"] = "other-league"
        other["gm_behavioral_intelligence"] = {"3": self.data["gm_behavioral_intelligence"]["2"]}
        second = evaluate_trade_request(other, self.payload)["evaluation"]
        self.assertGreater(
            first["dimensions"]["historical_counterparty_evidence"]["score"],
            second["dimensions"]["historical_counterparty_evidence"]["score"],
        )

    def test_market_trend_informs_timing_not_value(self) -> None:
        result = evaluate_trade_request(self.data, self.payload)["evaluation"]
        self.assertEqual(len(result["dimensions"]["historical_counterparty_evidence"]["trend_signals"]), 1)
        self.assertIn("does not alter canonical value", result["why_now"])

    def test_generation_reads_one_bounded_context_not_per_candidate(self) -> None:
        target = self.workspace["pools"][2][0].asset_id
        with patch(
            "services.trade_intelligence.build_trade_evidence_context",
            wraps=build_trade_evidence_context,
        ) as context:
            result = generate_trade_workflow(self.data, {
                "workflow": "trade_for", "active_roster_id": 1,
                "asset_id": target,
            })
        self.assertEqual(context.call_count, 1)
        self.assertEqual(result["provider_requests"], 0)
        self.assertEqual(result["raw_history_scans"], 0)
        self.assertEqual(result["profile_rebuilds"], 0)
        self.assertEqual(result["trend_rebuilds"], 0)

    def test_deterministic_input_order_and_no_fake_probability(self) -> None:
        first = evaluate_trade_request(self.data, self.payload)
        self.data["gm_behavioral_intelligence"]["2"]["dimensions"].reverse()
        second = evaluate_trade_request(self.data, self.payload)
        self.assertEqual(first, second)
        self.assertNotIn("acceptance_probability", first["evaluation"])


if __name__ == "__main__":
    unittest.main()
