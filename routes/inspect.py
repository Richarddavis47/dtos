"""Read-only DINS routes over the current cached application state."""
from __future__ import annotations

import os
import asyncio
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.inspection import (
    INSPECTION_SCHEMA_VERSION,
    VIEWPORTS,
    InspectionArtifactStore,
    InspectionEngine,
    discover_pages,
)
from src.core.inspection.publication import GitHubPublicationResolver
from src.core.valuation.universe import LAYER_NAMES, ValuationUniverse


def create_inspection_router(
    *,
    state: dict[str, Any],
    route_provider: Callable[[], Iterable[Any]] = tuple,
    artifact_root: Path | None = None,
    publication_resolver: GitHubPublicationResolver | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/inspect", tags=["inspection"])
    public_base = os.getenv("DTOS_PUBLIC_URL", "https://dtos.onrender.com").rstrip("/")
    store = InspectionArtifactStore(artifact_root or Path("static/inspection"), public_base)
    publication = publication_resolver or GitHubPublicationResolver()

    async def published(*, refresh: bool = False) -> dict[str, Any]:
        return await asyncio.to_thread(publication.current, refresh=refresh)

    def engine() -> InspectionEngine:
        return InspectionEngine(state)

    @router.get("")
    async def inspection_index() -> Any:
        return jsonable_encoder(engine().index())

    @router.get("/pages")
    async def inspect_pages() -> Any:
        return jsonable_encoder(engine().pages())

    def page_catalog() -> tuple[Any, ...]:
        return discover_pages(route_provider(), state)

    def current_manifest() -> dict[str, Any] | None:
        result = store.manifest()
        if result is None:
            return None
        deployment = deployment_metadata()
        return {**result, "version": VERSION, "build": BUILD_NUMBER, "commit_sha": deployment["commit"], "source_branch": deployment["branch"], "deployed_at": deployment["deployed_at"]}

    @router.get("/pages/{page_id}")
    async def inspect_page(page_id: str) -> Any:
        page = next((row for row in page_catalog() if row.page_id == page_id), None)
        if page is None:
            raise HTTPException(404, "Inspection page ID is not registered.")
        release = await published()
        bundle_url = release.get("full_bundle_url")
        local_visuals = any(store.page(page_id, viewport.name) for viewport in VIEWPORTS)
        return {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page": jsonable_encoder(page),
            "visual_artifacts": {
                viewport.name: (
                    {"url": f"{public_base}/api/inspect/visual/pages/{page_id}/{viewport.name}", "mode": "direct"}
                    if local_visuals else
                    {"bundle_url": bundle_url, "internal_path": f"dins/pages/{page_id}/{viewport.name}.json", "mode": "bundle"}
                )
                for viewport in VIEWPORTS
            },
        }

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

    @router.get("/valuation")
    async def inspect_valuation() -> Any:
        """Inspect the live valuation contract without provider calls or state changes."""
        data = state.get("data") or {}
        universe = ValuationUniverse(data, state)
        calibration = data.get("calibration_report") or {}
        provider_network = data.get("provider_network") or {}
        samples = [universe.assets[0], next((row for row in universe.assets if row["asset_type"] == "pick"), None)] if universe.assets else []
        return jsonable_encoder({
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page_name": "Valuation API",
            "route": "/api/valuation",
            "status": universe.status(),
            "valuation_layers": LAYER_NAMES,
            "sample_assets": [row for row in samples if row is not None],
            "market_calibration": {
                "schema_version": calibration.get("schema_version"),
                "summary": calibration.get("summary") or {},
                "recommendation_count": len(calibration.get("recommendations") or []),
                "last_calibration_timestamp": calibration.get("generated_at"),
            },
            "provider_network": {
                "provider_registry_version": provider_network.get("provider_registry_version"),
                "evidence_contract_version": provider_network.get("evidence_contract_version"),
                "provider_count": len(provider_network.get("providers") or []),
                "evidence_summary": provider_network.get("evidence_summary") or {},
                "consensus": provider_network.get("consensus") or {},
                "observed_market": provider_network.get("observed_market") or {},
                "safety": provider_network.get("safety") or {},
            },
            "warnings": universe.freshness["reasons"],
        })

    @router.get("/site-map")
    async def inspection_site_map() -> Any:
        pages = page_catalog()
        release = await published()
        return {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "pages": jsonable_encoder(pages),
            "publication": {key: release.get(key) for key in ("publication_status", "full_bundle_url", "published_manifest_url", "checksums_url")},
            "metrics": {"total": len(pages), "inspectable": sum(not page.excluded for page in pages), "excluded": sum(page.excluded for page in pages)},
        }

    @router.get("/schema")
    async def inspection_schema() -> Any:
        return {"application_version": VERSION, "application_build": BUILD_NUMBER, "inspection_schema_version": INSPECTION_SCHEMA_VERSION, "viewports": jsonable_encoder(VIEWPORTS), "contracts": ["semantic", "visual", "dom", "accessibility", "geometry", "interaction", "release"]}

    @router.get("/visual")
    @router.get("/visual/pages")
    async def visual_index() -> Any:
        return current_manifest() or {"application_version": VERSION, "application_build": BUILD_NUMBER, "inspection_schema_version": INSPECTION_SCHEMA_VERSION, "status": "pending", "pages": [], "message": "The versioned post-deployment inspection bundle has not completed."}

    @router.get("/visual/pages/{page_id}")
    async def visual_page_index(page_id: str) -> Any:
        rows = {viewport.name: store.page(page_id, viewport.name) for viewport in VIEWPORTS}
        if not any(rows.values()):
            raise HTTPException(404, "No generated visual inspection exists for this page.")
        return {"page_id": page_id, "viewports": rows}

    @router.get("/visual/pages/{page_id}/{viewport}")
    async def visual_page(page_id: str, viewport: str) -> Any:
        if viewport not in {row.name for row in VIEWPORTS}:
            raise HTTPException(404, "Unsupported inspection viewport.")
        result = store.page(page_id, viewport)
        if result is None:
            raise HTTPException(404, "Generated visual inspection not found.")
        return result

    @router.get("/releases")
    async def inspection_releases() -> Any:
        current = await published()
        return {"releases": [current, *store.releases()], "current": f"{public_base}/api/inspect/releases/current"}

    @router.get("/releases/current")
    async def current_release(refresh: bool = False) -> Any:
        return await published(refresh=refresh)

    def retained_release(version: str) -> dict[str, Any]:
        result = next((row for row in store.releases() if row.get("version") == version), None)
        if result is None:
            raise HTTPException(404, "Inspection release not retained.")
        return result

    @router.get("/releases/{version}")
    async def release(version: str) -> Any:
        if version.removeprefix("v") == VERSION:
            return await published()
        return retained_release(version)

    @router.get("/releases/{version}/changes")
    async def release_changes(version: str) -> Any:
        result = await published() if version.removeprefix("v") == VERSION else retained_release(version)
        return {key: result.get(key, []) for key in ("pages_added", "pages_removed", "pages_changed", "semantic_contract_changes")}

    @router.get("/releases/{version}/regressions")
    async def release_regressions(version: str) -> Any:
        result = await published() if version.removeprefix("v") == VERSION else retained_release(version)
        return {key: result.get(key, []) for key in ("visual_difference_results", "interaction_failures", "accessibility_regressions", "stale_version_mismatches")}

    @router.get("/health")
    async def inspection_health(refresh: bool = False) -> Any:
        current = await published(refresh=refresh)
        pages = page_catalog()
        deployment = deployment_metadata()
        branch, commit = deployment["branch"], deployment["commit"]
        completed = int(current.get("total_pages_completed") or 0)
        expected = sum(not page.excluded for page in pages)
        latest = current.get("version")
        identities_match = bool(current.get("identities_match"))
        return {"application_version": VERSION, "application_build": BUILD_NUMBER, "current_production_commit": commit, "expected_release_tag": f"v{VERSION}", "inspection_schema_version": INSPECTION_SCHEMA_VERSION, "latest_completed_inspection_version": latest, "inspection_status": current.get("publication_status", "pending"), "publication_status": current.get("publication_status", "pending"), "published_manifest_url": current.get("published_manifest_url"), "full_bundle_url": current.get("full_bundle_url"), "checksums_url": current.get("checksums_url"), "total_pages_expected": expected, "total_pages_completed": completed, "total_visual_artifacts": current.get("total_visual_artifacts", 0), "failures": current.get("failures", []), "warnings": current.get("warnings", []), "generated_timestamp": current.get("generated_at"), "source_commit": current.get("commit_sha") or commit, "source_branch": branch, "identities_match": identities_match, "production_inspection_matches_deployment": identities_match and latest == VERSION and completed == expected}

    return router
