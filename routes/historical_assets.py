"""Connected Historical Asset Graph APIs and dossier routes."""
from __future__ import annotations

from html import escape
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse

from services.history import history_progress_contracts
from src.core.historical_memory import historical_graph, historical_store
from src.core.historical_memory.models import HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION


RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_historical_assets_router(
    *, league_id: str, require_data: RequireData, page: PageRenderer,
) -> APIRouter:
    router = APIRouter(tags=["historical-assets"])

    def graph():
        return historical_graph(historical_store, league_id, require_data())

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
    async def pick_page(pick_id: str) -> HTMLResponse:
        dossier = graph().pick_dossier(pick_id)
        if dossier is None:
            raise HTTPException(404, "Pick not found")
        rows = "".join(
            f'<tr><td>{escape(str(item["season"]))}</td><td>{escape(str(item["event_type"]))}</td><td>{escape(str(item.get("from_franchise_id") or "Unavailable"))}</td><td>{escape(str(item.get("to_franchise_id") or "Unavailable"))}</td><td>{escape(str(item["event_status"]))}</td></tr>'
            for item in dossier["events"]
        ) or '<tr><td colspan="5">No verified ownership events are available.</td></tr>'
        selected = (
            f'<a href="{escape(dossier["selected_player_url"])}">{escape(dossier["selected_player_id"])}</a>'
            if dossier.get("selected_player_url") else "Not exercised"
        )
        body = f'''<a class="back" href="/picks">← Back to Draft Capital</a><h2>{escape(pick_id)}</h2>
<div class="summary-grid"><article class="metric"><b>{escape(str(dossier.get("season")))}</b><span>Draft Year</span></article><article class="metric"><b>{escape(str(dossier.get("round")))}</b><span>Round</span></article><article class="metric"><b>{escape(str(dossier.get("current_owner") or "Unknown"))}</b><span>Current Owner</span></article><article class="metric"><b>{escape(str(dossier["slot_status"]))}</b><span>Slot Status</span></article></div>
<div class="card"><h3>Pick Conversion</h3><p>{selected}</p><p class="muted">Future slots remain unknown until determined by verified draft results.</p></div>
<div class="card"><h3>Ownership Chain</h3><table><thead><tr><th>Season</th><th>Event</th><th>From</th><th>To</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>'''
        return page(f"{pick_id} — Pick Dossier", body)

    @router.get("/api/trades/history/{transaction_id}")
    async def historical_trade_api(transaction_id: str) -> JSONResponse:
        dossier = graph().trade_dossier(transaction_id)
        if dossier is None:
            raise HTTPException(404, "Historical trade not found")
        return JSONResponse(jsonable_encoder(dossier))

    @router.get("/trades/history/{transaction_id}", response_class=HTMLResponse)
    async def historical_trade_page(transaction_id: str) -> HTMLResponse:
        dossier = graph().trade_dossier(transaction_id)
        if dossier is None:
            raise HTTPException(404, "Historical trade not found")
        assets = "".join(
            f'<li><a href="{_asset_url(item)}">{escape(item["asset_id"])}</a> — {escape(item["event_type"])} — {escape(item["event_status"])}</li>'
            for item in dossier["asset_events"]
        ) or "<li>No normalized asset legs were available.</li>"
        body = f'''<a class="back" href="/trades">← Back to Trade Center</a><h2>Historical Trade</h2>
<div class="summary-grid"><article class="metric"><b>{escape(str(dossier["season"]))}</b><span>Season</span></article><article class="metric"><b>{escape(str(dossier["week"]))}</b><span>Week</span></article><article class="metric"><b>{escape(dossier["status"])}</b><span>Status</span></article><article class="metric"><b>{len(dossier["asset_events"])}</b><span>Asset Legs</span></article></div>
<div class="card"><h3>Assets Exchanged</h3><ul>{assets}</ul></div><div class="card"><h3>Valuation Disclosure</h3><p>Value at trade: Unavailable unless a timestamped valuation exists.</p><p class="muted">Current values are never represented as historical values.</p></div>'''
        return page(f"Trade {transaction_id} — Historical Dossier", body)

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
        progress = history_progress_contracts(league_id)
        return JSONResponse(jsonable_encoder({
            **graph().coverage(),
            "canonical_progress": progress["canonical_history_progress"],
            **progress,
        }))

    @router.get("/api/search")
    async def unified_search(q: str = "", limit: int = Query(50, ge=1, le=100)) -> JSONResponse:
        rows = graph().search(q, limit)
        return _response("unified_search", len(rows), rows, query=q)

    @router.get("/search", response_class=HTMLResponse)
    async def search_page(q: str = "") -> HTMLResponse:
        rows = graph().search(q)
        results = "".join(
            f'<li><a href="{escape(str(row["canonical_url"]))}">{escape(str(row["display_label"]))}</a> <span class="pill">{escape(str(row["result_type"]))}</span><br><small>{escape(str(row["resolution_status"]))} · {escape(str(row["match_reason"]))}</small></li>'
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
