"""Bounded early response for Asset Market generation warming."""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import parse_qs

from starlette.background import BackgroundTask
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

MARKET_WARMING_DETAIL = (
    "Asset Market generation is building safely in the background; retry shortly."
)
MARKET_WARMING_PATHS = frozenset({"/market", "/api/market/assets"})
MARKET_WARMING_METHODS = frozenset({"GET", "HEAD"})


class AssetMarketWarmingMiddleware:
    """Short-circuit exact directory routes before FastAPI route preparation."""

    def __init__(
        self, app: ASGIApp, *, cache: Any,
        data_provider: Callable[[], dict[str, Any]], state: dict[str, Any],
        store: Any, league_id: str, build_allowed: Callable[[], bool],
    ) -> None:
        self.app = app
        self.cache = cache
        self.data_provider = data_provider
        self.state = state
        self.store = store
        self.league_id = league_id
        self.build_allowed = build_allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        requested = (query.get("league_id") or query.get("league") or [None])[0]
        if (
            scope["type"] != "http"
            or scope.get("method") not in MARKET_WARMING_METHODS
            or scope.get("path") not in MARKET_WARMING_PATHS
            or (requested is not None and str(requested) != str(self.league_id))
        ):
            await self.app(scope, receive, send)
            return
        build_allowed = self.build_allowed()
        if not self.cache.begin_warming_guard(
            self.data_provider(), self.state, self.store, self.league_id,
            start_background=False,
        ):
            await self.app(scope, receive, send)
            return
        headers = {
            "Retry-After": "5",
            "X-DTOS-Market-Refresh": "refreshing",
        }
        background = (
            BackgroundTask(
                self.cache.reconcile,
                self.data_provider(), self.state, self.store, self.league_id,
            )
            if build_allowed else None
        )
        response: Response
        if scope["method"] == "HEAD":
            response = Response(status_code=503, headers=headers, background=background)
        else:
            response = JSONResponse(
                status_code=503,
                content={"detail": MARKET_WARMING_DETAIL},
                headers=headers,
                background=background,
            )
        await response(scope, receive, send)
