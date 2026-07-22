"""DTOS health, API, and synchronization routes."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app_metadata import VERSION
from services.asset_intelligence import player_asset_index
from src.core.intelligence import intelligence_orchestrator
from src.platform.observability import environment_summary, runtime_metrics


EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
SyncSleeper = Callable[..., Awaitable[dict[str, Any]]]


def create_api_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    sync_sleeper: SyncSleeper,
    state: dict[str, Any],
    league_id: str,
) -> APIRouter:
    """Create system routes using shared application dependencies."""
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok" if state.get("data") else "starting",
            "league_id": league_id,
            "last_sync": state.get("last_sync"),
            "last_error": state.get("last_error"),
            "runtime": runtime_metrics.health(),
        }

    @router.get("/api/status")
    async def api_status() -> JSONResponse:
        await ensure_fresh()
        data = state.get("data") or {}
        return JSONResponse(
            {
                "version": VERSION,
                "league_id": league_id,
                "last_sync": state.get("last_sync"),
                "last_error": state.get("last_error"),
                "syncing": state.get("syncing"),
                "counts": {
                    "owners": len(data.get("owners") or []),
                    "teams": len(data.get("teams") or []),
                    "traded_picks": len(data.get("traded_picks") or []),
                    "transactions": len(data.get("transactions") or []),
                },
            }
        )

    @router.get("/api/platform/health")
    async def platform_health() -> JSONResponse:
        return JSONResponse({"version": VERSION, "runtime": runtime_metrics.health(), "configuration": environment_summary(), **intelligence_orchestrator.health(state)})

    @router.get("/api/intelligence")
    async def unified_intelligence(front_office: int | None = None) -> JSONResponse:
        await ensure_fresh()
        data = require_data()
        teams = data.get("teams") or []
        valid_ids = {int(team.get("roster_id") or 0) for team in teams}
        roster_id = front_office if front_office in valid_ids else min(valid_ids)
        result = intelligence_orchestrator.analyze(data, roster_id)
        from dataclasses import asdict
        from fastapi.encoders import jsonable_encoder
        market_summary = {
            "available_assets": sum(item.consensus.value is not None for item in result.market.assets.values()),
            "opportunities": [asdict(item) for item in result.market.opportunities],
            "provider_health": result.market.provider_health,
            "offline": result.market.offline,
        }
        return JSONResponse(jsonable_encoder({"active_front_office": roster_id, "recommendation": asdict(result.recommendation), "market": market_summary, "player_values": {key: asdict(value) for key, value in result.player_values.items()}, "roster": asdict(result.roster), "league_intelligence": asdict(result.league), "timings_ms": result.timings_ms, "cache_hit": result.cache_hit}))

    @router.get("/api/league")
    async def api_league(include_players: bool = False) -> JSONResponse:
        await ensure_fresh()
        data = require_data().copy()
        data.pop("players", None)
        if include_players:
            data["players"] = player_asset_index(require_data())
        return JSONResponse(data)

    @router.get("/api/players")
    async def api_players() -> JSONResponse:
        """List cached rostered players with canonical dossier URLs."""
        await ensure_fresh()
        players = player_asset_index(require_data())
        return JSONResponse({"count": len(players), "players": players})

    @router.post("/sync")
    async def manual_sync(request: Request):
        await sync_sleeper(force_players=False)
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse(
                {
                    "ok": state.get("last_error") is None,
                    "last_sync": state.get("last_sync"),
                    "error": state.get("last_error"),
                }
            )
        return RedirectResponse(url="/", status_code=303)

    return router
