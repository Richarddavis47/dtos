"""Private My DTOS ranking editor over prepared canonical Market evidence."""
from __future__ import annotations

import hmac
import json
import logging
from html import escape
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from src.core.request_execution import run_manager_read
from src.platform.account_context import current_account, SESSION_COOKIE

_STATIC = Path(__file__).resolve().parents[1] / 'static'
_HEADERS = {'Cache-Control': 'no-store', 'Vary': 'Cookie'}
_BODY_LIMIT = 524_288


def create_personal_rankings_router(*, service: Any, require_data: Callable,
                                    market_model: Callable, page: Callable) -> APIRouter:
    router = APIRouter(tags=['my-dtos'])

    def account_context(request: Request, *, allow_no_league=False):
        account = current_account()
        # Recheck the live session rather than trusting a context acquired before
        # a revocation. Inspection contexts cannot write account-owned intent.
        token = request.cookies.get(SESSION_COOKIE, '')
        live = service.store.context_for_session(token) if token else None
        if account is None or live is None or live.account_id != account.account_id:
            raise HTTPException(401, 'Sign in to view your My DTOS preferences.')
        if live.membership is None:
            if allow_no_league:
                return live
            raise HTTPException(403, 'Connect or select your league before using My DTOS.')
        if (account.membership is None
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
                             'message': 'My DTOS could not complete this operation. No rankings were reset. Retry to review saved state, or use Neutral Trade.'},
                            status_code=503, headers=_HEADERS)

    def enrich(result, account):
        return {**result, 'csrf_token': account.csrf_token,
                'account_scope': {'league_id': account.membership.league_id,
                                  'roster_id': account.membership.roster_id},
                'heavy_work': {'provider_calls': 0, 'discovery_calls': 0,
                               'solver_calls': 0, 'fois_calls': 0, 'history_calls': 0}}

    def source_check(data, reader, token):
        from services.personal_rankings import PersonalRankingError, _publication_token
        if (require_data() is not data or market_model() is not reader
                or _publication_token(data, reader) != token):
            raise PersonalRankingError('market_source_changed',
                'Market changed while this operation was running. Retry rankings to review the current saved state.', 409)

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
        account = account_context(request, allow_no_league=True)
        if account.membership is None:
            return RedirectResponse('/account/leagues', status_code=303, headers=_HEADERS)
        body = '''<link rel="stylesheet" href="/static/css/personal_rankings.css">
<section id="my-dtos" class="personal-rankings" aria-labelledby="my-dtos-heading">
<div class="personal-heading"><h1 id="my-dtos-heading">My DTOS</h1><a class="btn" href="/account">Account</a></div>
<div class="personal-mode" role="group" aria-label="DTOS valuation mode"><button class="btn" id="personal-neutral" type="button" aria-pressed="true" disabled>Neutral DTOS</button><button class="btn" id="personal-custom" type="button" aria-pressed="false" disabled>Custom DTOS</button></div>
<section class="personal-method-choice" aria-labelledby="personal-method-heading">
<h2 id="personal-method-heading">Custom pricing method</h2><p id="personal-active-method">Absolute Slot · existing default</p>
<p>Separate from Neutral or Custom mode. Compare before changing; your saved ranking order and choices stay intact.</p>
<div class="personal-actions"><label for="personal-method-select">Compare with<select id="personal-method-select"><option value="personal-relative-priced-order-v1">Relative</option><option value="personal-current-market-slot-curve-v1">Absolute</option></select></label><button class="btn" id="personal-method-preview" type="button" disabled>Preview method</button></div>
<p id="personal-publication-review" class="personal-qualification" hidden></p>
</section>
<button class="btn personal-start" id="personal-initialize" type="button" hidden>Create Custom Rankings</button>
<div class="personal-filters"><label for="personal-search">Search assets<input id="personal-search" type="search" placeholder="Player, year or franchise" autocomplete="off"></label><label for="personal-position">Position<select id="personal-position"><option value="">Overall · players and picks</option><option>QB</option><option>RB</option><option>WR</option><option>TE</option><option value="PICK">Draft picks</option></select></label></div>
<nav class="personal-pagination" aria-label="Ranking pages"><button class="btn" id="personal-previous" type="button" disabled>Previous</button><span id="personal-page"></span><button class="btn" id="personal-next" type="button" disabled>Next</button></nav>
<div id="personal-status" role="status" aria-live="polite" tabindex="-1">Loading rankings…</div>
<div id="personal-error" role="alert" hidden></div>
<div id="personal-recovery" class="personal-actions" hidden><button class="btn" id="personal-retry" type="button">Retry rankings</button><a class="btn" href="/market">Check Market</a><a class="btn" href="/trades">Use Neutral Trade</a></div>
<p id="personal-warnings" class="personal-qualification" hidden></p>
<details id="personal-warning-details" class="personal-explanation" hidden><summary>Custom evidence and limitations</summary><ul id="personal-warning-list"></ul></details>
<details id="personal-compatibility" class="personal-explanation personal-compatibility" hidden><summary id="personal-compatibility-summary">Review assets needing attention</summary>
<p>Your saved order, tiers and Target/Avoid/Protect choices are intact. Missing prices can affect other personal rank values. Any personal values that can still be verified remain usable; calculations needing unresolved values stay paused. Neutral Trade remains available.</p>
<p id="personal-compatibility-counts" class="muted"></p>
<ul id="personal-compatibility-issues" class="personal-compatibility-issues"></ul>
<div class="personal-actions"><button class="btn" id="personal-compatibility-retry" type="button">Retry asset evidence</button><a class="btn" href="/trades">Use Neutral Trade</a></div>
</details>
<p id="personal-results-count" class="muted"></p>
<details id="personal-settings" class="personal-explanation"><summary>Ranking settings &amp; explanation</summary>
<p id="personal-scope" class="muted"></p><p id="personal-mode-description">Neutral values. Your saved rankings are preserved.</p>
<div class="personal-actions"><button class="btn" id="personal-reload" type="button">Reload rankings</button><button class="btn" id="personal-restart" type="button" disabled>Restart Rankings</button><a class="btn" href="/trades">Trade Center</a><a class="btn" href="/market">Market</a></div>
<p id="personal-method">How personal values are assigned will appear here when rankings load.</p><p>Target and Avoid guide suggestions. Protect keeps an exact owned asset out of generated outgoing offers. These saved choices are separate from temporary Trade choices; you can still evaluate a manual offer with a conflict warning.</p><p>Tier breaks organize your list without making unlike assets equally valuable. Restart Rankings replaces your order and tiers with the latest Market baseline only after confirmation.</p></details>
<ol id="personal-list" class="personal-list" aria-label="Overall asset rankings"></ol>
<nav class="personal-pagination" aria-label="Ranking pages at end"><button class="btn" id="personal-previous-bottom" type="button" disabled>Previous</button><span id="personal-page-bottom"></span><button class="btn" id="personal-next-bottom" type="button" disabled>Next</button></nav>

<dialog id="personal-method-dialog" aria-labelledby="personal-method-title" aria-describedby="personal-method-disclosure">
<h2 id="personal-method-title">Compare Custom pricing methods</h2><p>New or lost quotes can reprice other assets. Neutral prices and your saved ranking order stay unchanged.</p><div id="personal-method-comparison"></div><p id="personal-method-disclosure"></p>
<p>Your order, tiers and Target/Avoid/Protect choices will not change. Confirming saves only this method choice and review reference, with a new preference revision. It does not switch Neutral/Custom mode or create a trade.</p>
<div class="personal-actions"><button class="btn" id="personal-method-cancel" type="button">Keep current method</button><button class="btn" id="personal-method-confirm" type="button">Confirm method</button></div></dialog>
<dialog id="personal-remove-dialog" aria-labelledby="personal-remove-title" aria-describedby="personal-remove-description"><h3 id="personal-remove-title">Remove this asset from Custom ordering?</h3><p id="personal-remove-description"></p><p>This removes only this asset’s saved rank and tier break. Other assets keep their relative order and tier breaks. All Target/Avoid/Protect choices stay saved. Personal values are recalculated from the remaining ranked assets’ current Market prices. This does not change your roster or Market prices.</p><p>To include this asset in your ranking list again, use the separate Restart Rankings action. You can keep your order and retry instead if its evidence may return.</p><div class="personal-actions"><button class="btn" id="personal-remove-cancel" type="button">Keep this asset</button><button class="btn" id="personal-remove-confirm" type="button">Remove from Custom ordering</button></div></dialog>
<dialog id="personal-restart-dialog" aria-labelledby="personal-restart-title"><h3 id="personal-restart-title">Restart Rankings?</h3><p>This replaces your customized order and tier changes with the latest compatible Market rankings. Your Target, Avoid and Protect preferences are preserved unless you choose to reset them too.</p><label><input id="personal-reset-flags" type="checkbox"> Also reset Target, Avoid and Protect preferences</label><div class="personal-actions"><button class="btn" id="personal-restart-cancel" type="button">Keep my rankings</button><button class="btn" id="personal-restart-confirm" type="button">Replace with latest Market rankings</button></div></dialog>
</section><script src="/static/js/personal_rankings.js" defer></script>'''
        # Pin the rendered shell to the same scope as the first asynchronous read.
        body = body.replace('id="my-dtos"', 'id="my-dtos" data-league-id="' +
                            escape(str(account.membership.league_id), quote=True) +
                            '" data-roster-id="' + str(account.membership.roster_id) +
                            '" data-csrf-token="' + escape(account.csrf_token, quote=True) + '"', 1)
        response = page('My DTOS', body)
        for key, value in _HEADERS.items():
            response.headers[key] = value
        return response

    @router.get('/api/my-dtos')
    async def state(request: Request):
        from services.personal_rankings import _publication_token, view_state
        account = account_context(request)
        try:
            data, reader = require_data(), market_model()
            token = _publication_token(data, reader)
            result = await run_manager_read(lambda: view_state(service.store, data, reader, account))
            account_context(request)
            source_check(data, reader, token)
            return JSONResponse(enrich(result, account), headers=_HEADERS)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(exc)

    @router.post('/api/my-dtos')
    async def command(request: Request):
        from services.personal_rankings import _publication_token, apply_command
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
            token = _publication_token(data, reader)
            result = await run_manager_read(lambda: apply_command(service.store, data, reader, account, payload,
                verify_source=lambda: source_check(data, reader, token)))
            account_context(request)
            source_check(data, reader, token)
            return JSONResponse(enrich(result, account), headers=_HEADERS)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(exc)

    return router
