"""Structured logging, request correlation, and runtime health metrics."""
from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request

from config import LOG_FORMAT, LOG_LEVEL

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
        return {
            "started_at": self.started_at,
            "uptime_seconds": round(monotonic() - self.started_monotonic, 2),
            "startup_ms": self.startup_ms,
            "requests": self.requests,
            "errors": self.errors,
            "average_request_ms": round(self.total_request_ms / self.requests, 3) if self.requests else 0.0,
            "memory_high_water_kb": memory_kb,
        }


runtime_metrics = RuntimeMetrics()


def install_observability(app: FastAPI) -> None:
    configure_logging()
    logger = logging.getLogger("dtos.request")

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = request_id_context.set(request_id)
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = round((perf_counter() - started) * 1000, 3)
            runtime_metrics.record(duration_ms, status_code)
            logger.info(
                "request_complete",
                extra={"event": "request_complete", "duration_ms": duration_ms, "status_code": status_code, "method": request.method, "path": request.url.path, "request_id": request_id},
            )
            request_id_context.reset(token)


def mark_startup_complete(started: float) -> None:
    runtime_metrics.startup_ms = round((perf_counter() - started) * 1000, 3)


def environment_summary() -> dict[str, str]:
    """Return non-secret operational mode settings for health reporting."""
    return {"log_format": LOG_FORMAT, "log_level": LOG_LEVEL, "deployment": os.getenv("RENDER_SERVICE_NAME", "local")}
