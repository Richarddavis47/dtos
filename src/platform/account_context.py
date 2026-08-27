"""Authentication and league-scoped authorization at the ASGI boundary."""
from __future__ import annotations

import hmac
import os
import re
from contextvars import ContextVar
from typing import Any
from urllib.parse import parse_qsl, urlencode

from starlette.responses import JSONResponse, RedirectResponse

from src.core.accounts import AccountContext, AccountService, LeagueMembership

SESSION_COOKIE = "dtos_session"
_CURRENT_ACCOUNT: ContextVar[AccountContext | None] = ContextVar("dtos_account", default=None)


def current_account() -> AccountContext | None:
    return _CURRENT_ACCOUNT.get()


def _cookies(scope: dict[str, Any]) -> dict[str, str]:
    headers = {key.lower(): value for key, value in scope.get("headers") or ()}
    raw = headers.get(b"cookie", b"").decode("latin-1")
    return dict(item.strip().split("=", 1) for item in raw.split(";") if "=" in item)


def _header(scope: dict[str, Any], name: bytes) -> str:
    return next((value.decode("latin-1") for key, value in scope.get("headers") or () if key.lower() == name), "")


PUBLIC_PREFIXES = (
    "/account", "/health", "/api/status", "/api/platform", "/api/inspect",
    "/current-visual", "/openapi.json", "/docs", "/redoc", "/static",
)
PUBLIC_API_PREFIXES = (
    "/api/status", "/api/platform/health", "/api/data/health", "/api/inspect",
    "/api/account", "/api/market/health",
)


class AccountContextMiddleware:
    def __init__(self, app: Any, *, service: AccountService, required: bool) -> None:
        self.app = app
        self.service = service
        self.required = required

    def _inspection_context(self, scope: dict[str, Any]) -> AccountContext | None:
        expected = os.getenv("DTOS_INSPECTION_AUTH_TOKEN", "")
        supplied = _header(scope, b"x-dtos-inspection-auth")
        if not (expected and supplied and hmac.compare_digest(expected, supplied)):
            return None
        league_id = os.getenv("DTOS_INSPECTION_LEAGUE_ID", "").strip()
        roster_value = os.getenv("DTOS_INSPECTION_ROSTER_ID", "").strip()
        if not league_id or not roster_value.isdigit():
            return None
        roster_id = int(roster_value)
        membership = LeagueMembership(
            account_id="inspection-account",
            league_id=league_id,
            sleeper_user_id="inspection-sleeper",
            roster_id=roster_id,
            status="active",
            mapping_source="inspection_fixture",
            league_name=os.getenv("DTOS_INSPECTION_LEAGUE_NAME", "Inspection League").strip(),
            franchise_name=os.getenv("DTOS_INSPECTION_FRANCHISE_NAME", "Inspection Franchise").strip(),
            season=None,
        )
        return AccountContext(
            account_id="inspection-account",
            username="inspection",
            display_name="Inspection",
            sleeper_user_id="inspection-sleeper",
            sleeper_username=None,
            sleeper_link_state="inspection_fixture",
            active_league_id=league_id,
            membership=membership,
            csrf_token="",
            session_id="inspection-session",
        )

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path, method = str(scope.get("path") or "/"), str(scope.get("method") or "GET").upper()
        token = _cookies(scope).get(SESSION_COOKIE, "")
        context = self.service.store.context_for_session(token) if token else None
        inspection_context = self._inspection_context(scope)
        if context is None and inspection_context is not None:
            context = inspection_context
        inspection = inspection_context is not None
        private_api = path.startswith("/api/") and not path.startswith(PUBLIC_API_PREFIXES)
        if context is not None and method not in {"GET", "HEAD", "OPTIONS"} and not path.startswith(("/account", "/api/inspect")):
            supplied = _header(scope, b"x-csrf-token")
            body = b""
            if not supplied:
                while True:
                    message = await receive()
                    body += message.get("body", b"")
                    if not message.get("more_body"):
                        break
                supplied = dict(parse_qsl(body.decode("utf-8", errors="replace"), keep_blank_values=True)).get("csrf_token", "")
                sent = False
                async def replay() -> dict[str, Any]:
                    nonlocal sent
                    if sent:
                        return {"type": "http.request", "body": b"", "more_body": False}
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                receive = replay
            if not self.service.store.verify_csrf(token, supplied):
                response = JSONResponse({"status": "csrf_rejected"}, status_code=403)
                await response(scope, receive, send)
                return
        if context is not None and context.membership is not None:
            account_league_action = method == "POST" and (
                path == "/account/leagues/import"
                or bool(re.fullmatch(r"/account/leagues/[0-9]+(?:/activate)?", path))
            )
            league_path = None if account_league_action else re.search(r"/(?:league|leagues)/([^/]+)", path)
            if league_path and league_path.group(1) != context.membership.league_id:
                response = JSONResponse({"status": "unauthorized_league"}, status_code=403)
                await response(scope, receive, send)
                return
            query = dict(parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True))
            query["league"] = context.membership.league_id
            if "league_id" in query:
                query["league_id"] = context.membership.league_id
            if private_api or path.startswith(("/trades", "/front-offices", "/market", "/players")) or path in {"/", "/teams"}:
                query["front_office"] = str(context.membership.roster_id)
            scope["query_string"] = urlencode(query).encode()
            scope["dtos_authorized_league"] = context.membership.league_id
            if path == "/teams":
                scope["path"] = f"/teams/{context.membership.roster_id}"
                scope["raw_path"] = scope["path"].encode()
        private_html = path == "/" or path.startswith((
            "/teams", "/trades", "/league", "/market", "/front-offices", "/fois",
            "/matchups", "/transactions", "/picks", "/settings", "/brain", "/valuation",
            "/players", "/history", "/commissioner",
        ))
        if self.required and context is None and not inspection and (private_api or private_html):
            response = (
                JSONResponse({"status": "authentication_required", "reason": "Sign in to access this DTOS league context."}, status_code=401)
                if private_api or path.startswith("/api/")
                else RedirectResponse(f"/account/sign-in?next={path}", status_code=303)
            )
            await response(scope, receive, send)
            return
        if self.required and context is not None and context.membership is None and not inspection and (private_api or private_html):
            response = (
                JSONResponse({"status": "active_league_required"}, status_code=403)
                if private_api
                else RedirectResponse("/account/leagues", status_code=303)
            )
            await response(scope, receive, send)
            return
        private_response = bool(context is not None and (private_api or private_html or path.startswith(("/account", "/api/account"))))
        original_send = send
        if private_response:
            async def private_send(message: dict[str, Any]) -> None:
                if message.get("type") == "http.response.start":
                    headers = [(key, value) for key, value in message.get("headers", []) if key.lower() not in {b"cache-control", b"vary"}]
                    headers.extend(((b"cache-control", b"no-store, private"), (b"vary", b"Cookie")))
                    message = {**message, "headers": headers}
                await original_send(message)
            send = private_send
        marker = _CURRENT_ACCOUNT.set(context)
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT_ACCOUNT.reset(marker)
