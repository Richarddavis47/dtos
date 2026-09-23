"""Market comparison availability is not zero movement or an application error."""
import unittest
from routes.market import _trend_observation_summary


class MarketStatePresentationTests(unittest.TestCase):
    def test_missing_comparison_is_not_zero_or_stable_movement(self):
        for direction in ('not_comparable', 'insufficient_history'):
            html = _trend_observation_summary({'direction': direction, 'checkpoint_count': 2,
                                               'magnitude_band': 'none'})
            self.assertIn('Numerical movement unavailable', html)
            self.assertNotIn('none movement', html)
            self.assertNotIn('observed range', html)

    def test_methodology_boundary_overrides_direction(self):
        html = _trend_observation_summary({'direction': 'rising', 'checkpoint_count': 2,
                                          'comparison_reasons': ['METHODOLOGY_VERSION_CHANGED']})
        self.assertIn('comparable history is required', html)

    def test_comparable_true_zero_remains_zero(self):
        html = _trend_observation_summary({'direction': 'stable', 'checkpoint_count': 2,
                                          'magnitude_band': 'none', 'observed_low': 0, 'observed_high': 0})
        self.assertIn('observed range 0–0', html)
