"""A pre-reserve-contract prepared profile cannot bypass current admission.

The disposable legacy DTO uses the v1.21.70 published shape; no Git checkout,
network access, historical reconstruction or source mutation is required.
"""
from copy import deepcopy
from unittest.mock import patch
import unittest

from src.core.intelligence.team_strength import compatible_profile, prepare_for_data
from tests import test_reserve_quality as reserve


class ReserveQualityAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = reserve.ReserveQualityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def legacy_profile(self, *, missing=False):
        if missing:
            self.fixture.fixture.points.pop('b')
            self.fixture.fixture.publish()
        legacy = deepcopy(self.fixture.data['team_strength'])
        legacy['methodology_version'] = 'weekly-optimal-horizons-v2'
        # These are the only reserve fields published before v1.21.71.
        for team in legacy['teams'].values():
            for row in team['weekly'].values():
                row['reserve_capacity'] = {key: row['reserve_capacity'][key]
                    for key in ('supported_slots', 'unsupported_slots', 'known_subtotal', 'meaning')}
        self.fixture.data['team_strength'] = legacy
        return legacy

    def prepare(self):
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            return prepare_for_data(self.fixture.fixture.reader, self.fixture.data)

    def test_old_prepared_profile_is_not_current_compatible_evidence(self):
        self.legacy_profile()
        self.assertIsNone(compatible_profile(self.fixture.data, self.fixture.fixture.reader.snapshot()))

    def test_background_preparation_rebuilds_legacy_profile_without_source_refresh(self):
        legacy = self.legacy_profile()
        snapshot = deepcopy(self.fixture.fixture.reader.snapshot())
        with patch.object(self.fixture.fixture.reader, 'publish_horizon',
                          side_effect=AssertionError('Rebuilding derived evidence republished source facts')):
            prepared = self.prepare()
        self.assertIsNot(prepared, legacy)
        self.assertNotEqual(prepared['methodology_version'], 'weekly-optimal-horizons-v2')
        for row in prepared['teams']['1']['weekly'].values():
            self.assertIn('qualification', row['reserve_capacity'])
            self.assertEqual(row['reserve_capacity']['known_subtotal'], 40)
        self.assertEqual(self.fixture.fixture.reader.snapshot(), snapshot)

    def test_legacy_missing_outgoing_reserve_does_not_become_zero_strength(self):
        legacy = self.legacy_profile(missing=True)
        self.assertEqual(legacy['teams']['1']['weekly'][2]['reserve_capacity']['known_subtotal'], 0)
        prepared = self.prepare()
        self.assertIsNot(prepared, legacy)
        e = self.fixture.evaluate()
        quality = e['dimensions']['package_quality']['active']['reserve_quality']
        self.assertIsNone(quality['mean_weekly_delta'])
        self.assertFalse(quality['complete'])
        self.assertFalse(quality['material_gain'])
        self.assertIsNone(e['recommendation'])
        self.assertNotIn('No material downside identified', e['major_drawback'])
        for row in e['dimensions']['package_quality']['active']['reserve_quality_by_week'].values():
            self.assertIsNone(row['pre_points'])
            self.assertIsNone(row['delta'])

    def test_current_warm_preparation_reuses_exact_derived_profile_without_solving(self):
        before = self.fixture.data['team_strength']
        snapshot = deepcopy(self.fixture.fixture.reader.snapshot())
        with patch('src.core.intelligence.team_strength.optimal_legal_lineup',
                   side_effect=AssertionError('Unchanged warm profile solved another lineup')):
            for _ in range(3):
                self.assertIs(self.prepare(), before)
        self.assertEqual(self.fixture.fixture.reader.snapshot(), snapshot)


if __name__ == '__main__':
    unittest.main()
