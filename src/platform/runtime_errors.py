"""Public runtime failures and bounded, message-free operational diagnostics."""
from __future__ import annotations

from collections import deque
import logging
from pathlib import PurePath
import traceback
from typing import Any

from starlette.responses import JSONResponse


PRIVATE_HEADERS = {"Cache-Control": "no-store, private", "Vary": "Cookie, X-DTOS-Inspection-Auth"}


def runtime_error_payload(status: int) -> dict[str, str]:
    if status == 422:
        return {"status": "invalid", "code": "league_runtime_not_found",
                "reason": "This league could not be opened. Choose a connected league or try again."}
    if status != 503:
        raise ValueError("Unsupported runtime response status")
    return {"status": "failed", "code": "league_runtime_unavailable",
            "reason": "League data is temporarily unavailable. Try again or choose another connected league."}


def runtime_error_response(status: int) -> JSONResponse:
    return JSONResponse(runtime_error_payload(status), status_code=status, headers=PRIVATE_HEADERS)


def log_runtime_failure(exc: Exception, *, operation: str, status: int) -> None:
    # Neither str/repr(exc), chained messages, locals, source lines, request
    # headers/query nor source/league identifiers belong in request logs.
    from src.platform.observability import request_id_context

    frames = deque(traceback.walk_tb(exc.__traceback__), maxlen=6)
    logging.getLogger("dtos.request").warning(
        "league_runtime_failure",
        extra={"event": "league_runtime_failure", "request_id": request_id_context.get(),
               "status_code": status, "diagnostic": {
                   "operation": operation, "exception_type": type(exc).__name__,
                   "frames": [{"file": PurePath(frame.f_code.co_filename).name,
                               "function": frame.f_code.co_name, "line": line}
                              for frame, line in frames]}},
    )


def customer_runtime_health(payload: dict[str, Any]) -> dict[str, Any]:
    """Preserve health facts without reflecting a cached acquisition exception."""
    result = dict(payload)
    if result.get("last_error") is not None:
        result["last_error"] = runtime_error_payload(503)["reason"] if result["last_error"] else None
    return result
