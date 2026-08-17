"""Structured logging, request correlation, and runtime health metrics."""
from __future__ import annotations

import json
import logging
import os
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request

from config import LOG_FORMAT, LOG_LEVEL
from src.platform.request_capacity import serving_request

request_id_context: ContextVar[str] = ContextVar("dtos_request_id", default="system")


class StructuredFormatter(logging.Formatter):
    """Emit stable JSON records suitable for local logs and hosted collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key in ("event", "duration_ms", "provider", "cache", "status_code", "method", "path"):
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
        return super().format(record)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    formatter: logging.Formatter = StructuredFormatter() if LOG_FORMAT == "json" else CorrelationFormatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
    for handler in root.handlers:
        handler.setFormatter(formatter)


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
    logger = logging.getLogger("dtos.request")

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        with serving_request():
            request_id = request.headers.get("X-Request-ID") or uuid4().hex
            token = request_id_context.set(request_id)
            started = perf_counter()
            started_at = datetime.now(timezone.utc).isoformat()
            status_code = 500
            trace_request = request.headers.get("X-DTOS-Diagnostics") == "1" or request.url.path in {
                "/", "/market", "/health/live", "/api/market/health",
            }
            if trace_request:
                logger.info(
                    "request_accepted",
                    extra={"event": "request_accepted", "method": request.method,
                           "path": request.url.path, "request_id": request_id},
                )
            try:
                if trace_request:
                    logger.info(
                        "handler_scheduled",
                        extra={"event": "handler_scheduled", "method": request.method,
                               "path": request.url.path, "request_id": request_id},
                    )
                response = await call_next(request)
                status_code = response.status_code
                response.headers["X-Request-ID"] = request_id
                if request.headers.get("X-DTOS-Diagnostics") == "1":
                    duration_ms = round((perf_counter() - started) * 1000, 3)
                    response.headers["X-DTOS-Request-Start"] = started_at
                    response.headers["X-DTOS-Route-Duration"] = str(duration_ms)
                    response.headers["X-DTOS-Request-Duration"] = str(duration_ms)
                    response.headers["X-DTOS-Process-Uptime"] = str(
                        runtime_metrics.uptime_seconds()
                    )
                return response
            finally:
                duration_ms = round((perf_counter() - started) * 1000, 3)
                runtime_metrics.record(duration_ms, status_code)
                logger.info(
                    "request_complete",
                    extra={"event": "request_complete", "duration_ms": duration_ms, "status_code": status_code, "method": request.method, "path": request.url.path, "request_id": request_id},
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
