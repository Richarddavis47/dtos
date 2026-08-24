"""Asset Market and Dynasty Exchange read-only routes."""
from __future__ import annotations

from html import escape
from typing import Any, Callable
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse

from app_metadata import BUILD_NUMBER, VERSION
from src.core.asset_market import AssetMarketCache, MarketWarmingError, asset_market_cache
from src.core.history_context import canonical_history_store
from services.history import (
    history_progress_contracts,
    retained_history_progress_contracts,
)
from src.ui.intelligence_presentation import available
from src.ui.render_cache import GenerationRenderCache
from src.ui import player_summary

RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[..., HTMLResponse]

# Compatibility injection point for isolated route tests. Canonical production
# binds this name to the Sleeper-backed context store, never HistoricalStore.
historical_store = canonical_history_store
home_render_cache = GenerationRenderCache("home", max_entries=8)
market_render_cache = GenerationRenderCache("market", max_entries=24)
home_body_render_cache = GenerationRenderCache("home_body", max_entries=8)
market_body_render_cache = GenerationRenderCache("market_body", max_entries=24)


def _value(
    row: dict[str, Any], name: str,
    layers: dict[str, Any] | None = None,
) -> str:
    value = row["values"].get(name)
    if value is not None:
        return f"{value:,.0f}"
    layer = (layers or {}).get(name) or {}
    return str(layer.get("reason") or "Insufficient DTOS evidence")


def create_market_router(
    *, require_data: RequireData, state: dict[str, Any], league_id: str,
    page: PageRenderer,
    context_resolver: Callable[[], Any | None] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["asset-market"])

    def dependencies() -> tuple[dict[str, Any], str, AssetMarketCache]:
        context = context_resolver() if context_resolver is not None else None
        if context is None:
            return state, league_id, asset_market_cache
        return context.state, context.league_id, context.market

    def model():
        selected_state, selected_league, cache = dependencies()
        try:
            return cache.get(
                require_data(), selected_state, historical_store,
                selected_league, background=True,
            )
        except MarketWarmingError as exc:
            metrics = cache.metrics()
            headers = {
                "Retry-After": "5",
                "X-DTOS-Market-Refresh": str(metrics.get("refresh_state") or "warming"),
            }
            if metrics.get("last_valid_model"):
                headers["X-DTOS-Last-Valid-Generation"] = str(
                    metrics.get("market_generation") or "retained"
                )
            raise HTTPException(
                status_code=503, detail=str(exc), headers=headers,
            ) from exc

    @router.get("/api/market")
    async def market_index() -> Any:
        """Return retained lifecycle metadata without requiring a market model."""
        _selected_state, selected_league, cache = dependencies()
        health = cache.health()
        return {
            **health,
            "historical_progress": retained_history_progress_contracts(selected_league),
            "endpoints": [
            "/api/market/assets", "/api/market/assets/{asset_id}",
            "/api/market/search", "/api/market/trending", "/api/market/health",
            ],
        }

    @router.get("/api/market/health")
    async def market_health() -> Any:
        selected_state, selected_league, cache = dependencies()
        cache.reconcile(
            selected_state.get("data") or {}, selected_state,
            historical_store, selected_league,
        )
        health = cache.health()
        return {
            "application_version": VERSION, **health,
            "render_caches": {
                "home": home_render_cache.health(),
                "market": market_render_cache.health(),
                "home_body": home_body_render_cache.health(),
                "market_body": market_body_render_cache.health(),
            },
            "reason": (
                None if health["status"] == "ready"
                else "Awaiting a safe Asset Market snapshot."
            ),
        }

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
        result = model().directory(
            offset=offset, limit=limit, sort=sort, direction=direction,
            asset_type=asset_type, position=position, availability=availability,
            owner=owner, minimum=minimum, maximum=maximum,
            age_min=age_min, age_max=age_max, year=year,
            round_number=round_number,
        )
        result["historical_progress"] = history_progress_contracts(dependencies()[1])
        return jsonable_encoder(result)

    @router.get("/api/market/assets/{asset_id:path}")
    async def market_asset(asset_id: str, front_office: int | None = None) -> Any:
        result = model().detail(asset_id, front_office)
        if result is None:
            raise HTTPException(404, "Canonical market asset not found.")
        result["historical_progress"] = history_progress_contracts(dependencies()[1])
        return jsonable_encoder(result)

    @router.get("/api/market/search")
    async def market_search(q: str = "", limit: int = Query(50, ge=1, le=100)) -> Any:
        return jsonable_encoder(model().search(q, limit))

    @router.get("/api/market/trending")
    async def market_trending(limit: int = Query(10, ge=1, le=50)) -> Any:
        return jsonable_encoder(model().trending(limit))

    def market_page(
        request: Request,
        q: str = "", position: str = "", availability: str = "",
        sort: str = "market", direction: str = "desc",
        front_office: int | None = None, selected: str = "",
        offset: int = Query(0, ge=0), limit: int = Query(50, ge=10, le=100),
    ) -> HTMLResponse:
        market = model()
        selected_state, selected_league, _cache = dependencies()
        data = selected_state.get("data") or {}
        league_name = str((data.get("league") or {}).get("name") or "Sleeper League")
        generation = str(market.semantic_generation)
        route_variant = "market"
        key = (
            route_variant, selected_league, generation, market.dataset_version,
            VERSION, BUILD_NUMBER, league_name, selected_state.get("last_sync"),
            selected_state.get("last_error"), q, position, availability, sort,
            direction, front_office, selected, offset, limit,
        )
        render_cache = home_render_cache if route_variant == "home" else market_render_cache
        body_cache = (
            home_body_render_cache
            if route_variant == "home" else market_body_render_cache
        )
        body_key = (
            route_variant, selected_league, generation, market.dataset_version,
            VERSION, BUILD_NUMBER, q, position, availability, sort,
            direction, front_office, selected, offset, limit,
        )

        def render_body() -> bytes:
            directory_limit = limit if offset or q else min(limit, 10)
            result = market.search(q, limit) if q else market.directory(
                offset=offset, limit=directory_limit, sort=sort, direction=direction,
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
                    return available(value if value is not None else fallback)
                display_name = str(row.get("display_name") or asset_id)
                asset_label = (
                    player_summary(
                        player_id=asset_id.removeprefix("player:"),
                        name=display_name,
                        position=str(row.get("position") or ""),
                        nfl_team=str(row.get("nfl_team") or "Free Agent"),
                        context=f'Rank #{row.get("rank") or index}',
                    )
                    if asset_id.startswith("player:") else
                    f'<b>{escape(display_name)}</b><br><code>{escape(asset_id)}</code>'
                )
                table_rows.append(
                    f'''<tr><td>{row.get("rank") or index}</td><td><a href="/market?{escape(query)}">{asset_label}</a></td><td>{escape(str(owner.get("team_name") or owner.get("owner") or "Unrostered"))}</td><td>{escape(shown("market_value"))}</td><td>{escape(shown("intrinsic_dtos_value"))}</td><td>{escape(shown("contender_value"))}</td><td>{escape(shown("rebuilder_value"))}</td><td>{escape(available(row.get("confidence"), reason="Unavailable"))}</td><td>{escape(available(row.get("agreement"), reason="Unavailable"))}</td><td>{escape(available(row.get("evidence_coverage"), reason="Unavailable"))}</td></tr>'''
                )
            detail = market.detail(selected, front_office) if selected else None
            expanded = ""
            if detail:
                asset, recommendation = detail["asset"], detail["recommendation"]
                history = detail.get("history") or {}
                layers = detail.get("value_layers") or {}
                forward = (detail.get("valuation") or {}).get("forward_production") or {}
                forward_html = ""
                if forward:
                    weekly = forward.get("weekly_projected_points")
                    weekly_display = "Bye / unavailable" if weekly is None else f"{weekly:.1f}"
                    confidence = forward.get("projection_confidence")
                    confidence_html = "Unavailable" if confidence is None else f"{confidence}%"
                    forward_html = f'''<section class="card"><p class="eyebrow">Canonical Weekly Projection</p>{f'<div class="summary-grid"><article class="metric"><b>{weekly_display}</b><span>Sleeper projection</span></article><article class="metric"><b>{confidence_html}</b><span>Evidence confidence</span></article></div>' if weekly is not None else '<div class="evidence-unavailable"><b>Weekly projection unavailable.</b><br>Sleeper has not supplied a canonical projection for this asset and matchup context.</div>'}<details><summary>Evidence</summary><p>Sleeper supplies the weekly projection under this league's scoring profile. DTOS does not fabricate a fallback.</p></details></section>'''
                values = asset.get("values") or {}
                values_available = any(values.get(name) is not None for name in ("market_value", "intrinsic_dtos_value", "contender_value", "rebuilder_value"))
                value_html = (
                    f'<div class="summary-grid"><article class="metric"><b>{escape(_value(asset, "market_value", layers))}</b><span>Market</span></article><article class="metric"><b>{escape(_value(asset, "intrinsic_dtos_value", layers))}</b><span>Intrinsic</span></article><article class="metric"><b>{escape(_value(asset, "contender_value", layers))}</b><span>Contender</span></article><article class="metric"><b>{escape(_value(asset, "rebuilder_value", layers))}</b><span>Rebuilder</span></article></div>'
                    if values_available else
                    '<div class="evidence-unavailable"><b>Current market values are unavailable.</b><br>DTOS will show them when canonical market evidence supports this asset.</div>'
                )
                trade_href = "/trades" if front_office is None else f"/trades?front_office={front_office}"
                expanded = f'''<section class="card" id="selected-asset" tabindex="-1"><p class="eyebrow">Expanded Asset</p><h2>{escape(asset["display_name"])}</h2><p>{escape(str(asset.get("position") or asset["asset_type"]))} · {escape(str(asset.get("nfl_team") or "No NFL team"))}</p>{value_html}<p><b>DTOS view:</b> {escape(recommendation["primary_reason"])}</p><p><a href="{escape(asset["canonical_url"])}">Open canonical dossier</a> · <a href="{trade_href}">Trade Intelligence</a></p><details><summary>Why?</summary><p>Decision confidence: {escape(available(recommendation.get("confidence"), reason="Unavailable"))}</p><p>Historical availability: {escape(asset["historical_availability"])}</p><p>Missing evidence: {escape(", ".join(recommendation["missing_evidence"]) or "None reported")}</p></details><details class="technical-details"><summary>Technical Details</summary><p>Asset: <code>{escape(asset["asset_id"])}</code></p><p>Brain snapshot: <code>{escape(recommendation["brain_snapshot_id"])}</code></p><p>Market generation: <code>{escape(detail["market_generation"])}</code></p><p>Valuation generation: <code>{escape(str(detail.get("valuation_generation") or "Unavailable"))}</code></p><p>Historical dataset: <code>{escape(detail["historical_dataset_version"])}</code></p><p>Historical evidence records: {len(history.get("events") or history.get("ownership_intervals") or [])}</p></details></section>{forward_html}'''
            def options(values: Any, selected_value: str) -> str:
                return "".join(
                    f'<option value="{value}" {"selected" if selected_value == value else ""}>{label}</option>'
                    for value, label in values
                )
            trend_reason = market.trending()["unavailable_reason"]
            movers_html = f'<div class="evidence-unavailable"><b>Market movement is not available yet.</b><br>{escape(trend_reason)}</div>' if trend_reason else '<div class="card"><p>Meaningful timestamped movement is available.</p><a href="/api/market/trending">Review movement evidence →</a></div>'
            body = f'''<p class="eyebrow">DTOS v{VERSION}</p><h2>Asset Market &amp; Dynasty Exchange</h2><p class="muted">Search the canonical dynasty market first. Values remain separate; unavailable evidence is never substituted.</p><form class="card ux-answer" method="get" action="/market" aria-label="Asset Market filters"><h3>Search players &amp; picks</h3><label for="market-search">Player name or future pick</label><input id="market-search" name="q" value="{escape(q)}" placeholder="Josh Allen or 2028 1st"><label for="market-position">Position</label><select id="market-position" name="position"><option value="">All assets</option>{options(((item,item) for item in ("QB","RB","WR","TE","PICK")), position)}</select><label for="market-availability">Availability</label><select id="market-availability" name="availability"><option value="">All availability</option>{options((("rostered","Rostered"),("day_traders_free_agent","Free Agents"),("taxi","Taxi"),("retired","Retired"),("owned_pick","Picks")), availability)}</select><label for="market-sort">Sort</label><select id="market-sort" name="sort">{options(((item,item.title()) for item in ("market","intrinsic","contender","rebuilder","confidence","risk","liquidity")), sort)}</select><input type="hidden" name="front_office" value="{front_office or ''}"><button class="btn" type="submit">Search market</button></form><section class="ux-section" id="market-movers"><div class="ux-section-head"><h2>Market Movers</h2><p>Meaningful timestamped movement only</p></div>{movers_html}</section><section class="ux-section"><div class="ux-section-head"><h2>{'Search Results' if q else 'Top Rankings'}</h2><p>{'Exact compact matches' if q else 'A focused opening view; browse deeper when needed'}</p></div><div class="card"><p><b>{result.get("total", result.get("count", 0))}</b> matching assets</p><div style="overflow-x:auto"><table><caption>Canonical dynasty asset rankings</caption><thead><tr><th>Rank</th><th>Asset</th><th>Owner</th><th>Market</th><th>Intrinsic</th><th>Contender</th><th>Rebuilder</th><th>Confidence</th><th>Agreement</th><th>Evidence</th></tr></thead><tbody>{''.join(table_rows) or '<tr><td colspan="10">No canonical assets match these filters.</td></tr>'}</tbody></table></div><nav aria-label="Market pagination"><a href="/market?offset={max(0, offset-limit)}&limit={limit}&sort={escape(sort)}">Previous</a> · <a href="/market?offset={offset+limit}&limit={limit}&sort={escape(sort)}">Browse all assets →</a></nav><details class="technical-details"><summary>Technical Details</summary><p>Dataset <code>{escape(market.dataset_version[:12])}</code> · stable tie-break: canonical asset ID</p></details></div></section>{expanded}'''
            return body.encode("utf-8")

        def render() -> bytes:
            body = body_cache.get_or_build(
                body_key, generation, render_body,
            ).decode("utf-8")
            return page("Asset Market", body).body

        return HTMLResponse(render_cache.get_or_build(key, generation, render))

    router.add_api_route("/market", market_page, methods=["GET"], response_class=HTMLResponse)
    return router
