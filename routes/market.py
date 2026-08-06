"""Asset Market and Dynasty Exchange read-only routes."""
from __future__ import annotations

from html import escape
from typing import Any, Callable
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse

from app_metadata import VERSION
from src.core.asset_market import asset_market, asset_market_cache
from src.core.historical_memory import historical_store

RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[..., HTMLResponse]


def _value(row: dict[str, Any], name: str) -> str:
    value = row["values"].get(name)
    return "Unavailable" if value is None else f"{value:,.0f}"


def create_market_router(
    *, require_data: RequireData, state: dict[str, Any], league_id: str,
    page: PageRenderer,
) -> APIRouter:
    router = APIRouter(tags=["asset-market"])

    def model():
        return asset_market(require_data(), state, historical_store, league_id)

    @router.get("/api/market")
    async def market_index() -> Any:
        market = model()
        return {**market.health(), "endpoints": [
            "/api/market/assets", "/api/market/assets/{asset_id}",
            "/api/market/search", "/api/market/trending", "/api/market/health",
        ]}

    @router.get("/api/market/health")
    async def market_health() -> Any:
        return {**model().health(), "cache": asset_market_cache.metrics()}

    @router.get("/api/market/assets")
    async def market_assets(
        offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=250),
        sort: str = "market", direction: str = "desc",
        asset_type: str | None = None, position: str | None = None,
        availability: str | None = None, owner: int | None = None,
        minimum: float | None = Query(None, alias="min_value"),
        maximum: float | None = Query(None, alias="max_value"),
        age_min: float | None = None, age_max: float | None = None,
        year: int | None = None,
        round_number: int | None = Query(None, alias="round"),
    ) -> Any:
        return jsonable_encoder(model().directory(
            offset=offset, limit=limit, sort=sort, direction=direction,
            asset_type=asset_type, position=position, availability=availability,
            owner=owner, minimum=minimum, maximum=maximum,
            age_min=age_min, age_max=age_max, year=year,
            round_number=round_number,
        ))

    @router.get("/api/market/assets/{asset_id:path}")
    async def market_asset(asset_id: str, front_office: int | None = None) -> Any:
        result = model().detail(asset_id, front_office)
        if result is None:
            raise HTTPException(404, "Canonical market asset not found.")
        return jsonable_encoder(result)

    @router.get("/api/market/search")
    async def market_search(q: str = "", limit: int = Query(50, ge=1, le=100)) -> Any:
        return jsonable_encoder(model().search(q, limit))

    @router.get("/api/market/trending")
    async def market_trending(limit: int = Query(10, ge=1, le=50)) -> Any:
        return jsonable_encoder(model().trending(limit))

    async def market_page(
        q: str = "", position: str = "", availability: str = "",
        sort: str = "market", direction: str = "desc",
        front_office: int | None = None, selected: str = "",
        offset: int = Query(0, ge=0), limit: int = Query(50, ge=10, le=100),
    ) -> HTMLResponse:
        market = model()
        result = market.search(q, limit) if q else market.directory(
            offset=offset, limit=limit, sort=sort, direction=direction,
            position=position or None, availability=availability or None,
        )
        rows = result.get("assets") or result.get("results") or []
        table_rows = []
        for index, row in enumerate(rows, start=offset + 1):
            values = row.get("values") or {}
            owner = row.get("owner") or {}
            asset_id = str(row["asset_id"])
            query = urlencode({
                "q": q, "position": position, "availability": availability,
                "sort": sort, "direction": direction,
                "front_office": front_office or "", "selected": asset_id,
                "offset": offset, "limit": limit,
            })
            def shown(name: str) -> str:
                value = values.get(name)
                fallback = row.get(name)
                return str(value if value is not None else fallback if fallback is not None else "Unavailable")
            table_rows.append(
                f'''<tr><td>{row.get("rank") or index}</td><td><a href="/market?{escape(query)}">{escape(str(row.get("display_name") or asset_id))}</a><br><code>{escape(asset_id)}</code></td><td>{escape(str(owner.get("team_name") or owner.get("owner") or "Unrostered"))}</td><td>{escape(shown("market_value"))}</td><td>{escape(shown("intrinsic_dtos_value"))}</td><td>{escape(shown("contender_value"))}</td><td>{escape(shown("rebuilder_value"))}</td><td>{escape(str(row.get("confidence") or 0))}</td><td>{escape(str(row.get("agreement") or 0))}</td><td>{escape(str(row.get("evidence_coverage") or 0))}</td></tr>'''
            )
        detail = market.detail(selected, front_office) if selected else None
        expanded = ""
        if detail:
            asset, recommendation = detail["asset"], detail["recommendation"]
            history = detail.get("history") or {}
            expanded = f'''<section class="card" id="selected-asset" tabindex="-1"><p class="eyebrow">Expanded Asset</p><h2>{escape(asset["display_name"])}</h2><p><code>{escape(asset["asset_id"])}</code> · {escape(str(asset.get("position") or asset["asset_type"]))} · {escape(str(asset.get("nfl_team") or "No NFL team"))}</p><div class="summary-grid"><article class="metric"><b>{_value(asset, "market_value")}</b><span>Market</span></article><article class="metric"><b>{_value(asset, "intrinsic_dtos_value")}</b><span>Intrinsic</span></article><article class="metric"><b>{_value(asset, "contender_value")}</b><span>Contender</span></article><article class="metric"><b>{_value(asset, "rebuilder_value")}</b><span>Rebuilder</span></article></div><details><summary>Show reasoning and evidence</summary><p>{escape(recommendation["primary_reason"])}</p><p>Decision confidence: {recommendation["confidence"]}/100</p><p>Brain snapshot: <code>{escape(recommendation["brain_snapshot_id"])}</code></p><p>Market generation: <code>{escape(detail["market_generation"])}</code></p><p>Valuation generation: <code>{escape(str(detail.get("valuation_generation") or "Unavailable"))}</code></p><p>Historical dataset: <code>{escape(detail["historical_dataset_version"])}</code></p><p>Missing evidence: {escape(", ".join(recommendation["missing_evidence"]) or "None reported")}</p></details><p>Historical availability: {escape(asset["historical_availability"])}</p><p><a href="{escape(asset["canonical_url"])}">Open canonical dossier</a> · <a href="/trades?front_office={front_office or 1}">Trade Intelligence</a> · Historical evidence records: {len(history.get("events") or history.get("ownership_intervals") or [])}</p></section>'''
        def options(values: Any, selected_value: str) -> str:
            return "".join(
                f'<option value="{value}" {"selected" if selected_value == value else ""}>{label}</option>'
                for value, label in values
            )
        body = f'''<p class="eyebrow">DTOS v{VERSION}</p><h2>Asset Market &amp; Dynasty Exchange</h2><p class="muted">One canonical, explainable market for players, free agents, picks, and connected league history. Values remain separate; unavailable evidence is never substituted.</p><form class="card" method="get" action="/market" aria-label="Asset Market filters"><label for="market-search">Search players, picks, teams, managers, trades, and transactions</label><input id="market-search" name="q" value="{escape(q)}" placeholder="Josh Allen or 2028 1st"><label for="market-position">Position</label><select id="market-position" name="position"><option value="">All assets</option>{options(((item,item) for item in ("QB","RB","WR","TE","PICK")), position)}</select><label for="market-availability">Availability</label><select id="market-availability" name="availability"><option value="">All availability</option>{options((("rostered","Rostered"),("day_traders_free_agent","Free Agents"),("taxi","Taxi"),("retired","Retired"),("owned_pick","Picks")), availability)}</select><label for="market-sort">Sort</label><select id="market-sort" name="sort">{options(((item,item.title()) for item in ("market","intrinsic","contender","rebuilder","confidence","risk","liquidity")), sort)}</select><input type="hidden" name="front_office" value="{front_office or ''}"><button class="btn" type="submit">Apply market view</button></form><div class="card"><p><b>{result.get("total", result.get("count", 0))}</b> matching assets · Dataset <code>{escape(market.dataset_version[:12])}</code> · Stable tie-break: canonical asset ID</p><div style="overflow-x:auto"><table><caption>Canonical dynasty asset rankings</caption><thead><tr><th>Rank</th><th>Asset</th><th>Owner</th><th>Market</th><th>Intrinsic</th><th>Contender</th><th>Rebuilder</th><th>Confidence</th><th>Agreement</th><th>Evidence</th></tr></thead><tbody>{''.join(table_rows) or '<tr><td colspan="10">No canonical assets match these filters.</td></tr>'}</tbody></table></div><nav aria-label="Market pagination"><a href="/market?offset={max(0, offset-limit)}&limit={limit}&sort={escape(sort)}">Previous</a> · <a href="/market?offset={offset+limit}&limit={limit}&sort={escape(sort)}">Next</a></nav></div>{expanded}<section class="card"><h3>Trending Market</h3><p>{escape(market.trending()["unavailable_reason"] or "Timestamped comparable observations are available.")}</p><p><a href="/api/market/trending">Open explainable trending contract</a></p></section>'''
        return page("Asset Market", body)

    router.add_api_route("/", market_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/market", market_page, methods=["GET"], response_class=HTMLResponse)
    return router
