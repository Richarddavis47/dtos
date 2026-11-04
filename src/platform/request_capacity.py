"""Process-local request priority signal for best-effort background workers."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_condition = threading.Condition()
_active_requests = 0


@contextmanager
def serving_request() -> Iterator[None]:
    """Mark one accepted request active until its response is constructed."""
    global _active_requests
    with _condition:
        _active_requests += 1
        _condition.notify_all()
    try:
        yield
    finally:
        with _condition:
            _active_requests = max(0, _active_requests - 1)
            _condition.notify_all()


def request_active() -> bool:
    """Return bounded process-local state without request-path I/O."""
    with _condition:
        return _active_requests > 0


def wait_for_request_idle(timeout: float) -> bool:
    """Wait at most ``timeout`` seconds for accepted requests to finish."""
    with _condition:
        if _active_requests == 0:
            return True
        _condition.wait_for(lambda: _active_requests == 0, timeout=max(0.0, timeout))
        return _active_requests == 0
