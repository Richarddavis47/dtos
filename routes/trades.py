"""Trade Intelligence routes."""
from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Body, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response

from components.trade_intelligence import manager_context_selection, trade_center, trade_workflow
from services.trade_intelligence import assist_trade_request, autocomplete_trade_assets, build_trade_center, build_trade_workflow_context, build_trade_workspace, compare_trade_requests, create_trade_alternatives, evaluate_trade_request, generate_trade_workflow
from src.core.intelligence.serialization import recommendation_contract
from src.core.request_execution import run_manager_read
from src.platform.account_context import current_account
from services.trade_workspace_context import workspace_context, authorize_workspace
from services.trade_intelligence import TradeInputError

_STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
_WORKSPACE_JS = (_STATIC_ROOT / "js" / "trade_workspace.js").read_text(encoding="utf-8")
_WORKSPACE_CSS = (_STATIC_ROOT / "css" / "trade_workspace.css").read_text(encoding="utf-8")


def _trade_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, TradeInputError):
        return HTTPException(422, {"code": exc.code, "message": str(exc), "assets": exc.assets})
    if isinstance(exc, ValueError):
        return HTTPException(422, {"code": str(exc) if str(exc).startswith(("unauthorized_", "workspace_")) else "invalid_proposal", "message": str(exc)})
    # Bounded type/location only: never log submitted proposals or credentials.
    import traceback
    frames = traceback.extract_tb(exc.__traceback__)
    location = frames[-1] if frames else None
    logging.getLogger(__name__).error("trade_engine_failure type=%s function=%s line=%s", type(exc).__name__, location.name if location else "unknown", location.lineno if location else 0)
    return HTTPException(503, {"code": "evaluation_unavailable", "message": "DTOS couldn't complete this evaluation. Your proposal is still intact."})

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_trades_router(*, ensure_fresh: EnsureFresh, require_data: RequireData, page: PageRenderer) -> APIRouter:
    router = APIRouter()

    @router.get("/static/js/trade_workspace.js", include_in_schema=False)
    async def workspace_script() -> Response:
        return Response(_WORKSPACE_JS, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @router.get("/static/css/trade_workspace.css", include_in_schema=False)
    async def workspace_styles() -> Response:
        return Response(_WORKSPACE_CSS, media_type="text/css", headers={"Cache-Control": "no-cache"})

    async def view(front_office: int | None) -> dict[str, Any]:
        try:
            return await run_manager_read(
                lambda: build_trade_center(require_data(), front_office),
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    def workflow_view(front_office: int | None) -> dict[str, Any]:
        try:
            return build_trade_workflow_context(require_data(), front_office)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/trades", response_class=HTMLResponse)
    async def trades_page(front_office: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        if front_office is None:
            return page("Trade Intelligence", manager_context_selection(list(require_data().get("teams") or [])))
        return page("Trade Intelligence", trade_center(await view(front_office)))

    async def workflow_page(workflow: str, front_office: int | None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        if front_office is None:
            return page("Trade Center", manager_context_selection(list(require_data().get("teams") or []), workflow=workflow))
        try:
            body = trade_workflow(
                workflow_view(front_office), workflow, asset_id, owner_roster_id,
            )
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
        if front_office is None:
            return JSONResponse({"status": "manager_context_required", "active_front_office": None, "count": 0, "opportunities": [], "reason": "Choose the franchise you control before using Trade Center."})
        result = await view(front_office)
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
            workspace = await run_manager_read(
                lambda: build_trade_workspace(require_data(), front_office),
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        payload = {
            "active_front_office": workspace["active_roster_id"],
            "workflows": workspace["workflows"],
            "teams": [
                {
                    "roster_id": int(team.get("roster_id") or 0),
                    "team_name": str(team.get("team_name") or team.get("owner") or "Unassigned Franchise"),
                    "assets": [
                        {
                            **asdict(asset),
                            "nfl_team": str((require_data().get("players") or {}).get(asset.asset_id, {}).get("team") or ""),
                            "headshot_url": (
                                f"https://sleepercdn.com/content/nfl/players/{asset.asset_id}.jpg"
                                if asset.kind == "player" else None
                            ),
                            "raw_label": asset.label,
                            "label": (
                                f"{asset.position} · {asset.label} · {asset.positional_rank} · {asset.trade_value}"
                                if asset.kind == "player"
                                else f"{asset.label} · {asset.projected_range or 'UNKNOWN'} · {asset.projected_range_confidence or 'LOW'} · {asset.trade_value}"
                            ),
                            "display_label": (
                                f"{asset.position} · {asset.label} · {asset.positional_rank} · {asset.trade_value}"
                                if asset.kind == "player"
                                else f"{asset.label} · {asset.projected_range or 'UNKNOWN'} · {asset.projected_range_confidence or 'LOW'} · {asset.trade_value}"
                            ),
                        }
                        for asset in workspace["pools"][int(team.get("roster_id") or 0)]
                    ],
                }
                for team in workspace["teams"]
            ],
            "session_persistence": "temporary",
            "bilateral_only": True,
            "workspace_context": workspace_context(require_data(), workspace["active_roster_id"]),
            "csrf_token": current_account().csrf_token if current_account() else "",
            "manager_context": {
                "league_id": workspace["manager_context"].league_id,
                "roster_id": workspace["manager_context"].roster_id,
                "manager_id": workspace["manager_context"].manager_id,
                "source": workspace["manager_context"].source,
            },
        }
        return JSONResponse(jsonable_encoder(payload))

    @router.post("/api/trades/evaluate", response_class=JSONResponse)
    async def evaluate_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(
                lambda: evaluate_trade_request(require_data(), payload),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/generate", response_class=JSONResponse)
    async def generate_trades(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(
                lambda: generate_trade_workflow(require_data(), payload),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/assist", response_class=JSONResponse)
    async def assist_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(
                lambda: assist_trade_request(require_data(), payload),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/alternatives", response_class=JSONResponse)
    async def trade_alternatives(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(
                lambda: create_trade_alternatives(require_data(), payload),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.get("/api/trades/assets", response_class=JSONResponse)
    async def trade_assets(q: str = "", front_office: int | None = None, limit: int = 20) -> JSONResponse:
        await ensure_fresh()
        try:
            result = await run_manager_read(
                lambda: autocomplete_trade_assets(
                    require_data(), q, front_office, max(1, min(limit, 50)),
                ),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/compare", response_class=JSONResponse)
    async def compare_trades(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            for proposal in payload.get("proposals") or ():
                authorize_workspace(require_data(), {**proposal, "workspace_context": payload.get("workspace_context")})
            result = await run_manager_read(
                lambda: compare_trade_requests(
                    require_data(), list(payload.get("proposals") or ()),
                ),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    return router
