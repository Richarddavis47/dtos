"""Structured logging, request correlation, and runtime health metrics."""
from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import re
from contextvars import ContextVar
from logging.handlers import QueueHandler, QueueListener
from queue import Full, Queue
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders

from config import LOG_FORMAT, LOG_LEVEL
from src.platform.request_capacity import serving_request

request_id_context: ContextVar[str] = ContextVar("dtos_request_id", default="system")

_request_log_queue: Queue[logging.LogRecord] = Queue(maxsize=512)
_request_log_listener: QueueListener | None = None


class BoundedRequestQueueHandler(QueueHandler):
    """A stalled sink drops bounded telemetry instead of blocking navigation."""

    dropped = 0

    def enqueue(self, record):
        if hasattr(record, 'diagnostic'):
            record.diagnostic = {**record.diagnostic, 'queue_dropped_record_count': self.dropped}
        try:
            self.queue.put_nowait(record)
        except Full:
            self.dropped += 1


def _stop_request_log_listener() -> None:
    if _request_log_listener is not None:
        try:
            _request_log_listener.stop()
        except Full:
            # A full/stalled best-effort log sink cannot hold process shutdown.
            pass


class StructuredFormatter(logging.Formatter):
    """Emit stable JSON records suitable for local logs and hosted collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key in ("event", "duration_ms", "provider", "cache", "status_code", "method", "path", "diagnostic"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


class CorrelationFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_context.get()
        rendered = super().format(record)
        if hasattr(record, 'diagnostic'):
            rendered += ' ' + json.dumps(record.diagnostic, default=str, separators=(',', ':'))
        return rendered


def configure_logging() -> None:
    global _request_log_listener
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    formatter: logging.Formatter = StructuredFormatter() if LOG_FORMAT == "json" else CorrelationFormatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
    for handler in root.handlers:
        handler.setFormatter(formatter)
    request_logger = logging.getLogger("dtos.request")
    if _request_log_listener is None:
        # Request traces must never inherit filesystem/stdout stalls from the
        # application log sink. The listener retains the same handlers and
        # formatter while moving the potentially blocking write off the event
        # loop thread.
        targets = tuple(root.handlers)
        _request_log_listener = QueueListener(
            _request_log_queue, *targets, respect_handler_level=True,
        )
        _request_log_listener.start()
        atexit.register(_stop_request_log_listener)
        request_logger.handlers[:] = [BoundedRequestQueueHandler(_request_log_queue)]
        request_logger.propagate = False
        attribution_logger = logging.getLogger('dtos.attribution')
        attribution_logger.handlers[:] = list(request_logger.handlers)
        attribution_logger.propagate = False


@dataclass
class RuntimeMetrics:
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_monotonic: float = field(default_factory=monotonic)
    startup_ms: float | None = None
    requests: int = 0
    errors: int = 0
    total_request_ms: float = 0.0
    ready: bool = False
    readiness_reason: str = "Application startup has not completed."
    ready_at: str | None = None
    background_tasks: dict[str, str] = field(default_factory=dict)
    event_loop_lag_samples_ms: list[float] = field(default_factory=list)
    event_loop_current_lag_ms: float = 0.0

    def record(self, duration_ms: float, status_code: int) -> None:
        self.requests += 1
        self.total_request_ms += duration_ms
        if status_code >= 500:
            self.errors += 1

    def health(self) -> dict[str, Any]:
        try:
            import resource

            memory_kb: int | None = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except (ImportError, OSError):
            memory_kb = None
        lag = sorted(self.event_loop_lag_samples_ms)
        def percentile(fraction: float) -> float:
            if not lag:
                return 0.0
            return lag[min(len(lag) - 1, int((len(lag) - 1) * fraction))]
        return {
            "started_at": self.started_at,
            "uptime_seconds": round(monotonic() - self.started_monotonic, 2),
            "startup_ms": self.startup_ms,
            "requests": self.requests,
            "errors": self.errors,
            "average_request_ms": round(self.total_request_ms / self.requests, 3) if self.requests else 0.0,
            "memory_high_water_kb": memory_kb,
            "ready": self.ready,
            "readiness_reason": self.readiness_reason,
            "ready_at": self.ready_at,
            "background_tasks": dict(self.background_tasks),
            "event_loop_lag": {
                "current_ms": self.event_loop_current_lag_ms,
                "p50_ms": percentile(0.50), "p95_ms": percentile(0.95),
                "max_ms": max(lag, default=0.0), "sample_count": len(lag),
            },
        }

    def mark_ready(self, reason: str) -> None:
        self.ready = True
        self.readiness_reason = reason
        self.ready_at = datetime.now(timezone.utc).isoformat()

    def mark_not_ready(self, reason: str) -> None:
        self.ready = False
        self.readiness_reason = reason
        self.ready_at = None

    def mark_background(self, name: str, status: str) -> None:
        self.background_tasks[name] = status

    def uptime_seconds(self) -> float:
        return round(monotonic() - self.started_monotonic, 3)

    def record_event_loop_lag(self, lag_ms: float) -> None:
        self.event_loop_current_lag_ms = round(max(0.0, lag_ms), 3)
        self.event_loop_lag_samples_ms.append(self.event_loop_current_lag_ms)
        del self.event_loop_lag_samples_ms[:-256]


runtime_metrics = RuntimeMetrics()


def install_observability(app: FastAPI) -> None:
    configure_logging()
    app.add_middleware(RequestObservabilityMiddleware)


class RequestObservabilityMiddleware:
    """Observe the final ASGI body handoff, rather than only response headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            return await self.app(scope, receive, send)
        from contextlib import nullcontext
        from src.platform.request_diagnostics import request_trace, span

        logger = logging.getLogger('dtos.request')
        headers = Headers(scope=scope)
        supplied = headers.get('X-Request-ID') or ''
        # Never copy arbitrary client text or an oversized/private value to logs.
        request_id = supplied if re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', supplied) else uuid4().hex
        path, method = scope.get('path', '/'), scope.get('method', 'GET')
        with serving_request():
            token = request_id_context.set(request_id)
            started = perf_counter()
            started_at = datetime.now(timezone.utc).isoformat()
            status_code = 500
            diagnostic_headers = headers.get('X-DTOS-Diagnostics') == '1'
            trace_request = diagnostic_headers or path in {
                "/", "/market", "/health/live", "/api/market/health",
            }
            if trace_request:
                logger.info(
                    "request_accepted",
                    extra={"event": "request_accepted", "method": method,
                           "path": path, "request_id": request_id},
                )
            tracing = request_trace(request_id, enabled=diagnostic_headers) if not path.startswith(('/health', '/static/')) else nullcontext(None)
            try:
                if trace_request:
                    logger.info(
                        "handler_scheduled",
                        extra={"event": "handler_scheduled", "method": method,
                               "path": path, "request_id": request_id},
                    )
                with tracing as trace, span('request') as request_span:
                    async def observe_send(message):
                        nonlocal status_code
                        if message.get('type') == 'http.response.start':
                            status_code = message['status']
                            output = MutableHeaders(scope=message)
                            output['X-Request-ID'] = request_id
                            if diagnostic_headers:
                                duration = str(round((perf_counter() - started) * 1000, 3))
                                output['X-DTOS-Request-Start'] = started_at
                                output['X-DTOS-Route-Duration'] = duration
                                output['X-DTOS-Request-Duration'] = duration
                                output['X-DTOS-Process-Uptime'] = str(runtime_metrics.uptime_seconds())
                            if request_span is not None:
                                request_span.record('response_headers', status_code=status_code)
                        await send(message)
                        if message.get('type') == 'http.response.body' and not message.get('more_body', False) and request_span is not None:
                            request_span.record('response_body_handoff', status_code=status_code)
                    await self.app(scope, receive, observe_send)
                    if request_span is not None:
                        request_span.finish(dropped_diagnostic_events=trace.dropped)
            finally:
                duration_ms = round((perf_counter() - started) * 1000, 3)
                runtime_metrics.record(duration_ms, status_code)
                logger.info(
                    "request_complete",
                    extra={"event": "request_complete", "duration_ms": duration_ms, "status_code": status_code, "method": method, "path": path, "request_id": request_id},
                )
                request_id_context.reset(token)


async def monitor_event_loop_lag(interval_seconds: float = 0.1) -> None:
    """Retain a bounded scheduling-lag window for production diagnostics."""
    interval = max(0.05, float(interval_seconds))
    expected = monotonic() + interval
    while True:
        await asyncio.sleep(interval)
        now = monotonic()
        runtime_metrics.record_event_loop_lag((now - expected) * 1000)
        expected = now + interval


def mark_startup_complete(started: float) -> None:
    runtime_metrics.startup_ms = round((perf_counter() - started) * 1000, 3)


def environment_summary() -> dict[str, str]:
    """Return non-secret operational mode settings for health reporting."""
    return {"log_format": LOG_FORMAT, "log_level": LOG_LEVEL, "deployment": os.getenv("RENDER_SERVICE_NAME", "local")}
