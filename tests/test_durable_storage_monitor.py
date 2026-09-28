import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.platform.durable_storage_monitor import (
    COUNTERS, DurableStorageMonitor, MAX_BYTES, MonitoringAdmissionError,
)


def sample():
    totals = dict.fromkeys(COUNTERS, 0)
    totals['disk_free'] = 1024 ** 3
    return totals, {'league-private': {'current_bytes': 100, 'canonical_history_bytes': 200, 'event_count': 1}}


def at(year=2026, month=9, day=1):
    return datetime(year, month, day, tzinfo=timezone.utc)


class DurableStorageMonitorTests(unittest.TestCase):
    def test_restart_preserves_baseline_and_unchanged_replay_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'monitor.json'
            monitor = DurableStorageMonitor(path)
            totals, leagues = sample()
            monitor.record(totals, leagues, now=at())
            before = path.read_bytes()
            for _ in range(100):
                DurableStorageMonitor(path).record(totals, leagues, now=at(day=2))
            self.assertEqual(before, path.read_bytes())
            self.assertNotIn('league-private', before.decode())
            leagues['league-private']['canonical_history_bytes'] += 50
            report = DurableStorageMonitor(path).record(totals, leagues, now=at(day=2))
            self.assertEqual(report['leagues'][0]['history_growth_since_baseline_bytes'], 50)
            self.assertFalse(report['annualized'])
            self.assertEqual(report['baseline_observed_on'], '2026-09-01')

    def test_ten_years_keep_only_bounded_periods_and_baselines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'monitor.json'
            totals, leagues = sample()
            for year in range(2026, 2036):
                for month in range(1, 13):
                    DurableStorageMonitor(path).record(totals, leagues, now=at(year, month))
            data = json.loads(path.read_text())
            self.assertEqual(len(data['periods']), 24)
            self.assertEqual(len(data['annual_baselines']), 3)
            self.assertLess(path.stat().st_size, MAX_BYTES)
            self.assertLess(path.stat().st_size, 32 * 1024)

    def test_admission_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'monitor.json'
            monitor = DurableStorageMonitor(path)
            totals, leagues = sample()
            monitor.record(totals, leagues, now=at())
            before = path.read_bytes()
            totals['event_count'] = 10
            with patch('src.platform.durable_storage_monitor.MAX_BYTES', len(before) + 1):
                with self.assertRaises(MonitoringAdmissionError):
                    monitor.record(totals, leagues, now=at(month=10))
            self.assertEqual(before, path.read_bytes())

    def test_alerts_do_not_authorize_deletion_or_hide_growth(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = DurableStorageMonitor(Path(folder) / 'monitor.json')
            totals, leagues = sample()
            monitor.record(totals, leagues, now=at())
            totals.update(disk_free=1, projection_provenance_rows=10001,
                          fois_observations=10001, event_count=10001,
                          cache_bytes=1024 ** 3)
            leagues['league-private']['canonical_history_bytes'] += 51 * 1024 ** 2
            report = monitor.record(totals, leagues, now=at(month=10))
            self.assertEqual(len(report['reasons']), 6)
            self.assertFalse(report['canonical_deletion_authorized'])

    def test_daily_frequency_and_backward_time_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'monitor.json'
            monitor = DurableStorageMonitor(path)
            totals, leagues = sample()
            monitor.record(totals, leagues, now=at())
            self.assertFalse(monitor.due(now=at()))
            before = path.read_bytes()
            totals['event_count'] = 20
            monitor.record(totals, leagues, now=at(month=8))
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(MonitoringAdmissionError):
                monitor.record(totals, leagues, now=datetime(2026, 9, 1))

    def test_unknown_fields_and_missing_counters_are_not_stored(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = DurableStorageMonitor(Path(folder) / 'monitor.json')
            totals, leagues = sample()
            totals['source_payload'] = 'must not persist'
            with self.assertRaises(MonitoringAdmissionError):
                monitor.record(totals, leagues, now=at())
            self.assertFalse(monitor.path.exists())
