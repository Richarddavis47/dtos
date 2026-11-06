"""Preserve cache-admission policy while exposing advisory live metadata."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from services import league_preparation as preparation
from src.core.league_runtime import LeagueRuntime
from src.platform.cache_restoration_admission import MIB, restoration_admission
from src.platform.fois_admission import WORKING_RESERVE_BYTES, SAFETY_MARGIN_BYTES
from src.platform.lifecycle import HeavyWorkDeferred, LifecycleCoordinator, memory_snapshot
from tests.test_league_runtime import league_data


def plan(size, memory, active=False, **overrides):
    return restoration_admission(
        size, memory, active, fois_working_bytes=WORKING_RESERVE_BYTES,
        fois_safety_bytes=SAFETY_MARGIN_BYTES, **overrides,
    )


class RestorationArithmeticTests(unittest.TestCase):
    def test_granite_reserves_and_exact_boundary_remain_unchanged(self):
        size = 23_048_708
        for active, expected in ((False, 502_997_056), (True, 1_174_085_696)):
            with self.subTest(fois=active):
                limit = 2 * 1024**3
                at = plan(size, {'cgroup_current_bytes': limit - expected,
                                 'cgroup_limit_bytes': limit}, active)
                below = plan(size, {'cgroup_current_bytes': limit - expected + 1,
                                    'cgroup_limit_bytes': limit}, active)
                self.assertEqual(at['working_bytes'], 368_779_328)
                self.assertEqual(at['required_bytes'], expected)
                self.assertIs(at['would_admit'], True)
                self.assertEqual(at['headroom_bytes'], expected)
                self.assertIs(below['would_admit'], False)
                self.assertEqual(below['reason'], 'insufficient_headroom')

    def test_legacy_predicate_agrees_for_known_inputs_and_hard_cap(self):
        # Frozen pre-extraction contract: keep these edge cases independent of
        # the returned diagnostic fields and the function's own branch labels.
        for size in (0, 1, 8 * MIB, 23_048_708, 64 * MIB):
            for limit in (512 * MIB, 2 * 1024**3, 4 * 1024**3):
                for used in (0, 256 * MIB, 1490 * MIB, 2 * 1024**3, 3 * 1024**3):
                    for active in (False, True):
                        expected_required = max(128 * MIB, size * 16) + (
                            512 * MIB + 256 * MIB if active else 128 * MIB
                        )
                        expected = min(limit, 2 * 1024**3) - used >= expected_required
                        result = plan(size, {'cgroup_current_bytes': used,
                                             'cgroup_limit_bytes': limit}, active)
                        self.assertEqual(result['would_admit'], expected)
                        self.assertEqual(result['effective_limit_bytes'], min(limit, 2 * 1024**3))

    def test_unknown_is_not_zero_or_a_measured_negative_result(self):
        good = {'cgroup_current_bytes': 0, 'cgroup_limit_bytes': 2 * 1024**3}
        self.assertIs(plan(0, good)['would_admit'], True)
        bad = ({}, None, {'cgroup_current_bytes': False, 'cgroup_limit_bytes': 2 * 1024**3},
               {'cgroup_current_bytes': -1, 'cgroup_limit_bytes': 2 * 1024**3},
               {'cgroup_current_bytes': 1, 'cgroup_limit_bytes': True},
               {'cgroup_current_bytes': 1, 'cgroup_limit_bytes': 0},
               {'cgroup_current_bytes': 1.0, 'cgroup_limit_bytes': 2 * 1024**3})
        for memory in bad:
            with self.subTest(memory=memory):
                result = plan(1, memory)
                self.assertIsNone(result['would_admit'])
                self.assertFalse(result['telemetry_valid'])
                self.assertEqual(result['reason'], 'unknown_memory')
                self.assertIsNone(result['headroom_bytes'])
        for size in (None, False, -1, '12'):
            self.assertEqual(plan(size, good)['reason'], 'unknown_file_size')
        for active in (None, 0, 1, 'false'):
            result = plan(1, good, active)
            self.assertEqual(result['reason'], 'unknown_reservation')
            self.assertIsNone(result['required_bytes'])
            self.assertIsNone(result['would_admit'])

    def test_auxiliary_missing_memory_fields_do_not_change_actual_guard_inputs(self):
        memory = {'cgroup_current_bytes': MIB, 'cgroup_limit_bytes': 2 * 1024**3}
        self.assertIs(plan(1, memory)['would_admit'], True)
        self.assertEqual(plan(1, memory), plan(1, memory | {'cgroup_anonymous_bytes': None}))


class RestorationDelegationTests(unittest.TestCase):
    def test_real_restore_delegates_to_shared_calculation_and_preserves_decode_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.json'
            data = league_data('200')
            path.write_text(json.dumps({'data': data, 'last_sync': datetime.now(timezone.utc).isoformat()}))
            sample = {'cgroup_current_bytes': 2 * 1024**3 - 1,
                      'cgroup_limit_bytes': 2 * 1024**3}
            real = preparation.restoration_admission
            with patch.object(preparation, 'league_cache_file', return_value=path), \
                    patch.object(preparation, 'memory_snapshot', return_value=sample), \
                    patch.object(preparation, 'restoration_admission', wraps=real) as shared, \
                    patch.object(preparation, 'load_cache_json') as decoder:
                with self.assertRaises(HeavyWorkDeferred):
                    preparation.restore_cached_runtime(LeagueRuntime('200'), Mock())
                decoder.assert_not_called()
                self.assertEqual(shared.call_count, 1)
                self.assertEqual(shared.call_args.args[:2], (path.stat().st_size, sample))
                self.assertEqual(shared.call_args.kwargs['fois_working_bytes'], WORKING_RESERVE_BYTES)
                self.assertEqual(shared.call_args.kwargs['fois_safety_bytes'], SAFETY_MARGIN_BYTES)


class RestorationSnapshotTests(unittest.TestCase):
    def test_snapshot_reads_the_instance_without_lease_history_or_state_mutation(self):
        coordinator = LifecycleCoordinator()
        sample = {'cgroup_current_bytes': 10, 'cgroup_limit_bytes': 2 * 1024**3}
        coordinator._fois_generation = 1
        coordinator._market_critical = 1
        coordinator._market_critical_reason = '/PRIVATE_REASON_NOT_EXPORTED'
        before = (coordinator._phase, coordinator._owner, tuple(coordinator._history))
        with patch('src.platform.lifecycle.memory_snapshot', return_value=sample), \
                patch.object(coordinator, 'phase', side_effect=AssertionError('Lease acquisition')):
            result = coordinator.restoration_snapshot()
        self.assertTrue(result['available'])
        self.assertTrue(result['heavy_work']['fois_generation'])
        self.assertTrue(result['heavy_work']['market_critical'])
        self.assertFalse(result['cache_lease_conflict'])
        self.assertEqual(result['memory'], sample)
        self.assertEqual(result['coordination_scope'], 'serving_process')
        self.assertTrue(result['non_atomic'])
        self.assertNotIn('recent_phases', result)
        self.assertNotIn('PRIVATE', repr(result))
        self.assertEqual(before, (coordinator._phase, coordinator._owner, tuple(coordinator._history)))

    def test_snapshot_conflict_matches_cache_phase_and_changes_after_release(self):
        for field, value in (('_trade_search', True), ('_history_response', True),
                             ('_phase', 'sleeper_sync')):
            with self.subTest(field=field):
                coordinator = LifecycleCoordinator()
                setattr(coordinator, field, value)
                result = coordinator.restoration_snapshot()
                self.assertTrue(result['cache_lease_conflict'])
                with self.assertRaises(HeavyWorkDeferred):
                    with coordinator.phase('cache_persistence', wait=False):
                        self.fail('Conflicting phase must not be acquired')
                setattr(coordinator, field, None if field == '_phase' else False)
                self.assertFalse(coordinator.restoration_snapshot()['cache_lease_conflict'])
                with coordinator.phase('cache_persistence', wait=False):
                    self.assertEqual(coordinator._phase, 'cache_persistence')

    def test_contended_snapshot_returns_unknown_without_waiting_or_reading_memory(self):
        coordinator = LifecycleCoordinator()
        acquired, release = threading.Event(), threading.Event()
        def hold():
            with coordinator._condition:
                acquired.set()
                release.wait(3)
        worker = threading.Thread(target=hold)
        worker.start()
        self.assertTrue(acquired.wait(2))
        try:
            with patch('src.platform.lifecycle.memory_snapshot', side_effect=AssertionError('Should not sample')):
                result = coordinator.restoration_snapshot()
            self.assertFalse(result['available'])
            self.assertEqual(result['reason'], 'coordinator_busy')
            self.assertIsNone(result['cache_lease_conflict'])
            self.assertIsNone(result['phase'])
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())

    def test_memory_failure_keeps_known_flags_but_does_not_fabricate_capacity(self):
        coordinator = LifecycleCoordinator()
        with patch('src.platform.lifecycle.memory_snapshot', side_effect=OSError('PRIVATE')):
            result = coordinator.restoration_snapshot()
        self.assertTrue(result['available'])
        self.assertEqual(result['memory'], {})
        self.assertEqual(result['reason'], 'memory_unavailable')
        self.assertIsNone(plan(1, result['memory'])['would_admit'])

    def test_anonymous_counter_uses_the_existing_memory_stat_read(self):
        with patch('src.platform.lifecycle._integer_file', return_value=2 * 1024**3), \
                patch('src.platform.lifecycle._key_value_file', side_effect=[{'anon': 123, 'inactive_file': 456}, {}]) as read:
            result = memory_snapshot()
        self.assertEqual(result['cgroup_anonymous_bytes'], 123)
        self.assertEqual(result['cgroup_inactive_file_bytes'], 456)
        self.assertEqual(read.call_count, 2)  # memory.stat plus memory.events, no extra scan.


if __name__ == '__main__':
    unittest.main()
