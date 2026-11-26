"""Compact hypothetical offers, separate from completed League Trade News."""

from html import escape
from urllib.parse import urlencode

from src.ui.customer_experience import plain_reason


def section(roster_id):
    return f'''<section class="ux-section" id="home-opportunities" data-front-office="{roster_id}" data-presentation="loading" aria-labelledby="home-brief-title"><div class="ux-section-head"><h2 id="home-brief-title">Front Office Brief</h2></div><div id="home-opportunity-cards"></div><p class="home-brief-status" id="home-opportunity-status" role="status">Loading your team brief. No search runs automatically on Home.</p><div class="ux-feature-actions home-brief-actions"><button type="button" class="ds-action" id="home-find-ideas">Find Trade Ideas</button><button type="button" class="btn" id="home-reload-opportunities" hidden>Reload Home</button><a class="ds-action" href="/trades/recommended?front_office={roster_id}">Explore more trades →</a></div></section><script src="/static/js/strategy_session.js"></script><script src="/static/js/home-opportunities.js"></script>'''


def brief_text(text):
    text = plain_reason(str(text))
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
        partner = ('<p><b>Partner fit (inferred):</b> ' + escape(brief_text(e["why_this_partner"])) + '</p>') if e.get("why_this_partner") else ""
        recorded_cost = ('<p><b>Original cost explanation:</b> ' + escape(str(drawback)) + '</p>') if str(drawback) != str(e.get("dominant_reason") or "") else ""
        output.append(
            f'''<article class="home-opportunity"><p class="identity-kicker">{escape(kind)}</p><h3>{escape(str(p.get("partner_team_name") or "Counterparty"))}</h3><p><b>You send:</b> {assets("send")}</p><p><b>You receive:</b> {assets("receive")}</p><p>{escape(market)}</p><p><b>{escape(str(e.get("recommendation") or "Assessment unavailable"))}</b></p><p><b>Why consider:</b> {escape(brief_text(reason))}</p><p><b>Cost and uncertainty:</b> {escape(brief_text(drawback))}</p>{partner}<details><summary>Assessment evidence</summary><p>{escape(str(e.get("dominant_reason") or "Methodology details unavailable."))}</p>{recorded_cost}</details><a class="ds-action" href="{escape(url, quote=True)}">Explore / Edit · preview →</a></article>'''
        )
    return "".join(output[:2]) + (
        '<details class="ds-home-detail"><summary>Show more opportunities</summary>'
        + "".join(output[2:])
        + "</details>"
        if len(output) > 2
        else ""
    )


CSS = """.home-opportunity{background:var(--surface,#202628);border:1px solid #35413b;border-radius:12px;padding:14px;margin:10px 0;overflow-wrap:anywhere}.home-opportunity p{margin:6px 0}.home-opportunity h3{margin:6px 0}.home-opportunity .ds-action{min-height:44px;display:inline-flex;align-items:center}#home-opportunities button{min-height:44px}
.home-command{padding:0;border:0;background:transparent;border-radius:0}.home-command .identity-kicker{margin:0}.home-command h2{font-size:26px;margin:4px 0;overflow-wrap:anywhere}.home-record{display:flex;align-items:center;flex-wrap:wrap;gap:6px 10px}.home-command .ux-feature-actions{margin-top:8px;gap:8px}.home-command .ux-feature-actions>a{flex:1;padding:8px 12px}
#home-opportunities{margin-top:12px;display:flex;flex-direction:column}#home-opportunities>.ux-section-head{order:0}#home-opportunity-status{order:1}#home-opportunity-cards{order:2}#home-opportunities>.home-brief-actions{order:3}#home-opportunities[data-presentation="prepared"] #home-opportunity-cards{order:1}#home-opportunities[data-presentation="prepared"] #home-opportunity-status{order:2}#home-opportunities .ux-section-head{margin-bottom:8px}#home-opportunities .ux-section-head h2{margin:0}#home-opportunities .home-brief-actions{margin-top:8px;gap:8px}#home-opportunity-status{margin:8px 0;color:var(--text-secondary)}.home-secondary-controls .ds-home-detail{margin:8px 0}.home-secondary-controls .ds-action{margin:4px 0}
"""

CSS += """
.home-team,.home-first,.home-week{margin:0 0 14px;min-width:0}
.home-team h1{font-size:clamp(26px,5vw,36px);margin:0;line-height:1.15;overflow-wrap:anywhere}
.home-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:10px 0 0;padding:6px 0;text-align:center;background:var(--surface-elevated);border:1px solid var(--line);border-radius:10px}
.home-stats>div{display:flex;flex-direction:column;justify-content:center;min-width:0;padding:2px 7px}
.home-stats>div+div{border-inline-start:1px solid var(--line)}
.home-stats dt{color:var(--text-secondary);font-size:12px;line-height:1.35}
.home-stats dd{order:-1;font-weight:800;font-size:clamp(13px,4vw,19px);margin:0;overflow-wrap:anywhere}
.home-stats-context,.home-stats-unavailable{margin:6px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.35}
.home-stats-unavailable{padding:8px 10px;background:var(--surface-elevated);border:1px solid var(--line);border-radius:10px}
.home-first{border:2px solid var(--accent);border-radius:12px;padding:12px;background:linear-gradient(150deg,#252f24,var(--surface-elevated) 70%);box-shadow:0 0 11px #80df4233}
.home-first h2{font-size:15px;color:var(--accent);margin:0 0 5px}
.home-first h3{font-size:clamp(19px,4.9vw,26px);line-height:1.2;margin:0;overflow-wrap:anywhere}
.home-first p{font-size:14px;margin:7px 0 10px;max-width:58ch;line-height:1.45;overflow-wrap:anywhere}
.home-first .ux-primary-action{min-height:44px;display:flex;justify-content:center;align-items:center;text-align:center;scroll-margin-block:8px 12px}
.home-week h2{font-size:20px;margin:0 0 8px}
.home-shortcuts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-bottom:14px}
.home-week-links{background:var(--surface-elevated);border:1px solid var(--line);border-radius:10px;padding:0 10px}
.home-shortcuts a,.home-week-links a{color:var(--text);font-weight:650;display:flex;align-items:center;justify-content:space-between;gap:5px;text-decoration:none;min-height:44px;min-width:0;overflow-wrap:anywhere}
.home-shortcuts a{padding:6px 10px;background:var(--surface-elevated);border:1px solid var(--line);border-radius:10px}
.home-week-links a+a{border-top:1px solid var(--line)}
.home-shortcuts a:hover{border-color:var(--accent)}.home-shortcuts a span,.home-week-links a span{color:var(--accent);font-size:20px;line-height:1}
.home-week .ds-home-detail{margin:4px 0 0}
@media(min-width:761px){
.home-week{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);align-items:start;gap:0 16px}
.home-week h2{grid-column:1/-1}.home-week-links{display:grid;grid-template-columns:1fr 1fr;gap:0 12px}
.home-week-links a+a{border-top:0;border-left:1px solid var(--line);padding-left:12px}
}
@media(min-width:700px){.home-stats{max-width:590px}.home-shortcuts{max-width:590px}.home-first .ux-primary-action{width:min(100%,330px)}}
@media(max-width:359px) and (max-height:500px){
 .home-team,.home-first{margin-bottom:10px}
 .home-stats{margin-top:7px;padding-block:4px}
 .home-first{padding:9px}
 .home-first p{margin:5px 0 8px}
}
"""
