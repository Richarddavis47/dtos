"""Phone-first disclosure over existing, independently qualified evidence."""

from html import escape
from math import isfinite
from urllib.parse import urlencode

from src.ui.customer_experience import plain_reason, readable_time


def movement_panel(view, market_query):
    def text(value):
        return escape(str(value))

    reason = plain_reason(view["reason"])
    if reason.startswith('Roster evidence is provisional or incomplete;'):
        reason = 'Your roster comparison is provisional or incomplete, so personalized matches are not shown. Neutral prices and movement are still available.'
    reason = reason.replace('Compatible prepared roster projections are unavailable for this league.', 'Roster projections are not ready for this league.').replace('A matching prepared roster comparison is unavailable for this league, week, scoring and availability.', 'This week’s roster comparison cannot yet be verified.')
    html = [
        '<section class="card" id="market-roster-movement" style="min-width:0;overflow-wrap:anywhere" aria-labelledby="market-roster-title" tabindex="-1">',
        '<h2 id="market-roster-title">Market movement and your roster</h2>',
        "<p>" + text(reason) + "</p>",
        "<details><summary>Roster relevance sources</summary><p>" + text(view["reason"]) + "</p></details>",
        f'<p class="muted">Showing up to three from {view["sampled"]} assets on this page. No trade has been evaluated.</p>',
    ]
    if view["need"] and not view["has_related"]:
        html.append(
            "<p>No comparable movement in this page sample matches that need for an acquirable player. Any observations below are neutral context, not personalized leads.</p>"
        )
    if not view["cards"]:
        html.append(
            "<p>This page does not have enough comparable dated prices. Movement is unknown, not zero or evidence of no opportunities. Try the existing Market filters or review an asset’s retained observations.</p>"
        )
    for card in view["cards"]:
        trend = card["trend"]
        value = card["value"]
        price = (
            f"{value:,.2f} Market points"
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
            else "Unavailable"
        )
        detail = (
            "/market?"
            + urlencode(
                {
                    k: v
                    for k, v in {**market_query, "selected": card["asset_id"]}.items()
                    if v is not None
                }
            )
            + "#selected-asset"
        )
        html.extend(
            [
                f'<article class="market-roster-card" data-market-asset="{text(card["asset_id"])}">',
                "<h3>" + text(card["name"]) + "</h3>",
                f"<p><b>Observed change: {trend['magnitude']:+,.2f} Market points</b><br>{text(readable_time(trend['comparison_start_at']))} → {text(readable_time(trend['comparison_end_at']))}</p>",
                "<p>" + text(plain_reason(card["source"])) + " · " + text(card["age"]) + ".</p>",
                "<p>"
                + (
                    f"Position matches your supported {text(view['need']['position'])} {text(view['need']['kind'])} need. This match does not establish this player’s legal-lineup improvement."
                    if card["related"]
                    else "Neutral observation; no personalized match is established."
                )
                + "</p>",
                f"<p>Current neutral Market: {text(price)}.</p>",
                "<details><summary>Comparison coverage and limits</summary>",
                "<p>Original price source label: " + text(card["source"]) + "</p>",
                f"<p>Exact comparison dates: {text(trend['comparison_start_at'])} → {text(trend['comparison_end_at'])}.</p><p>{text(trend.get('checkpoint_count', 'Unknown'))} retained checkpoints · {text(trend.get('comparison_scope', 'Unknown'))}. Sparse observations are not continuous daily history. {text(trend.get('current_qualification') or 'Current endpoint qualification unavailable.')}</p></details>",
                f'<div class="ds-actions"><a class="ds-action" href="{text(detail)}">Review asset evidence</a>',
            ]
        )
        if card["href"]:
            html.append(
                f'<a class="ds-action primary" href="{text(card["href"])}">Explore in Trade For</a>'
            )
        elif card["related"]:
            html.append(
                "<p>Current compatible quote evidence cannot bind this handoff. Review the asset; no target was applied.</p>"
            )
        html.append("</div></article>")
    html.append(
        '<p class="muted">Market movement and a position match are reasons to investigate, not an evaluated trade recommendation. Opening a link runs no search.</p><details><summary>How to use these observations</summary><p>A decline does not prove buy low, and a rise does not prove sell high. This is not a manager’s asking price; package cost, reserve effects and bilateral fit still need evaluation. A position match is not an evaluated trade recommendation. Opening these links runs no search or evaluation.</p></details></section>'
    )
    return "".join(html)
