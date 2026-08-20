"""Stable public delivery of the verified rolling Current Visual mirror."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from src.core.inspection.current_visual import CurrentVisualMirror, consumer_manifest


def _json_response(payload: dict[str, Any], *, head: bool) -> Response:
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    headers = {
        "Cache-Control": "public, max-age=0, must-revalidate",
        "ETag": f'"{hashlib.sha256(content).hexdigest()}"',
        "Content-Length": str(len(content)),
        "X-Content-Type-Options": "nosniff",
        "X-Robots-Tag": "index, follow",
    }
    if head:
        return Response(status_code=200, media_type="application/json", headers=headers)
    return Response(content=content, status_code=200, media_type="application/json", headers=headers)


def create_current_visual_router(
    *, mirror: CurrentVisualMirror, public_base: str,
) -> APIRouter:
    router = APIRouter(tags=["current visual"])

    def manifest() -> dict[str, Any]:
        return consumer_manifest(mirror.manifest(), public_base)

    @router.get("/current-visual", response_class=JSONResponse)
    async def current_visual_discovery(request: Request) -> Response:
        value = manifest()
        captures = value.get("captures") or []
        representative = next(
            (row for row in captures if row.get("capture_id") == "fois-page-desktop"),
            captures[0] if captures else None,
        )
        payload = {
            "status": value.get("status"),
            "kind": "dtos_current_visual_discovery",
            "manifest_url": value.get("manifest_url"),
            "current_generation": value.get("current_generation"),
            "application_version": value.get("application_version"),
            "application_build": value.get("application_build"),
            "commit": value.get("commit"),
            "representative_image": representative,
        }
        return _json_response(payload, head=request.method == "HEAD")

    @router.head("/current-visual", include_in_schema=False)
    async def current_visual_discovery_head(request: Request) -> Response:
        return await current_visual_discovery(request)

    @router.get("/current-visual/manifest.json", response_class=JSONResponse)
    async def current_visual_manifest(request: Request) -> Response:
        return _json_response(manifest(), head=request.method == "HEAD")

    @router.head("/current-visual/manifest.json", include_in_schema=False)
    async def current_visual_manifest_head(request: Request) -> Response:
        return await current_visual_manifest(request)

    @router.get("/current-visual/images/{name}", response_class=FileResponse)
    async def current_visual_image(name: str, request: Request) -> Response:
        if Path(name).name != name or not name.endswith(".png"):
            raise HTTPException(404, "Current visual image is unavailable.")
        path = mirror.current_image(name)
        if path is None:
            raise HTTPException(404, "Current visual image is unavailable.")
        return FileResponse(path, media_type="image/png", headers={
            "Cache-Control": "public, max-age=60, must-revalidate",
            "Content-Disposition": f'inline; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "index, follow",
        })

    @router.head("/current-visual/images/{name}", include_in_schema=False)
    async def current_visual_image_head(name: str, request: Request) -> Response:
        return await current_visual_image(name, request)

    return router
