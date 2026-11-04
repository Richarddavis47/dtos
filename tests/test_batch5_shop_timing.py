import unittest

from tools.validation.batch5_shop_timing import differences, semantic


class TimingDiagnosticsTests(unittest.TestCase):
    def test_timing_only_is_not_semantic_change(self):
        a = {'historical_context_duration_ms': 1, 'timings_seconds': {'total': 2},
             'weekly': {2: {'points': 12.345}}}
        b = {**a, 'historical_context_duration_ms': 3, 'timings_seconds': {'total': 5}}
        self.assertEqual(differences(semantic(a), semantic(b)), [])

    def test_integer_week_keys_preserve_real_differences(self):
        self.assertEqual(differences({'weekly': {2: 1}}, {'weekly': {2: 2}}),
                         [{'path': '/weekly/2', 'optimized': 1, 'reference': 2}])

    def test_evidence_and_confidence_changes_are_not_filtered(self):
        self.assertTrue(differences(semantic({'confidence': 'HIGH'}), semantic({'confidence': 'LOW'})))
