"""Read-only DINS routes over the current cached application state."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from src.core.inspection import InspectionEngine


def create_inspection_router(*, state: dict[str, Any]) -> APIRouter:
    router = APIRouter(prefix="/api/inspect", tags=["inspection"])

    def engine() -> InspectionEngine:
        return InspectionEngine(state)

    @router.get("")
    async def inspection_index() -> Any:
        return jsonable_encoder(engine().index())

    @router.get("/pages")
    async def inspect_pages() -> Any:
        return jsonable_encoder(engine().pages())

    @router.get("/team/{roster_id}")
    async def inspect_team(roster_id: int) -> Any:
        result = engine().team(roster_id)
        if result is None:
            raise HTTPException(404, "Team not found in cached state.")
        return jsonable_encoder(result)

    @router.get("/player/{player_id}")
    async def inspect_player(player_id: str) -> Any:
        result = engine().player(player_id)
        if result is None:
            raise HTTPException(404, "Player not found in cached state.")
        return jsonable_encoder(result)

    @router.get("/front-office/{roster_id}")
    async def inspect_front_office(roster_id: int) -> Any:
        result = engine().front_office(roster_id)
        if result is None:
            raise HTTPException(404, "Front Office not found in cached state.")
        return jsonable_encoder(result)

    @router.get("/trades")
    async def inspect_trades() -> Any:
        return jsonable_encoder(engine().trades())

    return router
