"""Single execution boundary for every external DTOS data source."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from time import monotonic, perf_counter
from typing import Any

from src.core.data_platform.aggregation import consensus, trend
from src.core.data_platform.models import DataEnvelope, DataQuality, ProviderHealth, ProviderStatus, RefreshResult
from src.core.data_platform.normalization import PlayerIdentityResolver
from src.core.data_platform.provider_activation import player_context
from src.core.data_platform.provider import DataProvider
from src.core.data_platform.reliability import ReliabilityTracker
from src.core.data_platform.registry import ProviderRegistry
from src.core.data_platform.scheduler import RefreshScheduler
from src.core.data_platform.storage import SnapshotWarehouse


class DataPlatform:
    def __init__(self, registry: ProviderRegistry | None = None, warehouse: SnapshotWarehouse | None = None, cache_ttl_seconds: float = 3600) -> None:
        self.registry = registry or ProviderRegistry()
        self.warehouse = warehouse or SnapshotWarehouse()
        self.scheduler = RefreshScheduler()
        self.reliability = ReliabilityTracker()
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[tuple[str, str, str], DataEnvelope] = {}
        self._cache_stored: dict[tuple[str, str, str], float] = {}
        self._health: dict[str, ProviderHealth] = {}

    def register(self, provider: DataProvider) -> None:
        self.registry.register(provider)
        meta = provider.metadata
        status = ProviderStatus.UNAVAILABLE if meta.enabled else ProviderStatus.DISABLED
        self._health[meta.name] = ProviderHealth(meta.name, status, None, None, None, None, "empty", "unavailable", 0.0, 0, "Provider-defined", meta.licensing_tier, None if meta.enabled else "Disabled by licensing or deployment configuration")

    def fetch(self, provider_name: str, key: str, context: dict[str, Any], *, mode: str = "online", allow_cached: bool = True) -> DataEnvelope:
        provider = self.registry.provider(provider_name)
        meta = provider.metadata
        namespace = str(context.get("namespace") or "global")
        cache_key = (namespace, provider_name, key)
        now = datetime.now(timezone.utc).isoformat()
        started = perf_counter()
        if not meta.enabled:
            return replace(self._unavailable(key, meta.category, provider_name, now, "Provider disabled by licensing or deployment configuration."), availability="Disabled")
        if mode == "offline":
            cached = self._cache.get(cache_key) if allow_cached else None
            if cached:
                return replace(cached, freshness="stale", cache_state="historical_snapshot", retrieval_mode="cached_fallback", confidence=max(0, cached.confidence - 20), limitations=(*cached.limitations, "Live provider unavailable; using disclosed cached snapshot."), availability="Cached")
            historical = self.warehouse.latest(provider_name, key) if allow_cached else None
            if historical:
                return replace(historical, freshness="stale", cache_state="historical_snapshot", retrieval_mode="historical_snapshot", confidence=max(0, historical.confidence - 30), limitations=(*historical.limitations, "Live and fresh cache unavailable; using historical snapshot."), availability="Historical")
            if context.get("dtos_estimate") is not None:
                return self._estimate(key, meta.category, provider_name, now, context["dtos_estimate"])
            return self._unavailable(key, meta.category, provider_name, now, "Provider unavailable in offline context and no fallback snapshot exists.")
        cached = self._cache.get(cache_key)
        stored = self._cache_stored.get(cache_key)
        age = monotonic() - stored if stored is not None else None
        if allow_cached and not context.get("force_refresh") and cached and age is not None and age <= self.cache_ttl_seconds:
            return replace(cached, cache_state="fresh_cache", retrieval_mode="cache_hit", freshness="fresh", availability="Cached")
        try:
            envelope = provider.fetch(key, context)
            latency = round((perf_counter() - started) * 1000, 3)
            if envelope.quality.status == "blocked" or envelope.value is None:
                raise ValueError("Provider returned no usable value.")
            reliability = self.reliability.record(provider_name, success=True, latency_ms=latency)
            envelope = replace(envelope, cache_state="fresh", retrieval_mode="live", availability="Live", reliability=reliability)
            self._cache[cache_key] = envelope
            self._cache_stored[cache_key] = monotonic()
            self.warehouse.append(envelope)
            self._health[provider_name] = self._health_row(provider, ProviderStatus.HEALTHY, now, now, None, "fresh", envelope.freshness, latency, envelope.confidence, None)
            return envelope
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            latency = round((perf_counter() - started) * 1000, 3)
            self.reliability.record(provider_name, success=False, latency_ms=latency, schema_failure=isinstance(exc, (TypeError, ValueError)))
            prior = self._health.get(provider_name)
            failure_status = ProviderStatus.RATE_LIMITED if "rate limit" in str(exc).casefold() else ProviderStatus.DEGRADED
            self._health[provider_name] = self._health_row(provider, failure_status, now, prior.last_success if prior else None, now, "fallback", "stale", latency, 0, str(exc))
            cached = self._cache.get(cache_key) if allow_cached else None
            if cached:
                return replace(cached, freshness="stale", cache_state="fresh_cache", retrieval_mode="cached_fallback", confidence=max(0, cached.confidence - 20), limitations=(*cached.limitations, f"Live provider failed: {exc}"), availability="Cached")
            historical = self.warehouse.latest(provider_name, key) if allow_cached else None
            if historical:
                return replace(historical, freshness="stale", cache_state="historical_snapshot", retrieval_mode="historical_snapshot", confidence=max(0, historical.confidence - 30), limitations=(*historical.limitations, f"Live provider and fresh cache failed: {exc}"), availability="Historical")
            if context.get("dtos_estimate") is not None:
                return self._estimate(key, meta.category, provider_name, now, context["dtos_estimate"])
            return self._unavailable(key, meta.category, provider_name, now, str(exc))

    def aggregate(self, category: str, key: str, context: dict[str, Any], *, mode: str = "online"):
        providers = self.registry.providers(category)
        rows = tuple(self.fetch(provider.metadata.name, key, context, mode=mode) for provider in providers)
        return consensus(key, rows, tuple(provider.metadata.name for provider in providers))

    def trend(self, key: str, category: str | None = None):
        return trend(key, self.warehouse.history(key, category))

    def player_report(self, player_id: str, data: dict[str, Any]) -> dict[str, Any]:
        players = data.get("players") or {}
        resolver = PlayerIdentityResolver(players)
        player = resolver.resolve(player_id)
        if player is None:
            raise KeyError(f"Player {player_id!r} was not found in normalized identity data.")
        market_data = data.get("market_data") or {}
        context = {"asset": players.get(player_id) or {}, "market_data": market_data, "namespace": f"player:{player_id}"}
        mode = "online" if market_data.get("providers") else "offline"
        providers = self.registry.providers("market")
        values = tuple(self.fetch(provider.metadata.name, player_id, context, mode=mode) for provider in providers)
        result = consensus(player_id, values, tuple(provider.metadata.name for provider in providers))
        status_rows = market_data.get("provider_status") or {}
        availability = {}
        for row in values:
            provider_status = status_rows.get(row.provider) or {}
            if row.value is None and provider_status.get("status") == "healthy":
                reason = f"{row.provider} returned no record for this canonical player."
            else:
                reason = provider_status.get("reason") or (row.limitations[0] if row.limitations else "Normalized provider value available.")
            availability[row.provider] = {"state": row.availability, "reason": reason, "freshness": row.freshness, "confidence": row.confidence, "licensing": self.registry.provider(row.provider).metadata.licensing_tier.value}
        details = {
            provider.metadata.name: ((market_data.get("providers") or {}).get(provider.metadata.name) or {}).get(player_id)
            for provider in providers
        }
        return {"normalized_player": asdict(player), "provider_values": tuple(asdict(row) for row in values), "provider_details": details, "consensus": asdict(result), "market_trend": asdict(self.trend(player_id, "market")), "provider_availability": availability, "provider_health": market_data.get("provider_status") or {}, "attribution": market_data.get("attribution") or {}, "player_context": player_context(player_id, data), "normalization": {"identity": "canonical DTOS player", "contract": "NormalizedPlayer + DataEnvelope", "provider_ids": player.provider_ids}, "unavailable_reasons": tuple(sorted({row.limitations[0] for row in values if row.value is None and row.limitations}))}

    def refresh(self, category: str, context: dict[str, Any], keys: tuple[str, ...], *, provider_name: str | None = None) -> tuple[RefreshResult, ...]:
        providers = (self.registry.provider(provider_name),) if provider_name else self.registry.providers(category)
        now = datetime.now(timezone.utc).isoformat()
        results: list[RefreshResult] = []
        for provider in providers:
            if not provider.metadata.supports_live_refresh:
                results.append(RefreshResult(provider.metadata.name, category, "skipped", now, 0, "Provider does not support on-demand refresh."))
                continue
            rows = tuple(self.fetch(provider.metadata.name, key, context, mode="online", allow_cached=False) for key in keys)
            count = sum(row.value is not None for row in rows)
            results.append(RefreshResult(provider.metadata.name, category, "success" if count else "unavailable", now, count, "Refresh completed without interrupting scheduled jobs."))
        return tuple(results)

    def invalidate(self, provider: str | None = None) -> int:
        keys = [key for key in self._cache if provider is None or key[1] == provider]
        for key in keys:
            del self._cache[key]
            self._cache_stored.pop(key, None)
        return len(keys)

    def scheduled(self, *, in_season: bool) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(self.scheduler.schedule(provider.metadata, (self._health.get(provider.metadata.name) or self._empty_health(provider)).last_refresh, in_season=in_season)) for provider in self.registry.providers())

    def health(self) -> dict[str, Any]:
        return {"status": "healthy" if all(row.status not in {ProviderStatus.DEGRADED, ProviderStatus.RATE_LIMITED} for row in self._health.values()) else "degraded", "providers": {name: asdict(row) for name, row in self._health.items()}, "reliability": self.reliability.health(), "cache": {"entries": len(self._cache), "ttl_seconds": self.cache_ttl_seconds}, "snapshots": sum(len(self.warehouse.history(key[2])) for key in self._cache)}

    @staticmethod
    async def get_json(client: Any, url: str) -> Any:
        """HTTP transport boundary used by approved live adapters such as Sleeper."""
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

    def _health_row(self, provider: DataProvider, status: ProviderStatus, refresh: str, success: str | None, failure: str | None, cache: str, freshness: str, latency: float, confidence: int, reason: str | None) -> ProviderHealth:
        schedule = self.scheduler.schedule(provider.metadata, refresh, in_season=True)
        return ProviderHealth(provider.metadata.name, status, refresh, success, failure, schedule.next_refresh, cache, freshness, latency, confidence, "Provider-defined", provider.metadata.licensing_tier, reason)

    def _empty_health(self, provider: DataProvider) -> ProviderHealth:
        return ProviderHealth(provider.metadata.name, ProviderStatus.UNAVAILABLE, None, None, None, None, "empty", "unavailable", 0, 0, "Provider-defined", provider.metadata.licensing_tier, None)

    @staticmethod
    def _estimate(key: str, category: str, provider: str, timestamp: str, value: Any) -> DataEnvelope:
        return DataEnvelope(key, category, value, "DTOS deterministic estimate", provider, timestamp, "estimated", 35, "none", "dtos_estimate", DataQuality("warning", ("External provider data unavailable",), 50), ("DTOS estimate is not provider consensus.",), "Estimated", 35, {"contract": "NormalizedValue"})

    @staticmethod
    def _unavailable(key: str, category: str, provider: str, timestamp: str, reason: str) -> DataEnvelope:
        return DataEnvelope(key, category, None, provider, provider, timestamp, "unavailable", 0, "empty", "unavailable", DataQuality("blocked", (reason,), 0), (reason, "Fallback chain exhausted: live, fresh cache, historical snapshot, and DTOS estimate unavailable."), "Unavailable", 0, {"contract": "NormalizedValue"})
