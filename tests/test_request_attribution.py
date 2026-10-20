"""Actual HTTPX/ASGI clocks, bounded telemetry and absence of payload capture."""
from __future__ import annotations

import asyncio
import gc
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.data_platform import data_platform
from src.core.league_runtime.manager import LeagueRuntimeManager
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware
from src.platform.memory_attribution import (
    ACTIVITY_LIMIT, PENDING_LIMIT, MemoryAttribution, capture_memory,
)
from src.platform.observability import BoundedRequestQueueHandler, CorrelationFormatter, RequestObservabilityMiddleware, install_observability
from src.platform.request_diagnostics import (
    MAX_EVENTS, MAX_PENDING, Trace, decode_json, request_trace, source_hooks, span,
)


def diagnostics(records):
    return [record.diagnostic for record in records if hasattr(record, 'diagnostic')]


class TransferClockTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_loopback_transfer_stays_pending_after_response_headers(self):
        release = threading.Event()
        headers_seen = asyncio.Event()
        payload = b'{"score":0.0}'
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.flush()
                if release.wait(5):
                    self.wfile.write(payload)
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        hooks = source_hooks()
        async def notice(_response):
            headers_seen.set()
        hooks['response'].append(notice)
        try:
            with self.assertLogs('dtos.attribution', level='INFO') as captured, request_trace('real-transfer', enabled=True):
                async with httpx.AsyncClient(trust_env=False, event_hooks=hooks) as client:
                    task = asyncio.create_task(data_platform.get_json(client, f'http://127.0.0.1:{server.server_port}/league/100'))
                    await asyncio.wait_for(headers_seen.wait(), 5)
                    self.assertFalse(task.done())
                    self.assertFalse(any(x.get('body_complete') for x in diagnostics(captured.records)))
                    self.assertTrue(any(x['boundary'] == 'transport_headers_received' for x in diagnostics(captured.records)))
                    release.set()
                    self.assertEqual(await task, {'score': 0.0})
            self.assertTrue(any(x.get('body_complete') for x in diagnostics(captured.records)))
        finally:
            release.set()
            await asyncio.to_thread(server.shutdown)
            thread.join(2)
            server.server_close()

    async def test_headers_do_not_mean_body_complete_and_payload_never_enters_trace(self):
        body_started, release = asyncio.Event(), asyncio.Event()

        class Body(httpx.AsyncByteStream):
            async def __aiter__(self):
                body_started.set()
                await release.wait()
                yield b'{"score":0,"private_payload":"do-not-log-this-value"}'

        async def transport(_request):
            return httpx.Response(200, stream=Body())

        with self.assertLogs('dtos.attribution', level='INFO') as captured, request_trace('cold-barrier', enabled=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport), event_hooks=source_hooks()) as client:
                task = asyncio.create_task(data_platform.get_json(client,
                    'https://api.sleeper.app/projections/nfl/2026/6?private=do-not-log-query'))
                await body_started.wait()
                prior = diagnostics(captured.records)
                self.assertTrue(any(x['boundary'] == 'headers_received' for x in prior))
                self.assertFalse(any(x.get('body_complete') for x in prior))
                release.set()
                result = await task
        self.assertEqual(result['score'], 0)
        rows = diagnostics(captured.records)
        transfer = next(x for x in rows if x.get('body_complete'))
        parsing = next(x for x in rows if x['name'] == 'source_json_parse' and x['boundary'] == 'finished')
        self.assertEqual(parsing['related_source_span_id'], transfer['span_id'])
        self.assertGreaterEqual(parsing['elapsed_from_trace_ms'], transfer['elapsed_from_trace_ms'])
        self.assertIn('timestamp', transfer)
        serialized = json.dumps(rows)
        self.assertNotIn('do-not-log', serialized)
        self.assertNotIn('https://', serialized)
        self.assertTrue(all(record.request_id == 'cold-barrier' for record in captured.records))

    async def test_failed_partial_transfer_never_becomes_completed_or_zero(self):
        class Body(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{"score":'
                raise httpx.ReadError('sensitive upstream detail')
        with self.assertLogs('dtos.attribution', level='INFO') as captured, request_trace('failed-transfer', enabled=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Body())), event_hooks=source_hooks()) as client:
                with self.assertRaises(httpx.ReadError):
                    await data_platform.get_json(client, 'https://api.sleeper.app/players/nfl')
        rows = diagnostics(captured.records)
        self.assertFalse(any(x.get('body_complete') for x in rows))
        self.assertTrue(any(x.get('status') == 'incomplete' for x in rows))
        self.assertNotIn('sensitive upstream detail', json.dumps(rows))

    async def test_preloaded_transport_and_json_error_preserve_existing_semantics(self):
        with self.assertLogs('dtos.attribution', level='INFO') as captured, request_trace('parse-failure', enabled=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b'not-json')), event_hooks=source_hooks()) as client:
                response = await client.get('https://api.sleeper.app/state/nfl')
                with self.assertRaises(ValueError):
                    decode_json(response)
        self.assertTrue(any(x['name'] == 'source_json_parse' and x.get('status') == 'failed' for x in diagnostics(captured.records)))

    async def test_asgi_completion_waits_for_last_body_handoff(self):
        headers_sent, release = asyncio.Event(), asyncio.Event()
        messages = []
        async def application(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            headers_sent.set()
            await release.wait()
            await send({'type': 'http.response.body', 'body': b'private-page', 'more_body': False})
        async def send(message):
            messages.append(message)
        scope = {'type': 'http', 'path': '/', 'method': 'GET',
                 'headers': [(b'x-request-id', b'body-barrier'), (b'x-dtos-diagnostics', b'1')]}
        request_logger = logging.getLogger('dtos.request')
        with self.assertLogs('dtos.attribution', level='INFO') as captured, patch.object(request_logger, 'info', wraps=request_logger.info) as request_events:
            task = asyncio.create_task(RequestObservabilityMiddleware(application)(scope, None, send))
            await headers_sent.wait()
            self.assertFalse(any(call.args[0] == 'request_complete' for call in request_events.call_args_list))
            self.assertFalse(any(x['boundary'] == 'response_body_handoff' for x in diagnostics(captured.records)))
            release.set()
            await task
        self.assertEqual(messages[0]['status'], 200)
        self.assertEqual(sum(call.args[0] == 'request_complete' for call in request_events.call_args_list), 1)
        self.assertTrue(any(x['boundary'] == 'response_body_handoff' for x in diagnostics(captured.records)))
        self.assertNotIn('private-page', json.dumps(diagnostics(captured.records)))

    async def test_expired_request_context_does_not_exhaust_future_maintenance_trace(self):
        proceed = asyncio.Event()
        async def background():
            await proceed.wait()
            with span('sleeper_sync', activate=True):
                pass
        with self.assertLogs('dtos.attribution', level='INFO') as captured:
            with request_trace('original-request'):
                task = asyncio.create_task(background())
            proceed.set()
            await task
        self.assertTrue(all(x.request_id.startswith('activity-') for x in captured.records))
        self.assertTrue(all(x['origin_request_id'] == 'original-request' for x in diagnostics(captured.records)))


class BoundAndPrivacyTests(unittest.TestCase):
    def test_text_log_mode_preserves_numeric_diagnostic_evidence(self):
        record = logging.LogRecord('dtos.attribution', logging.INFO, '', 1, 'diagnostic_boundary', (), None)
        record.request_id = 'known-trace'
        record.diagnostic = {'duration_ms': 7.92, 'body_complete': True}
        rendered = CorrelationFormatter('%(request_id)s %(message)s').format(record)
        self.assertIn('known-trace', rendered)
        self.assertIn('"duration_ms":7.92', rendered)
        self.assertIn('"body_complete":true', rendered)

    def test_public_trace_header_does_not_bypass_account_authentication_or_log_cookie(self):
        with tempfile.TemporaryDirectory() as directory:
            app = FastAPI()
            service = AccountService(AccountStore(Path(directory) / 'accounts.sqlite3'))
            app.add_middleware(AccountContextMiddleware, service=service, required=True)
            install_observability(app)
            @app.get('/')
            async def private():
                return {'private': True}
            with self.assertLogs('dtos.attribution', level='INFO') as captured:
                response = TestClient(app).get('/', follow_redirects=False, headers={
                    'X-DTOS-Diagnostics': '1', 'Cookie': 'dtos_session=do-not-log-cookie',
                })
            self.assertEqual(response.status_code, 303)
            self.assertTrue(response.headers['location'].startswith('/account/sign-in'))
            self.assertNotIn('do-not-log-cookie', json.dumps(diagnostics(captured.records)))

    def test_diagnostic_sink_failure_does_not_fail_the_observed_operation(self):
        with patch('src.platform.request_diagnostics.logger.info', side_effect=OSError):
            with request_trace('failed-log-sink', enabled=True) as trace:
                with span('home_render'):
                    supported_result = {'score': 0, 'state': 'available'}
        self.assertEqual(supported_result, {'score': 0, 'state': 'available'})
        self.assertEqual(trace.dropped, 2)

    def test_warm_buffer_event_and_queue_limits_are_explicit(self):
        trace = Trace('bounded')
        for _ in range(MAX_PENDING + 5):
            trace.emit({'name': 'test'})
        self.assertEqual(len(trace.pending), MAX_PENDING)
        self.assertEqual(trace.dropped, 5)
        with self.assertLogs('dtos.attribution', level='INFO') as captured:
            trace.activate()
            for _ in range(MAX_EVENTS + 5):
                trace.emit({'name': 'test'})
        self.assertEqual(len(captured.records), MAX_EVENTS)
        self.assertEqual(captured.records[-1].diagnostic['event_index'], MAX_EVENTS)
        queue = Queue(maxsize=2)
        handler = BoundedRequestQueueHandler(queue)
        for _ in range(3):
            handler.enqueue(logging.LogRecord('test', logging.INFO, '', 1, 'safe', (), None))
        self.assertEqual(queue.qsize(), 2)
        self.assertEqual(handler.dropped, 1)

    def test_process_samples_filter_zombies_before_cap_and_do_not_sum_pss(self):
        info = SimpleNamespace(rss=9, pss=5, uss=3)
        def child(pid, status):
            return SimpleNamespace(pid=pid, status=lambda: status,
                memory_info=lambda: info, memory_full_info=lambda: info)
        parent = child(1, 'running')
        parent.children = lambda **_: [child(i, 'zombie') for i in range(20, 60)] + [child(i, 'running') for i in range(2, 22)]
        with patch('src.platform.memory_attribution.psutil.Process', return_value=parent), \
                patch('src.platform.memory_attribution.memory_snapshot', return_value={'cgroup_current_bytes': 123}), \
                patch('pathlib.Path.read_text', side_effect=OSError):
            report = capture_memory(full=True, fois_pids={2})
        self.assertEqual(report['active_process_count'], 21)
        self.assertEqual(report['zombie_count'], 40)
        self.assertEqual(len(report['processes']), 16)
        self.assertEqual(report['processes'][1]['role'], 'fois_worker')
        self.assertIsNone(report['anonymous_bytes'])
        self.assertTrue(report['process_samples_are_sequential'])
        self.assertNotIn('total_pss', report)

    def test_sampler_limits_and_completed_boundary_draining(self):
        sampler = MemoryAttribution()
        trace = Trace('memory-bounds', enabled=True)
        with patch('threading.Thread'):
            handles = [sampler.begin(trace, 'sleeper_sync', i) for i in range(ACTIVITY_LIMIT + 2)]
        self.assertEqual(len(sampler.active), ACTIVITY_LIMIT)
        self.assertEqual(handles.count(None), 2)
        for identity in handles:
            if identity is not None:
                sampler.end(identity)
        self.assertLessEqual(len(sampler.pending), PENDING_LIMIT)
        with patch('src.platform.memory_attribution.capture_memory', return_value={'state': 'fixture'}), \
                self.assertLogs('dtos.attribution', level='INFO') as captured:
            sampler._run()
        self.assertFalse(sampler.active)
        self.assertFalse(sampler.pending)
        self.assertIsNone(sampler.thread)
        self.assertEqual(len(captured.records), 1)

    def test_sampler_never_owns_runtime_or_source_graphs(self):
        sampler = MemoryAttribution()
        manager = LeagueRuntimeManager()
        manager.attach_default('100', {'data': {}}, warm=False)
        snapshot = manager.diagnostic_residency()
        self.assertNotIn('100', json.dumps(snapshot))
        self.assertNotIn('data', snapshot['runtimes'][0])
        reference = weakref.ref(manager)
        sampler.register_runtime_manager(manager)
        del manager
        gc.collect()
        self.assertIsNone(reference())

    def test_thread_start_failure_cannot_break_source_work(self):
        sampler = MemoryAttribution()
        with patch('threading.Thread.start', side_effect=RuntimeError):
            identity = sampler.begin(Trace('failed-sampler'), 'sleeper_sync', 1)
        self.assertIsNone(identity)
        self.assertFalse(sampler.active)
        self.assertFalse(sampler.pending)
