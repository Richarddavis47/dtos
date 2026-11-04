"""Full historical response ownership, isolation and complete wire equivalence."""
from dataclasses import replace
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from routes.fois import _metadata, create_fois_router
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.fois.models import FOIS_MODEL_VERSION
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.fois import history_execution as execution
from src.platform.lifecycle import lifecycle_coordinator


class HistoricalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.repo = FOISRepository(Path(self.folder.name) / 'fois.db')
        score = FOISEngine().evaluate(FOISFacts('A', 'A:1', 'gm',
            (SeasonResult(2025, 9, 5, 2, league_size=10),), gm_id='gm', tenure_id='A:gm'))
        self.score = replace(score, evidence_integrity_version=None,
            front_office_evidence={'refs': [{'id': str(n), 'zero': 0, 'missing': None}
                                          for n in range(80)]})
        self.repo.save(self.score, 'original-source')
        self.app = FastAPI()
        self.app.include_router(create_fois_router(service=FOISService(self.repo), require_data=lambda: {}))

    def test_complete_api_is_identical_to_original_encoder_without_durable_growth(self):
        from src.core.fois.history_execution import history_requests
        self.assertEqual(history_requests.active_count, 0)
        before = hashlib.sha256(self.repo.path.read_bytes()).hexdigest()
        expected = {**_metadata(self.repo.score_for_gm('A', 'gm', FOIS_MODEL_VERSION)),
                    'timeline': jsonable_encoder(self.repo.timeline('A', 'gm'))}
        with TestClient(self.app) as client:
            for _ in range(2):
                response = client.get('/api/fois/leagues/A/gms/gm/timeline')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), expected)
                self.assertEqual(len(response.content), int(response.headers['content-length']))
                self.assertEqual(history_requests.active_count, 0)
            self.assertEqual(client.get('/api/fois/leagues/B/gms/gm/timeline').status_code, 404)
        self.assertEqual(hashlib.sha256(self.repo.path.read_bytes()).hexdigest(), before)

    def test_incremental_history_preserves_full_typed_objects_and_independence(self):
        expected = self.repo.timeline('A', 'gm')
        values = tuple(self.repo.iter_timeline('A', 'gm'))
        self.assertEqual(values, expected)
        first = values[0].front_office_evidence['refs'][0]
        self.assertIs(type(first['zero']), int)
        self.assertIsNone(first['missing'])
        first['id'] = 'consumer-local'
        self.assertEqual(next(self.repo.iter_timeline('A', 'gm')).front_office_evidence['refs'][0]['id'], '0')

    def test_profile_preserves_metadata_takeover_and_all_qualified_history(self):
        score = self.repo.score_for_gm('A', 'gm', FOIS_MODEL_VERSION)
        tenure = self.repo.tenure_for_gm('A', 'gm')
        expected = {**_metadata(score), 'profile': jsonable_encoder(score),
            'tenure': jsonable_encoder(tenure),
            'takeover': jsonable_encoder(self.repo.takeover(tenure.tenure_id)) if tenure else None,
            'history': jsonable_encoder(tuple(x for x in self.repo.timeline('A', 'gm')
                                             if x.evaluation_kind != 'current_canonical')),
            'gm_quality_is_not_team_quality': True}
        with TestClient(self.app) as client:
            response = client.get('/api/fois/leagues/A/gms/gm')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, json.dumps(expected, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).encode())

    def response(self):
        return execution.HistoryResponse(database=self.repo.path, league_id='A', gm_id='gm',
            kind='timeline', metadata=_metadata(), retained=False)

    def test_busy_and_low_memory_are_qualified_without_spawning_or_waiting(self):
        for boundary in ('busy', 'memory'):
            with self.subTest(boundary=boundary):
                if boundary == 'busy':
                    self.assertTrue(lifecycle_coordinator.try_reserve_history_response())
                try:
                    with patch.object(execution, '_memory_available', return_value=boundary != 'memory'), \
                         patch.object(asyncio, 'create_subprocess_exec', side_effect=AssertionError('Not admitted')), \
                         TestClient(self.app) as client:
                        response = client.get('/api/fois/leagues/A/gms/gm/timeline')
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.headers['retry-after'], '5')
                    self.assertEqual(response.json()['history_status'], 'unavailable')
                finally:
                    if boundary == 'busy':
                        lifecycle_coordinator.release_history_response()

    def test_lease_covers_complete_backpressured_output_and_partial_send_failure(self):
        async def scenario(fail):
            output = asyncio.Event()
            resume = asyncio.Event()
            messages = []
            async def send(message):
                messages.append(message)
                if message['type'] == 'http.response.body' and message.get('body'):
                    output.set()
                    await resume.wait()
                    if fail:
                        raise OSError('Disposable interrupted output')
            job = asyncio.create_task(self.response()._run({'type': 'http'}, None, send))
            await asyncio.wait_for(output.wait(), 10)
            self.assertEqual(execution.history_requests.active_count, 1)
            rejected = []
            async def collect(message):
                rejected.append(message)
            await self.response()._run({'type': 'http'}, None, collect)
            self.assertEqual(rejected[0]['status'], 503)
            resume.set()
            if fail:
                with self.assertRaises(OSError):
                    await job
                self.assertFalse(any(m.get('more_body') is False for m in messages))
            else:
                await job
                self.assertIs(messages[-1]['more_body'], False)
            self.assertEqual(execution.history_requests.active_count, 0)
        for fail in (False, True):
            asyncio.run(scenario(fail))

    def test_repeated_cancellation_during_output_keeps_cleanup_owned(self):
        async def scenario():
            entered = asyncio.Event()
            async def send(message):
                if message['type'] == 'http.response.body':
                    entered.set()
                    await asyncio.Event().wait()
            task = asyncio.create_task(self.response()._run({'type': 'http'}, None, send))
            await asyncio.wait_for(entered.wait(), 10)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(execution.history_requests.active_count, 0)
        asyncio.run(scenario())

    def test_timeout_cancellation_and_shutdown_reap_owned_child_before_readmission(self):
        async def scenario(mode):
            started = asyncio.Event()
            children = []
            original = asyncio.create_subprocess_exec
            async def spawn(*args, **kwargs):
                process = await original(sys.executable, '-c', 'import time; time.sleep(30)', **kwargs)
                children.append(process)
                started.set()
                return process
            messages = []
            async def send(message):
                messages.append(message)
            with patch.object(asyncio, 'create_subprocess_exec', side_effect=spawn), \
                 patch.object(execution, 'PREPARATION_TIMEOUT_SECONDS', .05 if mode == 'timeout' else 60):
                task = asyncio.create_task(self.response()._run({'type': 'http'}, None, send))
                await asyncio.wait_for(started.wait(), 10)
                if mode == 'shutdown':
                    await execution.history_requests.shutdown()
                elif mode == 'cancel':
                    for _ in range(3):
                        task.cancel()
                        await asyncio.sleep(0)
                if mode != 'timeout':
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    await task
                    self.assertEqual(messages[0]['status'], 503)
            self.assertIsNotNone(children[0].returncode)
            self.assertEqual(execution.history_requests.active_count, 0)
            execution.history_requests.startup()
        for mode in ('timeout', 'cancel', 'shutdown'):
            with self.subTest(mode=mode):
                asyncio.run(scenario(mode))

    def test_memory_pressure_stops_preparation_and_later_retry_succeeds(self):
        with patch.object(execution, '_memory_available', side_effect=lambda reserve:
                          reserve == execution.MEMORY_RESERVE_BYTES), TestClient(self.app) as client:
            response = client.get('/api/fois/leagues/A/gms/gm/timeline')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(execution.history_requests.active_count, 0)
        with TestClient(self.app) as client:
            self.assertEqual(client.get('/api/fois/leagues/A/gms/gm/timeline').status_code, 200)

    def test_spawn_failure_releases_slot_and_does_not_publish_partial_json(self):
        with patch.object(asyncio, 'create_subprocess_exec', side_effect=OSError('Disposable spawn failure')), \
             TestClient(self.app) as client:
            response = client.get('/api/fois/leagues/A/gms/gm/timeline')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['history_status'], 'unavailable')
        self.assertEqual(execution.history_requests.active_count, 0)

    def test_temporary_storage_failure_is_qualified_and_does_not_leak_admission(self):
        with patch.object(execution.tempfile, 'TemporaryFile', side_effect=OSError('Disposable storage failure')), \
             TestClient(self.app) as client:
            response = client.get('/api/fois/leagues/A/gms/gm/timeline')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['history_status'], 'unavailable')
        self.assertEqual(execution.history_requests.active_count, 0)

    def test_disconnect_during_preparation_joins_worker_and_releases_slot(self):
        async def scenario():
            receive_queue = asyncio.Queue()
            started = asyncio.Event()
            processes = []
            original = asyncio.create_subprocess_exec
            async def spawn(*args, **kwargs):
                process = await original(sys.executable, '-c', 'import time; time.sleep(30)', **kwargs)
                processes.append(process)
                started.set()
                return process
            messages = []
            async def send(message):
                messages.append(message)
            with patch.object(asyncio, 'create_subprocess_exec', side_effect=spawn):
                task = asyncio.create_task(self.response()({'type': 'http'}, receive_queue.get, send))
                await asyncio.wait_for(started.wait(), 10)
                await receive_queue.put({'type': 'http.disconnect'})
                await asyncio.wait_for(task, 5)
            self.assertEqual(messages, [])
            self.assertIsNotNone(processes[0].returncode)
            self.assertEqual(execution.history_requests.active_count, 0)
        asyncio.run(scenario())

    def test_lifecycle_exclusion_is_symmetric_and_background_waiters_cannot_starve_output(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        async def scenario():
            loop = asyncio.get_running_loop()
            loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
            output = asyncio.Event()
            resume = asyncio.Event()
            waiting = threading.Event()
            async def send(message):
                if message['type'] == 'http.response.start':
                    output.set()
                    await resume.wait()
            task = asyncio.create_task(self.response()._run({'type': 'http'}, None, send))
            await asyncio.wait_for(output.wait(), 10)
            self.assertFalse(lifecycle_coordinator.market_build_allowed())
            def background():
                waiting.set()
                lifecycle_coordinator.reserve_fois_generation()
                try:
                    self.assertEqual(execution.history_requests.active_count, 0)
                    self.assertFalse(lifecycle_coordinator.try_reserve_history_response())
                finally:
                    lifecycle_coordinator.release_fois_generation()
            waiter = asyncio.create_task(asyncio.to_thread(background))
            while not waiting.is_set():
                await asyncio.sleep(0)
            resume.set()
            await asyncio.wait_for(task, 5)
            await asyncio.wait_for(waiter, 5)
        asyncio.run(scenario())

    def test_essential_source_hydration_is_not_queued_behind_history_output(self):
        import threading
        async def scenario():
            output = asyncio.Event()
            resume = asyncio.Event()
            entered = threading.Event()
            async def send(message):
                if message['type'] == 'http.response.start':
                    output.set()
                    await resume.wait()
            history = asyncio.create_task(self.response()._run({'type': 'http'}, None, send))
            await asyncio.wait_for(output.wait(), 10)
            def hydrate():
                with lifecycle_coordinator.phase('sleeper_sync'):
                    entered.set()
            source = asyncio.create_task(asyncio.to_thread(hydrate))
            try:
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(entered.is_set(), 'Essential source acquisition waited for a slow history client')
                self.assertEqual(execution.history_requests.active_count, 1)
            finally:
                resume.set()
                await history
                await source
        asyncio.run(scenario())
