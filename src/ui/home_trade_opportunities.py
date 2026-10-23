"""Compact hypothetical offers, separate from completed League Trade News."""

from html import escape
from urllib.parse import urlencode


def section(roster_id):
    return f'''<section class="ux-section" id="home-opportunities" data-front-office="{roster_id}" data-presentation="loading" aria-labelledby="home-brief-title"><div class="ux-section-head"><h2 id="home-brief-title">Front Office Brief</h2></div><div id="home-opportunity-cards"></div><p class="home-brief-status" id="home-opportunity-status" role="status">Reading prepared evidence. No search runs automatically on Home.</p><div class="ux-feature-actions home-brief-actions"><button type="button" class="ds-action" id="home-find-ideas">Find Trade Ideas</button><button type="button" class="btn" id="home-reload-opportunities" hidden>Reload Home</button><a class="ds-action" href="/trades/recommended?front_office={roster_id}">Explore more trades →</a></div></section><script src="/static/js/strategy_session.js"></script><script src="/static/js/home-opportunities.js"></script>'''


def _brief(text):
    text = str(text)
    return text if len(text) <= 240 else text[:237].rstrip() + "…"


def cards(rows, roster_id):
    output = []
    for row in rows:
        p = row.get("proposal_presentation") or {}
        e = row.get("evaluation") or {}

        def assets(side):
            return " + ".join(
                escape(str(a.get("label") or "Exact asset")) for a in p.get(side) or []
            )

        v = e.get("values") or {}
        market = "Market comparison unavailable"
        if (
            v.get("sent") is not None
            and v.get("received") is not None
            and (e.get("market_evidence") or {}).get("availability") == "full"
        ):
            market = f"Current Market: send {v['sent']} / receive {v['received']}"
        kind = (
            "TRADE IDEA · exploratory, not endorsed"
            if row.get("exploration")
            else "RECOMMENDED TRADE"
        )
        reason = e.get("why_you_would_do_it") or "No supported positive strategic case is available; explore only to review or edit the package."
        if e.get("recommendation") in {"REJECT", "NOT WORTH IT"}:
            reason = "Not endorsed. " + reason
        drawback = (
            e.get("major_drawback")
            or "; ".join(e.get("major_risks") or e.get("major_limitations") or [])
            or "No material drawback identified in available evidence; acceptance is not guaranteed."
        )
        url = "/trades/create?" + urlencode(
            {"front_office": roster_id, "home_offer": row["home_offer"]}
        )
        partner = ('<p><b>Why this partner:</b> ' + escape(_brief(e["why_this_partner"])) + '</p>') if e.get("why_this_partner") else ""
        output.append(
            f'''<article class="home-opportunity"><p class="identity-kicker">{escape(kind)}</p><h3>{escape(str(p.get("partner_team_name") or "Counterparty"))}</h3><p><b>You send:</b> {assets("send")}</p><p><b>You receive:</b> {assets("receive")}</p><p>{escape(market)}</p><p><b>{escape(str(e.get("recommendation") or "Assessment unavailable"))}</b></p><p><b>Why consider:</b> {escape(_brief(reason))}</p><p><b>Drawback:</b> {escape(_brief(drawback))}</p>{partner}<details><summary>Assessment evidence</summary><p>{escape(str(e.get("dominant_reason") or "Methodology details unavailable."))}</p></details><a class="ds-action" href="{escape(url, quote=True)}">Explore / Edit · preview →</a></article>'''
        )
    return "".join(output[:2]) + (
        '<details class="ds-home-detail"><summary>Show more opportunities</summary>'
        + "".join(output[2:])
        + "</details>"
        if len(output) > 2
        else ""
    )


CSS = """.home-opportunity{background:var(--surface,#202628);border:1px solid #35413b;border-radius:12px;padding:14px;margin:10px 0;overflow-wrap:anywhere}.home-opportunity p{margin:6px 0}.home-opportunity h3{margin:6px 0}.home-opportunity .ds-action{min-height:44px;display:inline-flex;align-items:center}#home-opportunities button{min-height:44px}
.home-command{padding:12px 16px}.home-command .identity-kicker{margin:0}.home-command h2{font-size:26px;margin:4px 0;overflow-wrap:anywhere}.home-record{display:flex;align-items:center;flex-wrap:wrap;gap:6px 10px}.home-command .ux-feature-actions{margin-top:8px;gap:8px}.home-command .ux-feature-actions>a{flex:1;padding:8px 12px}
#home-opportunities{margin-top:16px;display:flex;flex-direction:column}#home-opportunities>.ux-section-head{order:0}#home-opportunity-status{order:1}#home-opportunity-cards{order:2}#home-opportunities>.home-brief-actions{order:3}#home-opportunities[data-presentation="prepared"] #home-opportunity-cards{order:1}#home-opportunities[data-presentation="prepared"] #home-opportunity-status{order:2}#home-opportunities .ux-section-head{margin-bottom:8px}#home-opportunities .ux-section-head h2{margin:0}#home-opportunities .home-brief-actions{margin-top:8px;gap:8px}#home-opportunity-status{margin:8px 0;color:var(--text-secondary)}.home-secondary-controls .ds-home-detail{margin:8px 0}.home-secondary-controls .ds-action{margin:4px 0}
"""
