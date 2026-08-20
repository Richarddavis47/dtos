"""DTOS FastAPI application setup and router registration."""
from __future__ import annotations

import asyncio
import hashlib
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from html import escape
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app_metadata import APPLICATION_NAME, VERSION
from config import (
    BACKGROUND_START_DELAY, HISTORY_STORAGE_ROOT, MAX_WARM_LEAGUE_RUNTIMES,
    METADATA_DATABASE_FILE, SYNC_MINUTES,
)
from routes.api import create_api_router
from routes.audit import create_audit_router
from routes.crawl import create_crawl_router
from routes.draft import create_draft_router
from routes.front_offices import create_front_offices_router
from routes.fois import create_fois_router
from routes.hq import create_hq_router
from routes.history import create_history_router
from routes.historical_assets import create_historical_assets_router
from routes.inspect import create_inspection_router
from routes.intelligence_memory import create_intelligence_memory_router
from routes.league_runtime import create_league_runtime_router
from routes.matchups import create_matchups_router
from routes.market import create_market_router
from routes.settings import create_settings_router
from routes.teams import create_teams_router
from routes.trades import create_trades_router
from routes.transactions import create_transactions_router
from routes.valuation import create_valuation_router
from routes.projections import create_projections_router
from services.sleeper import (
    LEAGUE_ID,
    STATE,
    ensure_data_fresh,
    load_cache,
    start_sleeper_sync,
    sync_sleeper,
    sync_sleeper_league,
    sync_transactions,
)
from services.history import (
    direct_fetch,
    history_progress_contracts,
    start_background_backfill,
)
from services.fois import fois_service
from src.core.fois import FOIS_MODEL_VERSION
from src.core.asset_market import AssetMarketCache, asset_market_cache
from src.core.asset_market.resource_diagnostics import (
    disk_health, resource_diagnostics, runtime_component_sizes,
)
from src.core.league_runtime import (
    CanonicalLeagueContext, LeagueRuntime, LeagueRuntimeManager, RuntimeState,
)
from src.core.brain import BrainService
from src.core.history_context import (
    canonical_history_store, legacy_access_guard, minimal_metadata_store,
)
from src.core.projection_intelligence import projection_service
from src.core.projection_intelligence.service import ProjectionService
from src.core.intelligence_memory import historical_trade_resolution_service
from src.platform.observability import (
    install_observability,
    mark_startup_complete,
    monitor_event_loop_lag,
    runtime_metrics,
)
from src.platform.market_warming import AssetMarketWarmingMiddleware
from src.platform.lifecycle import lifecycle_coordinator
from src.platform.league_context import (
    LeagueContextMiddleware, RuntimeStateProxy, current_league_context,
)
from config import DURABLE_HISTORY_REQUIRED
from src.core.historical_memory.storage import validate_historical_storage
from src.core.inspection.live import LiveInspection
from src.core.inspection.live_visual import LiveVisualService, live_visual_capture_requests
from src.core.inspection.current_visual import CurrentVisualMirror
from src.core.intelligence_memory import (
    intelligence_checkpoint_store, sleeper_season_cache,
)
from src.ui import DESIGN_SYSTEM_CSS, page_header

historical_storage_status = validate_historical_storage(
    database=METADATA_DATABASE_FILE, root=HISTORY_STORAGE_ROOT,
    required=DURABLE_HISTORY_REQUIRED,
)

_PROCESS_STARTED = perf_counter()
_INSPECTION_REQUEST: ContextVar[bool] = ContextVar("dtos_inspection_request", default=False)
_CAPTURE_URL = os.getenv(
    "DTOS_CAPTURE_URL", f"http://127.0.0.1:{os.getenv('PORT', '8000')}",
).rstrip("/")
_MULTI_LEAGUE_IMPORT_ENABLED = (
    os.getenv("DTOS_MULTI_LEAGUE_IMPORT_ENABLED", "0").strip().casefold()
    in {"1", "true", "yes", "on"}
)
intelligence_heavy_lock = asyncio.Lock()


async def _generate_fois_coordinated(data: dict[str, Any]) -> tuple[Any, ...]:
    """Run FOIS as one lifecycle-heavy flight without overlapping other phases."""
    async with intelligence_heavy_lock:
        await asyncio.to_thread(lifecycle_coordinator.reserve_fois_generation)
        try:
            return await fois_service.generate(data)
        finally:
            lifecycle_coordinator.release_fois_generation()


def _publish_runtime_context(
    runtime: LeagueRuntime, projections: ProjectionService,
) -> CanonicalLeagueContext:
    """Publish one complete canonical consumer context atomically."""
    data = runtime.state.get("data") or {}
    brain = BrainService(data)
    market = runtime.market_context or AssetMarketCache(
        resource_context_provider=_resource_context_snapshot,
    )
    context = CanonicalLeagueContext(
        runtime=runtime,
        historical_store=canonical_history_store,
        projection=projections,
        brain=brain,
        market=market,
        fois_state=(
            "ready" if fois_service.repository.league(
                runtime.league_id, FOIS_MODEL_VERSION,
            ) else "pending"
        ),
    )
    runtime.projection_context = projections
    runtime.brain_context = brain
    runtime.market_context = market
    runtime.fois_context = fois_service
    context.refresh_generations()
    runtime.canonical_context = context
    return context


async def _hydrate_league_runtime(runtime: LeagueRuntime) -> dict[str, Any]:
    """Hydrate one requested league without replacing the configured default."""
    projections = ProjectionService(league_id=runtime.league_id)
    await sync_sleeper_league(
        runtime.league_id, runtime.state, force_players=False,
        projections=projections,
    )
    data = runtime.state.get("data") or {}
    runtime.apply_data(data)
    projections = ProjectionService(
        league_id=runtime.league_id,
        scoring_profile_id=runtime.scoring_profile,
    )
    projections.restore_into(data)
    await _generate_fois_coordinated(data)
    _publish_runtime_context(runtime, projections)
    return data


league_runtime_manager = LeagueRuntimeManager(
    max_warm=MAX_WARM_LEAGUE_RUNTIMES,
    hydrator=_hydrate_league_runtime,
)
default_league_runtime = league_runtime_manager.attach_default(
    LEAGUE_ID, STATE, warm=bool(STATE.get("data")),
)
# The configured league predates LeagueRuntimeManager and already has one
# canonical, durable Asset Market cache.  Its request context must expose that
# same object so artifact restoration and route serving share one owner.
default_league_runtime.market_context = asset_market_cache
runtime_state = RuntimeStateProxy(STATE)


def _resource_context_snapshot() -> dict[str, Any]:
    lifecycle = lifecycle_coordinator.snapshot()
    manager = league_runtime_manager.health()
    background = runtime_metrics.health().get("background_tasks") or {}
    return {
        "cgroup_limit_bytes": (lifecycle.get("memory") or {}).get("cgroup_limit_bytes"),
        "runtime_count": manager["resident_runtime_count"],
        "warm_runtime_count": manager["warm_runtime_count"],
        "lifecycle_phase": lifecycle["phase"],
        "startup_fence_state": lifecycle["startup_fence"]["state"],
        "synchronization_state": background.get("sleeper_sync", "idle"),
        "background_work": {
            str(name): str(status) for name, status in background.items()
        },
    }


asset_market_cache.configure_resource_context_provider(_resource_context_snapshot)


def _resource_health() -> dict[str, Any]:
    manager = league_runtime_manager.health()
    storage = disk_health(canonical_history_store.path)
    caches = [
        runtime.market_context
        for runtime in league_runtime_manager.resident_runtimes()
        if runtime.market_context is not None
    ]
    return {
        "status": storage["status"],
        "resident_runtime_count": manager["resident_runtime_count"],
        "warm_runtime_count": manager["warm_runtime_count"],
        "warm_runtime_limit": manager["warm_runtime_limit"],
        "cache_count": len(caches),
        "artifact_cleanup": {
            "removed": sum(getattr(cache, "artifact_cleanup_count", 0) for cache in caches),
            "failures": sum(getattr(cache, "artifact_cleanup_failures", 0) for cache in caches),
        },
        "admission": resource_diagnostics.health(),
        "storage": storage,
        "intelligence_memory": intelligence_checkpoint_store.health(),
        "sleeper_season_cache": sleeper_season_cache.health(),
    }


def _measure_resources() -> dict[str, Any]:
    measurements = [
        runtime_component_sizes(runtime)
        for runtime in league_runtime_manager.resident_runtimes()
    ]
    return {
        "status": "complete",
        "runtime_count": len(measurements),
        "runtimes": measurements,
        "storage": disk_health(canonical_history_store.path),
        "minimal_metadata": minimal_metadata_store.health(),
        "legacy_historical_store": legacy_access_guard.health(),
    }


def _capture_live_visual(request: Any, output: Any) -> dict[str, Any]:
    """Keep browser control outside the request-serving Python interpreter."""
    from src.core.inspection.live_capture_process import capture_page_isolated

    return capture_page_isolated(_CAPTURE_URL, request, output)


live_visual_service = LiveVisualService(
    HISTORY_STORAGE_ROOT / "live_visual" / (
        "league-" + hashlib.sha256(str(LEAGUE_ID).encode()).hexdigest()[:16]
    ),
    _capture_live_visual if os.getenv("RENDER") or os.getenv("DTOS_LIVE_VISUAL_CAPTURE") else None,
    start_grace_seconds=2.0,
)
current_visual_mirror = CurrentVisualMirror(
    live_visual_service.root / "current_mirror", live_visual_service,
)
def _complete_live_visual_capture() -> None:
    try:
        current_visual_mirror.promote()
    except Exception:
        runtime_metrics.mark_background("live_visual_capture", "failed")
        raise
    runtime_metrics.mark_background("live_visual_capture", "complete")


live_visual_service.on_complete(_complete_live_visual_capture)


def schedule_live_visual_capture() -> int:
    """Queue semantic changes after canonical maintenance; never block readiness."""
    if not STATE.get("data"):
        return 0
    if not lifecycle_coordinator.startup_complete():
        runtime_metrics.mark_background("live_visual_capture", "waiting")
        return 0
    market = asset_market_cache.current()
    market_health = asset_market_cache.metrics()
    if (
        market is None
        or market_health.get("status") != "ready"
    ):
        runtime_metrics.mark_background("live_visual_capture", "waiting")
        return 0
    inspector = LiveInspection(
        state=STATE, routes=app.routes, league_id=LEAGUE_ID,
        projection_snapshot=projection_service.snapshot(),
        market=market, fois_scores=(),
    )
    requests = live_visual_capture_requests(inspector)
    queued = live_visual_service.schedule(requests)
    runtime_metrics.mark_background("live_visual_capture", "running" if queued else "complete")
    return queued


asset_market_cache.on_publish(schedule_live_visual_capture)


async def ensure_fresh() -> None:
    context = current_league_context()
    if context is not None and context.league_id != LEAGUE_ID:
        return
    if _INSPECTION_REQUEST.get():
        return
    if not lifecycle_coordinator.startup_complete():
        return
    await ensure_data_fresh()


async def background_sync() -> None:
    while True:
        await asyncio.sleep(SYNC_MINUTES * 60)
        await start_sleeper_sync()
        projection_status = projection_service.health().get("status")
        runtime_metrics.mark_background(
            "projection_generation",
            "complete" if projection_status in {"ready", "stale"} else "failed",
        )
        if STATE.get("data"):
            runtime_metrics.mark_background("fois_generation", "running")
            try:
                await _generate_fois_coordinated(STATE["data"])
            except Exception:
                runtime_metrics.mark_background("fois_generation", "failed")
        else:
            runtime_metrics.mark_background("fois_generation", "complete")
        asset_market_cache.reconcile(
            STATE.get("data") or {}, STATE, canonical_history_store, LEAGUE_ID,
        )
        schedule_live_visual_capture()


async def resolve_historical_trade_market() -> None:
    """Run event-driven provider matching only after the first Market is stable."""
    runtime_metrics.mark_background("historical_market_resolution", "waiting")
    for _ in range(300):
        metrics = asset_market_cache.metrics()
        if metrics.get("status") == "ready" and not metrics.get("build_active"):
            break
        await asyncio.sleep(1)
    else:
        runtime_metrics.mark_background("historical_market_resolution", "deferred")
        return
    runtime_metrics.mark_background("historical_market_resolution", "running")
    async with intelligence_heavy_lock:
        with lifecycle_coordinator.phase("historical_market_resolution"):
            result = await asyncio.to_thread(
                historical_trade_resolution_service.run_safe,
                canonical_history_store, LEAGUE_ID,
            )
    runtime_metrics.mark_background(
        "historical_market_resolution", "complete" if result else "failed",
    )
    if result:
        runtime_metrics.mark_background("fois_generation", "running")
        try:
            await _generate_fois_coordinated(STATE["data"])
        except Exception:
            runtime_metrics.mark_background("fois_generation", "failed")
        else:
            runtime_metrics.mark_background("fois_generation", "complete")


async def deployment_maintenance(startup_epoch: int | None = None) -> None:
    """Start required data promptly and defer optional cached maintenance."""
    epoch = startup_epoch or lifecycle_coordinator.begin_startup(
        "Validating durable storage and cached canonical state."
    )
    cached_generation_available = bool(STATE.get("data"))
    if not historical_storage_status.healthy:
        runtime_metrics.mark_not_ready(historical_storage_status.reason)
        runtime_metrics.mark_background("historical_storage", "failed")
        lifecycle_coordinator.fail_startup(epoch, historical_storage_status.reason)
        return
    runtime_metrics.mark_background("historical_storage", "ready")
    if STATE.get("data"):
        runtime_metrics.mark_ready("Cached league data loaded.")
        runtime_metrics.mark_background("deployment_delay", "waiting")
        await asyncio.sleep(BACKGROUND_START_DELAY)
        lifecycle_coordinator.update_startup(
            epoch, "Synchronizing canonical Sleeper and provider state."
        )
        runtime_metrics.mark_background("sleeper_sync", "running")
        sleeper_task = start_sleeper_sync()
        await asyncio.gather(sleeper_task, return_exceptions=True)
        runtime_metrics.mark_background("sleeper_sync", "complete")
    else:
        runtime_metrics.mark_not_ready("Waiting for the initial Sleeper dataset.")
        runtime_metrics.mark_background("sleeper_sync", "running")
        await start_sleeper_sync(force_players=True)
        runtime_metrics.mark_background("sleeper_sync", "complete")
        if not STATE.get("data"):
            runtime_metrics.mark_not_ready(
                "Initial Sleeper synchronization did not produce league data."
            )
            lifecycle_coordinator.fail_startup(
                epoch, "Initial Sleeper synchronization produced no league data."
            )
            return
        runtime_metrics.mark_ready("Initial Sleeper dataset loaded.")
        await asyncio.sleep(BACKGROUND_START_DELAY)

    if STATE.get("last_error"):
        if not cached_generation_available or not STATE.get("data"):
            reason = "Canonical Sleeper synchronization did not complete successfully."
            runtime_metrics.mark_not_ready(reason)
            lifecycle_coordinator.fail_startup(epoch, reason)
            return
        lifecycle_coordinator.update_startup(
            epoch,
            "Refresh reached a terminal failure; retaining the cached canonical generation.",
        )

    runtime_metrics.mark_background("deployment_delay", "complete")
    lifecycle_coordinator.update_startup(
        epoch, "Completing bounded historical maintenance."
    )
    runtime_metrics.mark_background("history_backfill", "running")
    history_task = start_background_backfill(direct_fetch)
    history_results = await asyncio.gather(history_task, return_exceptions=True)
    history_result = history_results[0]
    if isinstance(history_result, BaseException):
        runtime_metrics.mark_background("history_backfill", "failed")
    else:
        runtime_metrics.mark_background(
            "history_backfill",
            "complete" if history_result.get("status") == "complete" else "partial",
        )
    await asyncio.to_thread(history_progress_contracts, LEAGUE_ID)
    projection_status = projection_service.health().get("status")
    runtime_metrics.mark_background(
        "projection_generation",
        "complete" if projection_status in {"ready", "stale"} else "failed",
    )
    runtime_metrics.mark_background("fois_generation", "running")
    try:
        await _generate_fois_coordinated(STATE["data"])
    except Exception:
        # FOIS is an optional persisted intelligence projection. Its failure is
        # observable, but cannot hold canonical readiness or Asset Market idle.
        runtime_metrics.mark_background("fois_generation", "failed")
    else:
        runtime_metrics.mark_background("fois_generation", "complete")
    startup_reason = (
        "Cached canonical generation established after refresh reached a terminal failure."
        if STATE.get("last_error")
        else "Canonical startup generation established."
    )
    lifecycle_coordinator.complete_startup(epoch, startup_reason)
    asset_market_cache.reconcile(
        STATE.get("data") or {}, STATE, canonical_history_store, LEAGUE_ID,
    )
    schedule_live_visual_capture()


async def startup_and_periodic_maintenance(startup_epoch: int) -> None:
    """Complete one startup epoch before beginning the refresh interval."""
    try:
        await deployment_maintenance(startup_epoch)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        lifecycle_coordinator.fail_startup(
            startup_epoch,
            f"Canonical startup failed: {type(exc).__name__}.",
        )
        runtime_metrics.mark_not_ready(
            f"Canonical startup failed: {type(exc).__name__}."
        )
        return
    if lifecycle_coordinator.startup_complete():
        resolution_task = asyncio.create_task(
            resolve_historical_trade_market(),
            name="dtos-historical-trade-market-resolution",
        )
        try:
            await background_sync()
        finally:
            resolution_task.cancel()
            await asyncio.gather(resolution_task, return_exceptions=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    event_loop_monitor = asyncio.create_task(
        monitor_event_loop_lag(), name="dtos-event-loop-lag-monitor",
    )
    runtime_metrics.mark_not_ready("Loading cached league data.")
    startup_epoch = lifecycle_coordinator.begin_startup(
        "Loading cached canonical state."
    )
    if not historical_storage_status.healthy:
        runtime_metrics.mark_not_ready(historical_storage_status.reason)
        lifecycle_coordinator.fail_startup(
            startup_epoch, historical_storage_status.reason,
        )
        mark_startup_complete(_PROCESS_STARTED)
        try:
            yield
        finally:
            event_loop_monitor.cancel()
            await asyncio.gather(event_loop_monitor, return_exceptions=True)
        return
    load_cache()
    default_runtime = league_runtime_manager.resident(LEAGUE_ID)
    if default_runtime is not None and STATE.get("data"):
        default_runtime.apply_data(STATE["data"])
        default_runtime.status = RuntimeState.WARM
    if STATE.get("data"):
        projection_service.restore_into(STATE["data"])
        if default_runtime is not None:
            _publish_runtime_context(default_runtime, projection_service)
        await asyncio.to_thread(asset_market_cache.cleanup_artifacts, canonical_history_store)
        await asyncio.to_thread(
            asset_market_cache.restore_compatible,
            STATE["data"], STATE, canonical_history_store, LEAGUE_ID,
        )
    await asyncio.to_thread(history_progress_contracts, LEAGUE_ID)
    mark_startup_complete(_PROCESS_STARTED)
    if STATE.get("data"):
        runtime_metrics.mark_ready("Cached league data loaded.")
    else:
        runtime_metrics.mark_not_ready(
            "Waiting for the initial Sleeper dataset."
        )
    maintenance_task = asyncio.create_task(
        startup_and_periodic_maintenance(startup_epoch),
        name="dtos-deployment-maintenance",
    )
    try:
        yield
    finally:
        maintenance_task.cancel()
        event_loop_monitor.cancel()
        await asyncio.gather(
            maintenance_task, event_loop_monitor,
            return_exceptions=True,
        )
        await league_runtime_manager.shutdown()


app = FastAPI(title=APPLICATION_NAME, version=VERSION, lifespan=lifespan)
app.add_middleware(
    LeagueContextMiddleware,
    manager=league_runtime_manager,
    default_league_id=LEAGUE_ID,
    import_enabled=_MULTI_LEAGUE_IMPORT_ENABLED,
)
app.add_middleware(
    AssetMarketWarmingMiddleware,
    cache=asset_market_cache,
    data_provider=lambda: STATE.get("data") or {},
    state=STATE,
    store=canonical_history_store,
    league_id=LEAGUE_ID,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-DTOS-Diagnostics"],
)
install_observability(app)


@app.middleware("http")
async def deterministic_inspection_mode(request: Any, call_next: Any) -> Any:
    """Make browser audits cached-only without changing ordinary requests."""
    enabled = request.headers.get("X-DTOS-Inspection", "").casefold() == "deterministic"
    token = _INSPECTION_REQUEST.set(enabled)
    try:
        response = await call_next(request)
        if enabled:
            response.headers["X-DTOS-Inspection-Mode"] = "deterministic"
        return response
    finally:
        _INSPECTION_REQUEST.reset(token)


CSS = """
:root{color-scheme:dark;--bg:#07111f;--panel:#101d2d;--line:#26374c;--text:#f5f7fb;--muted:#9fb0c6;--accent:#6ee7b7;--gold:#f5c451}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#07111f,#0b1727);color:var(--text);font-family:Inter,system-ui,-apple-system,sans-serif}
a{color:inherit;text-decoration:none}.wrap{max-width:1180px;margin:auto;padding:20px}.top{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:20px}
.brand h1{margin:0;font-size:28px}.brand p{margin:4px 0;color:var(--muted)}.btn{border:0;border-radius:10px;padding:11px 15px;background:var(--accent);color:#062018;font-weight:800;cursor:pointer}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.nav a{padding:9px 12px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:rgba(16,29,45,.94);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 10px 25px rgba(0,0,0,.15)}.card h2,.card h3{margin-top:0}.muted{color:var(--muted)}.good{color:var(--accent)}.warn{color:#fca5a5}
.stat{font-size:27px;font-weight:850}.team{margin-bottom:14px}.record{color:var(--gold);font-weight:800}.players{display:grid;gap:5px}.player{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid rgba(38,55,76,.65)}.starter{font-weight:800}.pill{font-size:12px;padding:3px 7px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.team-link{display:block;transition:transform .15s ease,border-color .15s ease}.team-link:hover{transform:translateY(-2px);border-color:#3d5877}.team-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.rank-badge{min-width:38px;height:38px;border-radius:12px;background:#182a40;border:1px solid var(--line);display:grid;place-items:center;font-weight:900;color:var(--gold)}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.metric{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:10px}.metric b{display:block;font-size:17px}.metric span{font-size:11px;color:var(--muted)}.roster-section{margin-top:18px}.section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.slot-label{font-size:12px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.back{display:inline-block;margin-bottom:14px;color:var(--accent)}.pick-year{margin-top:14px}.pick-list{display:grid;gap:7px}.pick-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 0;border-top:1px solid rgba(38,55,76,.65)}.pick-origin{font-size:12px;color:var(--muted)}.away{color:#fca5a5}

.identity-kicker{font-size:12px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.09em}.franchise-name{margin:3px 0 0}.owner-line{margin:8px 0 0;color:var(--muted)}
.fois-leaderboard{display:grid;gap:10px;margin-top:14px}.fois-leader{display:grid;grid-template-columns:72px minmax(170px,1.2fr) 110px minmax(180px,1fr) minmax(180px,1fr) auto;gap:14px;align-items:center}.fois-rank b{display:block;font-size:28px;color:var(--gold)}.fois-rank span,.fois-score span,.fois-evidence span{display:block;font-size:11px;color:var(--muted)}.fois-score b{display:block;font-size:28px}.fois-score span{font-size:16px;font-weight:800;color:var(--gold)}.fois-evidence b{display:block;color:var(--accent)}
.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.summary-grid .metric{min-height:66px}.analytics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.analytics-card{background:linear-gradient(180deg,#122238,#0b1727);border:1px solid var(--line);border-radius:12px;padding:12px}.analytics-card b{display:block;font-size:18px}.analytics-card span{font-size:11px;color:var(--muted)}
.position-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}.position-count{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:9px;text-align:center}.position-count b{display:block;font-size:18px}.position-count span{font-size:11px;color:var(--muted)}
.position-block{margin-top:10px}.position-head{display:flex;justify-content:space-between;align-items:center;padding:8px 2px;color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.player-name{display:flex;align-items:center;gap:8px}.pos-dot{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px rgba(110,231,183,.10)}
.pick-row.own{border-left:3px solid var(--accent);padding-left:10px}.pick-row.acquired{border-left:3px solid #60a5fa;padding-left:10px}.pick-row.traded-away{border-left:3px solid #f87171;padding-left:10px}.pick-status{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.pick-status.own{color:var(--accent)}.pick-status.acquired{color:#93c5fd}.pick-status.away{color:#fca5a5}

.team-report{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.report-card{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:12px;padding:12px}.report-card .grade{font-size:26px;font-weight:900;color:var(--gold)}.report-card small{display:block;color:var(--muted);margin-top:4px}
.progress-row{margin-top:10px}.progress-label{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;margin-bottom:5px}.progress-track{height:8px;background:#07111f;border:1px solid var(--line);border-radius:999px;overflow:hidden}.progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),#60a5fa);border-radius:999px}
details.pick-year{margin-top:12px}.pick-summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;background:#101d2d;border:1px solid var(--line);border-radius:12px;padding:12px 14px}.pick-summary::-webkit-details-marker{display:none}.pick-summary:after{content:"＋";color:var(--accent);font-size:18px}.pick-year[open] .pick-summary:after{content:"−"}.pick-year .pick-list{border-top-left-radius:0;border-top-right-radius:0;margin-top:-1px}
.sleeper-lineup{display:grid;gap:8px}.lineup-row{display:grid;grid-template-columns:56px 1fr;gap:8px;align-items:stretch}.lineup-slot{display:grid;place-items:center;background:#0b1727;border:1px solid var(--line);border-radius:10px;font-size:11px;font-weight:900;color:var(--accent)}.lineup-player{display:flex;justify-content:space-between;align-items:center;gap:10px;background:#101d2d;border:1px solid var(--line);border-radius:10px;padding:10px 12px}.lineup-player b{font-size:14px}.lineup-meta{font-size:11px;color:var(--muted);text-align:right}.lineup-empty{color:var(--muted);font-style:italic}
.owner-primary{font-size:13px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.08em}.franchise-secondary{color:var(--muted);font-size:13px;margin-top:3px}

.matchup-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.matchup-card{display:block;background:linear-gradient(180deg,#122238,#0d1a2a);border:1px solid var(--line);border-radius:16px;padding:16px;transition:transform .15s ease,border-color .15s ease}.matchup-card:hover{transform:translateY(-2px);border-color:#3d5877}.matchup-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.matchup-number{font-size:12px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.08em}.matchup-status{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:4px 8px}.versus{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.matchup-team{text-align:left}.matchup-team.right{text-align:right}.matchup-team h3{margin:3px 0 2px;font-size:18px}.matchup-owner{font-size:12px;color:var(--muted)}.score{font-size:30px;font-weight:900;margin-top:8px}.vs-mark{color:var(--muted);font-size:12px;font-weight:900}.matchup-footer{display:flex;justify-content:space-between;gap:10px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}.edge{color:var(--gold);font-weight:900}.matchup-hero{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:16px;padding:18px}.scoreboard{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.scoreboard-side.right{text-align:right}.scoreboard-score{font-size:42px;font-weight:950}.scoreboard-team{font-size:20px;font-weight:900}.battle-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.battle-card{background:#101d2d;border:1px solid var(--line);border-radius:14px;padding:12px;overflow:hidden}.battle-card h3{margin:0 0 10px;font-size:13px;color:var(--accent);letter-spacing:.08em;text-transform:uppercase}.battle-head{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);align-items:center;gap:8px}.battle-side{min-width:0;border:1px solid rgba(38,55,76,.8);border-radius:11px;padding:11px 9px;background:#0b1727;text-align:left}.battle-side.right{text-align:right}.battle-side.winning{border-color:rgba(110,231,183,.8);box-shadow:inset 0 0 0 1px rgba(110,231,183,.18)}.battle-side.losing{border-color:rgba(248,113,113,.55)}.battle-side.tied{border-color:var(--line)}.battle-side.vacant{border-style:dashed;opacity:.72}.battle-owner{font-size:9px;font-weight:900;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.battle-player b{display:block;font-size:14px;line-height:1.15;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.battle-player span{display:block;font-size:10px;color:var(--muted);margin-top:3px}.battle-points{font-size:18px;font-weight:950;margin-top:8px}.battle-points small{display:block;font-size:8px;color:var(--muted);text-transform:uppercase}.starter-projections{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:8px}.starter-projections>span{display:block;background:#13243a;border-radius:7px;padding:5px}.starter-projections small{display:block;font-size:7px;color:var(--muted);line-height:1.2}.starter-projections b{display:block;font-size:13px;margin-top:2px}.starter-projections .projection-difference{grid-column:1/-1;background:transparent;padding:2px;color:var(--accent);font-size:9px;font-weight:800}.starter-projections.unavailable{display:block;color:var(--muted);font-size:10px}.starter-projections details{margin-top:4px;font-size:8px}.battle-vs{display:grid;place-items:center;color:var(--muted);font-size:10px;font-weight:950}.battle-result{display:block;font-size:8px;margin-top:4px;text-transform:uppercase;letter-spacing:.08em}.winning .battle-result{color:var(--accent)}.losing .battle-result{color:#fca5a5}.tied .battle-result{color:var(--muted)}.matchup-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.leader-banner{margin-top:14px;padding:10px 12px;border-radius:10px;background:#0b1727;border:1px solid var(--line);color:var(--muted)}.advantage-strip{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;margin-top:14px}.advantage-side{background:#0b1727;border:1px solid var(--line);border-radius:12px;padding:10px 12px}.advantage-side.right{text-align:right}.advantage-side b{display:block;font-size:20px}.advantage-side span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.advantage-center{text-align:center;color:var(--muted);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.bench-compare{display:grid;gap:8px}.bench-row{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);gap:8px;align-items:stretch}.bench-player{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:9px;min-width:0}.bench-player.right{text-align:right}.bench-player.leading{border-color:rgba(110,231,183,.72)}.bench-player.trailing{border-color:rgba(248,113,113,.48)}.bench-player.empty{border-style:dashed;opacity:.68}.bench-player b{display:block;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bench-player span{display:block;color:var(--muted);font-size:9px;margin-top:3px}.bench-player strong{display:block;font-size:15px;margin-top:6px}.bench-vs{display:grid;place-items:center;color:var(--muted);font-size:9px;font-weight:900}.bench-total-card{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:14px;padding:12px;margin-bottom:10px}.bench-total-grid{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center}.bench-total-side.right{text-align:right}.bench-total-side b{display:block;font-size:24px}.bench-total-side span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.edge-badge{display:inline-block;margin-top:8px;padding:4px 8px;border-radius:999px;border:1px solid var(--line);font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.07em}.edge-badge.good{border-color:rgba(110,231,183,.55);background:rgba(110,231,183,.08)}.edge-badge.warn{border-color:rgba(248,113,113,.45);background:rgba(248,113,113,.07)}.edge-badge.tie{color:var(--muted)}
.matchup-hero.leading-left{border-color:rgba(110,231,183,.52);box-shadow:0 14px 34px rgba(0,0,0,.18),inset 3px 0 0 rgba(110,231,183,.75)}
.matchup-hero.leading-right{border-color:rgba(96,165,250,.52);box-shadow:0 14px 34px rgba(0,0,0,.18),inset -3px 0 0 rgba(96,165,250,.75)}
.matchup-hero.tied-game{box-shadow:0 14px 34px rgba(0,0,0,.16)}
.leader-banner.leading{border-color:rgba(110,231,183,.50);background:linear-gradient(90deg,rgba(110,231,183,.11),rgba(11,23,39,.96));color:var(--text)}
.leader-banner.tied{background:linear-gradient(90deg,rgba(159,176,198,.08),rgba(11,23,39,.96))}
.live-share{margin-top:12px}.live-share-head{display:flex;justify-content:space-between;gap:12px;font-size:10px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.07em}.live-share-track{height:8px;margin-top:6px;background:#07111f;border:1px solid var(--line);border-radius:999px;overflow:hidden;display:flex}.live-share-left{height:100%;background:linear-gradient(90deg,var(--accent),#34d399)}.live-share-right{height:100%;background:linear-gradient(90deg,#60a5fa,#93c5fd)}
.battle-card{box-shadow:0 8px 20px rgba(0,0,0,.10)}.battle-card.top-battle{border-color:rgba(245,196,81,.58);box-shadow:0 0 0 1px rgba(245,196,81,.08),0 10px 24px rgba(0,0,0,.14)}
.top-performer{position:relative}.top-performer:after{content:"TOP STARTER";display:inline-block;margin-top:7px;padding:3px 6px;border-radius:999px;border:1px solid rgba(245,196,81,.5);background:rgba(245,196,81,.08);color:var(--gold);font-size:7px;font-weight:950;letter-spacing:.08em}
.scoreboard-side.leading .scoreboard-score{color:var(--accent);text-shadow:0 0 18px rgba(110,231,183,.16)}.scoreboard-side.trailing{opacity:.84}.scoreboard-side.right.leading .scoreboard-score{color:#93c5fd;text-shadow:0 0 18px rgba(96,165,250,.16)}
@media(max-width:600px){.versus,.scoreboard{grid-template-columns:1fr auto 1fr;gap:8px}.score{font-size:24px}.scoreboard-score{font-size:32px}.scoreboard-team{font-size:16px}.matchup-summary-grid{grid-template-columns:repeat(2,1fr)}.battle-grid{grid-template-columns:1fr}.battle-card{padding:9px}.battle-head{grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr);gap:5px}.battle-side{padding:8px 7px}.battle-player b{font-size:13px}.battle-owner{font-size:8px}.battle-points{font-size:17px}.bench-row{grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr);gap:5px}.bench-player{padding:8px 6px}.bench-player b{font-size:11px}.bench-total-side b{font-size:20px}}
@media(max-width:760px){.summary-grid{grid-template-columns:repeat(2,1fr)}.team-report{grid-template-columns:repeat(2,1fr)}.analytics-grid{grid-template-columns:repeat(2,1fr)}.position-strip{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.fois-leader{grid-template-columns:58px minmax(0,1fr) 78px;gap:9px}.fois-leader .fois-evidence,.fois-leader>div:nth-of-type(5),.fois-leader .ds-action{grid-column:2/4}.fois-rank b,.fois-score b{font-size:23px}.fois-leader h3{font-size:16px;margin-bottom:2px}.fois-leader .ds-action{text-align:center}.fois-leader{overflow:hidden}}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word}.footer{color:var(--muted);font-size:13px;padding:24px 0}.error{background:#3b1720;border:1px solid #7f1d1d;padding:12px;border-radius:10px;margin-bottom:15px}@media(max-width:600px){.wrap{padding:14px}.card{padding:13px}th,td{padding:7px;font-size:13px}}
"""
CSS += DESIGN_SYSTEM_CSS


def page(title: str, body: str, commissioner_chrome: bool = False) -> HTMLResponse:
    context = current_league_context()
    selected_state = context.state if context is not None else STATE
    sync = selected_state.get("last_sync") or "Never"
    error = selected_state.get("last_error")
    error_html = f'<div class="error"><b>Sync error:</b> {escape(error)}</div>' if error else ""
    league_name = str(((selected_state.get("data") or {}).get("league") or {}).get("name") or "Sleeper League")
    standard_chrome = f"""<header class="top"><div class="brand"><h1>{APPLICATION_NAME}</h1><p>{escape(league_name)} Front Office</p></div><form method="post" action="/sync"><button class="btn" type="submit">Sync League</button></form></header>
<nav class="nav" aria-label="Primary navigation"><a href="/market">Market</a><a href="/commissioner">Commissioner</a><a href="/teams">Team HQ</a><a href="/trades">Trade Center</a><a href="/matchups">Matchups</a><a href="/transactions">Transactions</a><a href="/picks">Draft Capital</a><a href="/history">History</a><a href="/search">Search</a><a href="/front-offices">Front Office</a><a href="/fois">FOIS</a><a href="/brain">Brain</a><a href="/valuation/calibration">Calibration</a><a href="/settings">Settings</a></nav>{page_header(title, league_name=league_name, last_updated=str(sync))}"""
    footer = f'<footer class="footer"><b>League Sync:</b> {escape(str(sync))} · Intelligence is generated from the latest cached league state. Automatic refresh every {SYNC_MINUTES} minutes while service is active.</footer>'
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · {APPLICATION_NAME}</title><style>{CSS}</style></head>
<body><main class="wrap">{"" if commissioner_chrome else standard_chrome}{error_html}{body}{"" if commissioner_chrome else footer}</main></body></html>"""
    return HTMLResponse(html)


def require_data() -> dict[str, Any]:
    context = current_league_context()
    data = context.data if context is not None else STATE.get("data") or {}
    if not data:
        raise HTTPException(503, "DTOS has not completed its first Sleeper sync.")
    return data


def current_league_id() -> str:
    context = current_league_context()
    return context.league_id if context is not None else LEAGUE_ID


async def sync_current_league(*, force_players: bool = False) -> dict[str, Any]:
    context = current_league_context()
    if context is None or context.league_id == LEAGUE_ID:
        return await sync_sleeper(force_players=force_players)
    return await _hydrate_league_runtime(context.runtime)


async def sync_current_transactions() -> bool:
    context = current_league_context()
    if context is None or context.league_id == LEAGUE_ID:
        return await sync_transactions()
    result = await sync_transactions(
        state=context.state, league_id=context.league_id,
    )
    if result:
        context.refresh_generations()
    return result


app.include_router(
    create_api_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        sync_sleeper=sync_current_league,
        state=runtime_state,
        league_id=LEAGUE_ID,
        league_resolver=current_league_id,
    )
)

app.include_router(create_league_runtime_router(
    manager=league_runtime_manager,
    import_enabled=_MULTI_LEAGUE_IMPORT_ENABLED,
    resource_health=_resource_health,
    resource_measurement=_measure_resources,
))

app.include_router(create_intelligence_memory_router(
    default_league_id=LEAGUE_ID,
    secondary_import_enabled=_MULTI_LEAGUE_IMPORT_ENABLED,
))

app.include_router(
    create_valuation_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        state=STATE,
        page=page,
    )
)

def current_projection_service() -> ProjectionService:
    context = current_league_context()
    return context.projection if context is not None else projection_service


app.include_router(create_projections_router(
    service=projection_service, service_resolver=current_projection_service,
))
app.include_router(create_audit_router(
    require_data=require_data,
    projection_service=projection_service,
    market_cache=asset_market_cache,
    fois_service=fois_service,
    context_resolver=current_league_context,
))

app.include_router(
    create_crawl_router(
        get_data=require_data,
        state=runtime_state,
        league_id=LEAGUE_ID,
    )
)

app.include_router(
    create_draft_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_front_offices_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_fois_router(
        service=fois_service,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_hq_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        state=runtime_state,
        league_id=LEAGUE_ID,
        page=page,
        league_resolver=current_league_id,
    )
)

app.include_router(create_history_router(
    league_id=LEAGUE_ID, page=page, league_resolver=current_league_id,
))
app.include_router(
    create_historical_assets_router(
        league_id=LEAGUE_ID, require_data=require_data, page=page,
        league_resolver=current_league_id,
    )
)

app.include_router(create_inspection_router(
    state=runtime_state, route_provider=lambda: app.routes, league_id=LEAGUE_ID,
    artifact_root=Path("static/inspection") / (
        "league-" + hashlib.sha256(str(LEAGUE_ID).encode()).hexdigest()[:16]
    ),
    projection_service=projection_service, market_cache=asset_market_cache,
    context_resolver=current_league_context,
    live_visual_service=live_visual_service,
    current_visual_mirror=current_visual_mirror,
    resource_health=_resource_health,
))

app.include_router(
    create_matchups_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_market_router(
        require_data=require_data,
        state=runtime_state,
        league_id=LEAGUE_ID,
        page=page,
        context_resolver=current_league_context,
    )
)

app.include_router(
    create_settings_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_teams_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        state=runtime_state,
        page=page,
    )
)

app.include_router(
    create_transactions_router(
        ensure_fresh=ensure_fresh,
        refresh_transactions=sync_current_transactions,
        require_data=require_data,
        state=runtime_state,
        page=page,
    )
)

app.include_router(
    create_trades_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.mount(
    "/inspection-artifacts",
    StaticFiles(directory="static/inspection", check_dir=False),
    name="inspection-artifacts",
)
