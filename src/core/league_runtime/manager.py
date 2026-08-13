"""Bounded, lazy league runtime residency."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock
from time import monotonic
from typing import Any, Awaitable, Callable

from .identity import scoring_profile_id


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeState(StrEnum):
    COLD = "cold"
    HYDRATING = "hydrating"
    WARM = "warm"
    FAILED = "failed"
    EVICTING = "evicting"
    CLOSED = "closed"


class LeagueRuntimeError(RuntimeError):
    pass


class LeagueRuntimeNotFound(LeagueRuntimeError):
    pass


@dataclass(slots=True, weakref_slot=True)
class LeagueRuntime:
    league_id: str
    state: dict[str, Any] = field(default_factory=lambda: {
        "data": {}, "last_sync": None, "last_error": None, "syncing": False,
        "transactions_syncing": False, "transactions_last_sync": None,
        "transactions_last_error": None,
    })
    status: RuntimeState = RuntimeState.COLD
    season: int | None = None
    scoring_profile: str | None = None
    projection_context: Any = None
    brain_context: Any = None
    market_context: Any = None
    fois_context: Any = None
    canonical_context: Any = None
    lifecycle: dict[str, Any] = field(default_factory=dict)
    source_generations: dict[str, str] = field(default_factory=dict)
    cache_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow)
    last_access_at: str = field(default_factory=_utcnow)
    last_access_monotonic: float = field(default_factory=monotonic, repr=False)
    active_requests: int = 0
    pinned: bool = False
    owns_state: bool = True
    error: str | None = None
    background_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)

    def touch(self) -> None:
        self.last_access_at = _utcnow()
        self.last_access_monotonic = monotonic()

    def apply_data(self, data: dict[str, Any]) -> None:
        league = data.get("league") or {}
        actual_id = str(league.get("league_id") or self.league_id)
        if actual_id != self.league_id:
            raise LeagueRuntimeError(
                f"Hydrated league {actual_id!r} does not match requested league {self.league_id!r}."
            )
        self.state["data"] = data
        self.season = int(league.get("season") or data.get("season") or datetime.now().year)
        self.scoring_profile = scoring_profile_id(
            data.get("scoring_settings") or league.get("scoring_settings") or {},
            roster_positions=tuple(data.get("roster_positions") or league.get("roster_positions") or ()),
        )
        self.touch()

    async def close(self) -> None:
        self.status = RuntimeState.EVICTING
        tasks = tuple(self.background_tasks)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for context in (
            self.market_context, self.projection_context, self.brain_context,
            self.fois_context, self.canonical_context,
        ):
            closer = getattr(context, "close", None) or getattr(context, "clear", None)
            if callable(closer):
                result = closer()
                if hasattr(result, "__await__"):
                    await result
        self.background_tasks.clear()
        if self.owns_state:
            self.state["data"] = {}
        self.projection_context = None
        self.brain_context = None
        self.market_context = None
        self.fois_context = None
        self.canonical_context = None
        self.status = RuntimeState.CLOSED

    def public_health(self) -> dict[str, Any]:
        data = self.state.get("data") or {}
        result = {
            "league_id": self.league_id,
            "status": self.status.value,
            "season": self.season,
            "scoring_profile_id": self.scoring_profile,
            "last_access": self.last_access_at,
            "last_sync": self.state.get("last_sync"),
            "last_error": self.error or self.state.get("last_error"),
            "active_requests": self.active_requests,
            "team_count": len(data.get("teams") or ()),
            "source_generations": dict(self.source_generations),
        }
        if self.canonical_context is not None:
            result["product"] = self.canonical_context.health()
        return result


Hydrator = Callable[[LeagueRuntime], Awaitable[dict[str, Any] | LeagueRuntime | None]]


class LeagueRuntimeManager:
    """Lazy single-flight runtime manager with bounded LRU residency."""

    def __init__(self, *, max_warm: int = 2, hydrator: Hydrator | None = None) -> None:
        if not 1 <= max_warm <= 3:
            raise ValueError("max_warm must remain within the validated 1-3 runtime bound.")
        self.max_warm = max_warm
        self._hydrator = hydrator
        self._runtimes: OrderedDict[str, LeagueRuntime] = OrderedDict()
        self._flights: dict[str, asyncio.Task[LeagueRuntime]] = {}
        self._lock = asyncio.Lock()
        self._metrics_lock = RLock()
        self.hydrations = 0
        self.restore_hits = 0
        self.evictions = 0
        self.failures = 0

    @staticmethod
    def validate_league_id(league_id: str) -> str:
        value = str(league_id).strip()
        if not value or len(value) > 32 or not value.isdigit():
            raise LeagueRuntimeNotFound("Sleeper league_id must contain 1-32 digits.")
        return value

    async def get(self, league_id: str, *, hydrate: bool = True) -> LeagueRuntime:
        key = self.validate_league_id(league_id)
        async with self._lock:
            runtime = self._runtimes.get(key)
            if runtime is not None and runtime.status not in {RuntimeState.FAILED, RuntimeState.CLOSED}:
                runtime.touch()
                self._runtimes.move_to_end(key)
                if runtime.status is RuntimeState.WARM or not hydrate:
                    with self._metrics_lock:
                        self.restore_hits += 1
                    return runtime
            if not hydrate:
                if runtime is None:
                    runtime = LeagueRuntime(key)
                    self._runtimes[key] = runtime
                return runtime
            flight = self._flights.get(key)
            if flight is None or flight.done():
                if runtime is None or runtime.status in {RuntimeState.FAILED, RuntimeState.CLOSED}:
                    runtime = LeagueRuntime(key)
                    self._runtimes[key] = runtime
                runtime.status = RuntimeState.HYDRATING
                flight = asyncio.create_task(self._hydrate(runtime), name=f"league-runtime:{key}")
                self._flights[key] = flight
        return await flight

    async def _hydrate(self, runtime: LeagueRuntime) -> LeagueRuntime:
        try:
            if self._hydrator is None:
                raise LeagueRuntimeError("No league runtime hydrator is configured.")
            result = await self._hydrator(runtime)
            if isinstance(result, dict):
                runtime.apply_data(result)
            elif isinstance(result, LeagueRuntime) and result is not runtime:
                raise LeagueRuntimeError("Hydrator must update the runtime it was given.")
            if not runtime.state.get("data"):
                raise LeagueRuntimeNotFound(f"Sleeper league {runtime.league_id} returned no league data.")
            runtime.status = RuntimeState.WARM
            runtime.error = None
            runtime.touch()
            with self._metrics_lock:
                self.hydrations += 1
            await self._evict_if_needed(exclude=runtime.league_id)
            return runtime
        except Exception as exc:
            runtime.status = RuntimeState.FAILED
            runtime.error = f"{type(exc).__name__}: {exc}"
            with self._metrics_lock:
                self.failures += 1
            raise
        finally:
            async with self._lock:
                current = self._flights.get(runtime.league_id)
                if current is asyncio.current_task():
                    self._flights.pop(runtime.league_id, None)

    async def _evict_if_needed(self, *, exclude: str | None = None) -> None:
        while True:
            async with self._lock:
                warm = [
                    runtime for runtime in self._runtimes.values()
                    if runtime.status is RuntimeState.WARM
                ]
                if len(warm) <= self.max_warm:
                    return
                victim = next((
                    runtime for runtime in warm
                    if runtime.league_id != exclude and runtime.active_requests == 0
                    and not runtime.pinned
                ), None)
                if victim is None:
                    return
                self._runtimes.pop(victim.league_id, None)
            await victim.close()
            with self._metrics_lock:
                self.evictions += 1

    async def evict(self, league_id: str) -> bool:
        key = self.validate_league_id(league_id)
        async with self._lock:
            runtime = self._runtimes.get(key)
            if runtime is None or runtime.active_requests:
                return False
            self._runtimes.pop(key)
        await runtime.close()
        with self._metrics_lock:
            self.evictions += 1
        return True

    async def shutdown(self) -> None:
        async with self._lock:
            runtimes = tuple(self._runtimes.values())
            flights = tuple(self._flights.values())
            self._runtimes.clear()
            self._flights.clear()
        for flight in flights:
            if not flight.done():
                flight.cancel()
        if flights:
            await asyncio.gather(*flights, return_exceptions=True)
        await asyncio.gather(*(runtime.close() for runtime in runtimes), return_exceptions=True)

    def resident(self, league_id: str) -> LeagueRuntime | None:
        return self._runtimes.get(str(league_id))

    def attach_default(
        self, league_id: str, state: dict[str, Any], *, warm: bool = False,
    ) -> LeagueRuntime:
        """Attach the legacy configured state to the manager during migration."""
        key = self.validate_league_id(league_id)
        runtime = LeagueRuntime(key, state=state, pinned=True, owns_state=False)
        if state.get("data"):
            runtime.apply_data(state["data"])
            runtime.status = RuntimeState.WARM if warm else RuntimeState.COLD
        self._runtimes[key] = runtime
        return runtime

    def health(self) -> dict[str, Any]:
        with self._metrics_lock:
            metrics = {
                "hydrations": self.hydrations,
                "restore_hits": self.restore_hits,
                "evictions": self.evictions,
                "failures": self.failures,
            }
        runtimes = tuple(self._runtimes.values())
        return {
            "status": "healthy" if not any(row.status is RuntimeState.FAILED for row in runtimes) else "degraded",
            "resident_runtime_count": len(runtimes),
            "warm_runtime_count": sum(row.status is RuntimeState.WARM for row in runtimes),
            "warm_runtime_limit": self.max_warm,
            "resident_league_ids": [row.league_id for row in runtimes],
            "in_flight": sorted(self._flights),
            **metrics,
            "runtimes": [row.public_health() for row in runtimes],
        }
