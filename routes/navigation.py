"""Cheap navigation identity checks; never acquire a league or prepare analytics."""

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from services.contextual_navigation import navigation_context

_STATIC = Path(__file__).resolve().parents[1] / "static"


def create_navigation_router():
    router = APIRouter(tags=["navigation"])

    @router.get("/static/js/contextual_navigation.js", include_in_schema=False)
    async def script():
        return Response(
            (_STATIC / "js/contextual_navigation.js").read_text(encoding="utf-8"),
            media_type="text/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @router.get("/static/css/contextual_navigation.css", include_in_schema=False)
    async def stylesheet():
        return Response(
            (_STATIC / "css/contextual_navigation.css").read_text(encoding="utf-8"),
            media_type="text/css",
            headers={"Cache-Control": "no-cache"},
        )

    @router.get("/api/account/navigation-context")
    async def context():
        value = navigation_context()
        return JSONResponse(
            value or {"status": "authentication_required"},
            status_code=200 if value else 401,
            headers={"Cache-Control": "no-store, private", "Vary": "Cookie"},
        )

    return router
