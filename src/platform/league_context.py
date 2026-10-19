"""Request-scoped canonical league selection without singleton swapping."""
from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from contextvars import ContextVar
from html import escape
from typing import Any
from urllib.parse import parse_qs, parse_qsl, quote, urlencode

from starlette.responses import HTMLResponse, JSONResponse
from src.platform.inspection_security import operations_path

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


def _source_independent(path: str) -> bool:
    """Account recovery, health and static assets do not consume league facts.

    Authentication/CSRF stays in the outer account boundary. Account actions
    explicitly prepare their intended league before committing user intent.
    """
    return path in {"/account", "/api/account", "/health/live", "/health/ready"} or path.startswith(
        ("/account/", "/api/account/", "/static/")
    )


def _unavailable_response(scope: dict[str, Any], *, status: int, reason: str):
    path = str(scope.get("path") or "/")
    accept = next((value.decode("latin-1") for key, value in scope.get("headers") or () if key.lower() == b"accept"), "")
    if scope.get("method") != "GET" or path.startswith("/api/") or "text/html" not in accept:
        return JSONResponse({"status": "invalid" if status == 422 else "failed", "reason": reason}, status_code=status, headers={"Cache-Control": "no-store"})
    from src.platform.account_context import current_account
    from src.ui.theme import DESIGN_SYSTEM_CSS

    account = current_account()
    league = account.membership.league_name if account and account.membership else "Selected league"
    retry = quote(path, safe="/") if path.startswith("/") and not path.startswith("//") else "/"
    query = urlencode(parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True))
    if query:
        retry += "?" + query
    heading = "League could not be opened" if status == 422 else "League data is temporarily unavailable"
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>League data unavailable · DTOS</title><style>' + DESIGN_SYSTEM_CSS +
        'body{margin:0;background:var(--background,#141617);color:var(--text,#f1f5f3);font:16px system-ui}'
        'main{max-width:640px;margin:auto;padding:24px 16px;box-sizing:border-box;overflow-wrap:anywhere}'
        'nav{display:flex;flex-wrap:wrap;gap:12px}nav a{display:inline-flex;align-items:center;min-height:44px;padding:0 14px}</style></head>'
        '<body><main><p>' + escape(league or "Selected league") + '</p>'
        '<h1>' + heading + '</h1>'
        '<p>No supported roster is ready for this league right now. Your account and saved leagues are unchanged.</p>'
        '<p>You can retry this page or use your account controls to choose another connected league.</p>'
        '<nav aria-label="League recovery">'
        f'<a class="ds-action primary" href="{escape(retry, quote=True)}">Try this page again</a>'
        '<a class="ds-action" href="/account/leagues">Choose a connected league</a>'
        '<a class="ds-action" href="/account">Your account</a></nav></main></body></html>',
        status_code=status, headers={"Cache-Control": "no-store"},
    )


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
        if scope.get("type") != "http" or operations_path(str(scope.get('path') or '')) or _source_independent(str(scope.get("path") or "")):
            await self.app(scope, receive, send)
            return
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        trusted = scope.get("dtos_authorized_league")
        requested = (
            trusted
            or
            (query.get("league_id") or query.get("league") or [None])[0]
            or _path_league(str(scope.get("path") or ""), str(scope.get("method") or "GET"))
        )
        if not requested or str(requested) == self.default_league_id:
            runtime = await self.manager.acquire_request(self.default_league_id, hydrate=False)
        else:
            if not self.import_enabled and not trusted:
                response = JSONResponse({
                    "status": "feature_gated",
                    "reason": "Secondary-league hydration is disabled until isolation validation is enabled.",
                }, status_code=403)
                await response(scope, receive, send)
                return
            try:
                runtime = await self.manager.acquire_request(str(requested))
            except LeagueRuntimeNotFound as exc:
                response = _unavailable_response(scope, status=422, reason=str(exc))
                await response(scope, receive, send)
                return
            except LeagueRuntimeError as exc:
                response = _unavailable_response(scope, status=503, reason=str(exc))
                await response(scope, receive, send)
                return
        context = runtime.canonical_context if runtime is not None else None
        if runtime is not None:
            runtime.touch()
        token = _CURRENT_CONTEXT.set(context)
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT_CONTEXT.reset(token)
            if runtime is not None:
                await self.manager.release_request(runtime)
