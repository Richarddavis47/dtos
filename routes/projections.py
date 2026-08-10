"""Read-only Projection Intelligence API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app_metadata import BUILD_NUMBER, VERSION
from src.core.projection_intelligence.service import ProjectionService, provider_registry


def create_projections_router(*, service: ProjectionService) -> APIRouter:
    router = APIRouter(prefix="/api/projections", tags=["Projection Intelligence"])

    def envelope(payload: dict[str, Any]) -> dict[str, Any]:
        return {"application_version": VERSION, "application_build": BUILD_NUMBER, **payload}

    @router.get("")
    async def projections() -> dict[str, Any]:
        snapshot = service.snapshot()
        return envelope({"status": "ready" if snapshot else "pending", "projection": snapshot})

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return envelope(service.health())

    @router.get("/providers")
    async def providers() -> dict[str, Any]:
        return envelope({"providers": provider_registry(), "health": service.health().get("external_provider")})

    @router.get("/accuracy")
    async def accuracy() -> dict[str, Any]:
        return envelope({"accuracy": service.accuracy()})

    @router.get("/players/{player_id}")
    async def player(player_id: str) -> dict[str, Any]:
        projection = service.player(player_id)
        if projection is None:
            raise HTTPException(404, "Projection unavailable for this player.")
        return envelope({"projection": projection})

    @router.get("/weeks/{week}")
    async def week(week: int) -> dict[str, Any]:
        snapshot = service.snapshot()
        players = (snapshot or {}).get("players") or {}
        if snapshot is None or snapshot.get("week") != week:
            return envelope({"status": "unavailable", "week": week, "players": []})
        return envelope({"status": "ready", "week": week, "projection_snapshot_id": snapshot.get("projection_snapshot_id"), "players": list(players.values())})

    return router
