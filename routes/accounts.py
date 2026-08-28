"""Consumer-facing DTOS account and Sleeper onboarding routes."""
from __future__ import annotations

import hashlib
import sqlite3
from html import escape
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from config import SESSION_COOKIE_SECURE, SESSION_TTL_HOURS
from src.core.accounts import AccountService
from src.platform.account_context import SESSION_COOKIE, current_account
from src.ui.design_system import DESIGN_SYSTEM_CSS, account_page_header


def _shell(title: str, body: str, *, purpose: str = "Manage secure access to your dynasty front office.") -> HTMLResponse:
    css = """:root{--line:#26374c;--text:#f5f7fb;--muted:#9fb0c6;--accent:#6ee7b7;--gold:#f5c451}body{margin:0;background:#07111f;color:#f5f7fb;font-family:Inter,system-ui,sans-serif}.auth{max-width:720px;margin:auto;padding:28px 18px}.card{background:#101d2d;border:1px solid #26374c;border-radius:18px;padding:20px;margin:14px 0}.grid{display:grid;gap:12px}label{font-weight:800}input,select{width:100%;padding:13px;margin-top:6px;border-radius:10px;border:1px solid #39506b;background:#07111f;color:#fff}.btn{display:inline-flex;min-height:46px;align-items:center;justify-content:center;border:0;border-radius:10px;padding:10px 16px;background:#6ee7b7;color:#062018;font-weight:900;cursor:pointer}a{color:#6ee7b7}.muted{color:#9fb0c6}.error{color:#fca5a5}.good{color:#6ee7b7}@media(max-width:600px){.auth{padding:18px 13px}.card{padding:16px}}"""
    header = account_page_header(title, purpose=purpose)
    return HTMLResponse(f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · DTOS</title><style>{DESIGN_SYSTEM_CSS}{css}</style></head><body><main class="auth">{header}{body}</main></body></html>', headers={"Cache-Control": "no-store"})


async def _form(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8", errors="replace")
    return {key: values[-1] for key, values in parse_qs(raw, keep_blank_values=True).items()}


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL_HOURS * 3600, httponly=True, secure=SESSION_COOKIE_SECURE, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"


def _csrf(service: AccountService, request: Request, value: str) -> bool:
    token = request.cookies.get(SESSION_COOKIE, "")
    return bool(token and value and service.store.verify_csrf(token, value))


def _auth_client(request: Request) -> str:
    address = request.client.host if request.client else "unknown"
    return hashlib.sha256(address.encode()).hexdigest()


def _safe_browser_post(request: Request) -> bool:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    return origin.rstrip("/") == expected.rstrip("/")


def _recovery_page(codes: list[str]) -> HTMLResponse:
    rows = "".join(f"<li><code>{escape(code)}</code></li>" for code in codes)
    return _shell("Recovery codes", f'<section class="card"><h1>Save your recovery codes</h1><p>Store these one-time codes somewhere safe. DTOS cannot display them again. Using one rotates every code and signs out existing sessions.</p><ol>{rows}</ol><a class="btn" href="/account/sleeper">Continue</a></section>')


def create_accounts_router(*, service: AccountService, runtime_manager: Any) -> APIRouter:
    router = APIRouter(tags=["accounts"])

    @router.get("/account")
    async def account_home() -> HTMLResponse:
        context = current_account()
        if context is None:
            return _shell("Welcome", '<section class="card"><h2>Welcome to DTOS</h2><p>Your dynasty front office. Sign in or create an account, then connect Sleeper to find your leagues and teams.</p><p><a class="btn ds-action primary" data-dtos-action="primary" data-action-id="sign-in" href="/account/sign-in">Sign in</a> &nbsp; <a href="/account/create">Create account</a></p></section>', purpose="Sign in or create an account to open your dynasty front office.")
        if not context.sleeper_user_id:
            return RedirectResponse("/account/sleeper", status_code=303)
        if not context.membership:
            return RedirectResponse("/account/leagues", status_code=303)
        return _shell("Account", f'<section class="card"><h2>{escape(context.display_name)}</h2><p>Linked Sleeper identity: <b>{escape(context.sleeper_username or "Resolved")}</b> <span class="muted">(resolved, ownership not independently verified)</span></p><p>Active league: <b>{escape(context.membership.league_name or context.membership.league_id)}</b><br>Your team: <b>{escape(context.membership.franchise_name or "Mapped franchise")}</b></p><p><a class="btn ds-action primary" data-dtos-action="primary" data-action-id="open-front-office" href="/">Open DTOS</a> &nbsp; <a href="/account/leagues">Your leagues</a></p><form method="post" action="/account/logout"><input type="hidden" name="csrf_token" value="{escape(context.csrf_token)}"><button class="btn" type="submit">Log out</button></form></section>', purpose="Review the linked identity and open the active dynasty front office.")

    @router.get("/account/sign-in")
    async def sign_in_page(error: str = "") -> HTMLResponse:
        message = '<p class="error">Sign-in failed. Check your details and try again.</p>' if error else ""
        return _shell("Sign in", f'<section class="card"><h2>Sign in to DTOS</h2>{message}<form class="grid" method="post" action="/account/sign-in"><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button class="btn ds-action primary" data-dtos-action="primary" data-action-id="sign-in" type="submit">Sign in</button></form><p class="muted">New to DTOS? <a href="/account/create">Create an account</a>.</p></section>', purpose="Use your DTOS credentials to return to your saved leagues.")

    @router.post("/account/sign-in")
    async def sign_in(request: Request) -> Response:
        if not _safe_browser_post(request):
            return JSONResponse({"status": "request_rejected"}, status_code=403)
        client_digest = _auth_client(request)
        if service.store.recent_auth_failures("sign_in", client_digest) >= 5:
            return JSONResponse({"status": "rate_limited"}, status_code=429, headers={"Retry-After": "900"})
        values = await _form(request)
        account_id = service.authenticate(values.get("username", ""), values.get("password", ""))
        if account_id is None:
            service.store.record_auth_result(None, "sign_in", "failure", client_digest)
            return RedirectResponse("/account/sign-in?error=1", status_code=303)
        service.store.record_auth_result(account_id, "sign_in", "success", client_digest)
        token, _ = service.new_session(account_id)
        response = RedirectResponse("/account", status_code=303)
        _set_session(response, token)
        return response

    @router.get("/account/create")
    async def create_page(error: str = "") -> HTMLResponse:
        message = f'<p class="error">{escape(error)}</p>' if error else ""
        return _shell("Create account", f'<section class="card"><h2>Create your DTOS account</h2>{message}<form class="grid" method="post" action="/account/create"><label>Display name<input name="display_name" autocomplete="name" required></label><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="new-password" minlength="12" required></label><button class="btn ds-action primary" data-dtos-action="primary" data-action-id="create-account" type="submit">Create account</button></form><p class="muted">Your DTOS account is separate from your Sleeper identity.</p></section>', purpose="Create a secure DTOS identity before linking a public Sleeper account.")

    @router.post("/account/create")
    async def create_account(request: Request) -> Response:
        if not _safe_browser_post(request):
            return JSONResponse({"status": "request_rejected"}, status_code=403)
        client_digest = _auth_client(request)
        if service.store.recent_auth_failures("account_creation", client_digest, minutes=60) >= 3:
            return JSONResponse({"status": "rate_limited"}, status_code=429, headers={"Retry-After": "3600"})
        values = await _form(request)
        try:
            account_id, recovery_codes = service.create_account(values.get("username", ""), values.get("display_name", ""), values.get("password", ""))
        except Exception as exc:
            service.store.record_auth_result(None, "account_creation", "failure", client_digest)
            return _shell("Create account", f'<section class="card"><h1>We could not create that account.</h1><p class="error">{escape(str(exc) if isinstance(exc, ValueError) else "Choose a different username and try again.")}</p><p><a href="/account/create">Try again</a></p></section>')
        service.store.record_auth_result(account_id, "account_creation", "success", client_digest)
        token, _ = service.new_session(account_id)
        response = _recovery_page(recovery_codes)
        _set_session(response, token)
        return response

    @router.get("/account/recover")
    async def recover_page(error: str = "") -> HTMLResponse:
        message = '<p class="error">Recovery failed. Check the account name and unused code.</p>' if error else ""
        return _shell("Recover account", f'<section class="card"><h2>Recover your DTOS account</h2>{message}<form class="grid" method="post" action="/account/recover"><label>Username<input name="username" autocomplete="username" required></label><label>One-time recovery code<input type="password" name="recovery_code" autocomplete="one-time-code" required></label><label>New password<input type="password" name="new_password" autocomplete="new-password" minlength="12" required></label><button class="btn ds-action primary" data-dtos-action="primary" data-action-id="recover-account" type="submit">Reset password</button></form></section>', purpose="Use a one-time recovery code to restore secure account access.")

    @router.post("/account/recover")
    async def recover_account(request: Request) -> Response:
        if not _safe_browser_post(request):
            return JSONResponse({"status": "request_rejected"}, status_code=403)
        client_digest = _auth_client(request)
        if service.store.recent_auth_failures("credential_recovery", client_digest) >= 5:
            return JSONResponse({"status": "rate_limited"}, status_code=429, headers={"Retry-After": "900"})
        values = await _form(request)
        try:
            recovered = service.recover(values.get("username", ""), values.get("recovery_code", ""), values.get("new_password", ""))
        except ValueError as exc:
            return _shell("Recover account", f'<section class="card"><h1>Recovery failed.</h1><p class="error">{escape(str(exc))}</p><a href="/account/recover">Try again</a></section>')
        if recovered is None:
            service.store.record_auth_result(None, "credential_recovery", "failure", client_digest)
            return RedirectResponse("/account/recover?error=1", status_code=303)
        account_id, replacement_codes = recovered
        service.store.record_auth_result(account_id, "credential_recovery", "success", client_digest)
        token, _ = service.new_session(account_id)
        response = _recovery_page(replacement_codes)
        _set_session(response, token)
        return response

    @router.post("/account/logout")
    async def logout(request: Request) -> Response:
        values = await _form(request)
        if not _csrf(service, request, values.get("csrf_token", "")):
            return JSONResponse({"status": "csrf_rejected"}, status_code=403)
        token = request.cookies.get(SESSION_COOKIE, "")
        service.store.revoke_session(token)
        response = RedirectResponse("/account/sign-in", status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
        response.headers["Cache-Control"] = "no-store"
        return response

    @router.get("/account/sleeper")
    async def sleeper_page(error: str = "") -> HTMLResponse:
        context = current_account()
        if context is None:
            return RedirectResponse("/account/sign-in", status_code=303)
        message = f'<p class="error">{escape(error)}</p>' if error else ""
        return _shell("Connect Sleeper", f'<section class="card"><h2>Connect your Sleeper account</h2><p>Enter your Sleeper username so DTOS can resolve your public Sleeper identity and find your leagues.</p>{message}<form class="grid" method="post" action="/account/sleeper"><input type="hidden" name="csrf_token" value="{escape(context.csrf_token)}"><label>Sleeper username<input name="sleeper_username" required></label><button class="btn ds-action primary" data-dtos-action="primary" data-action-id="connect-sleeper" type="submit">Find my Sleeper account</button></form><p class="muted">This links a resolved Sleeper identity. Sleeper does not provide DTOS with proof that you control the account.</p></section>', purpose="Resolve a public Sleeper identity and discover its eligible leagues.")

    @router.post("/account/sleeper")
    async def link_sleeper(request: Request) -> Response:
        context = current_account()
        values = await _form(request)
        if context is None:
            return RedirectResponse("/account/sign-in", status_code=303)
        if not _csrf(service, request, values.get("csrf_token", "")):
            return JSONResponse({"status": "csrf_rejected"}, status_code=403)
        try:
            user = await service.resolve_sleeper(values.get("sleeper_username", ""))
            service.store.link_sleeper(context.account_id, sleeper_user_id=str(user["user_id"]), username=user.get("username"), display_name=user.get("display_name"))
        except (ValueError, sqlite3.IntegrityError) as exc:
            detail = str(exc) if isinstance(exc, ValueError) else "That Sleeper identity is already linked to another DTOS account."
            return _shell("Connect Sleeper", f'<section class="card"><h1>We could not connect that identity.</h1><p class="error">{escape(detail)}</p><a href="/account/sleeper">Try again</a></section>')
        return RedirectResponse("/account/leagues", status_code=303)

    @router.get("/account/leagues")
    async def leagues_page() -> HTMLResponse:
        context = current_account()
        if context is None:
            return RedirectResponse("/account/sign-in", status_code=303)
        if not context.sleeper_user_id:
            return RedirectResponse("/account/sleeper", status_code=303)
        if context.sleeper_link_state == "inspection_fixture" and context.membership is not None:
            discovered = [{
                "league_id": context.membership.league_id,
                "name": context.membership.league_name,
                "season": context.membership.season,
                "total_rosters": 1,
            }]
            memberships = {context.membership.league_id: context.membership}
        else:
            try:
                discovered_series = await service.discover_series(context.sleeper_user_id)
                discovered = [item.public() for item in discovered_series]
            except Exception:
                return _shell("Your leagues", '<section class="card"><h1>Sleeper is temporarily unavailable.</h1><p>Your linked identity is safe. Try league discovery again shortly.</p></section>')
            memberships = {item.league_id: item for item in service.store.memberships(context.account_id)}
        cards = []
        for league in discovered:
            league_id = str(league.get("league_id"))
            membership = memberships.get(league_id)
            connected = bool(membership and membership.status == "active")
            state = "Switch front office" if connected else "Add to DTOS"
            action = f"/account/leagues/{league_id}/activate" if connected else f"/account/leagues/{league_id}"
            history = league.get("historical_seasons") or []
            years = ", ".join(str(row.get("season")) for row in history if row.get("season"))
            cards.append(f'<article class="card"><h2>{escape(str(league.get("name") or "Sleeper league"))}</h2><p>Current season: {escape(str(league.get("season") or "Unknown"))} · {int(league.get("total_rosters") or 0)} teams</p>{f"<p>History: {escape(years)}</p>" if years else ""}<p>{"Your team: <b>" + escape(membership.franchise_name or "Mapped franchise") + "</b>" if membership else "DTOS will map the franchise associated with your resolved Sleeper identity."}</p><form method="post" action="{escape(action)}"><input type="hidden" name="csrf_token" value="{escape(context.csrf_token)}"><button class="btn" type="submit">{state}</button></form></article>')
        return _shell("Your leagues", f'<p class="muted">Current NFL dynasty leagues are shown first.</p>{"".join(cards) or "<section class=\"card\"><h2>No eligible leagues found</h2><p>Check the linked Sleeper username or try again later.</p></section>"}<section class="card"><h2>Add another league</h2><p>Enter a Sleeper league ID. DTOS will add it only if your resolved identity maps to exactly one franchise.</p><form class="grid" method="post" action="/account/leagues/import"><input type="hidden" name="csrf_token" value="{escape(context.csrf_token)}"><label>Sleeper league ID<input name="league_id" inputmode="numeric" required></label><button class="btn ds-action primary" data-dtos-action="primary" data-action-id="import-league" type="submit">Add to DTOS</button></form></section>', purpose="Choose an authorized league series or add another verified membership.")

    @router.post("/account/leagues/import")
    async def import_league(request: Request) -> Response:
        context = current_account()
        values = await _form(request)
        if context is None or not context.sleeper_user_id:
            return RedirectResponse("/account/sign-in", status_code=303)
        if not _csrf(service, request, values.get("csrf_token", "")):
            return JSONResponse({"status": "csrf_rejected"}, status_code=403)
        try:
            league = await service.league(values.get("league_id", ""))
            roster_id, franchise, status = await service.resolve_membership(league, context.sleeper_user_id)
        except (ValueError, httpx.HTTPError):
            return _shell("League unavailable", '<section class="card"><h1>We could not add that league.</h1><p>Confirm the Sleeper league ID and try again.</p></section>')
        if status != "active" or roster_id is None:
            return _shell("Review team mapping", '<section class="card"><h1>We found the league, but could not confidently match your team.</h1><p>DTOS did not guess or create ownership.</p></section>')
        service.store.upsert_membership(context.account_id, league, context.sleeper_user_id, roster_id, franchise, status)
        series = await service.complete_series(league)
        service.store.upsert_series(context.account_id, series_id=series.series_id, current_league=series.current_league, seasons=series.seasons, roster_id=roster_id, franchise_name=franchise)
        await runtime_manager.get(str(league["league_id"]))
        service.store.activate(context.account_id, str(league["league_id"]))
        return RedirectResponse("/", status_code=303)

    @router.post("/account/leagues/{league_id}")
    async def add_league(league_id: str, request: Request) -> Response:
        context = current_account()
        values = await _form(request)
        if context is None or not context.sleeper_user_id:
            return RedirectResponse("/account/sign-in", status_code=303)
        if not _csrf(service, request, values.get("csrf_token", "")):
            return JSONResponse({"status": "csrf_rejected"}, status_code=403)
        discovered = {item.current_league_id: item for item in await service.discover_series(context.sleeper_user_id)}
        series = discovered.get(league_id)
        if series is None:
            return _shell("League unavailable", '<section class="card"><h1>That league is not available to this Sleeper identity.</h1></section>')
        league = series.current_league
        series = await service.complete_series(league)
        roster_id, franchise, status = await service.resolve_membership(league, context.sleeper_user_id)
        if status != "active":
            return _shell("Review team mapping", '<section class="card"><h1>We found the league, but could not confidently match your team.</h1><p>DTOS did not guess or create ownership. Review the linked Sleeper identity or try again after Sleeper updates the league.</p></section>')
        service.store.upsert_membership(context.account_id, league, context.sleeper_user_id, roster_id, franchise, status)
        service.store.upsert_series(context.account_id, series_id=series.series_id, current_league=series.current_league, seasons=series.seasons, roster_id=roster_id, franchise_name=franchise)
        await runtime_manager.get(league_id)
        service.store.activate(context.account_id, league_id)
        return RedirectResponse("/", status_code=303)

    @router.post("/account/leagues/{league_id}/activate")
    async def activate_league(league_id: str, request: Request) -> Response:
        context = current_account()
        values = await _form(request)
        if context is None or not _csrf(service, request, values.get("csrf_token", "")):
            return JSONResponse({"status": "csrf_rejected"}, status_code=403)
        membership = service.store.activate(context.account_id, league_id)
        if membership is None:
            return JSONResponse({"status": "unauthorized_league"}, status_code=403)
        await runtime_manager.get(league_id)
        return RedirectResponse("/", status_code=303)

    @router.get("/api/account")
    async def account_api() -> JSONResponse:
        context = current_account()
        if context is None:
            return JSONResponse({"status": "authentication_required"}, status_code=401)
        return JSONResponse(service.public_context(context), headers={"Cache-Control": "no-store"})

    @router.get("/api/account/health")
    async def account_health_api() -> JSONResponse:
        health = service.store.health()
        return JSONResponse({
            "status": health["status"], "schema_version": health["schema_version"],
            "session_storage": "database_backed_opaque_tokens",
        }, headers={"Cache-Control": "no-store"})

    @router.get("/api/account/leagues")
    async def account_leagues_api() -> JSONResponse:
        context = current_account()
        if context is None:
            return JSONResponse({"status": "authentication_required"}, status_code=401)
        return JSONResponse({"status": "ok", "membership_model": "one_to_many", "hardcoded_league_limit": False, "leagues": [{
            "series_id": item["series_id"], "league_id": item["current_league_id"],
            "league_name": item.get("league_name"), "franchise_name": item.get("franchise_name"),
            "roster_id": item.get("roster_id"), "season": item.get("current_season"),
            "historical_season_count": max(0, int(item.get("season_count") or 1) - 1),
            "status": item.get("status"),
        } for item in service.store.series(context.account_id)]}, headers={"Cache-Control": "no-store"})

    @router.get("/api/account/active-league")
    async def active_league_api() -> JSONResponse:
        context = current_account()
        if context is None:
            return JSONResponse({"status": "authentication_required"}, status_code=401)
        membership = context.membership
        return JSONResponse({"status": "ready" if membership else "selection_required", "active_league": ({
            "league_id": membership.league_id, "league_name": membership.league_name,
            "franchise_name": membership.franchise_name, "roster_id": membership.roster_id,
        } if membership else None)}, headers={"Cache-Control": "no-store"})

    @router.post("/api/account/active-league")
    async def set_active_league_api(request: Request) -> JSONResponse:
        context = current_account()
        if context is None:
            return JSONResponse({"status": "authentication_required"}, status_code=401)
        payload = await request.json()
        league_id = str(payload.get("league_id") or "")
        membership = service.store.activate(context.account_id, league_id)
        if membership is None:
            return JSONResponse({"status": "unauthorized_league"}, status_code=403)
        await runtime_manager.get(league_id)
        return JSONResponse({"status": "ready", "active_league": {
            "league_id": membership.league_id, "league_name": membership.league_name,
            "franchise_name": membership.franchise_name, "roster_id": membership.roster_id,
        }}, headers={"Cache-Control": "no-store"})

    return router
