from dataclasses import replace
import unittest

from src.core.valuation.intrinsic_profile import build_intrinsic_profile
from src.core.valuation.player_methodology import ReferenceSeason, assess_intrinsic
from tests import test_forward_evidence as forward_fixture


class IntrinsicProfileTests(unittest.TestCase):
    def profile(self, samples=(), games=7):
        setup = forward_fixture.ForwardEvidenceTests()
        setup.setUp()
        quality = assess_intrinsic(position='RB', age=24, current_season=2026,
            seasons=tuple(ReferenceSeason(2025, games, value, 12) for value in samples))
        return build_intrinsic_profile(quality, setup.evidence, player_id='1', season=2026,
            week=1, as_of='2026-09-09T12:00:00Z')

    def test_rookie_forward_evidence_without_negative_history(self):
        row = self.profile()
        self.assertIsNone(row['demonstrated_quality']['score'])
        self.assertEqual(row['near_term_expectation']['points'], 20)
        self.assertIsNone(row['intrinsic_value'])

    def test_sample_depth_only_changes_historical_support(self):
        short, full = self.profile((25,), 7), self.profile((25,), 17)
        self.assertEqual(short['demonstrated_quality']['score'], full['demonstrated_quality']['score'])
        self.assertLess(short['demonstrated_quality']['sample_confidence'], full['demonstrated_quality']['sample_confidence'])
        self.assertEqual(short['near_term_expectation'], full['near_term_expectation'])

    def test_age_does_not_rewrite_demonstrated_production(self):
        setup = forward_fixture.ForwardEvidenceTests()
        setup.setUp()
        rows = []
        for age in (24, 34):
            quality = assess_intrinsic(position='RB', age=age, current_season=2026,
                seasons=(ReferenceSeason(2025, 17, 20, 12),))
            rows.append(build_intrinsic_profile(quality, replace(setup.evidence, projected_points=10),
                player_id='1', season=2026, week=1, as_of='2026-09-09T12:00:00Z'))
        self.assertEqual(rows[0]['demonstrated_quality'], rows[1]['demonstrated_quality'])
        self.assertGreater(rows[0]['longevity_context']['score'], rows[1]['longevity_context']['score'])
