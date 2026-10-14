"""Compact completed-trade cards; current Market is not a historical grade."""

from html import escape
from datetime import datetime
from src.ui import player_summary
from urllib.parse import quote, urlencode


def _safe(value):
    return escape(str(value))


def _evaluation(side):
    received, sent = side["received"], side["sent"]
    positions = sorted(
        {
            a["position"]
            for a in received
            if a["kind"] == "player" and a.get("position") not in {None, "—"}
        }
    )
    picks = [a for a in received if a["kind"] == "pick"]
    facts = []
    if positions:
        facts.append(
            "Adds player options at "
            + ", ".join(positions)
            + "; this alone does not establish improved starter quality or reliable depth."
        )
    if picks:
        facts.append(
            "Adds "
            + ", ".join(a["label"] for a in picks)
            + ". Future capital is not a guaranteed draft slot or production."
        )
    if sent:
        facts.append("Cost: gives up " + ", ".join(a["label"] for a in sent) + ".")
    return (
        "<p><b>"
        + _safe(side["name"])
        + "</b>: "
        + _safe(" ".join(facts) or "Supported strategic interpretation unavailable.")
        + "</p>"
    )


def render_news(model, *, viewer=None):
    cards = []
    for card in model["cards"]:
        sides = []
        for side in card["sides"]:
            assets = []
            for asset in side["received"]:
                kind = asset["kind"]
                if kind == "player":
                    url = "/players/" + quote(asset["player_id"], safe="")
                elif kind == "pick":
                    url = "/picks/" + quote(asset["canonical_pick_id"], safe="")
                else:
                    url = None
                if url:
                    url += "?" + urlencode({"from_trade": card["id"]})
                name = (
                    '<a href="'
                    + escape(url, quote=True)
                    + '">'
                    + _safe(asset["label"])
                    + "</a>"
                    if url
                    else _safe(asset["label"])
                )
                if kind == "player":
                    identity = player_summary(
                        player_id=asset["player_id"],
                        name=asset["label"],
                        position=asset.get("position"),
                        nfl_team=asset.get("nfl_team")
                        if asset.get("nfl_team") != "FA"
                        else None,
                        context=(str(asset["value"]) + " Market")
                        if asset["value"] is not None
                        else "Market unavailable",
                    )
                    name = (
                        '<a class="news-player" href="'
                        + escape(url, quote=True)
                        + '">'
                        + identity
                        + "</a>"
                    )
                value = (
                    "FAAB · not Market priced"
                    if kind == "faab"
                    else (
                        str(asset["value"]) + " Market"
                        if asset["value"] is not None
                        else "Market unavailable"
                    )
                )
                assets.append(
                    "<li><span>"
                    + name
                    + "</span>"
                    + (
                        "<small>" + _safe(value) + "</small>"
                        if kind != "player"
                        else ""
                    )
                    + "</li>"
                )
            total = (
                _safe(side["total"])
                if side["total"] is not None
                else _safe(side["known_total"]) + " known · incomplete"
                if side["known_count"]
                else "Unavailable"
            )
            you = " · You" if str(viewer) == side["roster_id"] else ""
            sides.append(
                '<section class="news-side"><h3>'
                + _safe(side["name"] + you)
                + '</h3><p class="news-received">Received</p><ul>'
                + ("".join(assets) or "<li>No received assets established.</li>")
                + '</ul><p class="news-total">'
                + total
                + " <small>player/pick Market points</small></p></section>"
            )
        comparison = ""
        if len(card["sides"]) == 2 and card["complete"]:
            a, b = card["sides"]
            gap = abs(a["total"] - b["total"])
            favored = a if a["total"] > b["total"] else b
            label = (
                f"{favored['name']} received {gap} more current Market points."
                if gap
                else "Equal current Market totals."
            )
            total = a["total"] + b["total"]
            left = a["total"] / total * 100 if total else 50
            ca, cb = (
                ("news-green", "news-red")
                if a["total"] > b["total"]
                else ("news-red", "news-green")
                if gap
                else ("news-neutral", "news-neutral")
            )
            comparison = (
                '<p class="news-advantage">'
                + _safe(label)
                + '</p><div class="news-bar" role="img" aria-label="'
                + escape(label, quote=True)
                + '"><span class="'
                + ca
                + '" style="width:'
                + f"{left:.3f}"
                + '%"></span><span class="'
                + cb
                + '" style="width:'
                + f"{100 - left:.3f}"
                + '%"></span></div>'
            )
        elif len(card["sides"]) > 2:
            comparison = '<p class="muted">Multi-franchise trade · no two-sided advantage assigned.</p>'
        else:
            comparison = '<p class="muted">Incomplete or incompatible prices · Market advantage unavailable.</p>'
        if card["has_faab"]:
            comparison += '<p class="muted">FAAB is separate consideration; these player/pick totals do not price the entire exchange.</p>'
        partial = (
            '<p class="muted">Some original consideration has unresolved direction or identity. Open source details; no complete comparison is claimed.</p>'
            if card["consideration_partial"]
            else ""
        )
        date = datetime.fromisoformat(card["completed_at"]).strftime(
            "%b %d · %H:%M UTC"
        )
        trade_url = "/trades/history/" + quote(card["id"], safe="") + "?from_home=1"
        cards.append(
            '<article class="news-card" data-news-trade="'
            + escape(card["id"], quote=True)
            + '"><header><time datetime="'
            + escape(card["completed_at"], quote=True)
            + '">'
            + _safe(date + " · status update")
            + '</time><small class="news-completed">Completed</small></header><div class="news-sides">'
            + "".join(sides)
            + '</div><p class="news-market-label">CURRENT DISPLAYED MARKET</p><p class="muted">Current values, not trade-date grades.</p>'
            + comparison
            + partial
            + '<details class="news-evaluation"><summary>Evaluation · supported gains and costs</summary><p>Exchange facts using current player identities. Decision-time strategy and full current-roster fit are unavailable here; no historical motives or overall winner are inferred.</p>'
            + "".join(_evaluation(s) for s in card["sides"])
            + '<p>Market advantage, strategic fit, production while held and later outcomes are separate. Open the original trade for admitted historical evidence; retained FOIS grades remain NOT REVALIDATED.</p></details><a class="ds-action" href="'
            + escape(trade_url, quote=True)
            + '">Open original completed trade →</a><details class="news-evidence"><summary>Source and pricing details</summary><p>'
            + _safe(card["source"])
            + "</p><p>"
            + _safe(model.get("league_name", "Selected league"))
            + "</p><p>"
            + _safe(card["clock_provenance"])
            + "</p><p>"
            + _safe(card["pricing_state"])
            + "</p><p>Shared current snapshot: <code>"
            + _safe(card["snapshot"])
            + "</code></p><p>Transaction: <code>"
            + _safe(card["id"])
            + "</code> · Season "
            + _safe(card["season"])
            + " · League <code>"
            + _safe(card["league_id"])
            + "</code></p></details></article>"
        )
    if not cards:
        cards = [
            '<p class="muted news-quiet">No completed league trades in the past seven days with supported completion-time evidence.</p>'
        ]
    limits = "".join("<p>" + _safe(s) + "</p>" for s in model["limitations"])
    return (
        '<section class="ux-section league-trade-news" aria-labelledby="trade-news-title"><div class="ux-section-head"><h2 id="trade-news-title">League Trade News</h2><p>Last 7 days · Biggest deals first</p></div>'
        + "".join(cards[:2])
        + (
            '<details class="news-more"><summary>More completed trades · '
            + str(len(cards) - 2)
            + "</summary>"
            + "".join(cards[2:])
            + "</details>"
            if len(cards) > 2
            else ""
        )
        + '<details class="news-evidence"><summary>Feed coverage and ordering</summary><p>'
        + _safe(model["ranking_policy"])
        + "</p><p>"
        + str(model["eligible_count"])
        + " time-qualified trades in prepared evidence · up to 6 cards, first 2 open to view; additional cards under More completed trades. No full historical archive is fetched on this page.</p><p>Time eligibility uses completed transactions’ supported status-update clocks, not creation time. Trades expire individually after 168 hours. Missing periods do not mean zero trades.</p>"
        + limits
        + "</details></section>"
    )


NEWS_CSS = """
@media(max-width:700px){.home-secondary-rail{display:none}.ux-feature:has(+.home-secondary-rail){padding:16px}.ux-feature:has(+.home-secondary-rail) h2{font-size:24px}}

.news-player{display:block}.news-player .player-summary{align-items:center;gap:8px}.news-player .player-portrait,.news-player .player-headshot,.news-player .player-headshot-fallback{width:40px;height:40px;flex-basis:40px}.news-player .player-summary-copy{min-width:0}.news-player .player-summary-copy b{font-size:14px;white-space:normal}.news-side li:has(.news-player){border:1px solid var(--line);border-radius:9px;padding:7px}.news-side li:has(.news-player)>small{padding-left:48px}.news-completed{color:var(--accent);border:1px solid var(--line);padding:3px 7px;border-radius:8px}.league-trade-news>.ux-section-head h2{color:var(--accent);font-size:17px;letter-spacing:.06em;text-transform:uppercase}

.league-trade-news{min-width:0}.news-card{background:var(--surface-elevated);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0;min-width:0;overflow-wrap:anywhere}.news-card header{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;color:var(--muted);font-size:12px}.news-sides{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:10px}.news-side{min-width:0}.news-side h3{font-size:15px;line-height:1.35;margin:0}.news-received{color:var(--accent);margin:4px 0;font-size:12px;font-weight:700}.news-side ul{list-style:none;margin:0;padding:0}.news-side li{margin:6px 0;line-height:1.35}.news-side li small{display:block;color:var(--muted);font-size:12px}.news-total{font-weight:800;margin:8px 0}.news-total small{font-weight:400;color:var(--muted);font-size:12px}.news-market-label{font-size:11px;font-weight:800;letter-spacing:.05em;margin-bottom:4px}.news-card p.muted{font-size:12px;margin:4px 0}.news-advantage{font-size:13px;line-height:1.4}.news-bar{display:flex;height:9px;border-radius:6px;overflow:hidden;margin:8px 0}.news-green{background:#6ee7b7}.news-red{background:#f87171}.news-neutral{background:#64748b}.news-evaluation,.news-evidence{font-size:13px;line-height:1.5;margin:8px 0;min-width:0}.news-evaluation summary,.news-evidence summary,.news-more>summary{cursor:pointer;min-height:44px;display:list-item;align-content:center}.news-evidence code{overflow-wrap:anywhere}.news-card .ds-action{min-height:44px;display:inline-flex;align-items:center}.news-quiet{margin:8px 0} @media(min-width:320px){.news-sides{grid-template-columns:repeat(2,minmax(0,1fr))}} @media(min-width:700px){.news-sides{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}}
"""
