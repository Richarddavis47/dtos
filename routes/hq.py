"""Commissioner Desk homepage route."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from components.commissioner import commissioner_desk
from services.commissioner import build_commissioner_desk

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[..., HTMLResponse]


def create_hq_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    state: dict[str, Any],
    league_id: str,
    page: PageRenderer,
) -> APIRouter:
    """Create the Commissioner Desk using shared application dependencies."""
    router = APIRouter(tags=["commissioner-desk"])

    @router.get("/", response_class=HTMLResponse)
    async def commissioner_home(
        active_league: str = Query("", alias="league"),
        active_front_office: int | None = Query(None, alias="front_office"),
        since: str = "",
    ) -> HTMLResponse:
        await ensure_fresh()
        view = build_commissioner_desk(
            require_data(),
            configured_league_id=league_id,
            active_league_id=active_league or None,
            active_roster_id=active_front_office,
            since=since or None,
            last_sync=state.get("last_sync"),
            last_error=state.get("last_error"),
        )
        return page("Commissioner Desk", commissioner_desk(view), True)

    return router
