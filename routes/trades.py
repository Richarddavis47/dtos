"""Trade Intelligence routes."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse

from components.trade_intelligence import trade_center
from services.trade_intelligence import build_trade_center

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_trades_router(*, ensure_fresh: EnsureFresh, require_data: RequireData, page: PageRenderer) -> APIRouter:
    router = APIRouter()

    def view(front_office: int | None) -> dict[str, Any]:
        try:
            return build_trade_center(require_data(), front_office)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/trades", response_class=HTMLResponse)
    async def trades_page(front_office: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        return page("Trade Intelligence", trade_center(view(front_office)))

    @router.get("/api/trades", response_class=JSONResponse)
    async def trades_api(front_office: int | None = None) -> JSONResponse:
        await ensure_fresh()
        result = view(front_office)
        payload = {
            "active_front_office": int(result["active_team"].get("roster_id") or 0),
            "count": len(result["dossiers"]),
            "opportunities": [asdict(item) for item in result["dossiers"]],
        }
        return JSONResponse(jsonable_encoder(payload))

    return router
