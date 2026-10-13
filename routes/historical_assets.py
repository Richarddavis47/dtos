"""Connected Historical Asset Graph APIs and dossier routes."""
from __future__ import annotations

from html import escape
from typing import Any, Callable
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse

from services.history import history_progress_contracts
from src.core.historical_memory.read_model import historical_graph
from src.core.history_context import canonical_history_store
from src.core.historical_memory.models import HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION
from services.fois import fois_service
from src.core.fois.models import FOIS_MODEL_VERSION
from src.ui.intelligence_presentation import event_label, human_status, technical_details
from services.asset_intelligence import contextual_player_url, validated_trade_origin


RequireData = Callable[[], dict[str, Any]]
historical_store = canonical_history_store
PageRenderer = Callable[[str, str], HTMLResponse]


def create_historical_assets_router(
    *, league_id: str, require_data: RequireData, page: PageRenderer,
    league_resolver: Callable[[], str] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["historical-assets"])

    def graph():
        return historical_graph(historical_store, selected_league(), require_data())

    def selected_league() -> str:
        return league_resolver() if league_resolver else league_id

    @router.get("/api/history/assets")
    async def asset_directory(
        asset_type: str | None = None, limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> JSONResponse:
        model = graph()
        count, assets = model.asset_directory_page(
            asset_type=asset_type, limit=limit, offset=offset,
        )
        return _response(
            "asset_directory", count, assets, limit=limit, offset=offset,
            read_model=model.query_metrics(),
        )

    @router.get("/api/history/assets/{asset_id}")
    async def asset_identity(asset_id: str) -> JSONResponse:
        model = graph()
        if asset_id.startswith("PICK-"):
            payload = model.pick_dossier(asset_id)
        else:
            payload = model.player_identity(asset_id)
        if payload is None:
            raise HTTPException(404, "Historical asset not found")
        return JSONResponse(jsonable_encoder(payload))

    @router.get("/api/history/assets/{asset_id}/events")
    async def asset_events(
        asset_id: str, season: int | None = None, event_type: str | None = None,
        status: str | None = None, franchise: str | None = None,
    ) -> JSONResponse:
        rows = graph().events(asset_id=asset_id)
        rows = [
            row for row in rows
            if (season is None or row["season"] == season)
            and (not event_type or row["event_type"] == event_type)
            and (not status or row["event_status"] == status)
            and (
                not franchise
                or franchise in {row.get("from_franchise_id"), row.get("to_franchise_id")}
            )
        ]
        return _response("asset_events", len(rows), rows)

    @router.get("/api/history/assets/{asset_id}/ownership")
    async def ownership_intervals(asset_id: str) -> JSONResponse:
        rows = graph().ownership_intervals(asset_id)
        return _response("ownership_intervals", len(rows), rows)

    @router.get("/api/history/players/{player_id}")
    async def player_history(player_id: str) -> JSONResponse:
        return JSONResponse(jsonable_encoder(graph().player_dossier(player_id)))

    @router.get("/api/history/players/{player_id}/seasons")
    async def player_seasons(player_id: str) -> JSONResponse:
        rows = graph().player_season_summaries(player_id)
        return _response("player_season_summaries", len(rows), rows)

    @router.get("/api/history/players/{player_id}/transactions")
    async def player_transactions(player_id: str) -> JSONResponse:
        canonical = f"DTOS-P-{player_id.removeprefix('DTOS-P-')}"
        rows = graph().events(asset_id=canonical)
        return _response("player_transactions", len(rows), rows)

    @router.get("/api/history/players/{player_id}/trades")
    async def player_trades(player_id: str) -> JSONResponse:
        rows = graph().player_trades(player_id)
        return _response("player_trades", len(rows), rows)

    @router.get("/api/picks/{pick_id}")
    async def pick_api(pick_id: str) -> JSONResponse:
        dossier = graph().pick_dossier(pick_id)
        if dossier is None:
            raise HTTPException(404, "Pick not found")
        return JSONResponse(jsonable_encoder(dossier))

    @router.get("/api/picks/{pick_id}/history")
    async def pick_history_api(pick_id: str) -> JSONResponse:
        dossier = graph().pick_dossier(pick_id)
        if dossier is None:
            raise HTTPException(404, "Pick not found")
        return _response("pick_lineage", len(dossier["events"]), dossier["events"], pick=dossier)

    @router.get("/picks/{pick_id}", response_class=HTMLResponse)
    async def pick_page(pick_id: str, front_office: int | None = None,
                        from_team: int | None = Query(default=None, ge=1),
                        from_trade: str | None = Query(default=None, max_length=100)) -> HTMLResponse:
        dossier = graph().pick_dossier(pick_id)
        if dossier is None:
            raise HTTPException(404, "Pick not found")
        origin = validated_trade_origin(graph(), from_trade)
        def event_link(item):
            parent = item.get('parent_id')
            event = validated_trade_origin(graph(), parent) if parent and parent.startswith('TRADE-') else None
            label = escape(event_label(item['event_type']))
            if event:
                suffix = '?from_trade=' + quote(origin['transaction_id'], safe='') if origin else ''
                return f'<a class="ds-action" href="/trades/history/{quote(event["transaction_id"], safe="")}{suffix}">{label}</a>'
            return label
        rows = "".join(
            f'<tr><td>{escape(str(item["season"]))}<p>{escape(str(item.get("occurred_at") or "Date unavailable"))}</p></td><td>{event_link(item)}</td><td>{escape(str(item.get("from_franchise_name") or "Original owner unavailable"))}</td><td>{escape(str(item.get("to_franchise_name") or "Holder unavailable"))}</td><td>{escape(human_status(item["event_status"]))}</td></tr>'
            for item in dossier["events"]
        ) or '<tr><td colspan="5">No verified ownership events are available.</td></tr>'
        selected_url = contextual_player_url(dossier['selected_player_id'].removeprefix('DTOS-P-'), from_trade=origin['transaction_id'] if origin else None) if dossier.get('selected_player_id') else None
        selected = (
            f'<a class="ds-action" href="{escape(selected_url)}">{escape(dossier["selected_player_name"])}</a>'
            if dossier.get("selected_player_url") else "Draft conversion not confirmed from available evidence"
        )
        pick_title = f'{dossier.get("season", "Future")} Round {dossier.get("round", "?")} Pick'
        from services.asset_explanations import pick_history_explanation
        from src.ui.explanations import explanation_panel
        history_explanation = explanation_panel(pick_history_explanation(dossier, league_id=selected_league()))
        facts = require_data()
        team_return = (f'<a class="back" href="/teams/{from_team}#draft-capital">← Back to My Team draft capital</a>'
                       if from_team is not None and any(t.get('roster_id') == from_team for t in facts.get('teams') or []) else '')
        # Resolve only identities belonging to this league. Keep the canonical
        # historical owner intact rather than replacing it with a guessed team.
        franchise_names = {}
        for team in facts.get('teams') or ():
            roster_id = str(team.get('roster_id') or '')
            name = str(team.get('team_name') or team.get('owner') or '')
            if roster_id and name:
                franchise_names[roster_id] = name
                franchise_names[f'{selected_league()}:franchise:{roster_id}'] = name
        raw_owner = str(dossier.get('current_owner') or '')
        owner_name = ('Consumed by verified draft conversion' if dossier.get('exercised')
                      else franchise_names.get(raw_owner, 'Current ownership unavailable'))
        original_identity = str(dossier.get('original_franchise_id') or '')
        original_name = franchise_names.get(original_identity, 'Original franchise name unavailable')
        active_id = int(front_office or 0)
        original_id = original_identity.removeprefix(f'{selected_league()}:franchise:')
        current_pick = next(
            (
                row for row in facts.get("pick_ledger") or ()
                if int(row.get("season") or 0) == int(dossier.get("season") or 0)
                and int(row.get("round") or 0) == int(dossier.get("round") or 0)
                and str(row.get("original_roster_id") or "") == original_id
            ),
            None,
        )
        trade_action = ""
        if current_pick and dossier.get('current_owner') and not dossier.get('exercised'):
            owner_id = int(current_pick.get("current_owner_id") or 0)
            trade_asset_id = f'{int(current_pick["season"])}-R{int(current_pick["round"])}-{current_pick["original_roster_id"]}'
            if active_id:
                trade_flow = "shop" if owner_id == active_id else "trade-for"
                trade_label = "Shop Asset" if owner_id == active_id else "Trade For"
                trade_action = (
                    f'<a class="button" href="/trades/{trade_flow}?front_office={active_id}'
                    f'&asset_id={quote(trade_asset_id, safe="")}&owner_roster_id={owner_id}">{trade_label}</a>'
                )
            else:
                trade_action = '<a class="button" href="/trades">Choose a franchise to trade this pick</a>'
        details = technical_details((("Canonical pick identity", pick_id), ("Current owner identity", raw_owner or 'Unavailable'), ("Original franchise identity", dossier.get('original_franchise_id')), ("Slot status", dossier.get("slot_status"))))
        holding = dossier.get('current_owner_observation') or {}
        observation_note = '<p>Current source observation as of ' + escape(str(holding.get('as_of') or 'date unavailable')) + '. An observation date is not an acquisition date.</p>' if raw_owner else ''
        transition_note = '<p role="status">The current source owner differs from the last historical holder; the intervening transition is unresolved. No intermediate trade is inferred.</p>' if dossier.get('current_owner_transition_unresolved') else ''
        last_note = '<p>Last historical holder: ' + escape(dossier.get('last_observed_holder_name') or 'Unavailable') + ' · ' + escape(str(dossier.get('reconciliation_status')).replace('_', ' ')) + '</p>'
        endpoint = dossier.get('selected_player_observation') or {}
        endpoint_note = ('<p>Drafted player current observed owner: ' + escape(endpoint.get('current_observed_owner_name') or 'Unavailable')
                         + ' · as of ' + escape(str(endpoint.get('as_of') or 'date unavailable')) + '. This does not establish uninterrupted ownership.</p>') if dossier.get('selected_player_id') else ''
        body = f'''<section class="pick-dossier"><a class="back" href="/picks">← Back to Draft Capital</a><h2>{escape(pick_title)}</h2>{history_explanation}
<div class="summary-grid"><article class="metric"><b>{escape(str(dossier.get("season")))}</b><span>Draft Year</span></article><article class="metric"><b>{escape(str(dossier.get("round")))}</b><span>Round</span></article><article class="metric"><b>{escape(owner_name)}</b><span>Current Owner</span></article><article class="metric"><b>{escape(str(dossier["slot_status"]))}</b><span>Slot Status</span></article><article class="metric"><b>{escape(original_name)}</b><span>Original franchise</span></article></div>
{observation_note}{transition_note}{last_note}<div class="card"><h3>Pick Conversion</h3><p>{selected}</p>{endpoint_note}<p>{trade_action}</p><p class="muted">Future slots remain unknown until determined by verified draft results.</p></div>
<div class="card"><h3>Ownership Chain</h3><div class="ds-table-wrap" tabindex="0" role="region" aria-label="Pick ownership history"><table class="pick-history-table"><caption>Verified ownership events for this exact pick</caption><thead><tr><th>Season</th><th>Event</th><th>From</th><th>To</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></div>{details}</section>'''
        trade_return = f'<a class="back" href="/trades/history/{quote(origin["transaction_id"], safe="")}">← Back to original trade timeline</a>' if origin else ''
        return page(f"{pick_title} — Pick Dossier", trade_return + team_return + body)

    @router.get("/api/trades/history/{transaction_id}")
    async def historical_trade_api(transaction_id: str) -> JSONResponse:
        dossier = graph().trade_dossier(transaction_id)
        if dossier is None:
            raise HTTPException(404, "Historical trade not found")
        dossier['timeline'] = graph().trade_timeline(transaction_id)
        return JSONResponse(jsonable_encoder(dossier))

    @router.get("/api/history/trades/coverage")
    async def historical_trade_coverage() -> JSONResponse:
        return JSONResponse(jsonable_encoder(graph().trade_time_coverage()))

    @router.get("/trades/history/{transaction_id}", response_class=HTMLResponse)
    async def historical_trade_page(transaction_id: str, from_trade: str | None = Query(default=None, max_length=100)) -> HTMLResponse:
        dossier = graph().trade_dossier(transaction_id)
        if dossier is None:
            raise HTTPException(404, "Historical trade not found")
        from src.ui.trade_timeline import render_timeline
        model = graph().trade_timeline(transaction_id)
        if model is None:
            raise HTTPException(404, 'Completed trade evidence unavailable')
        origin = validated_trade_origin(graph(), from_trade)
        return_url = f"/trades/history/{origin['transaction_id']}" if origin and origin['transaction_id'] != dossier['transaction_id'] else '/transactions'
        return page('Historical Trade Timeline', render_timeline(model, dossier, return_url=return_url, origin_id=origin['transaction_id'] if origin else None))

    @router.get('/trades/history/{transaction_id}/production', response_class=HTMLResponse)
    async def historical_trade_production(transaction_id: str, generation: str | None = Query(default=None, max_length=128)):
        import asyncio
        model = graph()
        current_generation = historical_store.dataset_version(selected_league())
        if generation and generation != current_generation:
            return HTMLResponse('<p role="status">Source evidence changed. Reload the trade before reviewing production.</p>', status_code=409)
        timeline = model.trade_timeline(transaction_id)
        if timeline is None:
            raise HTTPException(404, 'Completed trade evidence unavailable')
        def prepare():
            rows = []
            seen = set()
            for branch in timeline['branches']:
                player = (branch.get('converted_asset') or {}).get('player_id') or branch['asset_id']
                if not player.startswith('DTOS-P-') or len(branch['received_by']) != 1:
                    continue
                recipient = branch['received_by'][0]
                if (player, recipient['id']) in seen:
                    continue
                seen.add((player, recipient['id']))
                rows.append({'name': model.player_identity(player)['display_label'], 'recipient': recipient['name'],
                             **model.recipient_production(player, recipient['id'], minimum_season=timeline['season'])})
            return rows
        rows = await asyncio.to_thread(prepare)
        if historical_store.dataset_version(selected_league()) != current_generation:
            return HTMLResponse('<p role="status">Source evidence changed. Reload the trade before reviewing production.</p>', status_code=409)
        from src.ui.trade_timeline import render_production
        return HTMLResponse(render_production(rows, selected_league(), current_generation))

    @router.get("/api/history/transactions")
    async def historical_transactions(
        season: int | None = None, week: int | None = None,
        transaction_type: str | None = Query(None, alias="type"),
        status: str | None = None, franchise: str | None = None,
        player: str | None = None, pick: str | None = None,
        search: str | None = Query(None, alias="q"),
        limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    ) -> JSONResponse:
        rows = graph().transaction_archive()
        rows = [row for row in rows if (
            (season is None or row["season"] == season)
            and (week is None or row["week"] == week)
            and (not transaction_type or row["type"] == transaction_type)
            and (not status or row["status"] == status)
            and (not franchise or franchise in {str(value) for value in row["roster_ids"]})
            and (not player or player in row["adds"] or player in row["drops"])
            and (not pick or pick.casefold() in str(row["draft_picks"]).casefold())
            and (not search or search.casefold() in str(row).casefold())
        )]
        return _response("historical_transactions", len(rows), rows[offset:offset + limit], limit=limit, offset=offset)

    @router.get("/api/history/franchises/{roster_id}")
    async def franchise_history(roster_id: str) -> JSONResponse:
        return JSONResponse(jsonable_encoder(graph().franchise_history(roster_id)))

    @router.get("/api/history/coverage")
    async def historical_coverage() -> JSONResponse:
        selected = selected_league()
        progress = history_progress_contracts(selected)
        return JSONResponse(jsonable_encoder({
            **graph().coverage(),
            "canonical_progress": progress["canonical_history_progress"],
            "provider_memory_contract": {
                "source_of_truth": "sleeper",
                "completed_season_cache": "disposable",
                "historical_memory_fallback": False,
                "fixed_start_year": None,
                "missing_evidence_behavior": "unavailable_or_partial",
            },
            **progress,
        }))

    @router.get("/api/search")
    async def unified_search(q: str = "", limit: int = Query(50, ge=1, le=100)) -> JSONResponse:
        rows = graph().search(q, limit)
        selected = selected_league()
        needle = q.casefold().strip()
        if needle:
            for score in fois_service.repository.league(selected, FOIS_MODEL_VERSION):
                if needle in (score.gm_name or "").casefold():
                    rows.append({
                        "canonical_id": score.gm_id,
                        "result_type": "general_manager",
                        "display_label": score.gm_name,
                        "resolution_status": "resolved",
                        "canonical_url": f"/fois?league_id={selected}",
                        "historical_availability": score.evidence_state,
                        "match_reason": "canonical GM name",
                        "executive_score": score.overall_score,
                        "franchise_id": score.franchise_id,
                    })
                    if len(rows) >= limit:
                        break
        return _response("unified_search", len(rows), rows, query=q)

    @router.get("/search", response_class=HTMLResponse)
    async def search_page(q: str = "") -> HTMLResponse:
        rows = graph().search(q)
        selected = selected_league()
        needle = q.casefold().strip()
        if needle:
            rows.extend({
                "canonical_url": f"/fois?league_id={selected}",
                "display_label": score.gm_name,
                "result_type": "general_manager",
                "resolution_status": score.evidence_state,
                "match_reason": "canonical GM name",
            } for score in fois_service.repository.league(selected, FOIS_MODEL_VERSION)
              if needle in (score.gm_name or "").casefold())
        results = "".join(
            f'<li><a href="{escape(str(row["canonical_url"]))}">{escape(str(row["display_label"]))}</a> <span class="pill">{escape(str(row["result_type"]).replace("_", " ").title())}</span><br><small>{escape(human_status(row.get("historical_availability") or row.get("resolution_status")))}</small></li>'
            for row in rows
        ) or "<li>No matching current or historical assets were found.</li>"
        body = f'''<h2>DTOS Search</h2><form method="get"><label for="q">Players, picks, franchises, trades, or transaction IDs</label><input id="q" name="q" value="{escape(q)}"><button class="btn" type="submit">Search</button></form><div class="card"><ul>{results}</ul></div>'''
        return page("Search", body)

    return router


def _response(contract: str, count: int, records: list[Any], **metadata: Any) -> JSONResponse:
    return JSONResponse(jsonable_encoder({
        "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
        "contract": contract, "count": count, "records": records, **metadata,
    }))


def _asset_url(event: dict[str, Any]) -> str:
    if event["asset_type"] == "pick":
        return f'/picks/{event["asset_id"]}'
    return f'/players/{event["asset_id"].removeprefix("DTOS-P-")}'
