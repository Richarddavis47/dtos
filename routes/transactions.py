"""DTOS Transactions Center routes and presentation."""
from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, quote, urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.transactions import transaction_center


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
@media(max-width:600px){.tx-stats{grid-template-columns:repeat(2,1fr)}.tx-filters{grid-template-columns:1fr}.tx-refresh-meta{text-align:left}.tx-hero{display:block}.tx-actions{margin-top:10px}.tx-stat b{font-size:19px}}
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
        label = f'<b>{escape(str(asset["label"]))}</b>'
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
        raw = escape(json.dumps(transaction["raw"], indent=2)[:10000])
        rows.append(
            "<tr>"
            f'<td class="tx-time"><b>{escape(transaction["timestamp"])}</b></td>'
            f'<td><span class="tx-type {escape(transaction["type"])}">{escape(transaction["type_label"])}</span><br><small class="muted">{escape(transaction["status"])}</small></td>'
            f'<td><div class="tx-teams">{teams}</div></td>'
            f'<td><div class="tx-assets">{assets}</div><details class="tx-raw"><summary>Raw Sleeper data</summary><pre>{raw}</pre></details></td>'
            f'<td class="tx-id">{escape(transaction["id"] or "—")}</td>'
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5" class="tx-empty">No transactions match the current filters.</td></tr>')

    sort = str(filters["sort"])
    direction = str(filters["direction"])
    headings = "".join(
        f"<th>{_sort_heading(label, field, filters, sort, direction)}</th>"
        for label, field in (
            ("Timestamp", "date"),
            ("Type", "type"),
            ("Teams involved", "teams"),
            ("Assets exchanged", "assets"),
            ("Sleeper ID", "id"),
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
        sort: str = "date",
        direction: str = "desc",
        page_number: int = Query(1, alias="page", ge=1),
        per_page: int = Query(25),
        refresh: str = "",
    ) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        filters = _filters(**locals())
        view = transaction_center(data, filters)
        filters["page"] = view["page"]
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
            for value in view["transaction_types"]
        )
        pick_options = "".join(
            _option(value, label, draft_pick)
            for value, label in (("", "Any draft-pick state"), ("yes", "Includes a draft pick"), ("no", "No draft picks"))
        )
        page_options = "".join(
            _option(str(value), f"{value} per page", view["per_page"])
            for value in (10, 25, 50)
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
    <div class="tx-field"><label for="player">Player</label><input id="player" name="player" value="{escape(player)}" placeholder="Name or Sleeper ID"></div>
    <div class="tx-field"><label for="draft_pick">Draft pick</label><select id="draft_pick" name="draft_pick">{pick_options}</select></div>
    <div class="tx-field"><label for="date_from">From date</label><input id="date_from" type="date" name="date_from" value="{escape(date_from)}"></div>
    <div class="tx-field"><label for="date_to">To date</label><input id="date_to" type="date" name="date_to" value="{escape(date_to)}"></div>
    <div class="tx-field"><label for="q">Search</label><input id="q" name="q" value="{escape(search)}" placeholder="Team, owner, player, pick, or ID"></div>
    <div class="tx-field"><label for="per_page">Page size</label><select id="per_page" name="per_page">{page_options}</select></div>
    <input type="hidden" name="sort" value="{escape(sort)}"><input type="hidden" name="direction" value="{escape(direction)}">
    <div class="tx-filter-actions"><button type="submit">Apply filters</button><a class="tx-reset" href="/transactions">Reset</a></div>
  </div>
</form>
{_transactions_table(view, filters)}
{_pagination(view, filters)}
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

    @router.get("/players/{player_id}", response_class=HTMLResponse)
    async def player_page(player_id: str) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        player = (data.get("players") or {}).get(player_id)
        if not player:
            raise HTTPException(404, "Player not found")
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
        initials = "".join(part[:1] for part in str(name).split()[:2]).upper() or "P"
        cards = "".join(
            '<div class="card">'
            f'<div class="muted">{escape(transaction["timestamp"])}</div>'
            f'<h3>{escape(transaction["type_label"])}</h3>'
            f'<div class="tx-assets">{"".join(_asset_html(asset) for asset in transaction["assets"] if asset.get("player_id") == player_id)}</div>'
            "</div>"
            for transaction in view["transactions"]
        ) or '<div class="card muted">No cached transactions found for this player.</div>'
        body = f"""
{TRANSACTIONS_CSS}
<a class="back" href="/transactions">← Back to Transactions Center</a>
<section class="card player-hero"><div class="player-monogram">{escape(initials)}</div><div><div class="identity-kicker">Player transaction activity</div><h2>{escape(str(name))}</h2><div class="muted">{escape(str(player.get('position') or '—'))} · {escape(str(player.get('team') or 'Free Agent'))} · Sleeper ID {escape(player_id)}</div></div></section>
<h2>Recent Transactions</h2><div class="grid">{cards}</div>
"""
        return page(str(name), body)

    return router
