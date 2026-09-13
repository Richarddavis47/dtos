import json
import unittest
from src.core.fois.assessment_export import assessment_record


class AssessmentExportTests(unittest.TestCase):
    def test_actual_conclusion_preserved_without_payload(self):
        row = {'transaction_id': 't', 'owner_id': 'o', 'process_score': 40,
               'process_evidence': {'historical_process_dimensions': [
                   {'name': 'market', 'assessment': 'unfavorable', 'evidence_available': True,
                    'payload': {'secret': 'never export'}}]}}
        record = assessment_record(row, 'trading', league_id='l', franchise_id='f')
        self.assertEqual(record['process']['quality'], 40)
        self.assertEqual(record['process']['dimensions'][0]['assessment'], 'unfavorable')
        self.assertNotIn('secret', json.dumps(record))
        self.assertIsNone(record['outcome']['quality'])
        self.assertEqual(record, assessment_record(row, 'trading', league_id='l', franchise_id='f'))

    def test_missing_quality_not_zero_and_scope_is_distinct(self):
        row = {'draft_id': 'd', 'pick_number': 3}
        first = assessment_record(row, 'drafting', league_id='l', franchise_id='f')
        self.assertIsNone(first['process']['quality'])
        self.assertIsNone(first['as_of'])
        self.assertNotEqual(first, assessment_record(row, 'drafting', league_id='other', franchise_id='f'))
