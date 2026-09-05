"""Live, read-only valuation-universe API."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.core.brain import brain_service
from src.core.provider_network import provider_network_report
from src.core.valuation.automation import calibration_report
from src.core.valuation.config import DEFAULT_CONFIG, NORMALIZATION_VERSION
from src.core.valuation.universe import ValuationUniverse
from src.core.valuation_intelligence import valuation_intelligence_report

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
        return {**result.status(), "endpoints": ["/api/valuation/assets", "/api/valuation/status", "/api/valuation/providers", "/api/valuation/evidence", "/api/valuation/confidence", "/api/valuation/coverage", "/api/valuation/agreement", "/api/valuation/explanation", "/api/valuation/timeline", "/api/valuation/diagnostics", "/api/valuation/export.json", "/api/valuation/export.csv"]}

    @router.get("/status")
    async def valuation_status() -> Any:
        return (await universe()).status()

    @router.get("/providers")
    async def valuation_providers() -> Any:
        await ensure_fresh()
        report = provider_network_report(require_data())
        return _network_envelope(report, {"providers": report["providers"], "provider_dependencies": report["provider_dependencies"], "evidence_summary": report["evidence_summary"], "performance": report["performance"], "safety": report["safety"]})

    @router.get("/normalization-inputs")
    async def normalization_inputs(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=250)) -> Any:
        """Bounded retained inputs for restart diagnosis; no provider or DB work."""
        await ensure_fresh()
        data = require_data()
        market = data.get("market_data") or {}
        sources = market.get("providers") or {}
        keys = sorted((name, str(asset_id)) for name in ("FantasyCalc", "DynastyProcess")
                      for asset_id in (sources.get(name) or {}))
        rows = []
        for name, asset_id in keys[offset:offset + limit]:
            source = sources[name][asset_id]
            source = source if isinstance(source, dict) else {"value": source}
            rows.append({"asset_id": "player:" + asset_id, "provider": name,
                         "raw_value": source.get("value"),
                         "source_confidence": source.get("confidence"),
                         "source_timestamp": source.get("updated_at"),
                           "provider_rank": source.get("rank"),
                           "normalization_version": NORMALIZATION_VERSION,
                           "scale": asdict(DEFAULT_CONFIG.provider_scales[name])})
        return {"source": "retained_selected_league_provider_inputs",
                "synchronization_generation": state.get("last_sync"),
                "league_id": (data.get("league") or {}).get("league_id"),
                "total": len(keys), "offset": offset, "limit": limit, "records": rows}

    async def network() -> dict[str, Any]:
        await ensure_fresh()
        return await asyncio.to_thread(provider_network_report, require_data())

    async def intelligence() -> dict[str, Any]:
        await ensure_fresh()
        return await asyncio.to_thread(valuation_intelligence_report, require_data())

    @root.get("/api/brain", tags=["brain"])
    async def brain_index() -> Any:
        await ensure_fresh()
        brain = brain_service(require_data())
        return {**brain.health(), "endpoints": ["/api/brain/assets/{asset_id}", "/api/brain/health", "/api/brain/migration", "/api/brain/timeline/{asset_id}"]}

    @root.get("/api/brain/health", tags=["brain"])
    async def brain_health() -> Any:
        await ensure_fresh()
        return brain_service(require_data()).health()

    @root.get("/api/brain/migration", tags=["brain"])
    async def brain_migration() -> Any:
        await ensure_fresh()
        return brain_service(require_data()).migration()

    @root.get("/api/brain/assets/{asset_id:path}", tags=["brain"])
    async def brain_asset(asset_id: str) -> Any:
        await ensure_fresh()
        brain = brain_service(require_data())
        row = brain.asset(asset_id)
        if row is None:
            raise HTTPException(404, "The asset is not available in the synchronized Brain snapshot.")
        return _intelligence_envelope(brain.report, {"asset": row, "canonical_source": "DTOS Brain"})

    @root.get("/api/brain/timeline/{asset_id:path}", tags=["brain"])
    async def brain_timeline(asset_id: str) -> Any:
        await ensure_fresh()
        brain = brain_service(require_data())
        row = brain.asset(asset_id)
        if row is None:
            raise HTTPException(404, "The asset is not available in the synchronized Brain snapshot.")
        canonical_id = row["asset_id"]
        return _intelligence_envelope(brain.report, {"asset_id": canonical_id, "timeline": brain.report.get("timeline", {}).get(canonical_id, [])})

    @router.get("/evidence")
    async def valuation_evidence(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> Any:
        report = await intelligence()
        rows = sorted(report["assets"].values(), key=lambda row: row["asset_id"])
        return _intelligence_envelope(report, {"total": len(rows), "offset": offset, "limit": limit, "assets": rows[offset:offset + limit]})

    @router.get("/evidence/{asset_id:path}")
    async def valuation_asset_evidence(asset_id: str) -> Any:
        report = await intelligence()
        row = report["assets"].get(asset_id)
        if row is None:
            raise HTTPException(404, "Valuation evidence is not available for this asset.")
        return _intelligence_envelope(report, {"asset": row, "timeline": report["timeline"].get(asset_id, [])})

    @router.get("/confidence")
    async def valuation_confidence() -> Any:
        report = await intelligence()
        return _intelligence_envelope(report, {"average": report["summary"].get("average_confidence", 0), "highest": report["summary"].get("highest_confidence", []), "lowest": report["summary"].get("lowest_confidence", [])})

    @router.get("/coverage")
    async def valuation_coverage() -> Any:
        report = await intelligence()
        return _intelligence_envelope(report, {"average": report["summary"].get("average_coverage", 0), "highest": report["summary"].get("highest_coverage", []), "lowest": report["summary"].get("lowest_coverage", [])})

    @router.get("/agreement")
    async def valuation_agreement() -> Any:
        report = await intelligence()
        return _intelligence_envelope(report, {"average": report["summary"].get("average_agreement", 0), "strongest_consensus": report["summary"].get("strongest_consensus", []), "most_disputed": report["summary"].get("most_disputed", [])})

    @router.get("/explanation")
    async def valuation_explanation(asset_id: str | None = None) -> Any:
        report = await intelligence()
        if asset_id:
            row = report["assets"].get(asset_id)
            if row is None:
                raise HTTPException(404, "Valuation explanation is not available for this asset.")
            return _intelligence_envelope(report, {"asset_id": asset_id, "explanation": row["explanation"], "scores": row["scores"], "evidence_sources": row["evidence_sources"]})
        return _intelligence_envelope(report, {"explanations": [{"asset_id": row["asset_id"], "explanation": row["explanation"]} for row in list(report["assets"].values())[:100]]})

    @router.get("/timeline")
    async def valuation_timeline(asset_id: str | None = None) -> Any:
        report = await intelligence()
        if asset_id and asset_id not in report["assets"]:
            raise HTTPException(404, "Valuation timeline is not available for this asset.")
        return _intelligence_envelope(report, {"asset_id": asset_id, "timeline": report["timeline"].get(asset_id, []) if asset_id else {key: report["timeline"][key] for key in list(report["timeline"])[:100]}})

    @router.get("/diagnostics")
    async def valuation_diagnostics() -> Any:
        report = await intelligence()
        return _intelligence_envelope(report, {"diagnostics": report["diagnostics"], "summary": {key: len(value) for key, value in report["diagnostics"].items()}, "safety": report["safety"]})

    @router.get("/providers/{provider_id}/status")
    async def provider_status(provider_id: str) -> Any:
        row = _provider(await network(), provider_id)
        return _network_envelope(await network(), {"provider": row, "status": row["current_availability"], "reason": row["status_explanation"]})

    @router.get("/providers/{provider_id}/coverage")
    async def provider_coverage(provider_id: str) -> Any:
        row = _provider(await network(), provider_id)
        return _network_envelope(await network(), {"provider_id": provider_id, "record_count": row.get("record_count", 0), "coverage_percentage": row.get("coverage_percentage", 0.0), "identity_match_rate": row.get("identity_match_rate"), "unmatched_records": row.get("unmatched_records", 0), "runtime_metrics_status": "available" if "identity_match_rate" in row else "pending"})

    @router.get("/providers/{provider_id}/reliability")
    async def provider_reliability(provider_id: str) -> Any:
        row = _provider(await network(), provider_id)
        return _network_envelope(await network(), {"provider_id": provider_id, "reliability_score": row.get("reliability_score"), "dimensions": row.get("reliability_dimensions") or {}, "effective_calibration_weight": row.get("effective_calibration_weight"), "runtime_metrics_status": "available" if "reliability_score" in row else "pending"})

    @router.get("/providers/{provider_id}/history")
    async def provider_history(provider_id: str) -> Any:
        report = await network()
        _provider(report, provider_id)
        return _network_envelope(report, {"provider_id": provider_id, "history": [row for row in report["reliability_history"] if row["provider_id"] == provider_id]})

    @router.get("/providers/{provider_id}")
    async def provider_detail(provider_id: str) -> Any:
        report = await network()
        return _network_envelope(report, {"provider": _provider(report, provider_id)})

    @router.get("/provider-consensus")
    async def provider_consensus() -> Any:
        report = await network()
        return _network_envelope(report, {"consensus": report["consensus"]})

    @router.get("/provider-agreement")
    async def provider_agreement() -> Any:
        report = await network()
        return _network_envelope(report, {"provider_dependencies": report["provider_dependencies"], "agreement": {"average_disagreement": report["consensus"]["average_disagreement"], "independent_family_assets": report["consensus"]["assets_with_multiple_independent_families"]}})

    @router.get("/observed-market")
    async def observed_market() -> Any:
        report = await network()
        return _network_envelope(report, {"observed_market": report["observed_market"]})

    @router.get("/league-market")
    async def league_market() -> Any:
        report = await network()
        return _network_envelope(report, {"league_market": report["league_market"]})

    async def calibration() -> dict[str, Any]:
        await ensure_fresh()
        return await asyncio.to_thread(calibration_report, require_data(), state)

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
        @root.get("/brain", response_class=HTMLResponse, tags=["brain"])
        async def brain_dashboard() -> HTMLResponse:
            await ensure_fresh()
            health = brain_service(require_data()).health()
            migration = health["migration"]
            body = f'''<p class="eyebrow">Canonical Intelligence</p><h2>DTOS Brain</h2><p class="muted">There is only one Brain. Every intelligence consumer reads the same synchronized, explainable snapshot.</p><div class="grid"><article class="card"><p class="muted">Assets</p><h2>{health["asset_count"]}</h2></article><article class="card"><p class="muted">Coverage</p><h2>{health["coverage"]}</h2></article><article class="card"><p class="muted">Confidence</p><h2>{health["confidence"]}</h2></article><article class="card"><p class="muted">Agreement</p><h2>{health["agreement"]}</h2></article></div><div class="card"><h3>Migration</h3><p>{migration["migrated_count"]} of {migration["consumer_count"]} consumers use the canonical boundary.</p><p>Duplicate calculations: {migration["duplicate_calculation_count"]} · Legacy consumers: {migration["legacy_consumer_count"]}</p></div><div class="card"><h3>Cache and synchronization</h3><p>Mode: synchronized snapshot · Request-time provider calls: 0 · Request-time recalculation: no</p><p>Brain schema {health["brain_schema_version"]} · Generated {escape(str(health["generated_at"]))}</p></div>'''
            return page("DTOS Brain", body)

        @root.get("/valuation/calibration", response_class=HTMLResponse, tags=["valuation"])
        async def valuation_calibration_dashboard() -> HTMLResponse:
            result = await calibration()
            intelligence_report = await intelligence()
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
            provider_report = await network()
            provider_rows = "".join(
                f'<tr><td>{escape(row["provider_name"])}</td><td>{escape(row["evidence_category"])}</td>'
                f'<td>{escape(str(row.get("current_availability") or "Pending").title())}</td>'
                f'<td>{_display_metric(row.get("record_count"))}</td><td>{_display_metric(row.get("coverage_percentage"), "%")}</td>'
                f'<td>{_display_metric(row.get("identity_match_rate"), "%")}</td>'
                f'<td>{_display_metric(row.get("reliability_score"))}</td><td>{_display_metric(row.get("effective_calibration_weight"))}</td>'
                f'<td>{escape(str(row.get("status_explanation") or "Awaiting background provider generation."))}</td></tr>'
                for row in provider_report["providers"]
            )
            intelligence_cards = "".join(f'<article class="card"><p class="muted">{escape(label)}</p><h2>{escape(str(value))}</h2></article>' for label, value in (("Evidence Coverage", intelligence_report["summary"].get("average_coverage", 0)), ("Confidence", intelligence_report["summary"].get("average_confidence", 0)), ("Agreement", intelligence_report["summary"].get("average_agreement", 0)), ("Assets Evaluated", intelligence_report.get("asset_count", 0))))
            diagnostic_rows = "".join(f'<tr><td>{escape(name)}</td><td>{len(asset_ids)}</td></tr>' for name, asset_ids in sorted(intelligence_report["diagnostics"].items())) or '<tr><td>No diagnostics</td><td>0</td></tr>'
            body = f'''<p class="eyebrow">Valuation Intelligence</p><h2>Evidence Intelligence Dashboard</h2><p class="muted">DTOS selects the best-supported, explainable valuation using independently weighted evidence. Coverage, confidence, and agreement remain distinct.</p><div class="grid">{intelligence_cards}</div><div class="card"><h3>Valuation Diagnostics</h3><table><thead><tr><th>Diagnostic</th><th>Assets</th></tr></thead><tbody>{diagnostic_rows}</tbody></table></div><h2>Automated Market Calibration</h2><p class="muted">Consensus is an input, not the answer. DTOS audits the full universe and changes only bounded model-level principles when every safety rail passes.</p><div class="grid">{cards}</div><div class="card"><h3>Market Intelligence Providers</h3><p class="muted">Market, expert, performance, league-local, and intrinsic evidence remain distinct. Correlated provider families count only once.</p><table><thead><tr><th>Provider</th><th>Category</th><th>Status</th><th>Records</th><th>Coverage</th><th>Identity</th><th>Reliability</th><th>Weight</th><th>Explanation</th></tr></thead><tbody>{provider_rows}</tbody></table></div><div class="card"><h3>Category Health</h3><table><thead><tr><th>Category</th><th>Audited</th><th>Comparable</th><th>Median Difference</th><th>Confidence</th><th>Status</th><th>Impact</th></tr></thead><tbody>{category_rows}</tbody></table></div><h2>Calibration Recommendations</h2><div class="grid">{recommendations}</div><p class="muted">Last calibration: {escape(result["generated_at"])}</p>'''
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
        intelligence_row = (await intelligence())["assets"].get(asset_id)
        return JSONResponse(jsonable_encoder({**row, "valuation_intelligence": intelligence_row}))

    root.include_router(router)
    return root


def _provider(report: dict[str, Any], provider_id: str) -> dict[str, Any]:
    row = next((item for item in report["providers"] if item["provider_id"] == provider_id), None)
    if row is None:
        raise HTTPException(404, "Provider is not registered.")
    return row


def _network_envelope(report: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {key: report.get(key) for key in ("application_version", "application_build", "commit", "provider_registry_version", "evidence_contract_version", "generation_timestamp", "freshness", "availability")} | payload


def _intelligence_envelope(report: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {key: report.get(key) for key in ("application_version", "application_build", "commit", "schema_version", "generated_at", "availability", "asset_count")} | payload


def _display_metric(value: Any, suffix: str = "") -> str:
    """Format computed provider metrics without changing their canonical data."""
    return "Pending" if value is None else f"{value}{suffix}"
