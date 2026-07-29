"""Permanent relationship-based calibration benchmark for DTOS assets."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.core.asset_intelligence.picks.pick_value import dynasty_pick_value
from src.core.competitive_window import build_competitive_window
from src.core.valuation import CalibrationStatus, calibrate_asset_value, contextualize_valuation_tier


FIXTURE = Path(__file__).parent / "fixtures" / "golden_valuation_v159.json"


class GoldenValuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_set_is_representative_and_permanent(self) -> None:
        total = sum(
            len(self.benchmark[key])
            for key in ("players", "picks", "archetypes", "team_scenarios", "trade_packages")
        )
        self.assertGreaterEqual(total, 50)
        self.assertLessEqual(total, 100)
        tiers = {row["tier"] for row in self.benchmark["players"]}
        self.assertEqual(
            tiers,
            {
                "Elite Franchise Player", "Cornerstone", "Core Starter",
                "Quality Starter", "Flex Asset", "Depth", "Developmental",
            },
        )
        self.assertEqual(
            {row["position"] for row in self.benchmark["archetypes"]},
            {"QB", "RB", "WR", "TE"},
        )

    def test_player_calibration_matches_golden_tiers(self) -> None:
        values = []
        for row in self.benchmark["players"]:
            calibration = calibrate_asset_value(
                row["intrinsic"], row["market"], row["confidence"],
                status=CalibrationStatus.CALIBRATED,
            )
            self.assertEqual(calibration.tier, row["tier"], row["name"])
            values.append(calibration.calibrated_value)
            self.assertEqual(
                calibration,
                calibrate_asset_value(
                    row["intrinsic"], row["market"], row["confidence"],
                    status=CalibrationStatus.CALIBRATED,
                ),
            )
        tier_floor = {
            "Elite Franchise Player": 790, "Cornerstone": 675,
            "Core Starter": 550, "Quality Starter": 425,
            "Flex Asset": 300, "Depth": 200, "Developmental": 100,
        }
        for row, value in zip(self.benchmark["players"], values):
            self.assertGreaterEqual(value, tier_floor[row["tier"]], row["name"])

    def test_missing_market_evidence_cannot_create_elite_asset(self) -> None:
        calibration = calibrate_asset_value(
            1000, None, 0, status=CalibrationStatus.INSUFFICIENT_DATA,
        )
        self.assertNotIn(calibration.tier, {"Elite Franchise Player", "Cornerstone"})
        self.assertEqual(calibration.market_weight, 0)

    def test_older_low_value_players_are_not_called_developmental(self) -> None:
        self.assertEqual(
            contextualize_valuation_tier("Developmental", 31),
            "Veteran Depth",
        )
        self.assertEqual(
            contextualize_valuation_tier("Replacement Level", 29),
            "Veteran Replacement",
        )
        self.assertEqual(
            contextualize_valuation_tier("Developmental", 22),
            "Developmental",
        )

    def test_pick_curve_preserves_round_and_slot_relationships(self) -> None:
        current_year = datetime.now(timezone.utc).year
        values = {}
        for row in self.benchmark["picks"]:
            values[row["label"]] = dynasty_pick_value({
                "round": row["round"],
                "season": current_year + row["years_away"],
                "projected_slot": row["slot"],
            }).score
        self.assertGreater(values["Next early first"], values["Next middle first"])
        self.assertGreater(values["Next middle first"], values["Next late first"])
        self.assertGreater(values["Next early second"], values["Next early third"])
        self.assertGreater(values["Next early third"], values["Next fourth"])
        self.assertGreater(values["Next early first"], values["Future early first"])

    def test_two_thirds_cannot_equal_an_elite_player(self) -> None:
        current_year = datetime.now(timezone.utc).year
        third = dynasty_pick_value({
            "round": 3, "season": current_year + 1, "projected_slot": "middle",
        }).score * 10
        elite = calibrate_asset_value(
            750, 877, 89, status=CalibrationStatus.CALIBRATED,
        ).calibrated_value
        self.assertLess(third * 2, elite)

    def test_competitive_window_scenarios_are_stable(self) -> None:
        for row in self.benchmark["team_scenarios"]:
            self.assertEqual(
                build_competitive_window(
                    current_strength=row["current"],
                    overall_strength=row["overall"],
                    future_strength=row["future"],
                    depth=50,
                    youth=50,
                    draft_capital=50,
                    risk=50,
                    confidence=80,
                ).classification.value,
                row["window"],
                row["label"],
            )

    def test_trade_package_relationships_are_economically_reasonable(self) -> None:
        for row in self.benchmark["trade_packages"]:
            offered = sum(row["offered"])
            requested = sum(row["requested"])
            low_value_aggregation = (
                len(row["offered"]) >= 3
                and max(row["offered"]) < 300
                and max(row["requested"]) >= 675
            )
            economically_supported = (
                offered >= requested * 0.72 and not low_value_aggregation
            )
            self.assertEqual(economically_supported, row["accepted"], row["label"])


if __name__ == "__main__":
    unittest.main()
