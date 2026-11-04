from dataclasses import replace
import unittest

from src.core.valuation.forward_evidence import ForwardEvidence, assess_forward_context
from src.core.valuation.player_methodology import REFERENCE_SCORING


class ForwardEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = ForwardEvidence('1', '2026-09-09T00:00:00Z', '2026-09-10T00:00:00Z',
            'semantic-generation', team='BUF', status='Active', projection_player_id='1',
            projection_season=2026, projection_week=1, projected_points=20,
            projection_reference=REFERENCE_SCORING, projection_row_present=True,
            projection_stats_present=True, projection_applicable=True)

    def assess(self, evidence=None, as_of='2026-09-09T12:00:00Z'):
        return assess_forward_context(evidence or self.evidence, player_id='1', season=2026, week=1, as_of=as_of)

    def test_weekly_cannot_be_annualized_into_dynasty(self):
        row = self.assess()
        self.assertEqual(row['weekly_reference_projection'], 20)
        self.assertIsNone(row['forward_dynasty_utility'])

    def test_real_zero_differs_from_missing(self):
        self.assertEqual(self.assess(replace(self.evidence, projected_points=0))['weekly_reference_projection'], 0)
        self.assertIsNone(self.assess(replace(self.evidence, projected_points=None))['weekly_reference_projection'])

    def test_no_hindsight_or_stale_role(self):
        for stamp in ('2026-09-08T12:00:00Z', '2026-09-10T00:00:00Z'):
            row = self.assess(as_of=stamp)
            self.assertIsNone(row['weekly_reference_projection'])
            self.assertIsNone(row['current_team'])

    def test_player_week_and_scoring_mismatch_never_fallback(self):
        for changes in ({'projection_player_id': '2'}, {'projection_week': 2},
                        {'projection_season': 2025}, {'projection_reference': 'league-2ppr'}):
            self.assertIsNone(self.assess(replace(self.evidence, **changes))['weekly_reference_projection'])
        with self.assertRaises(ValueError):
            self.assess(replace(self.evidence, player_id='2'))

    def test_injury_and_depth_do_not_invent_multipliers_or_recovery(self):
        row = self.assess(replace(self.evidence, injury_designation='Questionable', depth_order=2))
        self.assertEqual(row['weekly_reference_projection'], 20)
        self.assertIn('INJURY_DESIGNATION_NOT_RECOVERY_FORECAST', row['reason_codes'])
        self.assertIn('DEPTH_ORDER_NOT_USAGE_SHARE', row['reason_codes'])

    def test_bad_numeric_and_temporal_evidence_rejected(self):
        for value in (True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.assess(replace(self.evidence, projected_points=value))
        with self.assertRaises(ValueError):
            self.assess(replace(self.evidence, expires_at=self.evidence.observed_at))

    def test_zero_states_are_distinct_without_inventing_status_causality(self):
        zero = replace(self.evidence, projected_points=0)
        self.assertEqual(self.assess(zero)['projection_state'], 'supported_numeric_zero')
        self.assertEqual(self.assess(replace(zero, injury_designation='Out'))['projection_state'], 'zero_with_unavailable_status')
        for changes, state in (({'projection_stats_present': False}, 'no_projection'),
                               ({'projection_row_present': False}, 'provider_missing_player'),
                               ({'projection_applicable': False}, 'not_applicable')):
            result = self.assess(replace(zero, **changes))
            self.assertEqual(result['projection_state'], state)
            self.assertIsNone(result['weekly_reference_projection'])
