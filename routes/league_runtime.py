"""Public-safe multi-league runtime foundation diagnostics."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.league_runtime import (
    LeagueRuntimeError, LeagueRuntimeManager, LeagueRuntimeNotFound,
)


def create_league_runtime_router(
    *, manager: LeagueRuntimeManager, import_enabled: bool = False,
    resource_health: Any = None, resource_measurement: Any = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/leagues", tags=["league-runtime"])

    @router.get("/runtime")
    async def runtime_health() -> dict[str, Any]:
        return manager.health()

    @router.get("/resources")
    async def resources() -> dict[str, Any]:
        return resource_health() if resource_health else {"status": "unavailable"}

    @router.post("/resources/measure")
    async def measure_resources() -> dict[str, Any]:
        """Run explicit bounded deep sizing; normal health never invokes it."""
        return (
            resource_measurement()
            if resource_measurement else {"status": "unavailable"}
        )

    @router.get("/{league_id}/runtime")
    async def league_health(league_id: str) -> JSONResponse:
        try:
            normalized = manager.validate_league_id(league_id)
        except LeagueRuntimeNotFound as exc:
            return JSONResponse({"status": "invalid", "reason": str(exc)}, status_code=422)
        runtime = manager.resident(normalized)
        if runtime is None:
            return JSONResponse({
                "league_id": normalized,
                "status": "cold",
                "resident": False,
                "import_enabled": import_enabled,
            })
        return JSONResponse({**runtime.public_health(), "resident": True})

    @router.post("/{league_id}/runtime")
    async def hydrate_league(league_id: str) -> JSONResponse:
        if not import_enabled:
            return JSONResponse({
                "status": "feature_gated",
                "reason": "Secondary-league hydration is disabled until isolation validation is enabled.",
            }, status_code=403)
        try:
            runtime = await manager.get(league_id)
        except LeagueRuntimeNotFound as exc:
            return JSONResponse({"status": "invalid", "reason": str(exc)}, status_code=422)
        except LeagueRuntimeError as exc:
            return JSONResponse({"status": "failed", "reason": str(exc)}, status_code=503)
        except Exception as exc:
            return JSONResponse({
                "status": "failed",
                "reason": f"{type(exc).__name__}: league hydration failed",
            }, status_code=503)
        return JSONResponse({**runtime.public_health(), "resident": True})

    return router
