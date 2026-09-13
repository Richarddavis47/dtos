import unittest

from src.core.fois.coverage import decision_coverage
from tools.validation.audit_fois_decision_coverage import manager_panel


class CoveragePanelTests(unittest.TestCase):
    def test_activity_faab_and_context_do_not_create_quality(self):
        history = {'waivers': [{'owner_id': 'a', 'faab_bid': None},
                               {'owner_id': 'a', 'faab_bid': 0}],
                   'owner_by_season': {'2023': 'a', '2024': 'b'},
                   'seasons': [{'season': 2023, 'championship': True}]}
        history['decision_coverage'] = decision_coverage(history)
        report = manager_panel({'1': history})['1']
        self.assertEqual(report['categories']['waivers']['faab'],
                         {'known': 1, 'explicit_zero': 1, 'unavailable': 1})
        self.assertIsNone(report['overall_quality'])
        self.assertEqual(report['owner_by_season'], history['owner_by_season'])
        self.assertEqual(report['historical_roster_context']['unique_states'], 0)

