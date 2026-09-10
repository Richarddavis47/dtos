from dataclasses import replace
import unittest

from src.core.intelligence.roster_grading import (
    PlayerGradingEvidence, grade_roster_evidence, rank_roster_dimension,
)


def roster(roster_id, price, points, depth, longevity=50):
    return grade_roster_evidence(league_id='league', roster_id=roster_id, generation='g1',
        players=(PlayerGradingEvidence('p', price, 80, points, longevity, 70),),
        actual_starter_ids=('p',), optimal_starter_ids=('p',) if points is not None else (),
        actual_points=points, optimal_points=points, legal_backup_points=depth)


class RosterGradingDimensionsTests(unittest.TestCase):
    def test_strong_assets_do_not_imply_strong_lineup(self):
        rich, ready = roster(1, 900, 10, 0), roster(2, 400, 25, 0)
        self.assertEqual(rank_roster_dimension((rich, ready), 'Market asset strength'), {1: 1, 2: 2})
        self.assertEqual(rank_roster_dimension((rich, ready), 'Optimal projected lineup'), {1: 2, 2: 1})

    def test_current_lineup_and_longevity_can_disagree(self):
        veteran, young = roster(1, 400, 25, 0, 20), roster(2, 800, 12, 0, 80)
        self.assertEqual(rank_roster_dimension((veteran, young), 'Optimal projected lineup')[1], 1)
        self.assertEqual(rank_roster_dimension((veteran, young), 'Longevity context')[1], 2)
        self.assertIsNone(veteran.intrinsic_dynasty_value)

    def test_depth_cannot_overwrite_starter_strength(self):
        starters, deep = roster(1, 700, 30, 2), roster(2, 700, 18, 16)
        self.assertEqual(rank_roster_dimension((starters, deep), 'Useful projected depth')[2], 1)
        self.assertEqual(rank_roster_dimension((starters, deep), 'Optimal projected lineup')[2], 2)

    def test_missing_projection_is_unranked_not_zero_or_rebuilding(self):
        missing, zero = roster(1, 900, None, None), roster(2, 200, 0, 0)
        self.assertEqual(rank_roster_dimension((missing, zero), 'Optimal projected lineup'), {1: None, 2: 1})
        self.assertEqual(missing.competitive_window, 'Unavailable')
        self.assertIsNone(missing.overall_grade)

    def test_partial_evidence_does_not_turn_known_subtotal_into_full_strength(self):
        row = grade_roster_evidence(league_id='league', roster_id=1, generation='g1',
            players=(PlayerGradingEvidence('p', 900, 80, 20, 70, 90),
                     PlayerGradingEvidence('q', None, None, None, None, 0)),
            actual_starter_ids=('p',), optimal_starter_ids=(), actual_points=20,
            optimal_points=None, legal_backup_points=None)
        self.assertIsNone(row.dimensions['Market asset strength'].value)
        self.assertEqual(row.dimensions['Market asset strength'].covered, 1)
        self.assertEqual(row.dimensions['Market asset strength'].expected, 2)

    def test_one_generation_cannot_publish_conflicting_generic_grades(self):
        row = roster(1, 999, 40, 20)
        self.assertIsNone(row.overall_grade)
        self.assertEqual(row.competitive_window, 'Unavailable')
        # Strong dimensional evidence is not permission to invent an overall A
        # or an Elite Contender classification from a Market-price total.
        self.assertEqual(row.dimensions['Market asset strength'].value, 999)

    def test_cross_league_and_generation_ranks_rejected(self):
        first, second = roster(1, 100, 10, 0), roster(2, 200, 20, 0)
        for changed in (replace(second, league_id='other'), replace(second, generation='g2')):
            with self.assertRaises(ValueError):
                rank_roster_dimension((first, changed), 'Market asset strength')
