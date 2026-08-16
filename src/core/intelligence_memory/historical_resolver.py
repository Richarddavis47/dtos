"""Bounded, global historical-market resolution without league warehouses."""
from __future__ import annotations

from collections import OrderedDict, Counter
from dataclasses import dataclass, replace
from threading import RLock
from time import monotonic, sleep
from typing import TYPE_CHECKING, Callable, Iterable, Protocol

from .market import HistoricalMarketSelection, select_historical_market
from .models import (
    EvidencePersistenceDecision, GlobalMarketObservation,
    HISTORICAL_RESOLUTION_POLICY_VERSION, HistoricalResolutionState,
    SourceObservation,
)
from .store import IntelligenceCheckpointStore

if TYPE_CHECKING:
    from .models import IntelligenceCheckpoint


class HistoricalMarketProvider(Protocol):
    """Approved provider adapter returning only bounded candidate evidence."""

    provider_id: str

    def observations(
        self, *, asset_id: str, asset_type: str, market_context_id: str,
        at_or_before: str,
    ) -> Iterable[SourceObservation]: ...


class HistoricalProviderRateLimitError(RuntimeError):
    """Historical evidence is still unresolved because a provider rate-limited it."""


@dataclass(frozen=True)
class HistoricalResolution:
    selection: HistoricalMarketSelection
    persistence: EvidencePersistenceDecision
    source: str
    observation_id: str | None
    policy_version: str = HISTORICAL_RESOLUTION_POLICY_VERSION

    @property
    def available(self) -> bool:
        return self.selection.value is not None


@dataclass(frozen=True)
class PersistenceContext:
    trigger: str
    future_access_guaranteed: bool = False


def persistence_decision(
    selection: HistoricalMarketSelection, context: PersistenceContext,
) -> EvidencePersistenceDecision:
    """One auditable policy; fetching alone never implies persistence."""
    if selection.value is None:
        return EvidencePersistenceDecision.UNAVAILABLE
    if context.future_access_guaranteed:
        return EvidencePersistenceDecision.EPHEMERAL_ONLY
    if context.trigger in {
        "trade_execution", "waiver_add", "drop", "fantasy_draft_pick",
        "approved_historical_analysis",
    }:
        return EvidencePersistenceDecision.PRESERVE_GLOBAL
    return EvidencePersistenceDecision.EPHEMERAL_ONLY


class HistoricalProviderCache:
    """Disposable global TTL cache keyed without league identity."""

    def __init__(self, *, ttl_seconds: float = 3600, maximum_entries: int = 4096):
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self.maximum_entries = max(1, int(maximum_entries))
        self._entries: OrderedDict[tuple[str, ...], tuple[float, tuple[SourceObservation, ...]]] = OrderedDict()
        self._lock = RLock()
        self.hits = self.misses = self.evictions = 0

    def get_or_create(
        self, key: tuple[str, ...], factory: Callable[[], Iterable[SourceObservation]],
    ) -> tuple[SourceObservation, ...]:
        now = monotonic()
        with self._lock:
            cached = self._entries.get(key)
            if cached and cached[0] > now:
                self.hits += 1
                self._entries.move_to_end(key)
                return cached[1]
            if cached:
                self._entries.pop(key, None)
            self.misses += 1
        value = tuple(factory())
        with self._lock:
            self._entries[key] = (now + self.ttl_seconds, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.maximum_entries:
                self._entries.popitem(last=False)
                self.evictions += 1
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def health(self) -> dict[str, int | float | str]:
        return {
            "ownership": "disposable_global_provider_cache",
            "entries": len(self._entries), "ttl_seconds": self.ttl_seconds,
            "maximum_entries": self.maximum_entries, "hits": self.hits,
            "misses": self.misses, "evictions": self.evictions,
        }


class HistoricalMarketResolver:
    """Resolve pre-event evidence from global memory, then approved providers."""

    def __init__(
        self, store: IntelligenceCheckpointStore,
        providers: Iterable[HistoricalMarketProvider] = (),
        *, cache: HistoricalProviderCache | None = None,
    ) -> None:
        self.store = store
        self.providers = tuple(providers)
        self.cache = cache or HistoricalProviderCache()
        self._counts: Counter[str] = Counter()

    @staticmethod
    def _from_global(row: GlobalMarketObservation) -> HistoricalResolution:
        selection = HistoricalMarketSelection(
            row.provenance_type, row.evidence_completeness,
            float(row.canonical_value), row.confidence,
            row.provider_evidence, len(row.provider_evidence) > 1,
            "compatible_global_observation",
        )
        return HistoricalResolution(
            selection, EvidencePersistenceDecision.ALREADY_PRESERVED,
            "global_market_memory", row.observation_id,
        )

    def resolve(
        self, *, asset_id: str, asset_type: str, market_context_id: str,
        occurred_at: str, persistence: PersistenceContext,
    ) -> HistoricalResolution:
        existing = self.store.observation_at_or_before(
            asset_id=asset_id, market_context_id=market_context_id,
            event_at=occurred_at,
        )
        if existing is not None:
            self._counts["global_reuse"] += 1
            return self._from_global(existing)

        candidates: list[SourceObservation] = []
        for provider in self.providers:
            key = (
                provider.provider_id.casefold(), asset_id, asset_type,
                market_context_id, occurred_at,
            )
            def fetch(p: HistoricalMarketProvider = provider) -> Iterable[SourceObservation]:
                self._counts["provider_queries"] += 1
                self._counts[f"provider_{p.provider_id.casefold()}_queries"] += 1
                try:
                    return p.observations(
                        asset_id=asset_id, asset_type=asset_type,
                        market_context_id=market_context_id, at_or_before=occurred_at,
                    )
                except Exception as exc:
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status == 403 or "rate limit" in str(exc).casefold():
                        self._counts["provider_rate_limited"] += 1
                        raise HistoricalProviderRateLimitError(
                            "Historical provider rate limited the request."
                        ) from exc
                    raise
            candidates.extend(self.cache.get_or_create(key, fetch))
        selected = select_historical_market(candidates, occurred_at)
        decision = persistence_decision(selected, persistence)
        self._counts[decision.value] += 1
        return HistoricalResolution(
            selected, decision,
            "approved_historical_provider" if selected.value is not None else "unavailable",
            None,
        )

    def resolve_checkpoint(
        self, checkpoint: "IntelligenceCheckpoint", *, market_context_id: str,
        persistence: PersistenceContext,
    ) -> tuple[HistoricalResolution, "IntelligenceCheckpoint", bool, bool]:
        """Resolve and, only when policy requires it, atomically preserve sparse evidence."""
        durable = self.store.compatible_resolution(
            checkpoint, market_context_id=market_context_id,
            resolver_version=HISTORICAL_RESOLUTION_POLICY_VERSION,
        )
        reused = self._reuse_durable(checkpoint, durable)
        if reused is not None:
            return reused
        return self._resolve_after_compatibility_miss(
            checkpoint, market_context_id=market_context_id,
            persistence=persistence,
        )

    def _reuse_durable(
        self, checkpoint: "IntelligenceCheckpoint",
        durable: tuple[
            "IntelligenceCheckpoint", GlobalMarketObservation | None,
            HistoricalResolutionState,
        ] | None,
    ) -> tuple[HistoricalResolution, "IntelligenceCheckpoint", bool, bool] | None:
        if durable is None:
            return None
        stored, observation, state = durable
        self._counts["replay_skipped"] += 1
        if observation is not None and state == HistoricalResolutionState.COMPLETE:
            self._counts["durable_reuse"] += 1
            result = self._from_global(observation)
            return replace(result, source="durable_resolution_reference"), stored, False, False
        if state == HistoricalResolutionState.FINAL_UNAVAILABLE:
            self._counts["durable_final_unavailable"] += 1
            selected = select_historical_market((), checkpoint.timestamp)
            return HistoricalResolution(
                selected, EvidencePersistenceDecision.UNAVAILABLE,
                "durable_final_unavailable", None,
            ), stored, False, False
        return None

    def resolve_checkpoints_bulk(
        self,
        requests: list[tuple["IntelligenceCheckpoint", str, PersistenceContext]],
    ) -> tuple[
        list[tuple[HistoricalResolution, "IntelligenceCheckpoint", bool, bool] | None],
        dict[str, int],
    ]:
        """Reuse compatible durable results in bulk, resolving only misses."""
        durable, metrics = self.store.compatible_resolutions([
            (checkpoint, context, HISTORICAL_RESOLUTION_POLICY_VERSION)
            for checkpoint, context, _persistence in requests
        ])
        results = []
        for index, ((checkpoint, context, persistence), compatible) in enumerate(zip(
            requests, durable, strict=True,
        ), 1):
            reused = self._reuse_durable(checkpoint, compatible)
            if reused is not None:
                results.append(reused)
                if index % 32 == 0:
                    sleep(0)
                continue
            try:
                results.append(self._resolve_after_compatibility_miss(
                    checkpoint, market_context_id=context, persistence=persistence,
                ))
            except HistoricalProviderRateLimitError:
                metrics["rate_limited"] = int(metrics.get("rate_limited", 0)) + 1
                results.append(None)
            if index % 32 == 0:
                sleep(0)
        metrics["assets_bulk_reused"] = sum(
            result is not None and result[0].source in {
                "durable_resolution_reference", "durable_final_unavailable",
            }
            for result in results
        )
        metrics["assets_provider_resolved"] = sum(
            result is not None and result[0].source not in {
                "durable_resolution_reference", "durable_final_unavailable",
            }
            for result in results
        )
        return results, metrics

    def _resolve_after_compatibility_miss(
        self, checkpoint: "IntelligenceCheckpoint", *, market_context_id: str,
        persistence: PersistenceContext,
    ) -> tuple[HistoricalResolution, "IntelligenceCheckpoint", bool, bool]:
        result = self.resolve(
            asset_id=checkpoint.asset_id, asset_type=checkpoint.asset_type,
            market_context_id=market_context_id, occurred_at=checkpoint.timestamp,
            persistence=persistence,
        )
        if result.persistence == EvidencePersistenceDecision.UNAVAILABLE:
            stored, _, _, observation_created, reference_created = self.store.put_sparse(
                checkpoint, market_context_id=market_context_id,
                resolver_version=HISTORICAL_RESOLUTION_POLICY_VERSION,
                resolution_state=HistoricalResolutionState.FINAL_UNAVAILABLE,
                unavailable_reason="provider_coverage_exhausted",
            )
            self._counts["final_unavailable_persisted"] += int(reference_created)
            return result, stored, observation_created, reference_created
        if result.persistence not in {
            EvidencePersistenceDecision.PRESERVE_GLOBAL,
            EvidencePersistenceDecision.ALREADY_PRESERVED,
        }:
            return result, checkpoint, False, False
        selection = result.selection
        candidate = replace(
            checkpoint, market_value=selection.value,
            confidence=selection.confidence,
            evidence_completeness=selection.completeness,
            provenance_type=selection.provenance,
        )
        stored, _, _, observation_created, reference_created = self.store.put_sparse(
            candidate, market_context_id=market_context_id,
            provider_evidence=selection.observations,
            resolver_version=HISTORICAL_RESOLUTION_POLICY_VERSION,
            resolution_state=HistoricalResolutionState.COMPLETE,
        )
        observation_id = stored.global_market_observation_id
        return (
            replace(result, observation_id=observation_id), stored,
            observation_created, reference_created,
        )

    def health(self) -> dict[str, object]:
        return {
            "policy_version": HISTORICAL_RESOLUTION_POLICY_VERSION,
            "provider_count": len(self.providers), "counts": dict(self._counts),
            "cache": self.cache.health(), "league_scoped_cache_keys": 0,
            "per_league_permanent_historical_market_bytes": 0,
            "current_market_fallbacks": 0,
        }
