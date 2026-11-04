"""Bounded, payload-free clocks for cold navigation and optional heavy work.

Records go to the existing hosted log sink, never to a database or local archive.
Request IDs identify correlation, span IDs identify nesting, and monotonic clocks
measure elapsed time. Thread CPU is explicitly the calling thread's CPU only.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import hashlib
import inspect
import logging
import threading
from time import perf_counter, thread_time
from uuid import uuid4
import asyncio

import httpx

logger = logging.getLogger('dtos.attribution')
MAX_EVENTS = 512
MAX_PENDING = 32
NAMES = frozenset({
    'request', 'account_context', 'runtime_acquire', 'runtime_hydration',
    'runtime_publication', 'home_freshness', 'home_render', 'sleeper_sync',
    'source_request', 'source_json_parse', 'history_prepare', 'projection_publish',
    'production_prepare', 'valuation_prepare', 'cache_size', 'cache_admission',
    'cache_encode_write', 'cache_fsync', 'cache_replace', 'cache_lifecycle_wait', 'fois_generation',
    'fois_copy', 'fois_submission', 'fois_publication', 'fois_coordination',
    'fois_worker_retirement', 'runtime_eviction',
    'lifecycle_phase', 'market_source_prepare', 'market_identity_parse',
    'team_strength_prepare', 'checkpoint_prepare', 'fois_profile', 'fois_profile_context',
    'fois_profile_lookup', 'fois_profile_validation', 'fois_profile_history',
    'fois_profile_aggregation', 'fois_profile_render', 'fois_profile_activity',
    'fois_profile_behavior', 'fois_profile_rankings', 'fois_history_fetch',
    'fois_history_decode', 'fois_history_current', 'fois_history_response',
})
_TRACE: ContextVar[Trace | None] = ContextVar('dtos_diagnostic_trace', default=None)
_SPAN: ContextVar[int | None] = ContextVar('dtos_diagnostic_span', default=None)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def scope_identity(value: str) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


class Trace:
    def __init__(self, request_id: str, *, enabled: bool = False):
        self.request_id = request_id
        self.started = perf_counter()
        self.enabled = enabled
        self.events = 0
        self.dropped = 0
        self.sequence = 0
        self.closed = False
        self.origin_request_id = None
        self.pending: deque[dict] = deque(maxlen=MAX_PENDING)
        self.lock = threading.RLock()

    def emit(self, record: dict) -> None:
        with self.lock:
            if not self.enabled:
                if len(self.pending) == MAX_PENDING:
                    self.dropped += 1
                self.pending.append(record)
                return
            if self.events >= MAX_EVENTS:
                self.dropped += 1
                return
            self.events += 1
            try:
                logger.info('diagnostic_boundary', extra={
                    'event': 'diagnostic_boundary', 'request_id': self.request_id,
                    'diagnostic': {'schema': 'request-attribution-v1',
                                   'event_index': self.events, 'event_limit': MAX_EVENTS,
                                   'dropped_so_far': self.dropped,
                                   'origin_request_id': self.origin_request_id, **record},
                })
            except (OSError, RuntimeError, ValueError):
                # A telemetry/sink failure must not invalidate canonical facts.
                self.dropped += 1

    def activate(self) -> None:
        with self.lock:
            if not self.enabled:
                self.enabled = True
                pending = tuple(self.pending)
                self.pending.clear()
                for record in pending:
                    self.emit(record)

    def next_id(self) -> int:
        with self.lock:
            self.sequence += 1
            return self.sequence


class Span:
    def __init__(self, trace: Trace, name: str, **metadata):
        self.trace, self.name = trace, name
        self.id = trace.next_id()
        self.parent = _SPAN.get()
        self.started, self.cpu = perf_counter(), thread_time()
        self.finished = False
        self.record('started', **metadata)

    def record(self, boundary: str, **numeric) -> None:
        now = perf_counter()
        self.trace.emit({
            'name': self.name, 'span_id': self.id, 'parent_span_id': self.parent,
            'boundary': boundary, 'timestamp': utcnow(),
            'elapsed_from_trace_ms': round((now - self.trace.started) * 1000, 3),
            'duration_ms': round((now - self.started) * 1000, 3),
            **numeric,
        })

    def finish(self, status: str = 'complete', **numeric) -> None:
        if not self.finished:
            self.finished = True
            self.record('finished', status=status,
                        calling_thread_cpu_ms=round((thread_time() - self.cpu) * 1000, 3),
                        **numeric)


@contextmanager
def request_trace(request_id: str, *, enabled: bool = False):
    trace = Trace(request_id, enabled=enabled)
    token = _TRACE.set(trace)
    parent_token = _SPAN.set(None)
    try:
        yield trace
    finally:
        trace.closed = True
        _SPAN.reset(parent_token)
        _TRACE.reset(token)


@contextmanager
def span(name: str, *, activate: bool = False, memory: bool = False):
    if name not in NAMES:
        raise ValueError('Unsupported diagnostic span')
    trace = _TRACE.get()
    owned = None
    if activate and (trace is None or trace.closed):
        origin = trace.request_id if trace is not None else None
        trace = Trace('activity-' + uuid4().hex, enabled=True)
        trace.origin_request_id = origin
        owned = _TRACE.set(trace)
    if trace is None:
        yield None
        return
    if activate:
        trace.activate()
    current = Span(trace, name)
    token = _SPAN.set(current.id)
    activity = None
    if memory:
        from src.platform.memory_attribution import memory_attribution
        activity = memory_attribution.begin(trace, name, current.id)
    try:
        yield current
    except BaseException as exc:
        current.finish('cancelled' if isinstance(exc, asyncio.CancelledError) else 'failed')
        raise
    finally:
        current.finish()
        if activity is not None:
            from src.platform.memory_attribution import memory_attribution
            memory_attribution.end(activity)
        _SPAN.reset(token)
        if owned is not None:
            trace.closed = True
            _TRACE.reset(owned)


def diagnosed(name: str, *, activate: bool = False, memory: bool = False):
    """Observe existing boundaries without changing their ownership or retries."""
    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def asynchronous(*args, **kwargs):
                with span(name, activate=activate, memory=memory):
                    return await function(*args, **kwargs)
            return asynchronous
        @wraps(function)
        def synchronous(*args, **kwargs):
            with span(name, activate=activate, memory=memory):
                return function(*args, **kwargs)
        return synchronous
    return decorate


def activate_current_trace() -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace.activate()


def sync_checkpoint(name: str, duration_ms: float, league_scope: str) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace.emit({'name': 'sync_checkpoint', 'boundary': name, 'timestamp': utcnow(),
                    'league_scope': league_scope,
                    'parent_span_id': _SPAN.get(), 'duration_ms': duration_ms,
                    'elapsed_from_trace_ms': round((perf_counter() - trace.started) * 1000, 3)})


class _TransferStream(httpx.AsyncByteStream):
    def __init__(self, stream, clock):
        self.stream, self.clock = stream, clock

    async def __aiter__(self):
        complete, size = False, 0
        try:
            async for chunk in self.stream:
                size += len(chunk)
                yield chunk
            complete = True
        finally:
            self.clock.finish('complete' if complete else 'incomplete',
                              body_complete=complete, transferred_bytes=size)

    async def aclose(self):
        await self.stream.aclose()


class _TransportTrace:
    """Observe actual transport headers before HTTPX's response log/hook work."""

    def __init__(self, clock, previous):
        self.clock = clock
        # HTTPX carries extensions through redirects. Do not chain old clocks.
        self.previous = previous.previous if isinstance(previous, _TransportTrace) else previous

    async def __call__(self, event_name, info):
        if event_name in {'http11.receive_response_headers.complete', 'http2.receive_response_headers.complete'}:
            self.clock.record('transport_headers_received')
        if self.previous is not None:
            result = self.previous(event_name, info)
            if inspect.isawaitable(result):
                await result


async def _source_started(request: httpx.Request) -> None:
    trace = _TRACE.get()
    if trace is not None:
        parts = request.url.path.strip('/').split('/')
        if request.url.host in {'api.sleeper.app', 'api.sleeper.com'} or '/league/' in request.url.path:
            category = next((key for key in ('projections', 'transactions', 'matchups', 'players',
                'drafts', 'traded_picks', 'rosters', 'users', 'league', 'state') if key in parts), 'other_sleeper')
        else:
            category = 'other_provider'
        clock = Span(trace, 'source_request', source_class=category)
        request.extensions['dtos_attribution'] = clock
        request.extensions['trace'] = _TransportTrace(clock, request.extensions.get('trace'))


async def _source_headers(response: httpx.Response) -> None:
    clock = response.request.extensions.pop('dtos_attribution', None)
    if clock is None:
        return
    response.extensions['dtos_source_span_id'] = clock.id
    clock.record('headers_received', status_code=response.status_code)
    if response.is_stream_consumed:
        clock.finish(body_complete=True, transferred_bytes=len(response.content))
    else:
        response.stream = _TransferStream(response.stream, clock)


def source_hooks() -> dict:
    """Observe HTTPX's existing transfer; do not refetch, buffer or retain bodies.

    Transfer duration includes HTTP content decoding performed by HTTPX between
    stream yields. JSON decoding/parsing is measured separately, not called pure
    network time. No URL, header, query, body or account identity is recorded.
    """
    return {'request': [_source_started], 'response': [_source_headers]}


def decode_json(response):
    with span('source_json_parse') as clock:
        result = response.json()
        if clock is not None:
            extensions = getattr(response, 'extensions', None)
            related = extensions.get('dtos_source_span_id') if isinstance(extensions, dict) else None
            clock.finish(related_source_span_id=related)
        return result
