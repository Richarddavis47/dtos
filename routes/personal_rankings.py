"""Private My DTOS ranking editor over prepared canonical Market evidence."""
from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.core.request_execution import run_manager_read
from src.platform.account_context import current_account, SESSION_COOKIE

_STATIC = Path(__file__).resolve().parents[1] / 'static'
_HEADERS = {'Cache-Control': 'no-store', 'Vary': 'Cookie'}
_BODY_LIMIT = 524_288


def create_personal_rankings_router(*, service: Any, require_data: Callable,
                                    market_model: Callable, page: Callable) -> APIRouter:
    router = APIRouter(tags=['my-dtos'])

    def account_context(request: Request):
        account = current_account()
        # Recheck the live session rather than trusting a context acquired before
        # a revocation. Inspection contexts cannot write account-owned intent.
        token = request.cookies.get(SESSION_COOKIE, '')
        live = service.store.context_for_session(token) if token else None
        if account is None or live is None or live.account_id != account.account_id:
            raise HTTPException(401, 'Sign in to view your My DTOS preferences.')
        if (live.membership is None or account.membership is None
                or live.membership.league_id != account.membership.league_id
                or live.membership.roster_id != account.membership.roster_id):
            raise HTTPException(409, 'Your league changed. Reload My DTOS before editing.')
        return live

    def failure(exc: Exception):
        code = getattr(exc, 'code', '')
        if code or isinstance(exc, ValueError):
            message = str(exc)
            status = getattr(exc, 'status', None) or (409 if any(word in (str(code) + ' ' + message).lower()
                               for word in ('revision', 'stale', 'changed', 'conflict')) else 422)
            return JSONResponse({'status': code or 'invalid_preference', 'message': message},
                                status_code=status, headers=_HEADERS)
        logging.getLogger(__name__).error('my_dtos_unavailable type=%s', type(exc).__name__)
        return JSONResponse({'status': 'preferences_unavailable',
                             'message': 'My DTOS could not complete this operation. Your saved rankings remain available; reload and try again.'},
                            status_code=503, headers=_HEADERS)

    def enrich(result, account):
        return {**result, 'csrf_token': account.csrf_token,
                'account_scope': {'league_id': account.membership.league_id,
                                  'roster_id': account.membership.roster_id},
                'heavy_work': {'provider_calls': 0, 'discovery_calls': 0,
                               'solver_calls': 0, 'fois_calls': 0, 'history_calls': 0}}

    @router.get('/static/js/personal_rankings.js', include_in_schema=False)
    async def script():
        return Response((_STATIC / 'js/personal_rankings.js').read_text(encoding='utf-8'),
                        media_type='text/javascript', headers={'Cache-Control': 'no-cache'})

    @router.get('/static/css/personal_rankings.css', include_in_schema=False)
    async def stylesheet():
        return Response((_STATIC / 'css/personal_rankings.css').read_text(encoding='utf-8'),
                        media_type='text/css', headers={'Cache-Control': 'no-cache'})

    @router.get('/account/my-dtos', response_class=HTMLResponse)
    async def editor(request: Request):
        account_context(request)
        body = '''<link rel="stylesheet" href="/static/css/personal_rankings.css">
<section id="my-dtos" class="personal-rankings" aria-labelledby="my-dtos-heading">
<div class="personal-heading"><div><p class="muted">Account · Your saved opinions</p><h2 id="my-dtos-heading">My DTOS</h2></div><a class="btn" href="/account">Account</a></div>
<p class="personal-intro">Your rankings. Neutral Market facts stay separate.</p>
<p id="personal-scope" class="muted"></p>
<div class="personal-mode" role="group" aria-label="DTOS valuation mode"><button class="btn" id="personal-neutral" type="button" aria-pressed="true">Neutral DTOS</button><button class="btn" id="personal-custom" type="button" aria-pressed="false">Custom DTOS</button></div>
<p id="personal-mode-description">Neutral values. Your saved rankings are preserved.</p>
<div id="personal-status" role="status" aria-live="polite">Loading rankings…</div>
<div id="personal-error" role="alert" hidden></div>
<div class="personal-actions"><button class="btn" id="personal-initialize" type="button" hidden>Create Custom Rankings</button><button class="btn" id="personal-reload" type="button">Reload rankings</button><button class="btn" id="personal-restart" type="button" disabled>Restart Rankings</button><a class="btn" href="/trades">Trade Center</a><a class="btn" href="/market">Market</a></div>

<details class="personal-explanation"><summary>How personal values work</summary><p id="personal-method">Your saved order is separate from neutral Market prices. Personal valuations use the supported canonical Market curve and are labeled as your opinion; they are never an opposing manager’s prices or historical quotes.</p><p>Targets and Avoid are soft saved preferences. Protect keeps an exact owned asset out of generated outgoing suggestions. Temporary Trade choices are separate. Manual packages remain editable and can be evaluated with an explicit conflict warning.</p><p>Tier breaks organize your personal ranking; they do not invent equal prices for unlike assets. New or unresolved assets require review or an explicit Restart.</p></details>
<div class="personal-filters"><label for="personal-search">Search players or exact picks<input id="personal-search" type="search" placeholder="Player, year or original franchise" autocomplete="off"></label><label for="personal-position">Position<select id="personal-position"><option value="">Overall · players and picks</option><option>QB</option><option>RB</option><option>WR</option><option>TE</option><option value="PICK">Draft picks</option></select></label></div>
<p class="muted personal-order-note">Positions refer to the full overall order.</p>
<p id="personal-results-count" class="muted"></p>
<ol id="personal-list" class="personal-list" aria-label="Overall asset rankings"></ol>
<nav class="personal-pagination" aria-label="Ranking pages"><button class="btn" id="personal-previous" type="button">Previous</button><span id="personal-page"></span><button class="btn" id="personal-next" type="button">Next</button></nav>

<dialog id="personal-restart-dialog" aria-labelledby="personal-restart-title"><h3 id="personal-restart-title">Restart Rankings?</h3><p>This replaces your customized order and tier changes with the latest compatible Market rankings. Your Target, Avoid and Protect preferences are preserved unless you choose to reset them too.</p><label><input id="personal-reset-flags" type="checkbox"> Also reset Target, Avoid and Protect preferences</label><div class="personal-actions"><button class="btn" id="personal-restart-cancel" type="button">Keep my rankings</button><button class="btn" id="personal-restart-confirm" type="button">Replace with latest Market rankings</button></div></dialog>
</section><script src="/static/js/personal_rankings.js" defer></script>'''
        response = page('My DTOS', body)
        for key, value in _HEADERS.items():
            response.headers[key] = value
        return response

    @router.get('/api/my-dtos')
    async def state(request: Request):
        from services.personal_rankings import view_state
        account = account_context(request)
        try:
            data, reader = require_data(), market_model()
            result = await run_manager_read(lambda: view_state(service.store, data, reader, account))
            account_context(request)
            return JSONResponse(enrich(result, account), headers=_HEADERS)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(exc)

    @router.post('/api/my-dtos')
    async def command(request: Request):
        from services.personal_rankings import apply_command
        account = account_context(request)
        supplied = request.headers.get('x-csrf-token', '')
        if not supplied or not hmac.compare_digest(supplied, account.csrf_token):
            raise HTTPException(403, 'csrf_rejected')
        origin = request.headers.get('origin')
        expected_origin = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if origin and origin.rstrip('/') != expected_origin.rstrip('/'):
            raise HTTPException(403, 'foreign_origin')
        if request.headers.get('content-type', '').split(';', 1)[0] != 'application/json':
            raise HTTPException(415, 'Use a JSON preference command.')
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > _BODY_LIMIT:
                raise HTTPException(413, 'Preference command is too large.')
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(422, 'Invalid preference command.') from exc
        if not isinstance(payload, dict):
            raise HTTPException(422, 'Invalid preference command.')
        try:
            data, reader = require_data(), market_model()
            result = await run_manager_read(lambda: apply_command(service.store, data, reader, account, payload))
            account_context(request)
            return JSONResponse(enrich(result, account), headers=_HEADERS)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(exc)

    return router
