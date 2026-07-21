"""Front Office Intelligence page and API routes."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse

from components.front_office_intelligence import front_office_center
from services.front_office_intelligence import build_front_office_center


def create_front_offices_router(*, ensure_fresh: Callable[[], Awaitable[None]], require_data: Callable[[], dict[str, Any]], page: Callable[[str, str], HTMLResponse]) -> APIRouter:
    router = APIRouter(tags=["front-office-intelligence"])

    def view(roster_id: int | None):
        try:
            return build_front_office_center(require_data(), roster_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/front-offices", response_class=HTMLResponse)
    async def front_offices_page(front_office: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        return page("Front Office Intelligence", front_office_center(view(front_office)))

    @router.get("/api/front-offices", response_class=JSONResponse)
    async def front_offices_api(front_office: int | None = None) -> JSONResponse:
        await ensure_fresh()
        result = view(front_office)
        return JSONResponse(jsonable_encoder({"active_front_office": result["active"].roster_id, "organizations": [asdict(item) for item in result["reports"]], "compatibilities": [asdict(item) for item in result["compatibilities"]], "relationships": [asdict(item) for item in result["relationships"]]}))

    return router
