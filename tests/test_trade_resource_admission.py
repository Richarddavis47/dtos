"""Memory decisions, genuine thread lifetime, and unchanged one-QB evidence."""
import asyncio
from copy import deepcopy
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.trades import create_trades_router
from src.platform import trade_execution as execution
from src.platform.lifecycle import LifecycleCoordinator, lifecycle_coordinator
from tests import test_multileague_projection_compatibility as one_qb


def sample(current=512 * execution.MIB, *, inactive=0, dirty=0):
    return {'cgroup_current_bytes': current, 'cgroup_limit_bytes': 2048 * execution.MIB,
        'cgroup_memory_events': {'oom': 0, 'oom_kill': 0},
        'file_accounting': {'file': inactive, 'inactive_file': inactive,
            'file_dirty': dirty, 'file_writeback': 0, 'shmem': 0, 'unevictable': 0}}


class TradeMemoryPolicyTests(unittest.TestCase):
    def test_raw_headroom_and_unknown_telemetry(self):
        self.assertTrue(execution.assess_memory(sample())['admitted'])
        for update in ({'cgroup_current_bytes': None}, {'cgroup_limit_bytes': None},
                       {'cgroup_current_bytes': True}, {'cgroup_current_bytes': -1}):
            with self.subTest(update=update):
                self.assertFalse(execution.assess_memory(sample() | update)['admitted'])
        self.assertFalse(execution.assess_memory({'system_available_bytes': 100 * 1024**3})['admitted'])
        self.assertFalse(execution.assess_memory(sample(2050 * execution.MIB, inactive=1024 * execution.MIB))['admitted'])

    def test_clean_file_allowance_is_half_bounded_and_not_free_memory(self):
        row = execution.assess_memory(sample(2000 * execution.MIB, inactive=624 * execution.MIB))
        self.assertFalse(row['admitted'])
        self.assertEqual(row['conditional_file_credit_bytes'], 312 * execution.MIB)
        self.assertEqual(row['raw_headroom_bytes'], 48 * execution.MIB)
        # This precise sample still cannot cover the 384MiB combined reserve.
        self.assertLess(row['admission_headroom_bytes'], execution.WORKING_BYTES + execution.SAFETY_BYTES)

    def test_dirty_shared_unknown_and_inconsistent_file_evidence_never_invents_credit(self):
        source = sample(1950 * execution.MIB, inactive=624 * execution.MIB)
        self.assertTrue(execution.assess_memory(source)['admitted'])
        for update in ({'file_accounting': {}}, {'cgroup_memory_events': None},
                {'file_accounting': source['file_accounting'] | {'file_dirty': 624 * execution.MIB}},
                {'file_accounting': source['file_accounting'] | {'shmem': 624 * execution.MIB}},
                {'file_accounting': source['file_accounting'] | {'file': 0}}):
            with self.subTest(update=update):
                row = execution.assess_memory(source | update)
                self.assertFalse(row['admitted'])
                self.assertEqual(row['conditional_file_credit_bytes'], 0)
        row = execution.assess_memory(sample(2040 * execution.MIB, inactive=1800 * execution.MIB))
        self.assertEqual(row['conditional_file_credit_bytes'], execution.MAX_FILE_CREDIT_BYTES)

    def test_trade_reservation_excludes_sync_fois_history_and_duplicate_search(self):
        coordinator = LifecycleCoordinator()
        self.assertTrue(coordinator.try_reserve_trade_search())
        self.assertFalse(coordinator.try_reserve_trade_search())
        self.assertFalse(coordinator.try_reserve_history_response())
        self.assertFalse(coordinator.market_build_allowed())
        with self.assertRaisesRegex(RuntimeError, 'deferred'):
            with coordinator.phase('sleeper_sync'):
                pass
        entered = threading.Event()
        def reserve():
            coordinator.reserve_fois_generation()
            entered.set()
            coordinator.release_fois_generation()
        thread = threading.Thread(target=reserve)
        thread.start()
        self.assertFalse(entered.wait(.03))
        coordinator.release_trade_search()
        thread.join(1)
        self.assertTrue(entered.is_set())
        self.assertTrue(coordinator.trade_search_available())
        coordinator.reserve_fois_generation()
        self.assertFalse(coordinator.try_reserve_trade_search())
        coordinator.release_fois_generation()
        with coordinator.phase('sleeper_sync'):
            self.assertFalse(coordinator.try_reserve_trade_search())


class TradeThreadLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(lifecycle_coordinator.trade_search_available())
        self.assertTrue(execution.assess_memory(execution.observe_memory())['admitted'],
                        'Normal-execution control needs measured container headroom.')

    def test_real_execution_and_failure_release_the_lease(self):
        async def journey():
            def operation():
                self.assertFalse(lifecycle_coordinator.trade_search_available())
                return sum(range(1000))
            self.assertEqual(await execution.run_trade_operation(operation), 499500)
            def failed():
                raise RuntimeError('Disposable failure')
            with self.assertRaises(RuntimeError):
                await execution.run_trade_operation(failed)
            self.assertTrue(lifecycle_coordinator.trade_search_available())
        asyncio.run(journey())

    def test_recovery_removes_only_expired_entries_and_retains_live_values(self):
        from src.core.intelligence.cache import IntelligenceCache
        from src.core.trade_intelligence.lineup_memo import LineupStore
        cache = IntelligenceCache()
        old, current = object(), object()
        cache.get_or_create('old', lambda: old, ttl=-1)
        cache.get_or_create('current', lambda: current, ttl=100)
        store = LineupStore(clock=lambda: 100)
        with patch('src.core.intelligence.cache.intelligence_cache', cache), \
             patch('src.core.trade_intelligence.lineup_memo.lineup_store', store), \
             patch('src.core.fois.process_execution.retire_idle_fois_executor_sync', return_value=False), \
             patch('src.platform.memory_reclamation.release_unused_allocator_pages', return_value=False):
            facts = execution._recover_unused(execution.TradeControl(time.monotonic()+10))
        self.assertEqual(facts['expired_entries'], 1)
        self.assertIsNone(cache.peek('old'))
        self.assertIs(cache.peek('current'), current)

    def test_admission_does_not_change_any_completed_trade_math_or_strategy(self):
        from services import trade_intelligence as trade
        from tests import test_trade_discovery_repair as fixtures
        from tests.test_trade_performance import business
        f = fixtures.DiscoveryRepairTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        before = deepcopy(f.data)
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            payload = {'workflow': 'recommended', 'active_roster_id': 1, 'strategy': strategy}
            reference = trade.generate_trade_workflow(f.data, payload)
            actual = asyncio.run(execution.run_trade_operation(lambda: trade.generate_trade_workflow(f.data, payload)))
            self.assertEqual(business(reference), business(actual))
        self.assertEqual(f.data, before)

    def test_actual_cancellation_drains_thread_before_releasing_ownership(self):
        entered, finished = threading.Event(), threading.Event()
        def operation():
            buffer = bytearray(8 * execution.MIB)
            entered.set()
            try:
                while True:
                    execution.trade_checkpoint()
                    buffer[0] = 1
                    time.sleep(.005)
            finally:
                finished.set()
        async def journey():
            task = asyncio.create_task(execution.run_trade_operation(operation))
            while not entered.is_set():
                await asyncio.sleep(.005)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(finished.is_set())
            self.assertTrue(lifecycle_coordinator.trade_search_available())
            self.assertEqual(await execution.run_trade_operation(lambda: 'recovered'), 'recovered')
        asyncio.run(journey())

    def test_real_timeout_and_disconnect_stop_work_without_a_completed_result(self):
        ended = threading.Event()
        def operation():
            try:
                while True:
                    execution.trade_checkpoint()
                    time.sleep(.005)
            finally:
                ended.set()
        async def journey():
            with patch.object(execution, 'TRADE_TIMEOUT_SECONDS', .03):
                with self.assertRaises(execution.TradeSearchTimedOut):
                    await execution.run_trade_operation(operation)
            self.assertTrue(ended.is_set())
            ended.clear()
            request = type('Disconnected', (), {'is_disconnected': AsyncMock(return_value=True)})()
            with self.assertRaises(asyncio.CancelledError):
                await execution.run_trade_operation(operation, request=request)
            self.assertTrue(ended.is_set())
            self.assertTrue(lifecycle_coordinator.trade_search_available())
        asyncio.run(journey())


class TradeResourceHTTPTests(unittest.TestCase):
    def setUp(self):
        f = one_qb.MultiLeagueProjectionTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f = f
        for team in f.data['teams']:
            team.update(strategy='RETOOL', team_name='Disposable franchise')
        f.data['market_data'] = {'providers': {'FantasyCalc': {
            pid: {'value': 3000, 'confidence': 90} for pid, row in f.data['players'].items()
            if row['position'] not in {'K', 'DEF'}}}}
        f.publish()
        self.enterContext(patch('services.trade_intelligence._trade_projection_service', return_value=f.service))
        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: f.data,
            page=lambda title, body: body))
        self.client = self.enterContext(TestClient(app))

    def test_one_qb_supported_legal_pre_post_and_unchanged_source(self):
        before = deepcopy(self.f.data)
        response = self.client.post('/api/trades/evaluate', json={'active_roster_id': 1,
            'partner_roster_id': 2, 'assets_sent': ['1-0'], 'assets_received': ['2-10'],
            'workflow': 'create', 'strategy': 'RETOOL'})
        self.assertEqual(response.status_code, 200, response.text)
        evaluation = response.json()['evaluation']
        self.assertEqual(evaluation['market_evidence']['availability'], 'full')
        for side in evaluation['multi_horizon_impact']['sides'].values():
            for phase in ('pre', 'post'):
                optimal = side['weekly']['8'][phase]['optimal']
                self.assertTrue(optimal['available'])
                self.assertTrue({'QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'DEF'} <= {e['slot'] for e in optimal['entries']})
        self.assertEqual(self.f.data, before)

    def test_deferral_is_503_not_zero_results_and_never_exposes_telemetry(self):
        pressure = sample(2000 * execution.MIB)
        with patch.object(execution, 'observe_memory', return_value=pressure), \
             patch('routes.trades.generate_trade_workflow') as generate:
            response = self.client.post('/api/trades/generate', json={'active_roster_id': 1,
                'workflow': 'recommended', 'strategy': 'REBUILD'})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()['detail']['code'], 'trade_capacity_deferred')
        self.assertNotIn('results', response.json())
        for private in ('2097152000', 'cgroup', 'anonymous', '/sys/', 'MemoryError'):
            self.assertNotIn(private, response.text)
        generate.assert_not_called()
        self.assertTrue(lifecycle_coordinator.trade_search_available())

    def test_workspace_observes_readiness_without_starting_or_reclaiming_work(self):
        with patch.object(execution, '_recover_unused') as recover, \
             patch('routes.trades.generate_trade_workflow') as generate:
            response = self.client.get('/api/trades/workspace?front_office=1')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(response.json()['search_readiness']['state'], ('ready', 'deferred', 'unknown'))
        self.assertEqual(response.json()['lineup_preparation']['state'], 'prepared')
        self.assertFalse(response.json()['search_readiness']['automatic_retry'])
        recover.assert_not_called()
        generate.assert_not_called()
