import unittest

from tools.validation.audit_batch4_assessment_quality import summarize


def decision(identity, classification='defensible_optional', quality=65, dimensions=()):
    return dict(league_id='league', franchise_id='1', owner_id='gm', season=2025,
                category='trading', decision_id=identity, selection=None,
                process=dict(classification=classification, quality=quality,
                             confidence='medium', dimensions=list(dimensions), limitations=[]),
                outcome=dict(classification=None, quality=None, confidence='unavailable',
                             dimensions=[], limitations=['NO_OUTCOME_EVIDENCE']))


class QualityPanelTests(unittest.TestCase):
    def test_missing_and_partial_do_not_become_quality(self):
        rows = [decision(str(i)) for i in range(3)]
        rows += [decision('missing', 'insufficient_evidence', None,
                          [{'name': 'future_capital_liquidity', 'assessment': 'improved'}])]
        result = summarize(rows, 'process')
        self.assertEqual(result['central_supported_process_conclusion'], ['defensible_optional'])
        self.assertEqual(result['supported_process_conclusions'], 3)
        self.assertIsNone(result['grade'])

    def test_volume_does_not_improve_quality_and_outlier_does_not_dominate(self):
        rows = [decision(str(i)) for i in range(3)]
        self.assertEqual(summarize(rows, 'process')['central_supported_process_conclusion'],
                         summarize(rows + [decision('outlier', 'strong_process', 90)], 'process')['central_supported_process_conclusion'])
        self.assertEqual(summarize([decision(str(i)) for i in range(60)], 'process')['central_supported_process_conclusion'], ['defensible_optional'])

    def test_small_sample_not_promoted_to_category(self):
        result = summarize([decision('1'), decision('2')], 'process')
        self.assertIsNone(result['central_supported_process_conclusion'])
        self.assertEqual(result['process_conclusion_distribution'], {'defensible_optional': 2})

    def test_outcome_cannot_rewrite_process_or_pool_horizons(self):
        rows = [decision(str(i)) for i in range(3)]
        before = summarize(rows, 'process')
        rows[0]['outcome']['dimensions'] = [dict(dimension='later_observed_market_change', change=-2000, horizon_days=700)]
        self.assertEqual(summarize(rows, 'process'), before)
        outcome = summarize(rows, 'outcome')
        self.assertEqual(outcome['outcome_horizon_days'], {'minimum': 700, 'maximum': 700})
        self.assertIsNone(outcome['grade'])

    def test_duplicate_decision_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize([decision('same'), decision('same')], 'process')

    def test_unavailable_dimension_not_counted(self):
        row = decision('1', dimensions=[dict(name='value_fairness', assessment='poor', evidence_available=False)])
        self.assertEqual(summarize([row], 'process')['dimension_distributions'], {})
