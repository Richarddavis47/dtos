import inspect
import unittest

from src.core.valuation.intrinsic_tiers import BANDS, intrinsic_tier
from src.core.valuation.player_methodology import ReferenceSeason, assess_intrinsic


class IntrinsicTierTests(unittest.TestCase):
    def test_no_market_confidence_or_league_dependency(self):
        self.assertEqual(set(inspect.signature(intrinsic_tier).parameters), {'value'})
        self.assertEqual(intrinsic_tier(800).number, 1)

    def test_monotonic_exact_boundaries(self):
        numbers = [intrinsic_tier(value).number for value in range(1001)]
        self.assertEqual(numbers, sorted(numbers, reverse=True))
        for number, (boundary, _) in enumerate(BANDS, 1):
            self.assertEqual(intrinsic_tier(boundary).number, number)
            if boundary:
                self.assertEqual(intrinsic_tier(boundary - .001).number, number + 1)

    def test_missing_is_not_low_quality_and_invalid_not_clamped(self):
        self.assertIsNone(intrinsic_tier(None).number)
        self.assertIsNotNone(intrinsic_tier(0).number)
        for value in (True, -1, 1001, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                intrinsic_tier(value)

    def test_excellent_seven_games_keeps_quality_and_tier_but_less_confidence(self):
        for position in ('QB', 'RB', 'WR', 'TE'):
            def assess(games):
                return assess_intrinsic(position=position, age=25, current_season=2026,
                    seasons=(ReferenceSeason(2025, games, 30, 12),))
            short, long = assess(7), assess(17)
            self.assertEqual(short.value, long.value)
            self.assertEqual(intrinsic_tier(short.value), intrinsic_tier(long.value))
            self.assertLess(short.confidence, long.confidence)
