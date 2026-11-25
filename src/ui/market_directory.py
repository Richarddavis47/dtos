"""Compact presentation of already prepared Market results."""

from datetime import datetime, timezone
from html import escape

from src.core.market_trends.models import has_comparable_movement
from src.ui.customer_experience import readable_time
from src.ui.market_roster_relevance import relevance_reason


POSITIONS = (("", "All"), ("QB", "QB"), ("RB", "RB"), ("WR", "WR"), ("TE", "TE"), ("PICK", "Picks"))


def mode_links(neutral_url, personal_url):
    return (
        '<link rel="stylesheet" href="/static/css/market_directory.css">'
        '<nav class="market-mode market-mode-switch" aria-label="Valuation views">'
        f'<a class="ds-action" href="{escape(neutral_url)}" aria-current="page">Neutral Market</a>'
        f'<a class="ds-action" href="{escape(personal_url)}">My DTOS</a></nav>'
    )


def _window(trend):
    if trend.get("comparison_start_at") and trend.get("comparison_end_at"):
        try:
            start, end = (datetime.fromisoformat(trend[key].replace("Z", "+00:00"))
                          for key in ("comparison_start_at", "comparison_end_at"))
            start, end = (stamp.astimezone(timezone.utc) if stamp.tzinfo else stamp for stamp in (start, end))
            return f"{start:%b} {start.day}–{end:%b} {end.day}"
        except (ValueError, TypeError, AttributeError):
            pass
    return "Dates in details"


def result_row(*, asset_id, name, metadata, price, has_price, rank, query, selected, trend,
               projection_html="", evidence_link=""):
    active = selected == asset_id
    if has_comparable_movement(trend, asset_id):
        amount = trend["magnitude"]
        change = f"{amount:+,.2f}".rstrip("0").rstrip(".") if amount else "0"
        movement = f'<b class="market-change-{("up" if amount > 0 else "down" if amount < 0 else "flat")}">{change}</b><small>{escape(_window(trend))}</small>'
    else:
        movement = '<small>No change data</small>'
    href = f'/market?{escape(query)}' + ("#market-open-row" if not active else "#market-results")
    focus = ' id="market-open-row"' if active else ''
    active_evidence = (
        f'<div class="market-row-detail" id="market-row-detail">'
        f'<!--market-active-relevance-->{projection_html}{evidence_link}</div>' if active else ''
    )
    return (
        f'<article class="market-result" data-asset-id="{escape(asset_id)}"{focus}>'
        f'<a class="market-asset market-row" href="{href}" '
        f'aria-expanded="{str(active).lower()}"{" aria-controls=\"market-row-detail\"" if active else ""}>'
        f'<span class="market-row-name"><b>{escape(name)}</b><small>{escape(metadata)}</small>'
        f'<span class="market-rank market-visually-hidden">Result #{rank}</span></span>'
        f'<span class="market-row-price" data-availability="{str(has_price).lower()}">'
        f'<span class="market-visually-hidden">Value: </span>{escape(price)}</span>'
        f'<span class="market-row-change"><span class="market-visually-hidden">Observed change: </span>{movement}</span>'
        '<span class="market-row-chevron" aria-hidden="true"></span></a>'
        f'{active_evidence}</article>'
    )


def movement_dates(trend):
    if not has_comparable_movement(trend, trend.get("asset_id")):
        return ""
    return (
        escape(readable_time(trend["comparison_start_at"])) + " → "
        + escape(readable_time(trend["comparison_end_at"]))
    )


def row_evidence(view, ownership_reason=""):
    card = view["selected_card"]
    need = view["need"]
    if card and card["related"]:
        fit = (f"Matches your supported {need['position']} {need['kind']} need. "
               "A weekly lineup gain for this player has not been confirmed.")
    elif need:
        fit = "A supported fit for this asset has not been established."
    else:
        fit = relevance_reason(view["reason"])
    movement = '<p>No comparable dated Market prices are available for this asset.</p>'
    action = ""
    if card:
        trend = card["trend"]
        dates = movement_dates(trend)
        delta = trend["magnitude"]
        amount = f"{delta:+,.2f}" if delta else "0"
        qualification = escape(str(trend.get("current_qualification") or ""))
        movement = (
            f'<p><b>{amount} Market points</b> · {dates}.</p>'
            '<details class="market-row-sources"><summary>Movement sources and limits</summary>'
            f'<p>{escape(card["source"])} · {escape(card["age"])}. {qualification}</p>'
            f'<p>{escape(str(trend.get("checkpoint_count", "Unknown")))} saved checkpoints. '
            'They do not establish daily prices between the dates.</p></details>'
        )
        if card["href"]:
            action = (f'<a class="ds-action primary market-trade-action" href="{escape(card["href"])}">'
                      f'Trade For {escape(card["name"])}</a>'
                      '<small>Review the editable target before you run a search.</small>')
        elif card["related"]:
            movement += '<p>Current price evidence cannot verify a Trade For handoff.</p>'
    ownership = f'<p>{escape(ownership_reason)}</p>' if ownership_reason else ""
    return (
        '<h3>Roster fit and Market movement</h3>'
        f'<p>{escape(fit)}</p>{ownership}{movement}{action}'
    )
