"""Broad, name-free calibration properties; no player-specific target ranks."""
from dataclasses import asdict
import json
import subprocess
import sys
import unittest

from src.core.valuation.player_methodology import CURVES, ReferenceSeason, assess_intrinsic


class PlayerMethodologyTests(unittest.TestCase):
    def assess(self, position="WR", age=25, ppg=15, usage=8, games=17):
        return assess_intrinsic(position=position, age=age, current_season=2026,
            seasons=(ReferenceSeason(2025, games, ppg, usage),))

    def test_broad_position_age_production_panel_is_monotonic_and_bounded(self):
        for position in CURVES:
            for age in (21, 24, 27, 30, 34, 38):
                values = [self.assess(position, age, points).value for points in (0, 5, 10, 15, 20, 25, 35)]
                self.assertEqual(values, sorted(values), (position, age, values))
                self.assertTrue(all(0 <= value <= 1000 for value in values))

    def test_rookie_or_veteran_without_performance_has_no_fabricated_intrinsic(self):
        for position in CURVES:
            for age in (21, 30):
                self.assertIsNone(self.assess(position, age, None, None, 0).value)
                self.assertEqual(self.assess(position, age, None, None, 0).confidence, 0)

    def test_real_zero_remains_evidence_not_missing(self):
        result = self.assess(ppg=0, usage=0)
        self.assertIsNotNone(result.value)
        self.assertGreater(result.confidence, 0)

    def test_age_alone_cannot_promote_young_player_over_productive_veteran(self):
        for position in CURVES:
            self.assertGreater(self.assess(position, 30, 25).value, self.assess(position, 21, 5).value)

    def test_position_specific_lifecycle_does_not_use_uniform_age_penalty(self):
        penalties = {position: self.assess(position, 27).value - self.assess(position, 32).value for position in CURVES}
        self.assertGreater(penalties["RB"], penalties["QB"])
        self.assertGreater(penalties["WR"], penalties["TE"])

    def test_no_large_cliff_at_birthday(self):
        for position in CURVES:
            for age in range(21, 39):
                self.assertLessEqual(abs(self.assess(position, age+.01).value - self.assess(position, age-.01).value), 2)

    def test_same_quality_short_sample_is_less_confident_not_less_productive(self):
        short, established = self.assess(ppg=35, games=1), self.assess(ppg=35, games=17)
        self.assertEqual(short.value, established.value)
        self.assertLess(short.confidence, established.confidence)

    def test_usage_support_is_bounded_and_cannot_dominate_production(self):
        base = self.assess(ppg=10, usage=1)
        production_change = self.assess(ppg=25, usage=1).value - base.value
        usage_change = self.assess(ppg=10, usage=20).value - base.value
        self.assertGreater(production_change, usage_change)
        self.assertLess(usage_change, 100)

    def test_market_projection_owner_and_league_are_not_intrinsic_inputs(self):
        import inspect
        parameters = inspect.signature(assess_intrinsic).parameters
        self.assertEqual(set(parameters), {"position", "age", "current_season", "seasons"})

    def test_incompatible_future_old_or_league_scoring_evidence_rejected(self):
        for row in (ReferenceSeason(2027, 1, 20), ReferenceSeason(2018, 17, 20),
                    ReferenceSeason(2025, 17, 20, scoring="league-PPR2")):
            with self.assertRaises(ValueError):
                assess_intrinsic(position="QB", age=25, current_season=2026, seasons=(row,))

    def test_prior_season_is_explicit_and_components_reconcile(self):
        result = self.assess()
        self.assertEqual(result.seasons, (2025,))
        self.assertTrue(any("prior-season" in item for item in result.limitations))
        self.assertEqual(result.value, round(sum(item.contribution for item in result.components)))
        self.assertAlmostEqual(sum(item.weight for item in result.components), 1, places=5)

    def test_cross_process_determinism(self):
        code = "from dataclasses import asdict; import json; from src.core.valuation.player_methodology import assess_intrinsic, ReferenceSeason; print(json.dumps(asdict(assess_intrinsic(position='WR', age=25, current_season=2026, seasons=(ReferenceSeason(2025,17,15,8),))),sort_keys=True))"
        completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), json.loads(json.dumps(asdict(self.assess()))))

    def test_multi_year_quality_uses_position_specific_recency(self):
        rows = (ReferenceSeason(2024, 17, 5, 5), ReferenceSeason(2025, 17, 25, 5))
        results = {p: assess_intrinsic(position=p, age=24, current_season=2026, seasons=rows) for p in CURVES}
        self.assertGreater(dict(results['RB'].season_weights)[2025], dict(results['QB'].season_weights)[2025])

    def test_missing_season_changes_confidence_not_observed_quality(self):
        recent = assess_intrinsic(position='QB', age=25, current_season=2026, seasons=(ReferenceSeason(2025,17,20),))
        missed = assess_intrinsic(position='QB', age=25, current_season=2026, seasons=(ReferenceSeason(2024,17,20),))
        self.assertEqual(recent.value, missed.value)
        self.assertGreater(recent.confidence, missed.confidence)

    def test_seven_years_are_not_seven_games(self):
        short = self.assess('QB', 29, 20, None, 7)
        long = assess_intrinsic(position='QB', age=29, current_season=2026,
            seasons=tuple(ReferenceSeason(year,17,20) for year in range(2019,2026)))
        self.assertEqual(short.value, long.value)
        self.assertGreater(long.confidence, short.confidence)

    def test_latest_usage_role_is_not_diluted_by_former_role(self):
        for position in ('RB', 'WR', 'TE'):
            def assess(old):
                return assess_intrinsic(position=position, age=25, current_season=2026,
                    seasons=(ReferenceSeason(2024, 17, 15, old), ReferenceSeason(2025, 17, 15, 12)))
            self.assertEqual(assess(1).value, assess(20).value)
            self.assertEqual(assess(1).usage_season, 2025)

    def test_missing_latest_role_cannot_be_filled_from_old_role(self):
        result = assess_intrinsic(position='WR', age=25, current_season=2026,
            seasons=(ReferenceSeason(2024, 17, 15, 12), ReferenceSeason(2025, 17, 15, None)))
        self.assertIsNone(result.usage_season)
        self.assertNotIn('supporting_usage', [item.name for item in result.components])
