"""Public runtime failures and bounded, message-free operational diagnostics."""
from __future__ import annotations

from collections import deque
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


def customer_runtime_health(payload: dict[str, Any]) -> dict[str, Any]:
    """Preserve health facts without reflecting a cached acquisition exception."""
    result = dict(payload)
    if result.get("last_error") is not None:
        result["last_error"] = runtime_error_payload(503)["reason"] if result["last_error"] else None
    return result
