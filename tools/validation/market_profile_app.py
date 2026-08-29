"""Validation-only timing wrapper for the production DTOS application."""
from __future__ import annotations

import base64
import asyncio
import contextvars
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, Response
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# Diagnostic comparison only: disable FOIS before importing the application.
if os.getenv("DTOS_VALIDATION_SUPPRESS_FOIS") == "1":
    os.environ["DTOS_FOIS_ENABLED"] = "0"

from config import (
    CACHE_FILE, HISTORY_DATABASE_FILE, HISTORY_STORAGE_ROOT, METADATA_DATABASE_FILE,
)
from dtos_app import app, intelligence_heavy_lock
from services.fois import fois_service
import services.sleeper as sleeper_service
from services.history import _SEASON_SECTION_CACHE, _SEASON_SECTION_CACHE_LOCK
from services.sleeper import LEAGUE_ID, STATE, save_cache
import src.core.asset_market.engine as market_engine
import src.core.asset_market.read_model as market_read_model
from src.core.asset_market.engine import AssetMarket, AssetMarketCache, asset_market_cache
from src.core.asset_market.read_model import MarketReadModel
from src.core.brain import brain_service
from src.core.history_context import (
    CanonicalHistoryStore,
    canonical_history_store as historical_store,
    minimal_metadata_store,
)
from src.core.history_context.guard import legacy_access_guard
from src.core.intelligence_memory import historical_trade_resolution_service
from src.platform.lifecycle import LifecycleCoordinator, lifecycle_coordinator
from src.platform.observability import request_id_context
from tools.validation.generate_sanitized_market_fixture import (
    material_market_fixture_change,
)
from tools.validation.market_semantic_contract import retained_semantic_contract

_profile: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "market_validation_profile", default=None,
)
_counter_lock = threading.Lock()
_preparation_active: dict[str, Any] = {}
_preparation_events: list[dict[str, Any]] = []
_handoff_started: float | None = None
_handoff_trace_id: str | None = None
_response_mode = os.getenv("DTOS_MARKET_PROFILE_MODE", "normal")
_traces: dict[str, list[dict[str, Any]]] = {}
_trace_lock = threading.Lock()
_trace_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "market_trace_id", default=None,
)
_cold_phase_events: list[dict[str, Any]] = []
_cold_phase_active: dict[str, Any] = {}
_cold_started = time.perf_counter()
_historical_resolution_task: asyncio.Task[Any] | None = None
_request_provider_calls: dict[str, int] = {}
_original_sleeper_get = sleeper_service.sleeper_get


async def _tracked_sleeper_get(client: Any, path: str) -> Any:
    request_id = request_id_context.get()
    if request_id != "system":
        with _counter_lock:
            _request_provider_calls[request_id] = _request_provider_calls.get(request_id, 0) + 1
    return await _original_sleeper_get(client, path)


sleeper_service.sleeper_get = _tracked_sleeper_get


def _working_memory() -> int | None:
    try:
        current = int(open("/sys/fs/cgroup/memory.current", encoding="ascii").read())
        values = {}
        with open("/sys/fs/cgroup/memory.stat", encoding="ascii") as handle:
            for line in handle:
                key, value = line.split()
                values[key] = int(value)
        return max(0, current - values.get("inactive_file", 0))
    except (OSError, ValueError):
        return None


def _record_cold_phase(name: str, started: float, **details: Any) -> None:
    event = {
        "name": name,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "cumulative_ms": round((time.perf_counter() - _cold_started) * 1000, 3),
        "effective_working_set_bytes": _working_memory(),
        "thread_name": threading.current_thread().name,
        "background": threading.current_thread() is not threading.main_thread(),
        "active_threads": threading.active_count(),
        **details,
    }
    with _counter_lock:
        _cold_phase_events.append(event)
        del _cold_phase_events[:-128]


def _cold_stage(name: str, function: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        with _counter_lock:
            _cold_phase_active.clear()
            _cold_phase_active.update({"name": name, "started_ms": round(
                (started - _cold_started) * 1000, 3,
            )})
        error = None
        try:
            return function(*args, **kwargs)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            _record_cold_phase(name, started, error=error)
            with _counter_lock:
                _cold_phase_active.clear()
    return wrapped


def _scope_trace_id(scope: dict[str, Any]) -> str | None:
    for name, value in scope.get("headers") or []:
        if name.lower() == b"x-dtos-trace-id":
            return value.decode("ascii", "replace")
    return None


def _trace(name: str, trace_id: str | None = None, **details: Any) -> None:
    identity = trace_id or _trace_context.get()
    if not identity:
        return
    event = {
        "name": name,
        "wall": round(time.perf_counter(), 6),
        "thread_cpu": round(time.thread_time(), 6),
        "thread_id": threading.get_ident(),
        "thread_name": threading.current_thread().name,
        **details,
    }
    with _trace_lock:
        _traces.setdefault(identity, []).append(event)


def _start_market_worker() -> None:
    _trace("deferred_worker_start")
    try:
        asset_market_cache.get(
            STATE.get("data") or {}, STATE, historical_store, LEAGUE_ID,
            background=True,
        )
    except market_engine.MarketWarmingError:
        pass


def _warming_response(*, background: bool = False) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Asset Market generation is building safely in the "
            "background; retry shortly.",
        },
        headers={"Retry-After": "5", "X-DTOS-Market-Refresh": "refreshing"},
        background=BackgroundTask(_start_market_worker) if background else None,
    )


if _response_mode == "prestarted_idle_thread":
    idle = threading.Thread(target=lambda: None, name="dtos-validation-idle")
    idle.start()
    idle.join()


_thread_init = threading.Thread.__init__
_thread_start = threading.Thread.start


def _profiled_thread_init(self: threading.Thread, *args: Any, **kwargs: Any) -> None:
    name = kwargs.get("name")
    if name == "dtos-market-builder":
        _trace("thread_construction_entry")
    _thread_init(self, *args, **kwargs)
    if self.name == "dtos-market-builder":
        _trace("thread_construction_return")


def _profiled_thread_start(self: threading.Thread) -> None:
    if self.name != "dtos-market-builder":
        return _thread_start(self)
    _trace("thread_start_entry")
    _thread_start(self)
    _trace("thread_start_return", started_signal=self._started.is_set())


threading.Thread.__init__ = _profiled_thread_init
threading.Thread.start = _profiled_thread_start
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
        if name in {"request_marker", "market_get", "lifecycle_lock"}:
            _trace(f"{name}_entry")
        try:
            return function(*args, **kwargs)
        finally:
            if name in {"request_marker", "market_get", "lifecycle_lock"}:
                _trace(f"{name}_return")
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
AssetMarketCache._discover_artifact = classmethod(_stage(
    "artifact_compatibility_lookup", _preparation_stage(
        "compatibility_validation", AssetMarketCache._discover_artifact.__func__,
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
    global _handoff_started, _handoff_trace_id
    _trace("start_background_entry")
    _handoff_started = time.perf_counter()
    _handoff_trace_id = _trace_context.get()
    result = _start_background(self, *args, **kwargs)
    _trace("start_background_return")
    return result


def _profiled_background_construct(
    self: AssetMarketCache, *args: Any, **kwargs: Any,
) -> Any:
    global _handoff_started, _handoff_trace_id
    token = _trace_context.set(_handoff_trace_id)
    _trace("worker_bootstrap_entry")
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
    try:
        return _background_construct(self, *args, **kwargs)
    finally:
        _trace("worker_bootstrap_return")
        _trace_context.reset(token)
        _handoff_trace_id = None


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

_build_read_model = market_engine.build_read_model


def _profiled_build_read_model(*args: Any, **kwargs: Any) -> Any:
    observer = kwargs.get("stage_observer")

    def observe(row: dict[str, Any]) -> None:
        _record_cold_phase(
            f"asset_market_{row.get('stage')}", time.perf_counter(),
            measured_duration_ms=row.get("duration_ms"), rows=row.get("rows"),
            memory_before=row.get("memory_before"), memory_after=row.get("memory_after"),
        )
        if observer:
            observer(row)

    kwargs["stage_observer"] = observe
    return _build_read_model(*args, **kwargs)


market_engine.build_read_model = _cold_stage(
    "asset_market_cold_construction", _profiled_build_read_model,
)

_fois_generate = fois_service.generate


async def _profiled_fois_generate(data: dict[str, Any]) -> Any:
    started = time.perf_counter()
    try:
        return await _fois_generate(data)
    finally:
        _record_cold_phase(
            "fois_startup_generation", started,
            suppressed=os.getenv("DTOS_VALIDATION_SUPPRESS_FOIS") == "1",
            records=fois_service.status().get("records", 0),
        )


fois_service.generate = _profiled_fois_generate

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
CanonicalHistoryStore.dataset_version = _timed(
    "dataset_version", _stage(
        "dataset_version_lookup",
        _preparation_stage(
            "semantic_marker_read", CanonicalHistoryStore.dataset_version,
            gil_heavy=False,
        ),
    ),
)
CanonicalHistoryStore.database_uuid = _timed(
    "database_uuid", _stage(
        "database_generation_read",
        _preparation_stage(
            "database_uuid_read", CanonicalHistoryStore.database_uuid,
            gil_heavy=False,
        ),
    ),
)
LifecycleCoordinator.market_build_allowed = _timed(
    "lifecycle_lock", LifecycleCoordinator.market_build_allowed,
)


@app.middleware("http")
async def validation_profile(request: Request, call_next):
    trace_id = request.headers.get("X-DTOS-Trace-ID")
    trace_token = _trace_context.set(trace_id)
    _trace("validation_middleware_entry")
    profile: dict[str, Any] = {}
    token = _profile.set(profile)
    try:
        if request.url.path == "/api/market/assets" and _response_mode in {
            "direct_response", "post_body_worker",
        } and not asset_market_cache.metrics().get("market_generation"):
            _trace("lifecycle_cache_checks")
            if _response_mode == "direct_response":
                _start_market_worker()
                _trace("route_response_construction", mode=_response_mode)
                response = _warming_response()
            else:
                _trace("route_response_construction", mode=_response_mode)
                response = _warming_response(background=True)
        else:
            _trace("call_next_entry")
            response = await call_next(request)
            _trace("call_next_return", status=response.status_code)
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
    response.headers["X-DTOS-Trace-ID"] = trace_id or ""
    _trace("validation_middleware_return", status=response.status_code)
    _trace_context.reset(trace_token)
    return response


@app.get("/__validation__/cold-build-profile")
async def cold_build_profile() -> dict[str, Any]:
    """Return bounded sanitized phase evidence for lifecycle validation."""
    with _counter_lock:
        events = [dict(event) for event in _cold_phase_events]
        active = dict(_cold_phase_active)
    return {
        "fois_suppressed": os.getenv("DTOS_VALIDATION_SUPPRESS_FOIS") == "1",
        "active_phase": active,
        "events": events,
        "market": asset_market_cache.metrics(),
        "fois": fois_service.status(),
    }


@app.post("/__validation__/historical-resolution")
async def historical_resolution() -> dict[str, Any]:
    """Start one real production-shaped durable replay inside the app process."""
    global _historical_resolution_task
    if _historical_resolution_task is not None and not _historical_resolution_task.done():
        return {"started": False, "single_flight": True,
                "health": historical_trade_resolution_service.health()}
    while historical_trade_resolution_service.health().get("status") == "running":
        await asyncio.sleep(0.05)
    started = asyncio.Event()

    async def run() -> None:
        async with intelligence_heavy_lock:
            with lifecycle_coordinator.phase("historical_market_resolution"):
                started.set()
                await asyncio.to_thread(
                    historical_trade_resolution_service.run_safe,
                    historical_store, LEAGUE_ID,
                )

    _historical_resolution_task = asyncio.create_task(
        run(), name="validation-historical-resolution",
    )
    await started.wait()
    return {"started": True, "single_flight": True,
            "health": historical_trade_resolution_service.health()}


@app.get("/__validation__/historical-resolution")
async def historical_resolution_health() -> dict[str, Any]:
    health = historical_trade_resolution_service.health()
    return {
        "active": bool(
            (_historical_resolution_task is not None
             and not _historical_resolution_task.done())
            or health.get("status") == "running"
        ),
        "health": health,
    }


@app.post("/__validation__/nonsemantic-refresh")
async def nonsemantic_refresh(marker: str) -> dict[str, Any]:
    """Change temporal synchronization/history state without market content."""
    before = asset_market_cache.metrics()
    data = STATE.get("data") or {}
    report = data.setdefault("valuation_intelligence", {})
    report["generated_at"] = marker
    STATE["last_sync"] = marker
    minimal_metadata_store.record_sync_generation(LEAGUE_ID, marker)
    return {
        "previous_generation": before.get("market_generation"),
        "previous_build_count": before.get("build_count"),
        "lifecycle": lifecycle_coordinator.snapshot().get("phase"),
    }


@app.post("/__validation__/material-market-change")
async def material_market_change(marker: str) -> dict[str, Any]:
    """Change one attached canonical player value and retain the fixture state."""
    current = STATE.get("data")
    if not isinstance(current, dict):
        raise HTTPException(409, "Canonical fixture data is unavailable.")
    report = current.get("valuation_intelligence") or {}
    target = (report.get("assets") or {}).get("player:10213")
    consumed_attached = brain_service(current).asset("player:10213") is target
    try:
        data, evidence = material_market_fixture_change(current)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    STATE["data"] = data
    save_cache()
    return {
        **evidence, "marker": marker,
        "canonical_path": (
            "valuation_intelligence.assets.player:10213.valuation_layers."
            "contender_value.value"
        ),
        "consumed_attached": consumed_attached,
    }


@app.get("/__validation__/semantic-market-contract")
async def semantic_market_contract() -> dict[str, Any]:
    """Expose retained semantic identities without rebuilding them on request."""
    return retained_semantic_contract(
        asset_market_cache, STATE.get("data") or {}, STATE,
        historical_store, LEAGUE_ID,
    )


@app.get("/__validation__/request-provider-calls")
async def request_provider_calls() -> dict[str, Any]:
    """Expose bounded counts only; never expose provider paths or payloads."""
    with _counter_lock:
        counts = dict(_request_provider_calls)
    return {
        "request_attributed_total": sum(counts.values()),
        "request_count": len(counts),
    }


@app.get("/__validation__/market-artifact")
async def market_artifact() -> dict[str, Any]:
    """Describe the active artifact without exposing its backing directory."""
    with asset_market_cache._lock:
        market = asset_market_cache._market
    if market is None:
        return {"active": False, "final_artifacts": 0, "temporary_artifacts": 0}
    target = market._artifact_path
    pattern = f".{market.store.path.stem}.asset-market-*.sqlite3"
    final_artifacts = list(target.parent.glob(pattern))
    temporary_artifacts = list(target.parent.glob(f".{target.name}.*.partial"))
    metadata = MarketReadModel(target).metadata() if target.is_file() else {}
    return {
        "active": True,
        "artifact_name": target.name,
        "exists": target.is_file(),
        "size_bytes": target.stat().st_size if target.is_file() else 0,
        "final_artifacts": len(final_artifacts),
        "temporary_artifacts": len(temporary_artifacts),
        "complete": metadata.get("complete") is True,
        "generation": metadata.get("generation"),
        "generated_at": metadata.get("generated_at"),
        "schema_version": metadata.get("schema_version"),
        "asset_count": metadata.get("asset_count"),
        "historical_dataset_version": metadata.get("historical_dataset_version"),
    }


@app.get("/__validation__/fixture-contract")
async def fixture_contract() -> dict[str, Any]:
    """Expose relative fixture identities for validation without local paths."""
    root = HISTORY_STORAGE_ROOT.resolve()

    def relative(path) -> str | None:
        try:
            return path.resolve().relative_to(root).as_posix() or "."
        except ValueError:
            return None

    return {
        "storage_root": ".",
        "cache_file": relative(CACHE_FILE),
        "legacy_history_database": relative(HISTORY_DATABASE_FILE),
        "metadata_database": relative(METADATA_DATABASE_FILE),
        "active_store_database": relative(historical_store.path),
        "league_id": LEAGUE_ID,
        "cache_league_id": (
            ((STATE.get("data") or {}).get("league") or {}).get("league_id")
        ),
        "database_identity_digest": market_engine._digest(
            historical_store.database_uuid()
        ),
        "file_identity_digest": hashlib.sha256(
            f"{METADATA_DATABASE_FILE.stat().st_dev}:"
            f"{METADATA_DATABASE_FILE.stat().st_ino}".encode()
        ).hexdigest(),
        "legacy_history_database_size": (
            HISTORY_DATABASE_FILE.stat().st_size if HISTORY_DATABASE_FILE.exists() else 0
        ),
        "metadata_database_size": METADATA_DATABASE_FILE.stat().st_size,
        "cache_exists": CACHE_FILE.is_file(),
        "legacy_history_database_exists": HISTORY_DATABASE_FILE.is_file(),
        "metadata_database_exists": METADATA_DATABASE_FILE.is_file(),
        "active_store_matches": (
            historical_store.path.resolve() == METADATA_DATABASE_FILE.resolve()
        ),
        "contained": all(
            relative(path) is not None
            for path in (
                CACHE_FILE, HISTORY_DATABASE_FILE, METADATA_DATABASE_FILE,
                historical_store.path,
            )
        ),
        "legacy_historical_store": legacy_access_guard.health(),
    }


@app.get("/__validation__/history-cache/clear")
async def clear_history_cache() -> dict[str, int]:
    """Reset only process-local History read models for a genuine cold-read gate."""
    with _SEASON_SECTION_CACHE_LOCK:
        entries = len(_SEASON_SECTION_CACHE)
        _SEASON_SECTION_CACHE.clear()
    return {"cleared_entries": entries}


@app.get("/__validation__/trace/{trace_id}")
async def response_trace(trace_id: str) -> dict[str, Any]:
    with _trace_lock:
        events = [dict(event) for event in _traces.get(trace_id, [])]
    return {"trace_id": trace_id, "mode": _response_mode, "events": events}


_http_handler = app.exception_handlers.get(HTTPException, http_exception_handler)


async def _profiled_http_handler(request: Request, exc: HTTPException) -> Response:
    _trace("http_exception_handler_entry")
    response = await _http_handler(request, exc)
    _trace("http_exception_handler_return", status=response.status_code)
    return response


app.add_exception_handler(HTTPException, _profiled_http_handler)


def _profiled_route_app(route_app: Callable[..., Any]) -> Callable[..., Any]:
    async def wrapped(
        scope: dict[str, Any], receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        _trace("route_entry", route="/api/market/assets")
        try:
            await route_app(scope, receive, send)
        finally:
            _trace("route_return", route="/api/market/assets")
    return wrapped


for _route in app.routes:
    if getattr(_route, "path", None) == "/api/market/assets":
        _route.app = _profiled_route_app(_route.app)


_response_call = Response.__call__


async def _profiled_response_call(
    self: Response, scope: dict[str, Any], receive: Callable[..., Any],
    send: Callable[..., Any],
) -> None:
    trace_id = _scope_trace_id(scope)
    token = _trace_context.set(trace_id)
    _trace("response_call_entry")
    try:
        await _response_call(self, scope, receive, send)
    finally:
        _trace("response_call_return")
        _trace_context.reset(token)


Response.__call__ = _profiled_response_call

_base_middleware_call = BaseHTTPMiddleware.__call__
_cors_middleware_call = CORSMiddleware.__call__


async def _profiled_base_middleware_call(
    self: BaseHTTPMiddleware, scope: dict[str, Any], receive: Callable[..., Any],
    send: Callable[..., Any],
) -> None:
    trace_id = _scope_trace_id(scope)
    token = _trace_context.set(trace_id)
    label = getattr(self.dispatch_func, "__name__", type(self).__name__)
    _trace("middleware_entry", middleware=label)
    try:
        await _base_middleware_call(self, scope, receive, send)
    finally:
        _trace("middleware_return", middleware=label)
        _trace_context.reset(token)


async def _profiled_cors_middleware_call(
    self: CORSMiddleware, scope: dict[str, Any], receive: Callable[..., Any],
    send: Callable[..., Any],
) -> None:
    trace_id = _scope_trace_id(scope)
    token = _trace_context.set(trace_id)
    _trace("middleware_entry", middleware="CORSMiddleware")
    try:
        await _cors_middleware_call(self, scope, receive, send)
    finally:
        _trace("middleware_return", middleware="CORSMiddleware")
        _trace_context.reset(token)


BaseHTTPMiddleware.__call__ = _profiled_base_middleware_call
CORSMiddleware.__call__ = _profiled_cors_middleware_call


class _TraceASGI:
    def __init__(self, wrapped: Any) -> None:
        self.wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        return getattr(self.wrapped, name)

    async def __call__(
        self, scope: dict[str, Any], receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        trace_id = _scope_trace_id(scope)
        if not trace_id or scope.get("path", "").startswith("/__validation__/trace/"):
            await self.wrapped(scope, receive, send)
            return
        token = _trace_context.set(trace_id)
        _trace("asgi_request_entry")

        async def traced_send(message: dict[str, Any]) -> None:
            kind = message.get("type")
            if kind == "http.response.start":
                _trace("asgi_response_start", status=message.get("status"))
            elif kind == "http.response.body":
                _trace(
                    "asgi_response_body", bytes=len(message.get("body") or b""),
                    more=bool(message.get("more_body")),
                )
            await send(message)

        try:
            await self.wrapped(scope, receive, traced_send)
        finally:
            _trace("final_request_completion")
            _trace_context.reset(token)


app = _TraceASGI(app)
