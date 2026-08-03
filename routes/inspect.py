"""Read-only DINS routes over the current cached application state."""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from app_metadata import BUILD_NUMBER, VERSION, repository_metadata
from src.core.inspection import (
    INSPECTION_SCHEMA_VERSION,
    VIEWPORTS,
    InspectionArtifactStore,
    InspectionEngine,
    discover_pages,
)


def create_inspection_router(
    *,
    state: dict[str, Any],
    route_provider: Callable[[], Iterable[Any]] = tuple,
    artifact_root: Path | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/inspect", tags=["inspection"])
    public_base = os.getenv("DTOS_PUBLIC_URL", "https://dtos.onrender.com").rstrip("/")
    store = InspectionArtifactStore(artifact_root or Path("static/inspection"), public_base)

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
        _, commit = repository_metadata()
        return {**result, "version": VERSION, "build": BUILD_NUMBER, "commit_sha": commit}

    @router.get("/pages/{page_id}")
    async def inspect_page(page_id: str) -> Any:
        page = next((row for row in page_catalog() if row.page_id == page_id), None)
        if page is None:
            raise HTTPException(404, "Inspection page ID is not registered.")
        return {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page": jsonable_encoder(page),
            "visual_urls": {
                viewport.name: f"{public_base}/api/inspect/visual/pages/{page_id}/{viewport.name}"
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

    @router.get("/site-map")
    async def inspection_site_map() -> Any:
        pages = page_catalog()
        return {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "pages": jsonable_encoder(pages),
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
        return {"releases": store.releases(), "current": f"{public_base}/api/inspect/releases/current"}

    @router.get("/releases/current")
    async def current_release() -> Any:
        return current_manifest() or {"version": VERSION, "build": BUILD_NUMBER, "status": "pending"}

    def retained_release(version: str) -> dict[str, Any]:
        result = next((row for row in store.releases() if row.get("version") == version), None)
        if result is None:
            raise HTTPException(404, "Inspection release not retained.")
        return result

    @router.get("/releases/{version}")
    async def release(version: str) -> Any:
        return retained_release(version)

    @router.get("/releases/{version}/changes")
    async def release_changes(version: str) -> Any:
        result = retained_release(version)
        return {key: result.get(key, []) for key in ("pages_added", "pages_removed", "pages_changed", "semantic_contract_changes")}

    @router.get("/releases/{version}/regressions")
    async def release_regressions(version: str) -> Any:
        result = retained_release(version)
        return {key: result.get(key, []) for key in ("visual_difference_results", "interaction_failures", "accessibility_regressions", "stale_version_mismatches")}

    @router.get("/health")
    async def inspection_health() -> Any:
        current = current_manifest() or {}
        pages = page_catalog()
        branch, commit = repository_metadata()
        completed = int(current.get("total_pages_completed") or 0)
        expected = sum(not page.excluded for page in pages)
        latest = current.get("version")
        return {"application_version": VERSION, "application_build": BUILD_NUMBER, "inspection_schema_version": INSPECTION_SCHEMA_VERSION, "latest_completed_inspection_version": latest, "inspection_status": current.get("status", "pending"), "total_pages_expected": expected, "total_pages_completed": completed, "total_visual_artifacts": current.get("total_visual_artifacts", 0), "failures": current.get("failures", []), "warnings": current.get("warnings", []), "generated_timestamp": current.get("generated_at"), "source_commit": current.get("commit_sha") or commit, "source_branch": branch, "production_inspection_matches_deployment": latest == VERSION and completed == expected}

    return router
