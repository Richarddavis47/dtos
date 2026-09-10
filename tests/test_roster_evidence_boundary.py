from copy import deepcopy
from types import SimpleNamespace
import unittest

from src.core.intelligence.roster_evidence import build_roster_evidence


def context():
    return SimpleNamespace(league_id='a', active_roster_id=1, evidence_generation='g1',
        settings={'roster_positions': ['QB', 'SUPER_FLEX', 'BN']},
        roster={'roster_id': 1, 'players': [
            {'id': 'q1', 'position': 'QB', 'roster_slot': 'Starter'},
            {'id': 'w1', 'position': 'WR', 'roster_slot': 'Starter'},
            {'id': 'q2', 'position': 'QB', 'roster_slot': 'Bench'},
        ]}, projection_snapshot={'league_id': 'a', 'week': 1, 'generation': 'p1',
            'players': {key: {'week': 1, 'weekly_projected_points': value}
                        for key, value in [('q1', 15), ('w1', 10), ('q2', 20)]}})


class RosterEvidenceBoundaryTests(unittest.TestCase):
    def test_actual_and_optimal_are_distinct_and_roster_unchanged(self):
        ctx = context()
        before = deepcopy(ctx.roster)
        row = build_roster_evidence(ctx)
        self.assertEqual(row.actual_lineup_projection, 25)
        self.assertEqual(row.optimal_lineup_projection, 35)
        self.assertEqual(set(row.optimal_starter_ids), {'q1', 'q2'})
        self.assertEqual(ctx.roster, before)

    def test_missing_not_filled_by_other_scalar(self):
        ctx = context()
        del ctx.projection_snapshot['players']['q2']
        ctx.roster['players'][2].update(dtos_value=999, projected_points=99, fantasy_points=100)
        row = build_roster_evidence(ctx)
        self.assertEqual(row.actual_lineup_projection, 25)
        self.assertIsNone(row.optimal_lineup_projection)
        self.assertEqual(row.optimal_starter_ids, ())

    def test_real_zero_preserved(self):
        ctx = context()
        for row in ctx.projection_snapshot['players'].values():
            row['weekly_projected_points'] = 0
        result = build_roster_evidence(ctx)
        self.assertEqual(result.actual_lineup_projection, 0)
        self.assertEqual(result.optimal_lineup_projection, 0)

    def test_wrong_week_does_not_fill_missing(self):
        ctx = context()
        ctx.projection_snapshot['players']['q1']['week'] = 2
        self.assertIsNone(build_roster_evidence(ctx).actual_lineup_projection)

    def test_cross_league_or_franchise_rejected(self):
        ctx = context()
        ctx.projection_snapshot['league_id'] = 'b'
        with self.assertRaisesRegex(ValueError, 'league mismatch'):
            build_roster_evidence(ctx)
        ctx = context()
        ctx.roster['roster_id'] = 2
        with self.assertRaisesRegex(ValueError, 'franchise mismatch'):
            build_roster_evidence(ctx)

    def test_league_rules_control_optimizer(self):
        ctx = context()
        ctx.settings['roster_positions'] = ['QB', 'WR']
        self.assertEqual(build_roster_evidence(ctx).optimal_lineup_projection, 30)

    def test_switch_return_is_identical_and_generation_retained(self):
        first = build_roster_evidence(context())
        other = context()
        other.league_id = other.projection_snapshot['league_id'] = 'b'
        build_roster_evidence(other)
        self.assertEqual(first, build_roster_evidence(context()))
        changed = context()
        changed.evidence_generation = 'g2'
        self.assertNotEqual(first.generation, build_roster_evidence(changed).generation)

    def test_incomplete_legal_lineup_unavailable(self):
        ctx = context()
        ctx.settings['roster_positions'] = ['QB', 'TE']
        self.assertIsNone(build_roster_evidence(ctx).optimal_lineup_projection)

    def test_missing_window_evidence_is_neither_rebuilding_nor_zero(self):
        from src.core.competitive_window import build_competitive_window
        result = build_competitive_window(current_strength=95, overall_strength=90,
            future_strength=None, depth=80, youth=60, draft_capital=50, risk=20, confidence=90)
        self.assertEqual(result.classification.value, 'Unavailable')
        self.assertIsNone(result.rebuild_score)
        self.assertIsNone(result.championship_score)
        self.assertEqual(result.confidence, 0)
