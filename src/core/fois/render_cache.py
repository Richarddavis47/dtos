"""Bounded disposable rendered-response cache for canonical FOIS views."""
from __future__ import annotations

import threading
from collections import OrderedDict
from time import perf_counter
from typing import Callable, Hashable


class FOISRenderCache:
    """Generation-keyed LRU with per-key single-flight publication."""

    def __init__(self, *, max_entries: int = 8, max_bytes: int = 1_048_576) -> None:
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
        """Return one complete representation; never expose partial builds."""
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
        with self._lock:
            return {
                "fois_render_cache_hits": self._hits,
                "fois_render_cache_misses": self._misses,
                "fois_render_cache_entries": len(self._entries),
                "fois_render_cache_bytes": self._bytes,
                "fois_render_cache_generation": self._generation,
                "fois_render_cache_evictions": self._evictions,
                "fois_render_singleflight_waiters": self._waiters,
                "fois_render_last_build_ms": self._last_build_ms,
                "fois_render_cache_max_entries": self.max_entries,
                "fois_render_cache_max_bytes": self.max_bytes,
            }
