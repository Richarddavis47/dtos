"""Cold restoration may reclaim unused objects, never relax measured admission."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
import threading
import unittest
from unittest.mock import Mock, patch

from services import league_preparation as preparation
from src.core.league_runtime import LeagueRuntime
from src.platform import memory_reclamation
from src.platform.lifecycle import HeavyWorkDeferred, lifecycle_coordinator
from tests.test_league_entry_coordination import CachedPublicationTests

MIB = 1024**2
LIMIT = 2 * 1024**3


def memory(headroom):
    return {'cgroup_current_bytes': LIMIT-headroom*MIB, 'cgroup_limit_bytes': LIMIT}


class RestorationRecoveryTests(unittest.TestCase):
    setUp = CachedPublicationTests.setUp
    write = CachedPublicationTests.write

    def test_healthy_restore_does_not_run_cleanup(self):
        runtime = LeagueRuntime('200')
        with patch.object(preparation, 'reclaim_unused_analytical_memory') as recover:
            self.assertTrue(preparation.restore_cached_runtime(runtime, Mock(), expected_season=2026))
        recover.assert_not_called()
        self.assertNotIn('cache_restore_memory_recovery', runtime.lifecycle)

    def test_one_recovery_then_fresh_measured_guard_allows_real_decode(self):
        runtime, publish = LeagueRuntime('200'), Mock()
        def recover():
            self.assertEqual(lifecycle_coordinator.snapshot()['phase'], 'cache_persistence')
            self.assertEqual(runtime.state['data'], {})
            return dict(expired_entries=1, idle_worker_retired=True, allocator_trimmed=True)
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), memory(300)]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory', side_effect=recover) as cleanup:
            self.assertTrue(preparation.restore_cached_runtime(runtime, publish, expected_season=2026))
        cleanup.assert_called_once_with()
        publish.assert_called_once_with(runtime)
        self.assertEqual(runtime.state['data'], self.data)
        result = runtime.lifecycle['cache_restore_memory_recovery']
        self.assertEqual(result['required_bytes'], 256*MIB)
        self.assertTrue(result['would_admit'])
        self.assertEqual(result['after_bytes'], memory(300)['cgroup_current_bytes'])
        self.assertEqual(runtime.lifecycle['preparation_state'], 'last_valid')

    def test_no_reported_cleanup_count_is_credited_as_capacity(self):
        runtime = LeagueRuntime('200')
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), memory(200)]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory', return_value={'expired_entries':512, 'idle_worker_retired':True, 'allocator_trimmed':True}) as cleanup, \
             patch.object(preparation.json, 'load') as decode:
            with self.assertRaises(HeavyWorkDeferred):
                preparation.restore_cached_runtime(runtime, Mock())
        cleanup.assert_called_once()
        decode.assert_not_called()
        self.assertEqual(runtime.state['data'], {})
        self.assertFalse(runtime.lifecycle['cache_restore_memory_recovery']['would_admit'])

    def test_unknown_and_near_limit_samples_defer_without_cleanup_or_decode(self):
        for sample in ({}, memory(0), memory(127)):
            with self.subTest(sample=sample), \
                 patch.object(preparation, 'memory_snapshot', return_value=sample), \
                 patch.object(preparation, 'reclaim_unused_analytical_memory') as cleanup, \
                 patch.object(preparation.json, 'load') as decode:
                with self.assertRaises(HeavyWorkDeferred):
                    preparation.restore_cached_runtime(LeagueRuntime('200'), Mock())
                cleanup.assert_not_called()
                decode.assert_not_called()

    def test_lost_telemetry_after_recovery_is_unknown_and_fails_closed(self):
        runtime = LeagueRuntime('200')
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), {}]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory'), \
             patch.object(preparation.json, 'load') as decode:
            with self.assertRaises(HeavyWorkDeferred):
                preparation.restore_cached_runtime(runtime, Mock())
        decode.assert_not_called()
        self.assertIsNone(runtime.lifecycle['cache_restore_memory_recovery']['would_admit'])

    def test_active_fois_keeps_its_entire_reservation_after_recovery(self):
        lifecycle_coordinator.reserve_fois_generation()
        self.addCleanup(lifecycle_coordinator.release_fois_generation)
        runtime = LeagueRuntime('200')
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(800), memory(850)]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory') as cleanup, \
             patch.object(preparation.json, 'load') as decode:
            with self.assertRaises(HeavyWorkDeferred):
                preparation.restore_cached_runtime(runtime, Mock())
        cleanup.assert_called_once()
        decode.assert_not_called()
        self.assertEqual(runtime.lifecycle['cache_restore_memory_recovery']['required_bytes'], 896*MIB)

    def test_competing_sync_phase_defers_before_recovery(self):
        with lifecycle_coordinator.phase('sleeper_sync'), \
             patch.object(preparation, 'reclaim_unused_analytical_memory') as cleanup, \
             patch.object(preparation.json, 'load') as decode:
            with self.assertRaises(HeavyWorkDeferred):
                preparation.restore_cached_runtime(LeagueRuntime('200'), Mock())
        cleanup.assert_not_called()
        decode.assert_not_called()

    def test_cleanup_failure_does_not_become_source_failure_or_allow_decode(self):
        runtime = LeagueRuntime('200')
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), memory(200)]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory', side_effect=OSError('private diagnostic text')), \
             patch.object(preparation.json, 'load') as decode:
            with self.assertRaises(HeavyWorkDeferred):
                preparation.restore_cached_runtime(runtime, Mock())
        decode.assert_not_called()
        self.assertTrue(runtime.lifecycle['cache_restore_memory_recovery']['cleanup_unavailable'])
        self.assertNotIn('private diagnostic text', repr(runtime.lifecycle))

    def test_atomic_file_replacement_during_cleanup_keeps_opened_generation(self):
        original = deepcopy(self.data)
        def recover():
            replacement = self.path.with_suffix('.next')
            replacement.write_text(json.dumps({'data':dict(league={'league_id':'300'}), 'different_generation': 'x'*10000}))
            os.replace(replacement, self.path)
            return {}
        runtime = LeagueRuntime('200')
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), memory(300)]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory', side_effect=recover):
            self.assertTrue(preparation.restore_cached_runtime(runtime, Mock(), expected_season=2026))
        self.assertEqual(runtime.state['data'], original)
        self.assertEqual(json.loads(self.path.read_text())['data']['league']['league_id'], '300')

    def test_sleeper_actuals_exact_picks_and_other_leagues_survive_recovery(self):
        from tests.test_sleeper_actual_results import actual_data, publish, profile
        for league_id, superflex in (('200', False), ('300', True)):
            with self.subTest(league_id=league_id):
                data = actual_data(league_id=league_id, scores=(0, -2.125, 23.4738))
                if superflex:
                    data['league']['roster_positions'].append('SUPER_FLEX')
                data['teams'] = [{'roster_id':1, 'league_id':league_id}]
                data['pick_ledger'] = [{'asset_id':f'pick:{league_id}:2029:1:2', 'original_franchise_id':2}]
                publish(data)
                source_scores = [r['players_points']['4984'] for w in data['season_matchups']['weeks'].values() for r in w['rows']]
                self.data = data
                self.write()
                runtime = LeagueRuntime(league_id)
                with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), memory(300)]), \
                     patch.object(preparation, 'reclaim_unused_analytical_memory'):
                    self.assertTrue(preparation.restore_cached_runtime(runtime, Mock(), expected_season=2026))
                restored = runtime.state['data']
                self.assertEqual([o['points'] for o in profile(restored).observations], source_scores)
                self.assertEqual(restored['pick_ledger'], data['pick_ledger'])
                self.assertEqual(restored['league']['roster_positions'], data['league']['roster_positions'])
                self.assertEqual(restored['scoring_settings'], data['scoring_settings'])


class RecoveryOwnershipTests(unittest.TestCase):
    def test_active_fois_owner_is_not_retired_even_between_submissions(self):
        from src.core.intelligence.cache import IntelligenceCache
        cache = IntelligenceCache()
        held, live = object(), object()
        cache.get_or_create('expired', lambda:held, ttl=-1)
        cache.get_or_create('live', lambda:live, ttl=100)
        lifecycle_coordinator.reserve_fois_generation()
        self.addCleanup(lifecycle_coordinator.release_fois_generation)
        with patch('src.core.intelligence.cache.intelligence_cache', cache), \
             patch('src.core.fois.process_execution.retire_idle_fois_executor_sync') as retire, \
             patch('src.platform.memory_reclamation.release_unused_allocator_pages', return_value=False):
            facts = memory_reclamation.reclaim_unused_analytical_memory()
        retire.assert_not_called()
        self.assertFalse(facts['idle_worker_retired'])
        self.assertEqual(facts['expired_entries'], 1)
        self.assertIsNone(cache.peek('expired'))
        self.assertIs(cache.peek('live'), live)
        self.assertIsNotNone(held)

    def test_cancellation_check_stops_before_any_cleanup(self):
        class Stopped(BaseException):
            pass
        with patch('src.core.fois.process_execution.retire_idle_fois_executor_sync') as retire:
            with self.assertRaises(Stopped):
                memory_reclamation.reclaim_unused_analytical_memory(stop_check=Mock(side_effect=Stopped()))
        retire.assert_not_called()

    def test_owned_cancellation_drains_real_restoration_before_releasing_state(self):
        fixture = RestorationRecoveryTests('test_healthy_restore_does_not_run_cleanup')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        entered, release = threading.Event(), threading.Event()
        publish, runtime = Mock(), LeagueRuntime('200')
        def cleanup():
            entered.set()
            if not release.wait(5):
                raise AssertionError('Controlled cleanup was not released')
            return {}
        async def journey():
            task = asyncio.create_task(preparation.restore_cached_runtime_owned(runtime, publish, expected_season=2026))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                task.cancel()
                await asyncio.sleep(.01)
                self.assertFalse(task.done())
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        with patch.object(preparation, 'memory_snapshot', side_effect=[memory(200), memory(300)]), \
             patch.object(preparation, 'reclaim_unused_analytical_memory', side_effect=cleanup):
            asyncio.run(journey())
        publish.assert_called_once_with(runtime)
        self.assertEqual(runtime.state['data'], fixture.data)
        asyncio.run(runtime.close())
        self.assertEqual(runtime.state['data'], {})
