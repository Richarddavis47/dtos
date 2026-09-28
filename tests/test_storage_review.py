import unittest
from dataclasses import replace
from src.platform.storage_review import MIB, StorageSample, review


class StorageReviewTests(unittest.TestCase):
    def test_unchanged_and_expected_growth(self):
        old = StorageSample(1, 100, 10, 10, 10, 10)
        new = replace(old, measured_at_seconds=2)
        self.assertEqual(review(new, previous=old)['reasons'], [])
        new = replace(new, rows=11, file_bytes=200)
        self.assertEqual(review(new, previous=old, expected_row_growth=1,
                                expected_byte_growth=100)['reasons'], [])

    def test_alert_is_not_authorization_to_delete_canonical_history(self):
        old = StorageSample(1, 100, 10, 10, 10, 10)
        new = StorageSample(2, 200, 20, 51 * MIB, 65 * MIB, 51 * MIB, 1, 1)
        report = review(new, previous=old, annual_start=old)
        self.assertEqual(len(report['reasons']), 7)
        self.assertFalse(report['canonical_deletion_authorized'])

    def test_no_false_annual_growth_from_timestamp_or_reset(self):
        old = StorageSample(1, 100, 10, 10, 10, 10)
        with self.assertRaises(ValueError):
            review(old, previous=old)
        new = replace(old, measured_at_seconds=2, canonical_history_bytes=1)
        self.assertNotIn('HISTORICAL_GROWTH_REVIEW', review(new, annual_start=old)['reasons'])
