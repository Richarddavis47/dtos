"""Live, read-only valuation-universe API."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.core.valuation.automation import calibration_report
from src.core.valuation.universe import ValuationUniverse

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_valuation_router(*, ensure_fresh: EnsureFresh, require_data: RequireData, state: dict[str, Any], page: PageRenderer | None = None) -> APIRouter:
    root = APIRouter()
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

    async def calibration() -> dict[str, Any]:
        await ensure_fresh()
        return calibration_report(require_data(), state)

    @router.get("/calibration")
    async def valuation_calibration() -> Any:
        return await calibration()

    @router.get("/calibration/categories")
    async def valuation_calibration_categories() -> Any:
        result = await calibration()
        return {"schema_version": result["schema_version"], "generated_at": result["generated_at"], "categories": result["category_health"]}

    @router.get("/calibration/recommendations")
    async def valuation_calibration_recommendations() -> Any:
        result = await calibration()
        return {"schema_version": result["schema_version"], "generated_at": result["generated_at"], "recommendations": result["recommendations"]}

    @router.get("/calibration/history")
    async def valuation_calibration_history() -> Any:
        await ensure_fresh()
        data = require_data()
        return {"schema_version": "1.0", "history": data.get("calibration_history") or []}

    if page is not None:
        @root.get("/valuation/calibration", response_class=HTMLResponse, tags=["valuation"])
        async def valuation_calibration_dashboard() -> HTMLResponse:
            result = await calibration()
            summary = result["summary"]
            cards = "".join(
                f'<article class="card"><p class="muted">{escape(label)}</p><h2>{escape(str(value))}</h2></article>'
                for label, value in (
                    ("Overall Calibration Score", summary["overall_calibration_score"]),
                    ("Total Assets Audited", summary["total_assets_audited"]),
                    ("Providers Available", summary["providers_available"]),
                    ("Provider Freshness", summary["provider_freshness"]),
                    ("Asset Integrity Score", f'{summary["asset_integrity_score"]}%'),
                    ("Calibration Confidence", f'{summary["calibration_confidence"]}%'),
                    ("High Priority Categories", summary["high_priority_categories"]),
                    ("Active Recommendations", summary["active_recommendations"]),
                )
            )
            category_rows = "".join(
                f'<tr><td>{escape(row["category"])}</td><td>{row["assets_audited"]}</td><td>{row["comparable_assets"]}</td><td>{escape(str(row["median_difference_percent"] if row["median_difference_percent"] is not None else "Insufficient evidence"))}</td><td>{row["confidence"]}%</td><td>{escape(row["status"])}</td><td>{row["impact_score"]}</td></tr>'
                for row in result["category_health"]
            )
            recommendations = "".join(
                f'<article class="card"><h3>{escape(row["title"])}</h3><p><b>{escape(row["status"])}</b> · Confidence {row["confidence"]}% · Impact {row["impact_score"]}</p><p>{escape(row["summary"])}</p><details><summary>Show Reasoning</summary><ul>{"".join(f"<li>{escape(item)}</li>" for item in row["evidence"])}</ul><p>{escape(row["explanation"])}</p></details></article>'
                for row in result["recommendations"][:12]
            ) or '<div class="card"><h3>No calibration required</h3><p>Current model evidence is within configured safety thresholds.</p></div>'
            body = f'''<p class="eyebrow">Valuation Operations</p><h2>Automated Market Calibration</h2><p class="muted">Consensus is an input, not the answer. DTOS audits the full universe and changes only bounded model-level principles when every safety rail passes.</p><div class="grid">{cards}</div><div class="card"><h3>Category Health</h3><table><thead><tr><th>Category</th><th>Audited</th><th>Comparable</th><th>Median Difference</th><th>Confidence</th><th>Status</th><th>Impact</th></tr></thead><tbody>{category_rows}</tbody></table></div><h2>Calibration Recommendations</h2><div class="grid">{recommendations}</div><p class="muted">Last calibration: {escape(result["generated_at"])}</p>'''
            return page("Market Calibration Dashboard", body)

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

    root.include_router(router)
    return root
