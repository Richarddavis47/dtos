"""Bounded read-only timings cannot publish facts or hide unavailable memory."""
from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.platform.sync_diagnostics import PHASES, SyncDiagnostics


class SyncDiagnosticsTests(unittest.TestCase):
    def test_fixed_phase_report_contains_numeric_samples_without_source_records(self):
        info = SimpleNamespace(rss=40, pss=30, uss=20)
        parent = SimpleNamespace(pid=7, children=lambda **_: [], memory_full_info=lambda: info)
        with patch('src.platform.sync_diagnostics._memory', return_value={'rss_bytes': 40}), \
                patch('src.platform.sync_diagnostics.psutil.Process', return_value=parent), \
                patch('src.platform.sync_diagnostics.perf_counter', side_effect=[1, 2, 4]), \
                self.assertLogs('dtos.sync_profile', level='INFO') as logs:
            trace = SyncDiagnostics('sensitive-league-identity')
            trace.mark('source_acquisition')
            report = trace.finish(failed=False)
        self.assertEqual(report['phase_ms'], {'source_acquisition': 1000})
        self.assertEqual(report['duration_ms'], 3000)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['process_samples'], [{'pid': 7, 'parent': True, 'rss': 40, 'pss': 30, 'uss': 20}])
        self.assertNotIn('sensitive-league-identity', json.dumps(report))
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(len(report['league_scope']), 16)
        self.assertLess(len(json.dumps(report)), 4096)

    def test_unavailable_telemetry_is_qualified_not_zero(self):
        with patch('src.platform.sync_diagnostics._memory', side_effect=OSError), \
                self.assertLogs('dtos.sync_profile', level='INFO'):
            trace = SyncDiagnostics('100')
            report = trace.finish(failed=True)
        self.assertEqual(report['memory_before'], {'state': 'unavailable'})
        self.assertEqual(report['memory_state'], 'unavailable')
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('memory_after', report)

    def test_process_count_and_phase_names_are_bounded(self):
        info = SimpleNamespace(rss=1, pss=None, uss=None)
        child = SimpleNamespace(pid=2, memory_full_info=lambda: info)
        parent = SimpleNamespace(pid=1, children=lambda **_: [child] * 100, memory_full_info=lambda: info)
        with patch('src.platform.sync_diagnostics._memory', return_value={}), \
                patch('src.platform.sync_diagnostics.psutil.Process', return_value=parent), \
                self.assertLogs('dtos.sync_profile', level='INFO'):
            trace = SyncDiagnostics('100')
            for name in PHASES:
                trace.mark(name)
            with self.assertRaises(ValueError):
                trace.mark('unbounded arbitrary input')
            report = trace.finish(failed=False)
        self.assertEqual(len(report['phase_ms']), 16)
        self.assertEqual(len(report['process_samples']), 16)
        self.assertTrue(report['process_samples_truncated'])
