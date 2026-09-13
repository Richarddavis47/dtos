import unittest
from src.core.fois.coverage import decision_coverage, decision_evaluability


class DecisionCoverageTests(unittest.TestCase):
    def test_scoped_assessment_does_not_require_legacy_score(self):
        row = {'owner_id': 'gm', 'season': 2024, 'decision_evaluation': {
            'process': {'evaluability': 'partially_evaluable', 'confidence': 'limited_scope',
                        'reasons': ['NO_SUPPORTED_ROSTER_FIT_CONCLUSION']},
            'outcome': {'evaluability': 'insufficient', 'confidence': 'unavailable',
                        'reasons': ['NO_OUTCOME_EVIDENCE']}}}
        report = decision_coverage({'drafts': [row]})['drafting']
        self.assertEqual(report['availability'], 'partial')
        group = report['by_manager_season'][0]
        self.assertEqual(group['missing_process_requirements'],
                         {'NO_SUPPORTED_ROSTER_FIT_CONCLUSION': 1})
        self.assertEqual(group['missing_outcome_requirements'], {'NO_OUTCOME_EVIDENCE': 1})
        self.assertEqual(group['process_confidence'], {'limited_scope': 1})

    def test_process_and_outcome_are_independent(self):
        row = {'owner_id': 'gm', 'occurred_at': '2024-01-01T00:00:00+00:00',
               'incoming_asset_ids': ['p'], 'market_coverage_ratio': 1,
               'process_evidence': {'historical_process_dimensions': [{'evidence_available': True}]},
               'process_score': 0}
        self.assertEqual(decision_evaluability(row, 'trading')['process'], 'evaluable')
        self.assertEqual(decision_evaluability(row, 'trading')['outcome'], 'insufficient')
        row.update(process_score=None, outcome_score=0, outcome_maturity='mature')
        self.assertEqual(decision_evaluability(row, 'trading')['process'], 'insufficient')
        self.assertEqual(decision_evaluability(row, 'trading')['outcome'], 'evaluable')

    def test_partial_market_and_missing_boundary_are_not_full_evaluation(self):
        row = {'process_score': 85, 'market_coverage_ratio': .5, 'owner_id': 'gm'}
        self.assertEqual(decision_evaluability(row, 'trading')['process'], 'partially_evaluable')

    def test_seasons_do_not_borrow_coverage(self):
        report = decision_coverage({'trades': [
            {'owner_id': 'gm', 'season': 2021},
            {'owner_id': 'gm', 'season': 2025, 'outcome_score': 70, 'outcome_maturity': 'mature'}]})
        old, recent = report['trading']['by_manager_season']
        self.assertEqual(old['outcome_states'], {'insufficient': 1})
        self.assertEqual(recent['outcome_states'], {'evaluable': 1})

    def test_coverage_is_not_quality_and_zero_is_evidence(self):
        report = decision_coverage({'trades': [
            {'owner_id': 'a', 'process_score': 0, 'outcome_score': None, 'market_coverage_ratio': 0},
            {'owner_id': 'a', 'process_score': None, 'outcome_score': 80, 'market_coverage_ratio': 1},
            {'owner_id': None, 'process_score': 90}]})['trading']
        self.assertEqual(report['discovered'], 3)
        self.assertEqual(report['attributed'], 2)
        self.assertEqual(report['process_evaluable'], 0)
        self.assertEqual(report['outcome_evaluable'], 0)
        self.assertEqual(report['process_partially_evaluable'], 1)
        self.assertEqual(report['outcome_partially_evaluable'], 1)
        self.assertEqual(report['market_coverage_measured'], 2)
        self.assertEqual(report['market_coverage_complete'], 1)
        self.assertIsNone(report['decision_time_player_coverage'])

    def test_draft_activity_is_not_process_evidence(self):
        report = decision_coverage({'drafts': [{'owner_id': 'a', 'pick_number': 1}]})['drafting']
        self.assertEqual(report['availability'], 'insufficient')
        self.assertEqual(report['process_insufficient'], 1)

    def test_league_inputs_do_not_accumulate_or_mutate(self):
        data = {'waivers': [{'owner_id': 'a'}]}
        first = decision_coverage(data)
        self.assertEqual(decision_coverage({})['waivers']['discovered'], 0)
        self.assertEqual(first, decision_coverage(data))
        self.assertEqual(data, {'waivers': [{'owner_id': 'a'}]})
