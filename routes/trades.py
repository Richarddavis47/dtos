"""Trade Intelligence routes."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Body, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse

from components.trade_intelligence import trade_center, trade_workflow
from services.trade_intelligence import assist_trade_request, autocomplete_trade_assets, build_trade_center, build_trade_workspace, compare_trade_requests, create_trade_alternatives, evaluate_trade_request, generate_trade_workflow
from src.core.intelligence.serialization import recommendation_contract

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

    async def workflow_page(workflow: str, front_office: int | None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        try:
            body = trade_workflow(view(front_office), workflow, asset_id, owner_roster_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return page("Trade Center", body)

    @router.get("/trades/create", response_class=HTMLResponse)
    async def create_trade_page(front_office: int | None = None) -> HTMLResponse:
        return await workflow_page("create", front_office)

    @router.get("/trades/trade-for", response_class=HTMLResponse)
    async def trade_for_page(front_office: int | None = None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        return await workflow_page("trade-for", front_office, asset_id, owner_roster_id)

    @router.get("/trades/shop", response_class=HTMLResponse)
    async def shop_asset_page(front_office: int | None = None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        return await workflow_page("shop", front_office, asset_id, owner_roster_id)

    @router.get("/trades/recommended", response_class=HTMLResponse)
    async def recommended_trades_page(front_office: int | None = None) -> HTMLResponse:
        return await workflow_page("recommended", front_office)

    @router.get("/api/trades", response_class=JSONResponse)
    async def trades_api(front_office: int | None = None) -> JSONResponse:
        await ensure_fresh()
        result = view(front_office)
        payload = {
            "active_front_office": int(result["active_team"].get("roster_id") or 0),
            "count": len(result["dossiers"]),
            "opportunities": [asdict(item) for item in result["dossiers"]],
            "canonical_bilateral_evaluations": result["canonical_results"],
            **recommendation_contract(result["unified_recommendation"], result.get("brain_recommendation")),
        }
        return JSONResponse(jsonable_encoder(payload))

    @router.get("/api/trades/workspace", response_class=JSONResponse)
    async def trade_workspace(front_office: int | None = None) -> JSONResponse:
        await ensure_fresh()
        try:
            workspace = build_trade_workspace(require_data(), front_office)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        payload = {
            "active_front_office": workspace["active_roster_id"],
            "workflows": workspace["workflows"],
            "teams": [
                {
                    "roster_id": int(team.get("roster_id") or 0),
                    "team_name": str(team.get("team_name") or team.get("owner") or "Unassigned Franchise"),
                    "assets": [asdict(asset) for asset in workspace["pools"][int(team.get("roster_id") or 0)]],
                }
                for team in workspace["teams"]
            ],
            "session_persistence": "temporary",
            "bilateral_only": True,
        }
        return JSONResponse(jsonable_encoder(payload))

    @router.post("/api/trades/evaluate", response_class=JSONResponse)
    async def evaluate_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            result = evaluate_trade_request(require_data(), payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/generate", response_class=JSONResponse)
    async def generate_trades(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            result = generate_trade_workflow(require_data(), payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/assist", response_class=JSONResponse)
    async def assist_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            result = assist_trade_request(require_data(), payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/alternatives", response_class=JSONResponse)
    async def trade_alternatives(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            result = create_trade_alternatives(require_data(), payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.get("/api/trades/assets", response_class=JSONResponse)
    async def trade_assets(q: str = "", front_office: int | None = None, limit: int = 20) -> JSONResponse:
        await ensure_fresh()
        try:
            result = autocomplete_trade_assets(require_data(), q, front_office, max(1, min(limit, 50)))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/compare", response_class=JSONResponse)
    async def compare_trades(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            result = compare_trade_requests(require_data(), list(payload.get("proposals") or ()))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    return router
