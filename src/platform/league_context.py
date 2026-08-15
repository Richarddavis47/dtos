"""Request-scoped canonical league selection without singleton swapping."""
from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from contextvars import ContextVar
from typing import Any
from urllib.parse import parse_qs

from starlette.responses import JSONResponse

from src.core.league_runtime import (
    CanonicalLeagueContext, LeagueRuntimeError, LeagueRuntimeManager,
    LeagueRuntimeNotFound,
)

_CURRENT_CONTEXT: ContextVar[CanonicalLeagueContext | None] = ContextVar(
    "dtos_canonical_league_context", default=None,
)


def current_league_context() -> CanonicalLeagueContext | None:
    return _CURRENT_CONTEXT.get()


class RuntimeStateProxy(MutableMapping[str, Any]):
    """Mapping proxy that resolves state from the active request context."""

    def __init__(self, default_state: dict[str, Any]) -> None:
        self._default_state = default_state

    def _mapping(self) -> dict[str, Any]:
        context = current_league_context()
        return context.state if context is not None else self._default_state

    def __getitem__(self, key: str) -> Any:
        return self._mapping()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._mapping()[key] = value

    def __delitem__(self, key: str) -> None:
        del self._mapping()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping())

    def __len__(self) -> int:
        return len(self._mapping())


def _path_league(path: str, method: str) -> str | None:
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[:3] == ["api", "fois", "leagues"]:
        return parts[3]
    if (
        len(parts) == 4
        and parts[:2] == ["api", "leagues"]
        and parts[3] == "runtime"
        and method == "POST"
    ):
        return parts[2]
    return None


class LeagueContextMiddleware:
    """Resolve an explicit league to its runtime before consumer routing."""

    def __init__(
        self, app: Any, *, manager: LeagueRuntimeManager, default_league_id: str,
        import_enabled: bool,
    ) -> None:
        self.app = app
        self.manager = manager
        self.default_league_id = str(default_league_id)
        self.import_enabled = import_enabled

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        requested = (
            (query.get("league_id") or query.get("league") or [None])[0]
            or _path_league(str(scope.get("path") or ""), str(scope.get("method") or "GET"))
        )
        if not requested or str(requested) == self.default_league_id:
            runtime = self.manager.resident(self.default_league_id)
        else:
            if not self.import_enabled:
                response = JSONResponse({
                    "status": "feature_gated",
                    "reason": "Secondary-league hydration is disabled until isolation validation is enabled.",
                }, status_code=403)
                await response(scope, receive, send)
                return
            try:
                runtime = await self.manager.get(str(requested))
            except LeagueRuntimeNotFound as exc:
                response = JSONResponse({"status": "invalid", "reason": str(exc)}, status_code=422)
                await response(scope, receive, send)
                return
            except LeagueRuntimeError as exc:
                response = JSONResponse({"status": "failed", "reason": str(exc)}, status_code=503)
                await response(scope, receive, send)
                return
        context = runtime.canonical_context if runtime is not None else None
        if runtime is not None:
            runtime.active_requests += 1
            runtime.touch()
        token = _CURRENT_CONTEXT.set(context)
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT_CONTEXT.reset(token)
            if runtime is not None:
                runtime.active_requests = max(0, runtime.active_requests - 1)
