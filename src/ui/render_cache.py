"""Bounded disposable cache for deterministic rendered page responses."""
from __future__ import annotations

import threading
from collections import OrderedDict
from time import perf_counter
from typing import Callable, Hashable


class GenerationRenderCache:
    """Generation-keyed byte cache with per-key single-flight publication."""

    def __init__(
        self, name: str, *, max_entries: int = 12, max_bytes: int = 2_097_152,
    ) -> None:
        self.name = name
        self.max_entries = max(1, int(max_entries))
        self.max_bytes = max(1, int(max_bytes))
        self._lock = threading.RLock()
        self._entries: OrderedDict[Hashable, bytes] = OrderedDict()
        self._building: dict[Hashable, threading.Event] = {}
        self._bytes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._waiters = 0
        self._last_build_ms: float | None = None
        self._generation: str | None = None

    def get_or_build(
        self, key: Hashable, generation: str, builder: Callable[[], bytes],
    ) -> bytes:
        """Return one complete representation without exposing partial builds."""
        while True:
            with self._lock:
                cached = self._entries.get(key)
                if cached is not None:
                    self._entries.move_to_end(key)
                    self._hits += 1
                    return cached
                event = self._building.get(key)
                if event is None:
                    event = threading.Event()
                    self._building[key] = event
                    self._misses += 1
                    break
                self._waiters += 1
            event.wait()

        started = perf_counter()
        try:
            value = bytes(builder())
            if len(value) > self.max_bytes:
                return value
            with self._lock:
                self._entries[key] = value
                self._entries.move_to_end(key)
                self._bytes += len(value)
                self._generation = generation
                while (
                    len(self._entries) > self.max_entries
                    or self._bytes > self.max_bytes
                ):
                    _old_key, old_value = self._entries.popitem(last=False)
                    self._bytes -= len(old_value)
                    self._evictions += 1
            return value
        finally:
            with self._lock:
                self._last_build_ms = round((perf_counter() - started) * 1000, 3)
                completed = self._building.pop(key, None)
                if completed is not None:
                    completed.set()

    def health(self) -> dict[str, object]:
        prefix = f"{self.name}_render"
        with self._lock:
            return {
                f"{prefix}_cache_hits": self._hits,
                f"{prefix}_cache_misses": self._misses,
                f"{prefix}_cache_entries": len(self._entries),
                f"{prefix}_cache_bytes": self._bytes,
                f"{prefix}_cache_generation": self._generation,
                f"{prefix}_cache_evictions": self._evictions,
                f"{prefix}_singleflight_waiters": self._waiters,
                f"{prefix}_last_build_ms": self._last_build_ms,
                f"{prefix}_cache_max_entries": self.max_entries,
                f"{prefix}_cache_max_bytes": self.max_bytes,
            }
