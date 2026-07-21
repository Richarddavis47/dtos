"""TTL provider cache with stale offline fallback."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import monotonic
from typing import Callable

from src.core.market_intelligence.models import ProviderQuote


@dataclass
class _Entry:
    quote: ProviderQuote
    stored_at: float
    expires_at: float


class MarketQuoteCache:
    def __init__(self, ttl_seconds: float = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[tuple[str, str, str, str], _Entry] = {}
        self.hits = 0
        self.misses = 0
        self.fallbacks = 0

    def quote(
        self,
        provider: str,
        asset_id: str,
        factory: Callable[[], ProviderQuote],
        *,
        namespace: str,
        context_mode: str,
        provider_version: str = "v1",
        allow_cached_fallback: bool = False,
        maximum_stale_seconds: float | None = None,
    ) -> ProviderQuote:
        key = (namespace, provider_version, provider, asset_id)
        now = monotonic()
        entry = self._entries.get(key)
        if context_mode != "offline" and entry and entry.expires_at > now:
            self.hits += 1
            age = max(0.0, now - entry.stored_at)
            return replace(entry.quote, cached=True, retrieval_mode="cache_hit", cache_age_seconds=round(age, 2), freshness="fresh")
        self.misses += 1
        fresh = factory()
        if context_mode == "offline":
            fresh = replace(
                fresh,
                value=None,
                confidence=0,
                available=False,
                detail="Provider unavailable in offline execution context.",
                retrieval_mode="unavailable",
                freshness="unavailable",
                confidence_impact=0,
            )
        if fresh.available and context_mode != "offline":
            self._entries[key] = _Entry(fresh, now, now + self.ttl_seconds)
            return fresh
        stale_limit = self.ttl_seconds if maximum_stale_seconds is None else maximum_stale_seconds
        age = max(0.0, now - entry.stored_at) if entry else None
        if allow_cached_fallback and entry and entry.quote.available and age is not None and age <= stale_limit:
            self.fallbacks += 1
            penalty = min(35, max(10, round(age / max(stale_limit, 1) * 35)))
            return replace(
                entry.quote,
                confidence=max(0, entry.quote.confidence - penalty),
                cached=True,
                retrieval_mode="cached_fallback",
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                cache_age_seconds=round(age, 2),
                freshness="stale",
                confidence_impact=-penalty,
                detail=f"Provider unavailable; using an explicit cached snapshot. {entry.quote.detail}",
            )
        return replace(fresh, retrieval_mode="unavailable", freshness="unavailable", confidence_impact=-fresh.confidence)

    def invalidate(self) -> None:
        self._entries.clear()

    def invalidate_provider(self, provider: str) -> int:
        keys = [key for key in self._entries if key[2] == provider]
        for key in keys:
            del self._entries[key]
        return len(keys)

    def health(self) -> dict[str, object]:
        now = monotonic()
        ages = [max(0.0, self.ttl_seconds - max(0.0, entry.expires_at - now)) for entry in self._entries.values()]
        return {"status": "healthy", "entries": len(self._entries), "ttl_seconds": self.ttl_seconds, "oldest_age_seconds": round(max(ages), 2) if ages else None, "hits": self.hits, "misses": self.misses, "offline_fallbacks": self.fallbacks}
