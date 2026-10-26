"""Public-safe multi-league runtime foundation diagnostics."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.platform.inspection_security import inspection_authorized
from src.platform.runtime_errors import customer_runtime_health, log_runtime_failure, runtime_error_response

from src.core.league_runtime import (
    LeagueRuntimeError, LeagueRuntimeManager, LeagueRuntimeNotFound,
)


def create_league_runtime_router(
    *, manager: LeagueRuntimeManager, import_enabled: bool = False,
    resource_health: Any = None, resource_measurement: Any = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/leagues", tags=["league-runtime"])

    @router.get("/runtime")
    async def runtime_health(request: Request) -> dict[str, Any]:
        from src.platform.account_context import current_account
        context = current_account()
        result = manager.health()
        if context is not None and context.membership is not None and not inspection_authorized(request.scope):
            # This shared manager owns other accounts' runtimes too. Preserve
            # aggregate operational counters, never their source errors/rows.
            league = context.membership.league_id
            result = dict(result)
            if "runtimes" in result:
                result["runtimes"] = [row for row in result["runtimes"] if row.get("league_id") == league]
                result["status"] = "degraded" if any(str(row.get("status")).lower() == "failed" for row in result["runtimes"]) else "healthy"
            for field in ("resident_league_ids", "in_flight"):
                if field in result:
                    result[field] = [value for value in result[field] if value == league]
        if not inspection_authorized(request.scope) and "runtimes" in result:
            result = {**result, "runtimes": [customer_runtime_health(row) for row in result["runtimes"]]}
        return result

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
    async def league_health(league_id: str, request: Request) -> JSONResponse:
        try:
            normalized = manager.validate_league_id(league_id)
        except LeagueRuntimeNotFound as exc:
            log_runtime_failure(exc, operation="runtime_validation", status=422)
            return runtime_error_response(422)
        runtime = manager.resident(normalized)
        if runtime is None:
            return JSONResponse({
                "league_id": normalized,
                "status": "cold",
                "resident": False,
                "import_enabled": import_enabled,
            })
        health = runtime.public_health()
        if not inspection_authorized(request.scope):
            health = customer_runtime_health(health)
        return JSONResponse({**health, "resident": True})

    @router.post("/{league_id}/runtime")
    async def hydrate_league(league_id: str, request: Request) -> JSONResponse:
        if not import_enabled:
            return JSONResponse({
                "status": "feature_gated",
                "reason": "Secondary-league hydration is disabled until isolation validation is enabled.",
            }, status_code=403)
        try:
            runtime = await manager.get(league_id)
        except LeagueRuntimeNotFound as exc:
            log_runtime_failure(exc, operation="explicit_hydration", status=422)
            return runtime_error_response(422)
        except LeagueRuntimeError as exc:
            log_runtime_failure(exc, operation="explicit_hydration", status=503)
            return runtime_error_response(503)
        except Exception as exc:
            log_runtime_failure(exc, operation="explicit_hydration", status=503)
            return runtime_error_response(503)
        health = runtime.public_health()
        if not inspection_authorized(request.scope):
            health = customer_runtime_health(health)
        return JSONResponse({**health, "resident": True})

    return router
