"""Trade Intelligence routes."""
from __future__ import annotations

from dataclasses import asdict
from html import escape
from services.trade_intelligence import validate_targeted_player_action
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response

from components.trade_intelligence import manager_context_selection, trade_center, trade_workflow
from services.trade_intelligence import assist_trade_request, autocomplete_trade_assets, build_trade_center, build_trade_workflow_context, build_trade_workspace, compare_trade_requests, create_trade_alternatives, evaluate_trade_request, generate_trade_workflow
from src.core.intelligence.serialization import recommendation_contract
from src.core.request_execution import run_manager_read
from src.platform.account_context import current_account
from services.trade_workspace_context import workspace_context, authorize_workspace
from services.trade_intelligence import TradeInputError
from services import home_trade_opportunities as home_ideas
from services.strategy_session import selected_strategy, COOKIE
from src.ui.home_trade_opportunities import cards as opportunity_cards
from services.trade_calculator import calculate_trade_market, balance_trade_market, market_generation

_STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
_WORKSPACE_JS = (_STATIC_ROOT / "js" / "trade_workspace.js").read_text(encoding="utf-8")
_WORKSPACE_CSS = (_STATIC_ROOT / "css" / "trade_workspace.css").read_text(encoding="utf-8")
_OPPORTUNITIES_JS = (_STATIC_ROOT / "js" / "home-opportunities.js").read_text(encoding="utf-8")
_STRATEGY_JS = (_STATIC_ROOT / "js" / "strategy_session.js").read_text(encoding="utf-8")


def _trade_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, TradeInputError):
        return HTTPException(422, {"code": exc.code, "message": str(exc), "assets": exc.assets})
    if isinstance(exc, ValueError):
        return HTTPException(422, {"code": str(exc) if str(exc).startswith(("unauthorized_", "workspace_")) else "invalid_proposal", "message": str(exc)})
    # Bounded type/location only: never log submitted proposals or credentials.
    import traceback
    frames = traceback.extract_tb(exc.__traceback__)
    location = frames[-1] if frames else None
    logging.getLogger(__name__).error("trade_engine_failure type=%s function=%s line=%s", type(exc).__name__, location.name if location else "unknown", location.lineno if location else 0)
    return HTTPException(503, {"code": "evaluation_unavailable", "message": "DTOS couldn't complete this evaluation. Your proposal is still intact."})

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_trades_router(*, ensure_fresh: EnsureFresh, require_data: RequireData, page: PageRenderer) -> APIRouter:
    router = APIRouter()

    @router.get("/static/js/strategy_session.js", include_in_schema=False)
    async def strategy_script() -> Response:
        return Response(_STRATEGY_JS, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @router.get("/static/js/trade_workspace.js", include_in_schema=False)
    async def workspace_script() -> Response:
        return Response(_WORKSPACE_JS, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @router.get("/static/css/trade_workspace.css", include_in_schema=False)
    async def workspace_styles() -> Response:
        return Response(_WORKSPACE_CSS, media_type="text/css", headers={"Cache-Control": "no-cache"})

    @router.get("/static/js/home-opportunities.js", include_in_schema=False)
    async def opportunity_script() -> Response:
        return Response(_OPPORTUNITIES_JS, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @router.get("/api/trades/home-opportunities", response_class=JSONResponse)
    async def home_opportunities(request: Request, front_office: int | None = None,
                                 protected: str = "[]", excluded: str = "[]", offer: str = "") -> JSONResponse:
        import json
        await ensure_fresh()
        data = require_data()
        account = current_account()
        rid = account.membership.roster_id if account and account.membership else front_office
        if not rid or (front_office is not None and front_office != rid):
            raise HTTPException(422, "unauthorized_franchise")
        context = workspace_context(data, rid)
        try:
            authorize_workspace(data, {'active_roster_id': rid, 'workspace_context': context})
        except ValueError as exc:
            raise _trade_failure(exc) from exc
        try:
            if len(protected) + len(excluded) > 8192:
                raise ValueError('invalid_exact_protections')
            locks, omissions = home_ideas.constraints(json.loads(protected), json.loads(excluded))
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, "invalid_exact_protections") from exc
        strategy = selected_strategy(request.cookies.get(COOKIE), context['league_id'], rid)
        try:
            key = await run_manager_read(lambda: home_ideas.cache_key(data, rid, strategy, locks, omissions))
        except Exception as exc:
            raise _trade_failure(exc) from exc
        result = home_ideas.read(key)
        if offer:
            row = next((r for r in result['rows'] if r['home_offer'] == offer), None)
            if row is None:
                raise HTTPException(410, "This idea expired or its source, strategy or protections changed. Your draft is unchanged. Find current ideas again.")
            return JSONResponse(row, headers={"Cache-Control": "no-store"})
        from services.front_office_brief import prepared_evidence, select_insights
        from services.home_attention import attention_state
        from services.attention_changes import pick_changes
        from src.ui.front_office_brief import cards as brief_cards
        from config import METADATA_DATABASE_FILE

        def prepared_brief():
            facts = prepared_evidence(data, rid, strategy)
            changes, coverage = pick_changes(data, rid, METADATA_DATABASE_FILE)
            from src.core.projection_intelligence import projection_service
            from src.platform.league_context import current_league_context
            active = current_league_context()
            reader = active.projection if active and active.league_id == context['league_id'] else projection_service
            attention = attention_state(data, rid, reader.snapshot(), change_rows=changes, change_coverage=coverage)
            items = select_insights(facts, attention['items'], result['rows'])
            rendered = brief_cards(items)
            current = require_data()
            from services.front_office_brief import intelligence_orchestrator
            same_generation = intelligence_orchestrator.context(current, rid, {'strategy': strategy}).evidence_generation == facts['generation']
            if not same_generation or home_ideas.cache_key(current, rid, strategy, locks, omissions) != key:
                raise HTTPException(409, 'Prepared evidence changed. Reload Home to review current facts; your draft is unchanged.')
            # Keep fingerprints and cache reads off-loop. These immutable
            # publication references fence the thread-to-response handoff.
            publication = (active.runtime.fois_publication_revision if active else None,
                           tuple(sorted(active.runtime.source_generations.items())) if active else (),
                           id((current.get('market_data') or {}).get('providers')),
                           id((current.get('market_data') or {}).get('pick_quotes')),
                           current.get('week'))
            return facts, items, rendered, current, reader, reader.snapshot(), active, publication

        facts, items, brief_html, pinned_data, reader, pinned_projection, active, publication = await run_manager_read(prepared_brief)
        # Publication may change while the off-loop prepared read is pending.
        # Do not let an obsolete response reintroduce an offer or roster claim.
        current = require_data()
        now = (active.runtime.fois_publication_revision if active else None,
               tuple(sorted(active.runtime.source_generations.items())) if active else (),
               id((current.get('market_data') or {}).get('providers')),
               id((current.get('market_data') or {}).get('pick_quotes')), current.get('week'))
        if current is not pinned_data or reader.snapshot() is not pinned_projection or now != publication:
            raise HTTPException(409, 'Prepared evidence changed. Reload Home to review current facts; your draft is unchanged.')
        return JSONResponse({'workspace_context': context, 'csrf_token': account.csrf_token if account else '',
            'strategy': strategy, 'source_identity': key[1] if key else None, 'count': len(result['rows']),
            'brief_html': brief_html, 'brief_count': len(items), 'brief_generation': facts['generation'],
            'state': result['state'], 'reason': result.get('reason'), 'html': opportunity_cards(result['rows'], rid),
            'retained': bool(result.get('source_identity'))}, headers={"Cache-Control": "no-store"})

    async def view(front_office: int | None) -> dict[str, Any]:
        try:
            return await run_manager_read(
                lambda: build_trade_center(require_data(), front_office),
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    def workflow_view(front_office: int | None) -> dict[str, Any]:
        try:
            return build_trade_workflow_context(require_data(), front_office)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/trades", response_class=HTMLResponse)
    async def trades_page(front_office: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        if front_office is None:
            return page("Trade Intelligence", manager_context_selection(list(require_data().get("teams") or [])))
        return page("Trade Intelligence", trade_center(await view(front_office)))

    async def workflow_page(workflow: str, front_office: int | None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        await ensure_fresh()
        if front_office is None:
            return page("Trade Center", manager_context_selection(list(require_data().get("teams") or []), workflow=workflow))
        try:
            context = workflow_view(front_office)
            if asset_id and workflow in {"shop", "trade-for"}:
                ownership = validate_targeted_player_action(require_data(), asset_id, int(context["active_team"]["roster_id"]), workflow)
                if ownership:
                    owner_roster_id = ownership["owner"]["roster_id"]
            body = trade_workflow(
                context, workflow, asset_id, owner_roster_id,
            )
        except TradeInputError as exc:
            response = page("Trade Center", f'<section class="card"><h2>Player action unavailable</h2><p>{escape(str(exc))}</p><a class="ds-action" href="/market">View Market</a></section>')
            response.status_code = 422
            return response
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return page("Trade Center", body)

    @router.get("/trades/create", response_class=HTMLResponse)
    async def create_trade_page(front_office: int | None = None) -> HTMLResponse:
        return await workflow_page("create", front_office)

    @router.get("/trades/calculator", response_class=HTMLResponse)
    async def calculator_page(front_office: int | None = None) -> HTMLResponse:
        return await workflow_page("calculator", front_office)

    @router.get("/trades/trade-for", response_class=HTMLResponse)
    async def trade_for_page(front_office: int | None = None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        return await workflow_page("trade-for", front_office, asset_id, owner_roster_id)

    @router.get("/trades/shop", response_class=HTMLResponse)
    async def shop_asset_page(front_office: int | None = None, asset_id: str | None = None, owner_roster_id: int | None = None) -> HTMLResponse:
        return await workflow_page("shop", front_office, asset_id, owner_roster_id)

    @router.get("/trades/recommended", response_class=HTMLResponse)
    async def recommended_trades_page(front_office: int | None = None) -> HTMLResponse:
        return await workflow_page("recommended", front_office)

    @router.get("/api/trades", response_class=JSONResponse)
    async def trades_api(front_office: int | None = None) -> JSONResponse:
        await ensure_fresh()
        if front_office is None:
            return JSONResponse({"status": "manager_context_required", "active_front_office": None, "count": 0, "opportunities": [], "reason": "Choose the franchise you control before using Trade Center."})
        result = await view(front_office)
        if result.get('search_state') == 'not_started':
            return JSONResponse({'active_front_office': int(result['active_team']['roster_id']),
                'count': 0, 'opportunities': [], 'canonical_bilateral_evaluations': [],
                'availability': 'not_started', 'decision_confidence': None,
                'reason': 'Run the authenticated Recommended Trades workflow to discover current opportunities.',
                'workflow_url': f'/trades/recommended?front_office={int(result["active_team"]["roster_id"])}'})
        payload = {
            "active_front_office": int(result["active_team"].get("roster_id") or 0),
            "count": len(result["dossiers"]),
            "opportunities": [asdict(item) for item in result["dossiers"]],
            "canonical_bilateral_evaluations": result["canonical_results"],
            **recommendation_contract(result["unified_recommendation"], result.get("brain_recommendation")),
        }
        return JSONResponse(jsonable_encoder(payload))

    @router.get("/api/trades/workspace", response_class=JSONResponse)
    async def trade_workspace(front_office: int | None = None, mode: str = "") -> JSONResponse:
        await ensure_fresh()
        try:
            workspace = await run_manager_read(
                lambda: build_trade_workspace(require_data(), front_office, market_only=True) if mode == 'calculator'
                else build_trade_workspace(require_data(), front_office),
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        payload = {
            "active_front_office": workspace["active_roster_id"],
            "workflows": workspace["workflows"],
            "teams": [
                {
                    "roster_id": int(team.get("roster_id") or 0),
                    "team_name": str(team.get("team_name") or team.get("owner") or "Unassigned Franchise"),
                    "assets": [
                        {
                            **asdict(asset),
                            "nfl_team": str((require_data().get("players") or {}).get(asset.asset_id, {}).get("team") or ""),
                            "headshot_url": (
                                f"https://sleepercdn.com/content/nfl/players/{asset.asset_id}.jpg"
                                if asset.kind == "player" else None
                            ),
                            "raw_label": asset.label,
                            "label": (
                                f"{asset.position} · {asset.label} · {asset.positional_rank} · {asset.trade_value}"
                                if asset.kind == "player"
                                else f"{asset.label} · {asset.projected_range or 'UNKNOWN'} · {asset.projected_range_confidence or 'LOW'} · {asset.trade_value}"
                            ),
                            "display_label": (
                                f"{asset.position} · {asset.label} · {asset.positional_rank} · {asset.trade_value}"
                                if asset.kind == "player"
                                else f"{asset.label} · {asset.projected_range or 'UNKNOWN'} · {asset.projected_range_confidence or 'LOW'} · {asset.trade_value}"
                            ),
                        }
                        for asset in workspace["pools"][int(team.get("roster_id") or 0)]
                    ],
                }
                for team in workspace["teams"]
            ],
            "session_persistence": "temporary",
            "calculator_generation": market_generation(workspace),
            "projection_evidence": workspace['projection_evidence'],
            "bilateral_only": True,
            "workspace_context": workspace_context(require_data(), workspace["active_roster_id"]),
            "csrf_token": current_account().csrf_token if current_account() else "",
            "manager_context": {
                "league_id": workspace["manager_context"].league_id,
                "roster_id": workspace["manager_context"].roster_id,
                "manager_id": workspace["manager_context"].manager_id,
                "source": workspace["manager_context"].source,
            },
        }
        return JSONResponse(jsonable_encoder(payload))

    @router.post("/api/trades/calculate", response_class=JSONResponse)
    async def calculate_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(lambda: calculate_trade_market(require_data(), payload))
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/balance", response_class=JSONResponse)
    async def balance_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(lambda: balance_trade_market(require_data(), payload))
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/evaluate", response_class=JSONResponse)
    async def evaluate_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            def assess():
                # A successful HTTP response alone does not establish assessment
                # freshness. Bind it to the same semantic canonical publication
                # contract used by generated offers, not an evaluation ID/clock.
                data = require_data()
                before = home_ideas.source_identity(data)
                if not before:
                    raise TradeInputError('canonical_evidence_changed', 'Canonical evidence is changing. Try again.')
                result = evaluate_trade_request(data, payload)
                if home_ideas.source_identity(require_data()) != before:
                    raise TradeInputError('canonical_evidence_changed', 'Canonical evidence changed during evaluation. Try again.')
                if isinstance(result.get('evaluation'), dict):
                    result['assessment_source_identity'] = before
                return result
            result = await run_manager_read(assess)
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/generate", response_class=JSONResponse)
    async def generate_trades(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            data = require_data()
            def discover():
                if str(payload.get('workflow') or 'recommended') != 'recommended':
                    return generate_trade_workflow(data, payload)
                from src.core.valuation.normalization import capture_market_publication
                market, coherent = capture_market_publication(data.get('market_data') or {})
                if not coherent:
                    raise TradeInputError('canonical_evidence_changed', 'Market publication changed. Try again.')
                prepared_data = {**data, 'market_data': market}
                key = home_ideas.cache_key(prepared_data, int(payload.get('active_roster_id') or 0), payload.get('strategy'),
                    payload.get('protected_assets') or [], payload.get('excluded_assets') or [])
                if payload.get('home_source_identity') and (key is None or payload['home_source_identity'] != key[1]):
                    raise TradeInputError('canonical_evidence_changed', 'Prepared evidence changed. Refresh Home and try again.')
                result = generate_trade_workflow(prepared_data, payload)
                if home_ideas.cache_key(data, int(payload.get('active_roster_id') or 0), payload.get('strategy'),
                    payload.get('protected_assets') or [], payload.get('excluded_assets') or []) != key:
                    raise TradeInputError('canonical_evidence_changed', 'Prepared evidence changed. Try the same search again.')
                home_ideas.publish(key, result, payload)
                return result
            def bounded_discover():
                if payload.get('home_source_identity'):
                    with home_ideas.search_slot(payload['workspace_context']['binding']):
                        return discover()
                return discover()
            result = await run_manager_read(bounded_discover)
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/assist", response_class=JSONResponse)
    async def assist_trade(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(
                lambda: assist_trade_request(require_data(), payload),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/alternatives", response_class=JSONResponse)
    async def trade_alternatives(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            authorize_workspace(require_data(), payload)
            result = await run_manager_read(
                lambda: create_trade_alternatives(require_data(), payload),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.get("/api/trades/assets", response_class=JSONResponse)
    async def trade_assets(q: str = "", front_office: int | None = None, limit: int = 20) -> JSONResponse:
        await ensure_fresh()
        try:
            result = await run_manager_read(
                lambda: autocomplete_trade_assets(
                    require_data(), q, front_office, max(1, min(limit, 50)),
                ),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(jsonable_encoder(result))

    @router.post("/api/trades/compare", response_class=JSONResponse)
    async def compare_trades(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        await ensure_fresh()
        try:
            for proposal in payload.get("proposals") or ():
                authorize_workspace(require_data(), {**proposal, "workspace_context": payload.get("workspace_context")})
            result = await run_manager_read(
                lambda: compare_trade_requests(
                    require_data(), list(payload.get("proposals") or ()),
                ),
            )
        except Exception as exc:
            raise _trade_failure(exc) from exc
        return JSONResponse(jsonable_encoder(result))

    return router
