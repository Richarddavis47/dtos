"""DTOS Transactions Center routes and presentation."""
from __future__ import annotations

import asyncio
from datetime import datetime
from html import escape
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, quote, urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from src.ui.intelligence_presentation import available, human_status, technical_details

from components.asset_intelligence import player_dossier
from src.core.player_ownership import PlayerOwnershipIndex
from config import LEAGUE_ID
from services.asset_intelligence import build_player_dossier, validated_trade_origin
from services.transactions import transaction_center
from services.historical_archive import archive_view
from src.core.data_platform import data_platform
from src.core.historical_memory.read_model import historical_graph
from src.core.history_context import canonical_history_store
from src.core.projection_intelligence import projection_service
from src.platform.league_context import current_league_context
from services.player_projection_view import player_projection_view
from src.ui.player_projections import player_projection_panel
from src.ui.market_facts import market_fact_html


EnsureFresh = Callable[[], Awaitable[None]]
RefreshTransactions = Callable[[], Awaitable[bool]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]

TRANSACTIONS_CSS = """
<style>
.tx-hero{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px;flex-wrap:wrap}
.tx-hero h2{margin:0 0 5px}.tx-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tx-actions form{margin:0}
.tx-refresh{border:0;border-radius:10px;padding:11px 15px;background:var(--accent);color:#062018;font-weight:850;cursor:pointer}
.tx-refresh-meta{font-size:11px;color:var(--muted);max-width:250px;text-align:right}.tx-alert{padding:11px 13px;border-radius:10px;margin:10px 0 14px;border:1px solid var(--line)}
.tx-alert.good{background:rgba(110,231,183,.08);border-color:rgba(110,231,183,.42)}.tx-alert.bad{background:rgba(248,113,113,.08);border-color:rgba(248,113,113,.42)}
.tx-stats{display:grid;grid-template-columns:repeat(6,minmax(130px,1fr));gap:10px;margin-bottom:14px}.tx-stat{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:13px;padding:13px}
.tx-stat b{display:block;font-size:23px;line-height:1.15}.tx-stat span{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}.tx-stat small{color:var(--muted)}
.tx-filters{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px}.tx-field label{display:block;color:var(--muted);font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.07em;margin:0 0 5px}
.tx-field input,.tx-field select{width:100%;border:1px solid var(--line);border-radius:9px;background:#0b1727;color:var(--text);padding:10px}.tx-filter-actions{display:flex;align-items:end;gap:8px}
.tx-filter-actions button,.tx-reset{display:inline-block;border:1px solid var(--line);border-radius:9px;padding:10px 13px;background:#182a40;color:var(--text);font-weight:800;cursor:pointer}.tx-reset{color:var(--muted)}
.tx-table-wrap{overflow-x:auto;margin-top:14px;border:1px solid var(--line);border-radius:14px;background:#101d2d}.tx-table{min-width:980px}.tx-table th{white-space:nowrap;background:#0b1727}.tx-table th a{color:var(--muted)}
.tx-table td{padding:13px 10px}.tx-time{white-space:nowrap}.tx-type{display:inline-block;padding:4px 8px;border-radius:999px;border:1px solid var(--line);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.06em}.tx-type.trade{color:var(--gold);border-color:rgba(245,196,81,.5)}.tx-type.waiver{color:#93c5fd;border-color:rgba(96,165,250,.5)}
.tx-teams,.tx-assets{display:grid;gap:6px}.tx-team{display:flex;gap:6px;align-items:baseline;flex-wrap:wrap}.tx-team a{color:var(--accent);font-weight:800}.tx-team small{color:var(--muted)}
.tx-asset{border-left:2px solid var(--line);padding-left:8px}.tx-asset-main{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.tx-asset a{font-weight:800}.tx-movement{font-size:10px;color:var(--muted)}
.position-badge{display:inline-block;min-width:34px;text-align:center;border:1px solid var(--line);border-radius:999px;padding:2px 5px;font-size:9px;color:var(--accent);font-weight:900}.tx-id{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10px;word-break:break-all;color:var(--muted)}
.tx-raw summary{cursor:pointer;color:var(--muted);font-size:10px;margin-top:7px}.tx-raw pre{max-width:440px;max-height:220px;overflow:auto;font-size:10px;background:#07111f;padding:8px;border-radius:8px}
.tx-empty{text-align:center;padding:34px;color:var(--muted)}.tx-pagination{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:12px;flex-wrap:wrap}.tx-pages{display:flex;gap:6px;flex-wrap:wrap}.tx-pages a,.tx-pages span{border:1px solid var(--line);border-radius:8px;padding:7px 10px}.tx-pages .current{background:var(--accent);color:#062018;font-weight:900}
.player-hero{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:center}.player-monogram{width:58px;height:58px;border-radius:16px;background:#182a40;border:1px solid var(--line);display:grid;place-items:center;font-size:20px;font-weight:950;color:var(--accent)}
@media(max-width:1000px){.tx-stats{grid-template-columns:repeat(3,1fr)}.tx-filters{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.tx-stats{grid-template-columns:repeat(2,1fr)}.tx-filters{grid-template-columns:1fr}.tx-refresh-meta{text-align:left}.tx-hero{display:block}.tx-actions{margin-top:10px}.tx-stat b{font-size:19px}
.tx-table{min-width:0;display:block}.tx-table thead{display:block}.tx-table thead tr{display:flex;flex-wrap:wrap}.tx-table thead th{border:0;padding:10px;font-size:12px}
.tx-table tbody{display:grid;gap:12px;padding:12px}.tx-table tbody tr{display:grid;grid-template-columns:minmax(0,1fr) auto;border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:12px}
.tx-table tbody td{display:block;border:0;padding:4px 0;min-width:0}.tx-table tbody td:nth-child(n+3){grid-column:1/-1;padding-top:12px}.tx-time{white-space:normal;font-size:12px}.tx-asset{padding:8px;border-left:2px solid var(--line);background:var(--surface-elevated);border-radius:6px}.tx-table-wrap{background:transparent;border:0}}
</style>
"""


def _filters(**values: Any) -> dict[str, Any]:
    return {
        "team": values["team"],
        "owner": values["owner"],
        "type": values["transaction_type"],
        "player": values["player"],
        "draft_pick": values["draft_pick"],
        "date_from": values["date_from"],
        "date_to": values["date_to"],
        "q": values["search"],
        "sort": values["sort"],
        "direction": values["direction"],
        "page": values["page_number"],
        "per_page": values["per_page"],
    }


def _query(filters: dict[str, Any], **changes: Any) -> str:
    values = {**filters, **changes}
    return urlencode(
        {key: value for key, value in values.items() if value not in (None, "")}
    )


def _option(value: str, label: str, selected: Any) -> str:
    marker = " selected" if str(selected) == value else ""
    return f'<option value="{escape(value)}"{marker}>{escape(label)}</option>'


def _team_link(roster_id: str | None, label: str | None) -> str:
    if not roster_id or not label:
        return "—"
    return f'<a href="/teams/{quote(str(roster_id))}">{escape(str(label))}</a>'


def _asset_html(asset: dict[str, Any]) -> str:
    if asset["kind"] == "player":
        label = (
            f'<a href="/players/{quote(str(asset["player_id"]))}">'
            f'{escape(str(asset["label"]))}</a>'
        )
    else:
        label = f'<a href="/picks/{quote(str(asset["canonical_pick_id"]))}">{escape(str(asset["label"]))}</a>' if asset.get('canonical_pick_id') else f'<b>{escape(str(asset["label"]))}</b>'
    movement_parts = []
    if asset.get("source_id"):
        movement_parts.append(
            "From " + _team_link(asset["source_id"], asset.get("source"))
        )
    if asset.get("destination_id"):
        movement_parts.append(
            "To " + _team_link(asset["destination_id"], asset.get("destination"))
        )
    if asset.get("original"):
        movement_parts.append(f'Originally {escape(str(asset["original"]))}')
    movement = " · ".join(movement_parts) or escape(str(asset["action"]))
    return (
        '<div class="tx-asset"><div class="tx-asset-main">'
        f'<span class="position-badge">{escape(str(asset["position"]))}</span>'
        f"{label}</div><div class=\"tx-movement\">{movement}</div></div>"
    )


def _sort_heading(
    label: str, field: str, filters: dict[str, Any], current_sort: str, direction: str
) -> str:
    next_direction = "asc" if field != current_sort or direction == "desc" else "desc"
    arrow = " ↓" if field == current_sort and direction == "desc" else " ↑" if field == current_sort else ""
    href = "/transactions?" + _query(
        filters, sort=field, direction=next_direction, page=1
    )
    return f'<a href="{escape(href)}">{escape(label + arrow)}</a>'


def _format_refresh_time(value: Any) -> str:
    if not value:
        return "Not yet refreshed"
    try:
        timestamp = datetime.fromisoformat(str(value))
        return timestamp.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return str(value)


def _historical_archive_row(row: dict[str, Any]) -> str:
    detail = (
        f'<a href="{escape(row["trade_dossier_url"])}">Trade Dossier</a>'
        if row["trade_dossier_url"]
        else '<details><summary>Source event</summary>' + escape(row["sleeper_transaction_id"]) + '</details>'
    )
    asset_count = len(set(row["adds"]) | set(row["drops"])) + len(row["draft_picks"])
    faab = f" · {len(row.get('waiver_budget') or [])} FAAB movement(s)" if row.get('waiver_budget') else ''
    return (
        f'<tr><td>{escape(str(row["season"]))} W{escape(str(row["week"] or "?"))}</td>'
        f'<td>{escape(str(row["occurred_at"] or "Date unavailable"))}</td>'
        f'<td>{escape(row["type"].replace("_", " ").title())}<p>{escape(row.get("franchise_summary") or "Franchise identities unavailable")}</p></td>'
        f'<td>{escape(str(row["status"]))}</td><td>{asset_count} assets{faab}</td><td>{detail}</td></tr>'
    )


def _transactions_table(view: dict[str, Any], filters: dict[str, Any]) -> str:
    rows = []
    for transaction in view["transactions"]:
        teams = "".join(
            '<div class="tx-team">'
            f'<a href="/teams/{quote(str(team["roster_id"]))}">{escape(team["team_name"])}</a>'
            f'<small>{escape(team["owner"])}</small></div>'
            for team in transaction["teams"]
        ) or "—"
        assets = "".join(_asset_html(asset) for asset in transaction["assets"]) or "—"
        trade_detail = (f'<br><a class="timeline-link" href="/trades/history/{quote(str(transaction["id"]), safe="")}">View completed trade trail</a>'
                        if transaction['type'] == 'trade' and transaction['status'] in {'complete', 'completed'} else '')
        rows.append(
            "<tr>"
            f'<td class="tx-time"><b>{escape(transaction["timestamp"])}</b></td>'
            f'<td><span class="tx-type {escape(transaction["type"])}">{escape(transaction["type_label"])}</span><br><small class="muted">{escape(transaction["status"])}</small>{trade_detail}</td>'
            f'<td><div class="tx-teams">{teams}</div></td>'
            f'<td><div class="tx-assets">{assets}</div></td>'
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="4" class="tx-empty"><b>No transactions match these filters.</b><br>Reset the filters or refresh transactions to check for new league activity.</td></tr>')

    sort = str(filters["sort"])
    direction = str(filters["direction"])
    headings = "".join(
        f"<th>{_sort_heading(label, field, filters, sort, direction)}</th>"
        for label, field in (
            ("Timestamp", "date"),
            ("Type", "type"),
            ("Teams involved", "teams"),
            ("Assets exchanged", "assets"),
        )
    )
    return f'<div class="tx-table-wrap"><table class="tx-table"><thead><tr>{headings}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _pagination(view: dict[str, Any], filters: dict[str, Any]) -> str:
    page = view["page"]
    page_count = view["page_count"]
    start = max(1, page - 2)
    end = min(page_count, page + 2)
    links = []
    if page > 1:
        links.append(f'<a href="/transactions?{escape(_query(filters, page=page - 1))}">Previous</a>')
    for number in range(start, end + 1):
        if number == page:
            links.append(f'<span class="current">{number}</span>')
        else:
            links.append(f'<a href="/transactions?{escape(_query(filters, page=number))}">{number}</a>')
    if page < page_count:
        links.append(f'<a href="/transactions?{escape(_query(filters, page=page + 1))}">Next</a>')
    return (
        '<div class="tx-pagination">'
        f'<span class="muted">Showing {len(view["transactions"])} of {view["total_filtered"]} filtered transactions</span>'
        f'<div class="tx-pages">{"".join(links)}</div></div>'
    )


def create_transactions_router(
    *,
    ensure_fresh: EnsureFresh,
    refresh_transactions: RefreshTransactions,
    require_data: RequireData,
    state: dict[str, Any],
    page: PageRenderer,
) -> APIRouter:
    """Create the Transactions Center router using shared app dependencies."""
    router = APIRouter()

    @router.get("/transactions", response_class=HTMLResponse)
    async def transactions_page(
        team: str = "",
        owner: str = "",
        transaction_type: str = Query("", alias="type"),
        player: str = "",
        draft_pick: str = "",
        date_from: str = "",
        date_to: str = "",
        search: str = Query("", alias="q"),
        scope: str = "current_activity",
        season: str | None = None,
        week: str | None = None,
        status: str = "",
        sort: str = "date",
        direction: str = "desc",
        page_number: int = Query(1, alias="page", ge=1),
        per_page: int = Query(25),
        refresh: str = "",
    ) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        def optional_number(value, field, minimum, maximum=None):
            if value is None or not value.strip():
                return None
            if not value.isdigit() or int(value) < minimum or (maximum is not None and int(value) > maximum):
                raise HTTPException(422, f'Invalid {field} filter')
            return int(value)
        season = optional_number(season, 'season', 1900)
        week = optional_number(week, 'week', 0, 18)
        filters = _filters(**locals())
        filters.update({"scope": scope, "season": season, "week": week, "status": status})
        view = transaction_center(data, filters)
        filters["page"] = view["page"] if scope == 'current_activity' else page_number
        filters["per_page"] = view["per_page"]
        summary = view["summary"]

        team_options = _option("", "All teams", team) + "".join(
            _option(str(item["roster_id"]), str(item["team_name"]), team)
            for item in view["teams"]
        )
        owner_options = _option("", "All owners", owner) + "".join(
            _option(value, value, owner) for value in view["owners"]
        )
        type_options = _option("", "All transaction types", transaction_type) + "".join(
            _option(value, value.replace("_", " ").title(), transaction_type)
            for value in sorted(set(view["transaction_types"]) | {'trade', 'waiver', 'free_agent', 'commissioner'})
        )
        pick_options = "".join(
            _option(value, label, draft_pick)
            for value, label in (("", "Any draft-pick state"), ("yes", "Includes a draft pick"), ("no", "No draft picks"))
        )
        page_options = "".join(
            _option(str(value), f"{value} per page", view["per_page"])
            for value in (10, 25, 50)
        )
        scope_options = "".join(
            _option(value, label, scope) for value, label in (
                ("current_activity", "Current activity"),
                ("current_season", "Current season"),
                ("all_history", "All league history"),
            )
        )
        refresh_query = _query(filters)
        refresh_alert = ""
        if refresh == "success":
            refresh_alert = '<div class="tx-alert good">Transactions refreshed successfully.</div>'
        elif refresh == "error":
            message = state.get("transactions_last_error") or "Transaction refresh failed. Cached data is still available."
            refresh_alert = f'<div class="tx-alert bad"><b>Refresh failed:</b> {escape(str(message))}</div>'

        stats = "".join(
            f'<div class="tx-stat"><span>{escape(label)}</span><b>{escape(str(value))}</b>{f"<small>{escape(note)}</small>" if note else ""}</div>'
            for label, value, note in (
                ("Total Trades", summary["trades"], ""),
                ("Total Waiver Claims", summary["waivers"], ""),
                ("Total Adds", summary["adds"], ""),
                ("Total Drops", summary["drops"], ""),
                ("Most Active Team", summary["most_active_team"], f'{summary["most_active_count"]} transactions'),
                ("Most Recent Transaction", summary["most_recent"], ""),
            )
        )
        selected_league = str((data.get("league") or {}).get("league_id") or LEAGUE_ID)
        model = historical_graph(canonical_history_store, selected_league, data)
        archive = archive_view(model, data, filters)
        if scope != 'current_activity':
            owner_options = _option('', 'All season-observed managers', owner) + ''.join(
                _option(value, value, owner) for value in archive['owners'])
        archive_rows = "".join(_historical_archive_row(row) for row in archive['rows'])
        archive_table_body = archive_rows or '<tr><td colspan="6">No archived transactions match these filters.</td></tr>'
        from src.ui.trade_timeline import render_source_coverage
        coverage = canonical_history_store.source_coverage(selected_league) if scope != 'current_activity' and hasattr(canonical_history_store, 'source_coverage') else {}
        archive_panel = (f'<section class="card"><h2>Historical Archive</h2><p>{archive["total_filtered"]} archived transactions match this scope. Source: retained Sleeper observations.</p><p>{escape(archive["qualification"])}</p><p>Archive page {archive["page"]} of {archive["page_count"]} · {len(archive["rows"])} shown · {archive["per_page"]} per page. Only acquired source periods are included.</p><div class="ds-table-wrap" tabindex="0" role="region" aria-label="Historical transactions"><table><thead><tr><th>Season</th><th>Timestamp</th><th>Type</th><th>Status</th><th>Consideration</th><th>Details</th></tr></thead><tbody>{archive_table_body}</tbody></table></div>{_pagination({**archive, "transactions": archive["rows"]}, filters)}{render_source_coverage(coverage)}</section>') if scope != 'current_activity' else ''
        activity = _transactions_table(view, filters) + _pagination(view, filters) if scope == 'current_activity' else ''
        body = f"""
{TRANSACTIONS_CSS}
<section class="tx-hero">
  <div><h2>Transactions Center</h2><p class="muted">Track every roster move, asset exchange, and front-office decision from the current league week.</p></div>
  <div class="tx-actions">
    <form method="post" action="/transactions/refresh{f'?{escape(refresh_query)}' if refresh_query else ''}"><button class="tx-refresh" type="submit">Refresh Transactions</button></form>
    <div class="tx-refresh-meta">Last successful refresh<br><b>{escape(_format_refresh_time(state.get('transactions_last_sync')))}</b></div>
  </div>
</section>
{refresh_alert}
<section class="tx-stats">{stats}</section>
<form class="card" method="get" action="/transactions">
  <div class="tx-filters">
    <div class="tx-field"><label for="team">Team</label><select id="team" name="team">{team_options}</select></div>
    <div class="tx-field"><label for="owner">Owner</label><select id="owner" name="owner">{owner_options}</select></div>
    <div class="tx-field"><label for="type">Transaction type</label><select id="type" name="type">{type_options}</select></div>
    <div class="tx-field"><label for="player">Player</label><input id="player" name="player" value="{escape(player)}" placeholder="Player name"></div>
    <div class="tx-field"><label for="draft_pick">Draft pick</label><select id="draft_pick" name="draft_pick">{pick_options}</select></div>
    <div class="tx-field"><label for="date_from">From date</label><input id="date_from" type="date" name="date_from" value="{escape(date_from)}"></div>
    <div class="tx-field"><label for="date_to">To date</label><input id="date_to" type="date" name="date_to" value="{escape(date_to)}"></div>
    <div class="tx-field"><label for="q">Search</label><input id="q" name="q" value="{escape(search)}" placeholder="Team, owner, player, or draft pick"></div>
    <div class="tx-field"><label for="per_page">Page size</label><select id="per_page" name="per_page">{page_options}</select></div>
    <div class="tx-field"><label for="scope">History scope</label><select id="scope" name="scope">{scope_options}</select></div>
    <div class="tx-field"><label for="season">Season</label><input id="season" type="number" name="season" value="{escape(str(season or ""))}" min="2021"></div>
    <div class="tx-field"><label for="week">Week</label><input id="week" type="number" name="week" value="{escape(str(week or ""))}" min="1" max="18"></div>
    <div class="tx-field"><label for="status">Status</label><select id="status" name="status">{_option("", "All statuses", status)}{_option("complete", "Completed", status)}{_option("failed", "Failed", status)}{_option("pending", "Pending", status)}</select></div>
    <input type="hidden" name="sort" value="{escape(sort)}"><input type="hidden" name="direction" value="{escape(direction)}">
    <div class="tx-filter-actions"><button type="submit">Apply filters</button><a class="tx-reset" href="/transactions">Reset</a></div>
  </div>
</form>
{activity}
{archive_panel}
"""
        return page("Transactions Center", body)

    @router.post("/transactions/refresh")
    async def transactions_refresh(request: Request) -> RedirectResponse:
        await ensure_fresh()
        success = await refresh_transactions()
        parameters = [
            (key, value)
            for key, value in parse_qsl(request.url.query, keep_blank_values=False)
            if key != "refresh"
        ]
        parameters.append(("refresh", "success" if success else "error"))
        return RedirectResponse(
            url="/transactions?" + urlencode(parameters), status_code=303
        )

    def team_origin(data, from_team, from_section):
        if from_team is None or not any(t.get('roster_id') == from_team for t in data.get('teams') or []):
            return {}
        return {'from_team': from_team, 'from_section': from_section if from_section in {'full-roster', 'my-team-advanced'} else 'full-roster'}

    @router.get("/players/{player_id}/projections", response_class=HTMLResponse)
    async def player_week_projection(player_id: str, front_office: int | None = None,
                                     week: int | None = Query(default=None, ge=1, le=18),
                                     from_team: int | None = Query(default=None, ge=1),
                                     from_section: str = Query(default='full-roster', max_length=40)) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        if player_id not in (data.get('players') or {}):
            raise HTTPException(404, 'Player not found')
        active = current_league_context()
        view = await asyncio.to_thread(player_projection_view, data, player_id,
            active.projection if active else projection_service, week)
        view['navigation_context'] = team_origin(data, from_team, from_section)
        return HTMLResponse(player_projection_panel(view, front_office))

    @router.get("/players/{player_id}", response_class=HTMLResponse)
    async def player_page(player_id: str, front_office: int | None = None,
                          week: int | None = Query(default=None, ge=1, le=18),
                          matchup: str | None = Query(default=None, max_length=80),
                          from_team: int | None = Query(default=None, ge=1),
                          from_section: str = Query(default='full-roster', max_length=40),
                          from_trade: str | None = Query(default=None, max_length=100)) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        player = (data.get("players") or {}).get(player_id)
        if not player:
            raise HTTPException(404, "Player not found")
        active = current_league_context()
        projection_view = await asyncio.to_thread(player_projection_view, data, player_id,
            active.projection if active else projection_service, week)
        projection_view['navigation_context'] = team_origin(data, from_team, from_section)
        weekly_panel = player_projection_panel(projection_view, front_office)
        try:
            report, selected_team, teams = build_player_dossier(data, player_id, front_office)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        ownership = PlayerOwnershipIndex(data).resolve(player_id, int(selected_team.get("roster_id") or 0))
        view = transaction_center(
            data,
            {
                "player": player_id,
                "sort": "date",
                "direction": "desc",
                "page": 1,
                "per_page": 50,
            },
        )
        name = player.get("full_name") or " ".join(
            value for value in (player.get("first_name"), player.get("last_name")) if value
        ) or player_id
        live = data_platform.player_report(player_id, data, market_fact=report.market_fact)
        # Reuse the same selected-week/scoring/generation as the numeric panel.
        projection_availability = (
            f"Available · Sleeper week {projection_view['week']} · {projection_view['display']} points"
            if projection_view['value'] is not None else projection_view['reason']
        )
        selected_league = str((data.get("league") or {}).get("league_id") or LEAGUE_ID)
        history = historical_graph(canonical_history_store, selected_league, data).player_dossier(player_id)
        history_league_name = escape(str((data.get("league") or {}).get("name") or "Active League"))
        consensus = live["consensus"]
        from services.asset_explanations import player_profile_explanation
        from src.ui.explanations import explanation_panel
        profile_explanation = explanation_panel(player_profile_explanation(report, league_id=selected_league))
        provider_values = "".join(
            f'<tr><td>{escape(str(row["provider"]))}</td><td>{escape(str(row["value"] if row["value"] is not None else row["availability"]))}</td><td>{escape(str(row["freshness"]))}</td><td>{escape(str(row["confidence"]))}%</td><td>{escape(str((live["provider_availability"].get(row["provider"]) or {}).get("reason", "Available")))}</td></tr>'
            for row in live["provider_values"]
        )
        normalized = live["normalized_player"]
        context = live["player_context"]
        metadata = context["metadata"]
        league_context = context["league"]
        reasons = context["availability"]
        fantasycalc = live["provider_details"].get("FantasyCalc") or {}
        trend_value = fantasycalc.get("trend_30_day")
        trend_label = f"{trend_value:+}" if isinstance(trend_value, (int, float)) else "No historical provider trend is available."
        consensus_value = consensus["value"] if consensus["value"] is not None else "Unavailable"
        attribution = " · ".join(
            f'<a href="{escape(str(item["url"]))}" target="_blank" rel="noopener">{escape(str(item["label"]))}</a>'
            for item in live["attribution"].values()
        ) or "No external provider data was used."
        depth_role = metadata.get("depth_chart_role") if metadata.get("depth_chart_role") is not None else reasons["depth_chart_role"]
        bye_week = metadata.get("bye_week") if metadata.get("bye_week") is not None else reasons["bye_week"]
        live_panel = f'''<section class="card"><h2>Live Data &amp; Market</h2>
<div class="grid"><div><div class="muted">{escape(consensus["evidence_state"])} · 0–1000</div><div class="stat">{escape(str(consensus_value))}</div><p>Evidence confidence {consensus["confidence"]}/100 · Agreement {str(consensus["agreement"]) + "/100" if consensus["agreement"] is not None else "Unavailable"}</p>{market_fact_html(live["market_fact"])}<p>FantasyCalc raw-price 30-day change (provider units): {escape(str(trend_label))}</p></div>
<div><div class="muted">Player Context</div><p><b>{escape(str(normalized["position"]))}</b> · {escape(str(normalized["nfl_team"]))} · {escape(human_status(normalized["status"]))}</p><p>Age: {escape(available(metadata.get("age"), reason="Age is not supplied by the current source."))}</p><p>Depth chart: {escape(str(depth_role))} · Bye: {escape(str(bye_week))}</p></div></div>
<div class="ds-table-wrap" tabindex="0" role="region" aria-label="Provider value evidence"><table><thead><tr><th>Provider</th><th>Raw provider value / State</th><th>Freshness</th><th>Confidence</th><th>Availability reason</th></tr></thead><tbody>{provider_values}</tbody></table></div>
<h3>League Context</h3><div class="grid"><div><b>Trending</b><p>{league_context["trending_adds"]} adds · {league_context["trending_drops"]} drops (Sleeper, last cached window)</p></div><div><b>Ownership</b><p class="player-ownership-label">{escape(ownership["label"])}</p></div><div><b>Transactions</b><p>{league_context["transaction_count"]} cached league transactions</p></div></div>
<h3>Data Availability</h3><ul><li><b>ADP:</b> {escape(str(reasons["adp"]))}</li><li><b>Current projections:</b> {escape(str(projection_availability))}</li><li><b>Production:</b> {escape(str(reasons["production"]))}</li><li><b>Usage:</b> {escape(str(reasons["usage"]))}</li></ul>
<p class="muted">Sources: {attribution} · Sleeper player, league, transaction, and trending metadata.</p></section>'''
        cards = "".join(
            '<div class="card">'
            f'<div class="muted">{escape(transaction["timestamp"])}</div>'
            f'<h3>{escape(transaction["type_label"])}</h3>'
            f'<div class="tx-assets">{"".join(_asset_html(asset) for asset in transaction["assets"] if asset.get("player_id") == player_id)}</div>'
            "</div>"
            for transaction in view["transactions"]
        ) or '<div class="card muted">No cached transactions found for this player.</div>'
        season_history = "".join(
            f'<tr><td>{row["season"]}</td><td>{escape(human_status(row["status"]))}</td><td>{escape(str(row["games_observed"]))}</td><td>{escape(str(row["starts"]))}</td><td>{escape(str(row["bench_appearances"]))}</td><td>{row.get("unknown_role_appearances", 0)}</td><td>{escape(available(row["fantasy_points"], reason="No verified production"))}</td><td>{escape(available(row["overall_rank"], reason="Not ranked"))}</td><td>{escape(available(row["positional_rank"], reason="Not ranked"))}</td><td>{escape(str(row["completeness_percentage"]))}%</td></tr>'
            for row in history["season_summaries"]
        ) or '<tr><td colspan="10">No supported annual observations are available.</td></tr>'
        from src.ui.trade_timeline import render_ownership_events
        history_graph = historical_graph(canonical_history_store, selected_league, data)
        original = validated_trade_origin(history_graph, from_trade)
        origin_query = '?from_trade=' + quote(original['transaction_id'], safe='') if original else ''
        ownership_history = render_ownership_events(history['ownership_timeline'], graph=history_graph, from_trade=original['transaction_id'] if original else None) or f'<li>No verified {history_league_name} ownership event is available.</li>'
        origin = history["league_origin"]
        historical_details = technical_details((("Canonical identity", history["identity"]["canonical_id"]), ("Identity resolution", history["identity"]["resolution_status"])))
        historical_panel = f'''<section class="card"><h2>{history_league_name} Career History</h2><p><b>League origin:</b> {escape(human_status(origin.get("event_type")))}</p><p><a href="/history/player/{escape(player_id)}{origin_query}">Open observed historical performance</a></p>{historical_details}<p>Unknown lineup roles remain separate from bench. Missing weekly scoring remains unavailable.</p>
<h3>Annual League History</h3><div class="ds-table-wrap" tabindex="0" role="region" aria-label="Observed season production"><table><thead><tr><th>Season</th><th>Status</th><th>Scored observations</th><th>Known starts</th><th>Explicit bench</th><th>Unknown role</th><th>Observed points</th><th>Sample overall rank</th><th>Sample position rank</th><th>Scored-week coverage</th></tr></thead><tbody>{season_history}</tbody></table></div>
<h3>Ownership Timeline</h3><ul>{ownership_history}</ul><p class="muted">Failed transactions remain behavioral evidence and never modify ownership. Missing weeks are not converted to zero. Current values are never backdated.</p></section>'''
        trade_return = f'<a class="back" href="/trades/history/{quote(original["transaction_id"], safe="")}">← Back to original trade timeline</a>' if original else ''
        matchup_return = ''
        section = from_section if from_section in {'full-roster', 'my-team-advanced'} else 'full-roster'
        team_return = (f'<a class="back" href="/teams/{from_team}#{section}">← Back to My Team {"intelligence" if section == "my-team-advanced" else "roster"}</a>'
                       if from_team is not None and any(t.get('roster_id') == from_team for t in data.get('teams') or []) else '')
        if week is not None and matchup and (matchup.isdecimal() or (matchup.startswith('unassigned-') and matchup[11:].isdecimal())):
            matchup_return = f'<link rel="stylesheet" href="/static/css/matchups.css"><a class="back matchup-return" href="/matchups/{escape(matchup)}?week={week}">← Back to Week {week} matchup</a>'
        body = f"""
{TRANSACTIONS_CSS}
{trade_return}
{matchup_return}
{team_return or '<a class="back" href="/transactions">← Back to Transactions Center</a>'}
{player_dossier(report, selected_team, teams, weekly_projection_html=weekly_panel, ownership=ownership)}
<p class="player-reported-status">Sleeper reported status: {escape(str(player.get("injury_status") or player.get("status") or "Unavailable"))}</p>
{profile_explanation}
{live_panel}
{historical_panel}
<h2>Recent Transactions</h2><div class="grid">{cards}</div>
"""
        return page(f"{name} — Player Intelligence", body)

    return router
