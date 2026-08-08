"""Bounded early response for Asset Market generation warming."""
from __future__ import annotations

from typing import Any, Callable

from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

MARKET_WARMING_DETAIL = (
    "Asset Market generation is building safely in the background; retry shortly."
)
MARKET_WARMING_PATHS = frozenset({"/", "/market", "/api/market/assets"})
MARKET_WARMING_METHODS = frozenset({"GET", "HEAD"})


class AssetMarketWarmingMiddleware:
    """Short-circuit exact directory routes before FastAPI route preparation."""

    def __init__(
        self, app: ASGIApp, *, cache: Any,
        data_provider: Callable[[], dict[str, Any]], state: dict[str, Any],
        store: Any, league_id: str,
    ) -> None:
        self.app = app
        self.cache = cache
        self.data_provider = data_provider
        self.state = state
        self.store = store
        self.league_id = league_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") not in MARKET_WARMING_METHODS
            or scope.get("path") not in MARKET_WARMING_PATHS
        ):
            await self.app(scope, receive, send)
            return
        if not self.cache.begin_warming_guard(
            self.data_provider(), self.state, self.store, self.league_id,
        ):
            await self.app(scope, receive, send)
            return
        headers = {
            "Retry-After": "5",
            "X-DTOS-Market-Refresh": "refreshing",
        }
        response: Response
        if scope["method"] == "HEAD":
            response = Response(status_code=503, headers=headers)
        else:
            response = JSONResponse(
                status_code=503,
                content={"detail": MARKET_WARMING_DETAIL},
                headers=headers,
            )
        await response(scope, receive, send)
