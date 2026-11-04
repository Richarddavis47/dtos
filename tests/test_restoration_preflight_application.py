"""Serving-application provider wiring remains read-only and reports unknowns."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core.league_runtime import RuntimeState


class PreflightApplicationProviderTests(unittest.TestCase):
    def test_absent_runtime_is_observed_without_creation(self):
        import dtos_app
        with patch.object(dtos_app.league_runtime_manager, 'resident', return_value=None) as resident, patch.object(dtos_app.league_runtime_manager, 'get', side_effect=AssertionError('No hydration')):
            result = dtos_app._restoration_runtime_metadata('1314695233040052224')
        resident.assert_called_once_with('1314695233040052224')
        self.assertEqual(result, {'resident': False, 'status': 'cold',
                                 'cooldown_remaining_seconds': 0.0, 'cooldown_valid': True})

    def test_unavailable_or_unrepresentable_cooldown_is_unknown(self):
        import dtos_app
        for value in (None, True, 'not-a-clock', -1, float('inf'), float('nan'), 10**1000):
            with self.subTest(kind=type(value).__name__):
                runtime = SimpleNamespace(status=RuntimeState.DEFERRED,
                    lifecycle={'hydration_retry_after': value})
                with patch.object(dtos_app.league_runtime_manager, 'resident', return_value=runtime):
                    result = dtos_app._restoration_runtime_metadata('1314695233040052224')
                self.assertFalse(result['cooldown_valid'])
                self.assertIsNone(result['cooldown_remaining_seconds'])
                self.assertIs(runtime.lifecycle['hydration_retry_after'], value)

    def test_valid_cooldown_is_computed_without_touching_runtime(self):
        import dtos_app
        runtime = SimpleNamespace(status=RuntimeState.DEFERRED,
            lifecycle={'hydration_retry_after': 112.5})
        with patch.object(dtos_app.league_runtime_manager, 'resident', return_value=runtime), patch.object(dtos_app, 'monotonic', return_value=100.0):
            result = dtos_app._restoration_runtime_metadata('1314695233040052224')
        self.assertTrue(result['cooldown_valid'])
        self.assertEqual(result['cooldown_remaining_seconds'], 12.5)
        self.assertEqual(runtime.lifecycle, {'hydration_retry_after': 112.5})
