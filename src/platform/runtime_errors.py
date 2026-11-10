"""Public runtime failures and bounded, message-free operational diagnostics."""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import logging
from pathlib import PurePath
import traceback
from typing import Any

from starlette.responses import JSONResponse


PRIVATE_HEADERS = {"Cache-Control": "no-store, private", "Vary": "Cookie, X-DTOS-Inspection-Auth"}


def runtime_error_payload(status: int, *, deferred: bool = False) -> dict[str, str]:
    if deferred and status == 503:
        return {"status": "deferred", "code": "league_preparation_waiting",
                "reason": "League preparation is waiting for capacity. Another preparation task is active or safe memory headroom is not available. Try this page again in a minute; no Trade search has run."}
    if status == 422:
        return {"status": "invalid", "code": "league_runtime_not_found",
                "reason": "This league could not be opened. Choose a connected league or try again."}
    if status != 503:
        raise ValueError("Unsupported runtime response status")
    return {"status": "failed", "code": "league_runtime_unavailable",
            "reason": "League data is temporarily unavailable. Try again or choose another connected league."}


def runtime_error_response(status: int, *, deferred: bool = False) -> JSONResponse:
    headers = {**PRIVATE_HEADERS, **({"Retry-After": "60"} if deferred else {})}
    return JSONResponse(runtime_error_payload(status, deferred=deferred), status_code=status, headers=headers)


def _log_failure(exc: Exception, *, event: str, operation: str, status: int | None = None) -> None:
    # Neither str/repr(exc), chained messages, locals, source lines, request
    # headers/query nor source/league identifiers belong in request logs.
    from src.platform.observability import request_id_context

    frames = deque(traceback.walk_tb(exc.__traceback__), maxlen=6)
    extra = {"event": event, "request_id": request_id_context.get(), "diagnostic": {
        "operation": operation, "exception_type": type(exc).__name__,
        "frames": [{"file": PurePath(frame.f_code.co_filename).name,
                    "function": frame.f_code.co_name, "line": line}
                   for frame, line in frames]}}
    if status is not None:
        extra["status_code"] = status
    logging.getLogger("dtos.request").warning(event, extra=extra)


def log_runtime_failure(exc: Exception, *, operation: str, status: int) -> None:
    _log_failure(exc, event="league_runtime_failure", operation=operation, status=status)


def log_sync_failure(exc: Exception, *, operation: str) -> None:
    """Keep bounded operational locations and correlation without credentials."""
    _log_failure(exc, event="synchronization_failure", operation=operation)


def log_restoration_admission(*, file_bytes: Any, memory: Any, plan: Any,
                              recovery: Any = None) -> None:
    """One best-effort bounded record of existing guard inputs, never a guard.

    No new measurement, source read, path, identifier or exception message.
    Missing records (including a full logging queue) establish nothing about
    admission or cleanup. Only the caller's unchanged predicate grants work.
    """
    from src.platform.observability import request_id_context

    sample = memory if isinstance(memory, Mapping) else {}
    decision = plan if isinstance(plan, Mapping) else {}
    reclaimed = recovery if isinstance(recovery, Mapping) else {}

    def number(value):
        return value if type(value) is int and value >= 0 else None

    def boolean(value):
        return value if type(value) is bool else None

    reason = decision.get('reason')
    diagnostic = {
        'schema': 'cache-restoration-admission-v1',
        'scope': 'existing_guard_inputs_not_atomic',
        'file_bytes': number(file_bytes),
        'current_bytes': number(sample.get('cgroup_current_bytes')),
        'limit_bytes': number(sample.get('cgroup_limit_bytes')),
        'anonymous_bytes': number(sample.get('cgroup_anonymous_bytes')),
        'inactive_file_bytes': number(sample.get('cgroup_inactive_file_bytes')),
        'reason': reason if isinstance(reason, str) and reason in {
            'sufficient_headroom', 'insufficient_headroom', 'unknown_file_size',
            'unknown_reservation', 'unknown_memory',
        } else None,
        'would_admit': boolean(decision.get('would_admit')),
        'headroom_bytes': decision.get('headroom_bytes') if type(decision.get('headroom_bytes')) is int else None,
        **{key: number(decision.get(key)) for key in (
            'effective_limit_bytes', 'working_bytes',
            'safety_bytes', 'fois_working_bytes', 'fois_safety_bytes', 'required_bytes',
        )},
        'cleanup': {
            'attempted': reclaimed.get('attempted') is True,
            **{key: number(reclaimed.get(key)) for key in (
                'before_bytes', 'after_bytes', 'expired_entries',
            )},
            **{key: boolean(reclaimed.get(key)) for key in (
                'idle_worker_retired', 'allocator_trimmed', 'cleanup_unavailable',
            )},
        },
    }
    try:
        logging.getLogger('dtos.request').info('cache_restoration_admission', extra={
            'event': 'cache_restoration_admission', 'request_id': request_id_context.get(),
            'diagnostic': diagnostic,
        })
    except (OSError, ValueError, TypeError, RuntimeError):
        # Optional telemetry must not turn a capacity deferral into a source
        # failure/fallback. The caller still executes its exact existing guard.
        pass


def customer_runtime_health(payload: dict[str, Any]) -> dict[str, Any]:
    """Preserve health facts without reflecting a cached acquisition exception."""
    result = dict(payload)
    if result.get("last_error") is not None:
        result["last_error"] = runtime_error_payload(503)["reason"] if result["last_error"] else None
    return result
