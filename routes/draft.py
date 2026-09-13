"""DTOS draft pick routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.core.data_platform.pick_quotes import canonical_pick_market
from src.core.intelligence.pick_context import assess_pick_range
from src.core.historical_memory.graph import canonical_pick_id

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_draft_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the Draft Picks router using shared app dependencies."""
    router = APIRouter()

    @router.get("/picks", response_class=HTMLResponse)
    async def picks_page() -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        roster_names = {
            str(team["roster_id"]): team["team_name"] for team in data["teams"]
        }
        rows = []
        cards = []
        sorted_picks = sorted(
            data["traded_picks"],
            key=lambda item: (
                item.get("season", ""),
                item.get("round", 0),
                item.get("roster_id", 0),
            ),
        )
        league_id = str((data.get("league") or {}).get("league_id") or "")
        def identity(pick: dict[str, Any]) -> tuple[str, str, str]:
            return (str(pick.get("year", pick.get("season"))), str(pick.get("round")),
                    str(pick.get("original_roster_id", pick.get("roster_id"))))
        prepared = {identity(p): p for p in data.get("pick_ledger") or []
                    if p.get("league_id") in (None, league_id)}
        for pick in sorted_picks:
            canonical = prepared.get(identity(pick), pick)
            canonical = {**canonical,
                         "original_roster_id": canonical.get("original_roster_id", canonical.get("roster_id")),
                         "year": canonical.get("year", canonical.get("season"))}
            scoped = assess_pick_range(canonical, league_id=league_id)
            market = canonical_pick_market(scoped, data.get("market_data") or {})
            price = market["normalized_market_price"]
            price_text = "Unavailable" if price is None else str(price)
            quote = market.get("quote") or {}
            market_text = escape(str(market.get("evidence_state") or "MARKET UNAVAILABLE"))
            provider = escape(str(quote.get("provider") or "Unavailable"))
            concept = escape(str(quote.get("pick_type") or "Unavailable"))
            range_text = escape(str(scoped["projected_range"]))
            confidence = escape(str(scoped["projected_range_confidence"]))
            exact = escape(str(scoped.get("exact_slot"))) if scoped.get("exact_slot_established") is True else "Unavailable"
            details = (
                '<details><summary>Supporting Evidence</summary>'
                f'<p>Market unit: normalized 0–1000. Format: {escape(str(quote.get("market_format") or "Unavailable"))}.</p>'
                f'<p>Market availability: {escape(str(market.get("availability")))}. '
                f'{escape(str(market.get("reason") or "Prepared external quote"))}</p>'
                f'<p>Range: {escape(", ".join(scoped["range_reasons"]))}. '
                'A generic Market quote does not forecast the original franchise’s finish.</p></details>'
            )
            roster_id = str(canonical.get("original_roster_id"))
            owner_id = str(canonical.get("current_owner_id", canonical.get("owner_id")))
            pick_id = canonical_pick_id(
                pick.get("season", "UNKNOWN"), pick.get("round", "UNKNOWN"), roster_id,
            )
            def franchise(identity: str) -> str:
                label = escape(roster_names.get(identity, "Ownership unavailable"))
                return f'<a href="/teams/{int(identity)}">{label}</a>' if identity in roster_names and identity.isdigit() else label

            cards.append(
                f'<article class="card pick-asset-card"><a class="pick-asset-title" href="/picks/{escape(pick_id)}">'
                f'<span class="pick-emblem" aria-hidden="true">R{escape(str(pick.get("round", "?")))}</span>'
                f'<span><b>{escape(str(pick.get("season", "")))} Round {escape(str(pick.get("round", "")))}</b><small>View pick details →</small></span></a>'
                f'<p class="pick-owner"><span>Current owner</span>{franchise(owner_id)}</p>'
                f'<p class="pick-owner"><span>Original franchise</span>{franchise(roster_id)}</p>'
                f'<div class="pick-outlook"><b>Market price: {price_text}</b><span>{market_text} · {provider} · {concept}</span></div>'
                f'<p class="muted">Projected range: {range_text} · Confidence: {confidence} · Exact slot: {exact}</p>{details}</article>'
            )
            rows.append(
                f'<tr><td><a href="/picks/{escape(pick_id)}">{escape(str(pick.get("season", "")))}</a></td>'
                f'<td>{escape(str(pick.get("round", "")))}</td>'
                f'<td>{escape(roster_names.get(roster_id, roster_id))}</td>'
                f'<td>{escape(roster_names.get(owner_id, owner_id))}</td>'
                f'<td><b>{price_text}</b><br><small>{market_text} · {provider} · {concept}</small></td>'
                f'<td>{range_text} · {confidence}</td><td>{exact}</td></tr>'
            )

        body = (
            '<h2>Traded Draft Picks</h2><div class="pick-asset-grid">'
            + ("".join(cards) or '<div class="ds-empty"><b>No traded picks are available.</b>Current roster-owned picks remain available in Team HQ.</div>')
            + '</div><details class="technical-details"><summary>Compare all pick evidence</summary><div class="card ds-table-wrap"><table><thead>'
            '<tr><th>Season</th><th>Round</th><th>Original Team</th>'
            '<th>Current Owner</th><th>Market price</th><th>Projected range / confidence</th><th>Exact slot</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table></div></details>"
        )
        return page("Draft Picks", body)

    return router
