"""DTOS health, API, and synchronization routes."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app_metadata import VERSION
from services.asset_intelligence import player_asset_index


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
