"""Validation-only admission and publication barrier; never imported by DTOS."""
from __future__ import annotations

import asyncio
import threading
import time
from contextlib import asynccontextmanager


class ReplacementWindow:
    def __init__(self, timeout: float = 60, preparation_lock=None) -> None:
        self.timeout = timeout
        self._preparation_lock = preparation_lock
        self._owns_preparation_lock = False
        self._released = threading.Event()
        self._lock = threading.Lock()
        self._active = False
        self.events: list[dict[str, object]] = []

    def record(self, event: str) -> None:
        with self._lock:
            self.events.append({"event": event, "timestamp_ns": time.time_ns()})
            del self.events[:-32]

    @asynccontextmanager
    async def admitted(self, coordinator):
        with self._lock:
            if self._active:
                raise RuntimeError("Replacement validation already active")
            self._active = True
            self.events.clear()
            self._released.clear()
        coordinator.reserve_market_critical("Validation material replacement probe")
        self.record("admission_requested")
        try:
            deadline = time.monotonic() + self.timeout
            if self._preparation_lock is not None:
                await asyncio.wait_for(self._preparation_lock.acquire(), self.timeout)
                self._owns_preparation_lock = True
                self.record("preparation_lock_acquired")
            while not coordinator.market_build_allowed():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Replacement validation admission timed out")
                await asyncio.sleep(.01)
            self.record("admitted")
            yield
        except BaseException:
            self.release()
            raise
        finally:
            coordinator.release_market_critical()

    def before_publication(self) -> None:
        with self._lock:
            active = self._active
        if not active:
            return
        self.record("publication_waiting")
        if not self._released.wait(self.timeout):
            self.record("publication_timeout")
            raise TimeoutError("Replacement validation publication was not released")
        self.record("publication_released")

    def release(self) -> list[dict[str, object]]:
        self.record("probe_complete")
        self._released.set()
        if self._owns_preparation_lock:
            self._owns_preparation_lock = False
            self._preparation_lock.release()
        with self._lock:
            self._active = False
            return list(self.events)
