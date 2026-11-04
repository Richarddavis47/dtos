import copy
import unittest

from src.core.operational_history import calibration_history, provider_history, TRANSITION_LIMIT


class OperationalHistoryTests(unittest.TestCase):
    def test_provider_unchanged_refresh_is_stable(self):
        original = [{'timestamp': '1', 'provider_id': 'a', 'dimensions': {'coverage': 0}}]
        result = original
        for n in range(100):
            result = provider_history(result, [{**original[0], 'timestamp': str(n)}])
        self.assertEqual(result, original)

    def test_cap_is_per_provider_and_return_to_old_state_is_a_transition(self):
        rows = [{'timestamp': f'{n:04}', 'provider_id': provider, 'dimensions': {'coverage': n % 2}}
                for n in range(200) for provider in ('a', 'b')]
        result = provider_history([], rows)
        self.assertEqual(len(result), TRANSITION_LIMIT * 2)
        self.assertEqual(provider_history(result, []), result)

    def test_calibration_ignores_observation_time_not_quality_or_methodology(self):
        row = {'timestamp': '1', 'model_version': '1', 'before_metrics': {},
               'after_metrics': {'quality': None, 'last_calibration_timestamp': '1'}}
        history = [row]
        for n in range(100):
            new = copy.deepcopy(row)
            new['timestamp'] = str(n)
            new['before_metrics'] = row['after_metrics']
            new['after_metrics']['last_calibration_timestamp'] = str(n)
            history = calibration_history(history, new)
        self.assertEqual(history, [row])
        changed = copy.deepcopy(row)
        changed['after_metrics']['quality'] = 0
        history = calibration_history(history, changed)
        self.assertEqual(len(history), 2)
        history = calibration_history(history, {**changed, 'model_version': '2'})
        self.assertEqual(len(history), 3)

    def test_calibration_cap(self):
        history = []
        for n in range(200):
            history = calibration_history(history, {'timestamp': str(n), 'confidence': n})
        self.assertEqual(len(history), TRANSITION_LIMIT)


if __name__ == '__main__':
    unittest.main()
