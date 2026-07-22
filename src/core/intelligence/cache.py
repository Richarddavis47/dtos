"""Thread-safe TTL cache with fallback-safe health and invalidation."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Callable

from config import INTELLIGENCE_CACHE_TTL


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class IntelligenceCache:
    def __init__(self, default_ttl: float = 60.0) -> None:
        self.default_ttl = default_ttl
        self._entries: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self.hits = 0
        self.misses = 0
        self.invalidations = 0

    def get_or_create(self, key: str, factory: Callable[[], Any], ttl: float | None = None) -> Any:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                self.hits += 1
                return entry.value
            self.misses += 1
        value = factory()
        with self._lock:
            self._entries[key] = CacheEntry(value, monotonic() + (self.default_ttl if ttl is None else ttl))
        return value

    def get_or_create_with_status(self, key: str, factory: Callable[[], Any], ttl: float | None = None) -> tuple[Any, bool]:
        """Return a cached value and hit status while serializing expensive creation."""
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                self.hits += 1
                return entry.value, True
            self.misses += 1
            value = factory()
            self._entries[key] = CacheEntry(value, monotonic() + (self.default_ttl if ttl is None else ttl))
            return value, False

    def invalidate(self, prefix: str | None = None) -> int:
        with self._lock:
            keys = [key for key in self._entries if prefix is None or key.startswith(prefix)]
            for key in keys:
                del self._entries[key]
            self.invalidations += len(keys)
            return len(keys)

    def health(self) -> dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            namespaces: dict[str, int] = {}
            for key in self._entries:
                namespace = key.rsplit(":", 1)[-1]
                namespaces[namespace] = namespaces.get(namespace, 0) + 1
            return {"status": "healthy", "entries": len(self._entries), "namespaces": namespaces, "hits": self.hits, "misses": self.misses, "hit_rate": round(self.hits / total, 3) if total else 0.0, "invalidations": self.invalidations, "default_ttl_seconds": self.default_ttl}


intelligence_cache = IntelligenceCache(default_ttl=INTELLIGENCE_CACHE_TTL)
