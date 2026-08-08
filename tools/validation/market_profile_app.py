"""Validation-only timing wrapper for the production DTOS application."""
from __future__ import annotations

import base64
import contextvars
import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable

from fastapi import Request

from dtos_app import app
from services.sleeper import STATE
import src.core.asset_market.engine as market_engine
import src.core.asset_market.read_model as market_read_model
from src.core.asset_market.engine import AssetMarket, AssetMarketCache, asset_market_cache
from src.core.asset_market.read_model import MarketReadModel
from src.core.historical_memory.store import HistoricalStore
from src.platform.lifecycle import LifecycleCoordinator, lifecycle_coordinator

_profile: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "market_validation_profile", default=None,
)
_counter_lock = threading.Lock()
_preparation_active: dict[str, Any] = {}
_preparation_events: list[dict[str, Any]] = []
_handoff_started: float | None = None
_counters = {
    "market_construction_total": 0,
    "artifact_load_total": 0,
    "market_object_build_total": 0,
}
_stages: dict[str, dict[str, float | int]] = {
    name: {"calls": 0, "duration_ms": 0.0, "rows": 0}
    for name in (
        "artifact_compatibility_lookup", "sqlite_connection_and_cleanup",
        "generation_metadata_read", "market_row_loading_and_decoding",
        "row_decoding", "compact_summary_reconstruction",
        "search_index_reconstruction", "ranking_index_reconstruction",
        "trending_metadata_loading", "object_publication",
    )
}


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


def _counted(name: str, function: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        with _counter_lock:
            _counters[name] += 1
        return function(*args, **kwargs)
    return wrapped


def _stage(name: str, function: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        result = function(*args, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        rows = len(result) if isinstance(result, list) else 0
        with _counter_lock:
            current = _stages.setdefault(name, {"calls": 0, "duration_ms": 0.0, "rows": 0})
            current["calls"] = int(current["calls"]) + 1
            current["duration_ms"] = round(float(current["duration_ms"]) + elapsed, 3)
            current["rows"] = int(current["rows"]) + rows
        return result
    return wrapped


def _preparation_stage(
    name: str, function: Callable[..., Any], *, gil_heavy: bool,
) -> Callable[..., Any]:
    """Profile one worker boundary and expose its active interval to requests."""
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        wall_started = time.perf_counter()
        cpu_started = time.thread_time()
        thread = threading.current_thread()
        file_bytes = 0
        if name in {"artifact_path_resolution", "compatibility_validation"} and args:
            candidate = args[-2] if name == "artifact_path_resolution" else args[0]
            try:
                if hasattr(candidate, "is_file") and candidate.is_file():
                    file_bytes = int(candidate.stat().st_size)
            except OSError:
                file_bytes = 0
        previous: dict[str, Any]
        with _counter_lock:
            previous = dict(_preparation_active)
            _preparation_active.clear()
            _preparation_active.update({
                "name": name,
                "started_monotonic": round(wall_started, 6),
                "thread_id": thread.ident,
                "thread_name": thread.name,
                "worker_thread": thread.name == "dtos-market-builder",
                "gil_heavy": gil_heavy,
            })
        error: str | None = None
        try:
            return function(*args, **kwargs)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            event = {
                "name": name,
                "wall_ms": round((time.perf_counter() - wall_started) * 1000, 3),
                "cpu_ms": round((time.thread_time() - cpu_started) * 1000, 3),
                "thread_id": thread.ident,
                "thread_name": thread.name,
                "process_id": os.getpid(),
                "worker_thread": thread.name == "dtos-market-builder",
                "gil_heavy": gil_heavy,
                "files_read": 1 if file_bytes else 0,
                "file_bytes": file_bytes,
                "error": error,
            }
            with _counter_lock:
                _preparation_events.append(event)
                del _preparation_events[:-24]
                _preparation_active.clear()
                _preparation_active.update(previous)
    return wrapped


AssetMarketCache.request_marker = staticmethod(_timed(
    "request_marker", AssetMarketCache.request_marker,
))
AssetMarketCache.get = _timed("market_get", AssetMarketCache.get)
AssetMarketCache.key = classmethod(_timed(
    "cache_key", _preparation_stage(
        "market_cache_key_composition", AssetMarketCache.key.__func__,
        gil_heavy=True,
    ),
))
AssetMarketCache.durable_generation = staticmethod(_timed(
    "durable_generation", _preparation_stage(
        "durable_generation_composition", AssetMarketCache.durable_generation,
        gil_heavy=True,
    ),
))
AssetMarketCache.artifact_path = staticmethod(_preparation_stage(
    "artifact_path_resolution", AssetMarketCache.artifact_path,
    gil_heavy=True,
))
AssetMarketCache._compatible = staticmethod(_stage(
    "artifact_compatibility_lookup", _preparation_stage(
        "compatibility_validation", AssetMarketCache._compatible,
        gil_heavy=False,
    ),
))
AssetMarketCache._construct = _timed(
    "market_construction",
    _counted("market_construction_total", AssetMarketCache._construct),
)
_start_background = AssetMarketCache._start_background
_background_construct = AssetMarketCache._background_construct
_prepare_generation = AssetMarketCache._prepare_generation


def _profiled_start_background(self: AssetMarketCache, *args: Any, **kwargs: Any) -> Any:
    global _handoff_started
    _handoff_started = time.perf_counter()
    return _start_background(self, *args, **kwargs)


def _profiled_background_construct(
    self: AssetMarketCache, *args: Any, **kwargs: Any,
) -> Any:
    global _handoff_started
    worker_started = time.perf_counter()
    handoff_ms = (
        (worker_started - _handoff_started) * 1000
        if _handoff_started is not None else 0.0
    )
    with _counter_lock:
        _preparation_events.append({
            "name": "thread_scheduling_handoff",
            "wall_ms": round(handoff_ms, 3),
            "cpu_ms": 0.0,
            "thread_id": threading.get_ident(),
            "thread_name": threading.current_thread().name,
            "process_id": os.getpid(),
            "worker_thread": True,
            "gil_heavy": False,
            "files_read": 0,
            "file_bytes": 0,
            "error": None,
        })
        del _preparation_events[:-24]
    _handoff_started = None
    return _background_construct(self, *args, **kwargs)


AssetMarketCache._start_background = _profiled_start_background
AssetMarketCache._background_construct = _profiled_background_construct
AssetMarketCache._prepare_generation = _preparation_stage(
    "generation_preparation_total", _prepare_generation, gil_heavy=True,
)
_asset_market_init = AssetMarket.__init__


def _profiled_market_init(self: AssetMarket, *args: Any, **kwargs: Any) -> None:
    counter = "artifact_load_total" if kwargs.get("load_existing") else "market_object_build_total"
    started = time.perf_counter()
    with _counter_lock:
        _counters[counter] += 1
        if kwargs.get("load_existing"):
            _preparation_events.append({
                "name": "artifact_load_counter_increment",
                "wall_ms": 0.0,
                "cpu_ms": 0.0,
                "thread_id": threading.get_ident(),
                "thread_name": threading.current_thread().name,
                "process_id": os.getpid(),
                "worker_thread": threading.current_thread().name
                == "dtos-market-builder",
                "gil_heavy": False,
                "files_read": 0,
                "file_bytes": 0,
                "error": None,
            })
            del _preparation_events[:-24]
    try:
        _asset_market_init(self, *args, **kwargs)
    finally:
        if kwargs.get("load_existing"):
            elapsed = (time.perf_counter() - started) * 1000
            with _counter_lock:
                current = _stages.setdefault(
                    "artifact_hydration_total",
                    {"calls": 0, "duration_ms": 0.0, "rows": 0},
                )
                current["calls"] = int(current["calls"]) + 1
                current["duration_ms"] = round(
                    float(current["duration_ms"]) + elapsed, 3,
                )


AssetMarket.__init__ = _profiled_market_init
MarketReadModel.__init__ = _stage(
    "artifact_compatibility_and_open",
    _preparation_stage(
        "artifact_manifest_open", MarketReadModel.__init__, gil_heavy=False,
    ),
)
MarketReadModel.metadata = _stage(
    "generation_metadata_read",
    _preparation_stage(
        "artifact_manifest_header_read", MarketReadModel.metadata,
        gil_heavy=False,
    ),
)
MarketReadModel.fetch_summaries = _stage("market_row_loading_and_decoding", MarketReadModel.fetch_summaries)
market_read_model._json_object = _stage("row_decoding", market_read_model._json_object)
AssetMarket.health = _stage("compact_summary_reconstruction", AssetMarket.health)
AssetMarketCache._publish = _stage("object_publication", AssetMarketCache._publish)
market_engine.brain_service = _stage("brain_snapshot_lookup", market_engine.brain_service)

_read_model_connection = MarketReadModel.connection


@contextmanager
def _profiled_connection(self: MarketReadModel):
    started = time.perf_counter()
    try:
        with _read_model_connection(self) as connection:
            yield connection
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        with _counter_lock:
            current = _stages.setdefault(
                "sqlite_connection_and_cleanup",
                {"calls": 0, "duration_ms": 0.0, "rows": 0},
            )
            current["calls"] = int(current["calls"]) + 1
            current["duration_ms"] = round(float(current["duration_ms"]) + elapsed, 3)


MarketReadModel.connection = _profiled_connection
HistoricalStore.dataset_version = _timed(
    "dataset_version", _stage(
        "dataset_version_lookup",
        _preparation_stage(
            "semantic_marker_read", HistoricalStore.dataset_version,
            gil_heavy=False,
        ),
    ),
)
HistoricalStore.database_uuid = _timed(
    "database_uuid", _stage(
        "database_generation_read",
        _preparation_stage(
            "database_uuid_read", HistoricalStore.database_uuid,
            gil_heavy=False,
        ),
    ),
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
    cache = asset_market_cache.metrics()
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
        "market_build_phase": cache.get("build_phase"),
        "market_last_error": cache.get("last_error"),
        "hydration_stages": {name: dict(value) for name, value in _stages.items()},
        "preparation_active": dict(_preparation_active),
        "preparation_events": [dict(event) for event in _preparation_events],
        **_counters,
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
