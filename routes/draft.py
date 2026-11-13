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
        historical_cards = []
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
        source_season = str((data.get('league') or {}).get('season') or '')
        prepared = {}
        duplicate_rights = set()
        for row in data.get('pick_ledger') or []:
            if row.get('league_id') in (None, league_id):
                key = identity(row)
                if key in prepared:
                    duplicate_rights.add(key)
                prepared[key] = row
        for pick in sorted_picks:
            year = str(pick.get('season') or '')
            current_right = (identity(pick) in prepared and identity(pick) not in duplicate_rights and source_season.isdigit()
                             and year.isdigit() and int(year) > int(source_season))
            canonical = prepared.get(identity(pick), pick)
            canonical = {**canonical,
                         "original_roster_id": canonical.get("original_roster_id", canonical.get("roster_id")),
                         "year": canonical.get("year", canonical.get("season"))}
            scoped = assess_pick_range(canonical, league_id=league_id)
            market = canonical_pick_market(scoped, data.get("market_data") or {})
            from services.asset_explanations import pick_explanation
            from src.ui.explanations import explanation_panel
            shared_explanation = explanation_panel(pick_explanation(scoped, market, league_id=league_id))
            price = market["normalized_market_price"]
            price_text = "Unavailable" if price is None else str(price)
            quote = market.get("quote") or {}
            market_text = escape(str(market.get("evidence_state") or "MARKET UNAVAILABLE"))
            provider = escape(str(quote.get("provider") or "Unavailable"))
            concept = escape(str(quote.get("pick_type") or "Unavailable"))
            market_summary = ('<span>' + provider + '</span>') if price is not None and quote.get('provider') else ''
            market_gap = ('<p class="muted">No compatible Market quote is available for this exact pick.</p>') if price is None else ''
            range_text = escape(str(scoped["projected_range"]))
            confidence = escape(str(scoped["projected_range_confidence"]))
            exact = escape(str(scoped.get("exact_slot"))) if scoped.get("exact_slot_established") is True else "Unavailable"
            details = (
                '<details><summary>Supporting Evidence</summary>'
                f'<p>{market_text} · {provider} · {concept}</p><p>Market unit: normalized 0–1000. Format: {escape(str(quote.get("market_format") or "Unavailable"))}.</p>'
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

            card = (
                f'<article class="card pick-asset-card"><a class="pick-asset-title" href="/picks/{escape(pick_id)}">'
                f'<span class="pick-emblem" aria-hidden="true">R{escape(str(pick.get("round", "?")))}</span>'
                f'<span><b>{escape(str(pick.get("season", "")))} Round {escape(str(pick.get("round", "")))}</b><small>View pick details →</small></span></a>'
                f'<p class="pick-owner"><span>{"Current owner" if current_right else "Owner in recorded transfer"}</span>{franchise(owner_id)}</p>'
                f'<p class="pick-owner"><span>Original franchise</span>{franchise(roster_id)}</p>'
                f'<div class="pick-outlook"><b>Market price: {price_text}</b>{market_summary}</div>{market_gap}'
                '<details><summary>Draft position and valuation details</summary>'
                f'<p class="muted">Projected range: {range_text} · Confidence: {confidence} · Exact slot: {exact}</p>{details}{shared_explanation}</details></article>'
            )
            (cards if current_right else historical_cards).append(card)
            rows.append(
                f'<tr><td><a href="/picks/{escape(pick_id)}">{escape(str(pick.get("season", "")))}</a></td>'
                f'<td>{escape(str(pick.get("round", "")))}</td>'
                f'<td>{escape(roster_names.get(roster_id, roster_id))}</td>'
                f'<td>{escape(roster_names.get(owner_id, owner_id))}</td>'
                f'<td><b>{price_text}</b><br><small>{market_text} · {provider} · {concept}</small></td>'
                f'<td>{range_text} · {confidence}</td><td>{exact}</td></tr>'
            )

        body = (
            '<h2>Draft Picks</h2><p>Current traded picks are separate from past transfers. Your full owned inventory is in My Team draft capital.</p><h3>Current traded picks</h3><div class="pick-asset-grid">'
            + ("".join(cards) or '<div class="ds-empty"><b>No current traded picks are established here.</b>View My Team for supported owned picks.</div>')
            + '</div>' + ('<details class="cx-evidence"><summary>Past or unconfirmed pick transfers · ' + str(len(historical_cards)) + '</summary><p>These recorded transfers do not establish a currently tradable pick. Open its history to check conversion and ownership.</p><div class="pick-asset-grid">' + ''.join(historical_cards) + '</div></details>' if historical_cards else '')
            + '<details class="technical-details"><summary>Compare all pick evidence</summary><div class="card ds-table-wrap"><table><thead>'
            '<tr><th>Season</th><th>Round</th><th>Original Team</th>'
            '<th>Current Owner</th><th>Market price</th><th>Projected range / confidence</th><th>Exact slot</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table></div></details>"
        )
        return page("Draft Picks", body)

    return router
