"""Compact hypothetical offers, separate from completed League Trade News."""

from html import escape
from urllib.parse import urlencode


def section(roster_id):
    return f'''<section class="ux-section" id="home-opportunities" data-front-office="{roster_id}"><div class="ux-section-head"><h2>Trade Opportunities</h2><p>Hypothetical offers · explore before adopting</p></div><p id="home-opportunity-status" role="status">No search runs automatically on Home.</p><div id="home-opportunity-cards"></div><div class="ux-feature-actions"><button type="button" class="btn" id="home-find-ideas">Find Trade Ideas</button><button type="button" class="btn" id="home-reload-opportunities" hidden>Reload Home</button><a class="ds-action" href="/trades/recommended?front_office={roster_id}">Explore more trades →</a></div></section><script src="/static/js/strategy_session.js"></script><script src="/static/js/home-opportunities.js"></script>'''


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


CSS = """.home-opportunity{background:var(--surface,#202628);border:1px solid #35413b;border-radius:12px;padding:14px;margin:10px 0;overflow-wrap:anywhere}.home-opportunity p{margin:6px 0}.home-opportunity h3{margin:6px 0}.home-opportunity .ds-action{min-height:44px;display:inline-flex;align-items:center}#home-opportunities button{min-height:44px}"""
