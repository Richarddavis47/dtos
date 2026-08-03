"""Live, read-only valuation-universe API."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from src.core.valuation.universe import ValuationUniverse

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]


def create_valuation_router(*, ensure_fresh: EnsureFresh, require_data: RequireData, state: dict[str, Any]) -> APIRouter:
    router = APIRouter(prefix="/api/valuation", tags=["valuation"])

    async def universe() -> ValuationUniverse:
        await ensure_fresh()
        return ValuationUniverse(require_data(), state)

    @router.get("")
    async def valuation_index() -> Any:
        result = await universe()
        return {**result.status(), "endpoints": ["/api/valuation/assets", "/api/valuation/status", "/api/valuation/providers", "/api/valuation/export.json", "/api/valuation/export.csv"]}

    @router.get("/status")
    async def valuation_status() -> Any:
        return (await universe()).status()

    @router.get("/providers")
    async def valuation_providers() -> Any:
        return (await universe()).providers()

    @router.get("/assets")
    async def valuation_assets(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), asset_type: str | None = None) -> Any:
        result = await universe()
        rows = [row for row in result.assets if asset_type is None or row["asset_type"] == asset_type]
        return jsonable_encoder({"freshness": result.freshness, "total": len(rows), "offset": offset, "limit": limit, "assets": rows[offset:offset + limit]})

    @router.get("/export.json")
    async def valuation_json_export() -> Any:
        result = await universe()
        return jsonable_encoder({"schema_version": result.status()["schema_version"], "freshness": result.freshness, "assets": result.assets})

    @router.get("/export.csv")
    async def valuation_csv_export() -> Response:
        result = await universe()
        return Response(result.csv_bytes(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=dtos-valuation-universe.csv"})

    @router.get("/assets/{asset_id:path}")
    async def valuation_asset(asset_id: str) -> Any:
        result = await universe()
        row = result.by_id.get(asset_id)
        if row is None:
            raise HTTPException(404, "Valuation asset not found in current production state.")
        return JSONResponse(jsonable_encoder(row))

    return router
