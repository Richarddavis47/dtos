"""Validation-only timing wrapper for the production DTOS application."""
from __future__ import annotations

import base64
import contextvars
import json
import threading
import time
from typing import Any, Callable

from fastapi import Request

from dtos_app import app
from services.sleeper import STATE
from src.core.asset_market.engine import AssetMarketCache, asset_market_cache
from src.core.historical_memory.store import HistoricalStore
from src.platform.lifecycle import LifecycleCoordinator, lifecycle_coordinator

_profile: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "market_validation_profile", default=None,
)


def _timed(name: str, function: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        profile = _profile.get()
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            if profile is not None:
                profile[f"{name}_calls"] = int(profile.get(f"{name}_calls", 0)) + 1
                profile[f"{name}_ms"] = round(
                    float(profile.get(f"{name}_ms", 0.0))
                    + (time.perf_counter() - started) * 1000,
                    3,
                )
    return wrapped


AssetMarketCache.request_marker = staticmethod(_timed(
    "request_marker", AssetMarketCache.request_marker,
))
AssetMarketCache.get = _timed("market_get", AssetMarketCache.get)
AssetMarketCache.key = classmethod(_timed(
    "cache_key", AssetMarketCache.key.__func__,
))
AssetMarketCache.durable_generation = staticmethod(_timed(
    "durable_generation", AssetMarketCache.durable_generation,
))
AssetMarketCache._construct = _timed("market_construction", AssetMarketCache._construct)
HistoricalStore.dataset_version = _timed(
    "dataset_version", HistoricalStore.dataset_version,
)
HistoricalStore.database_uuid = _timed(
    "database_uuid", HistoricalStore.database_uuid,
)
LifecycleCoordinator.market_build_allowed = _timed(
    "lifecycle_lock", LifecycleCoordinator.market_build_allowed,
)


@app.middleware("http")
async def validation_profile(request: Request, call_next):
    profile: dict[str, Any] = {}
    token = _profile.set(profile)
    try:
        response = await call_next(request)
    finally:
        _profile.reset(token)
    get_ms = float(profile.get("market_get_ms", 0.0))
    marker_ms = float(profile.get("request_marker_ms", 0.0))
    lifecycle_ms = float(profile.get("lifecycle_lock_ms", 0.0))
    profile.update({
        "cache_lookup_ms": round(max(0.0, get_ms - marker_ms - lifecycle_ms), 3),
        "active_threads": threading.active_count(),
        "thread_pool_threads": sum(
            thread.name == "AnyIO worker thread" for thread in threading.enumerate()
        ),
        "worker_alive": bool(
            asset_market_cache._build_thread
            and asset_market_cache._build_thread.is_alive()
        ),
        "sleeper_syncing": bool(STATE.get("syncing")),
        "transactions_syncing": bool(STATE.get("transactions_syncing")),
    })
    encoded = base64.urlsafe_b64encode(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    response.headers["X-DTOS-Validation-Profile"] = encoded
    return response


@app.post("/__validation__/replace-generation")
async def replace_generation(marker: str) -> dict[str, Any]:
    """Change only the in-memory canonical marker for controlled validation."""
    before = asset_market_cache.metrics()
    STATE["last_sync"] = marker
    return {
        "previous_generation": before.get("market_generation"),
        "previous_build_count": before.get("build_count"),
        "lifecycle": lifecycle_coordinator.snapshot().get("phase"),
    }
