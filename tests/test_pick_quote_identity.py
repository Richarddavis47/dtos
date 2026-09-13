import unittest

from src.core.data_platform.pick_quotes import pick_concept


class PickQuoteIdentityTests(unittest.TestCase):
    def test_fc_round_offsets_are_checked(self):
        self.assertEqual(pick_concept('FantasyCalc', '2027 1st (Early)', 'FP_2027_early_0')['round'], 1)
        self.assertIsNone(pick_concept('FantasyCalc', '2027 1st (Early)', 'FP_2027_early_1'))
        self.assertEqual(pick_concept('FantasyCalc', '2027 1st', 'FP_2027_1')['pick_type'], 'generic_round')

    def test_concepts_are_not_interchangeable(self):
        concepts = [pick_concept('DynastyProcess', label) for label in
                    ('2027 1st', '2027 Early 1st', '2027 Mid 1st', '2027 Late 1st', '2027 Pick 1.03')]
        self.assertEqual(len({str(value) for value in concepts}), 5)
        self.assertTrue(all(value['exact_slot'] is None for value in concepts[:4]))
        self.assertIsNone(concepts[-1]['range'])

    def test_future_years_are_not_hardcoded_and_unknown_labels_fail_closed(self):
        self.assertEqual(pick_concept('FantasyCalc', '2040 3rd', 'FP_2040_3')['year'], 2040)
        for label in ('1.03', '2027 First', '2027 Pick 1.00', '2027 UNKNOWN 1st'):
            self.assertIsNone(pick_concept('DynastyProcess', label))
