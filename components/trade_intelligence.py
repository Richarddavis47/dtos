"""Server-rendered Trade Intelligence components."""
from __future__ import annotations

from html import escape

from src.core.trade_intelligence import TradeDossier

TRADE_CSS = """
<style>
.ti-hero{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.ti-hero h2{margin:3px 0}.ti-selector select{background:#0b1727;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px}.ti-list{display:grid;gap:13px;margin-top:15px}.ti-card{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:15px;padding:15px}.ti-head{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:start}.ti-priority{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--gold)}.ti-score{font-size:24px;font-weight:950;color:var(--accent);text-align:right}.ti-score small{display:block;font-size:9px;color:var(--muted)}.ti-assets{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;margin:12px 0}.ti-package{background:#101d2d;border:1px solid var(--line);border-radius:11px;padding:11px}.ti-package span{display:block;color:var(--muted);font-size:9px;text-transform:uppercase}.ti-package b{display:block;margin-top:5px}.ti-arrow{color:var(--accent);font-weight:950}.ti-metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.ti-metric{background:#07111f;border:1px solid var(--line);border-radius:9px;padding:8px}.ti-metric b{display:block}.ti-metric span{font-size:9px;color:var(--muted)}.ti-details summary{cursor:pointer;color:var(--accent);font-weight:850;margin-top:11px}.ti-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:9px}.ti-section{background:#101d2d;border:1px solid var(--line);border-radius:10px;padding:10px}.ti-section h4{margin:0 0 6px}.ti-section ul{padding-left:18px}.ti-empty{padding:34px;text-align:center;color:var(--muted)}
@media(max-width:760px){.ti-head{grid-template-columns:1fr}.ti-assets{grid-template-columns:1fr}.ti-arrow{text-align:center;transform:rotate(90deg)}.ti-metrics{grid-template-columns:repeat(2,1fr)}.ti-grid{grid-template-columns:1fr}}
</style>
"""


def _assets(assets) -> str:
    return " + ".join(escape(asset.label) for asset in assets)


def _evidence(dossier: TradeDossier) -> str:
    return "".join(
        f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)} <small>Source: {escape(item.source)}</small></li>"
        for item in dossier.recommendation.evidence
    )


def trade_card(dossier: TradeDossier) -> str:
    rec, impact, plan = dossier.recommendation, dossier.impact, dossier.negotiation
    strengths = "".join(f"<li>{escape(item)}</li>" for item in dossier.strengths)
    weaknesses = "".join(f"<li>{escape(item)}</li>" for item in dossier.weaknesses)
    risks = "".join(f"<li>{escape(item)}</li>" for item in dossier.risks)
    alternatives = ", ".join(plan.alternative_targets) or "No equivalent cached target"
    return f"""
<article class="ti-card"><div class="ti-head"><div><div class="ti-priority">{escape(rec.priority.value)} · {escape(rec.trade_type.value)} · {escape(dossier.proposal.package_type)}</div><h3>{escape(rec.title)}</h3><p class="muted">{escape(dossier.executive_summary)}</p></div><div class="pill">{dossier.partner.compatibility_score}% compatibility<br>{escape(dossier.partner.difficulty)}</div><div class="ti-score">{rec.expected_value:+d}<small>Expected Value</small></div></div>
<div class="ti-assets"><div class="ti-package"><span>Send</span><b>{_assets(dossier.proposal.assets_sent)}</b></div><div class="ti-arrow">→</div><div class="ti-package"><span>Receive</span><b>{_assets(dossier.proposal.assets_received)}</b></div></div>
<div class="ti-metrics"><div class="ti-metric"><b>{impact.current_outlook:+d}</b><span>Current Outlook</span></div><div class="ti-metric"><b>{impact.future_outlook:+d}</b><span>Future Outlook</span></div><div class="ti-metric"><b>{impact.positional_depth:+d}</b><span>Depth</span></div><div class="ti-metric"><b>{impact.asset_value:+d}</b><span>Asset Value</span></div><div class="ti-metric"><b>{rec.confidence}%</b><span>Confidence</span></div></div>
<details class="ti-details"><summary>Open Trade Dossier</summary><div class="ti-grid"><section class="ti-section"><h4>Why Both Sides Improve</h4><p><b>Active:</b> {escape(dossier.why_active_improves)}</p><p><b>Partner:</b> {escape(dossier.why_partner_improves)}</p><p>{escape(dossier.why_realistic)}</p><p>{escape(dossier.why_now)}</p></section><section class="ti-section"><h4>Strengths</h4><ul>{strengths}</ul><h4>Weaknesses</h4><ul>{weaknesses}</ul></section><section class="ti-section"><h4>Risk</h4><ul>{risks}</ul><p>Acceptance likelihood: <b>{rec.acceptance_likelihood if rec.acceptance_likelihood is not None else 'Unavailable'}</b></p></section><section class="ti-section"><h4>Negotiation Plan</h4><p><b>Opening:</b> {escape(plan.opening_offer)}</p><p><b>Minimum offer:</b> {escape(plan.minimum_offer)}</p><p><b>Maximum offer:</b> {escape(plan.maximum_offer)}</p><p><b>Likely counter:</b> {escape(plan.likely_counter)}</p><p><b>Walk-away:</b> {escape(plan.walk_away_point)}</p><p><b>Fallback:</b> {escape(plan.fallback_offer)}</p><p><b>Alternatives:</b> {escape(alternatives)}</p></section><section class="ti-section"><h4>Supporting Evidence</h4><ul>{_evidence(dossier)}</ul></section></div></details></article>
"""


def trade_center(view: dict) -> str:
    active = view["active_team"]
    unified = view["unified_recommendation"]
    options = "".join(
        f'<option value="{int(team.get("roster_id") or 0)}" {"selected" if int(team.get("roster_id") or 0) == int(active.get("roster_id") or 0) else ""}>{escape(str(team.get("owner") or team.get("team_name")))}</option>'
        for team in view["teams"]
    )
    cards = "".join(trade_card(item) for item in view["dossiers"]) or '<div class="card ti-empty">No balanced cached opportunity crossed the v1 generation boundary. Monitor roster and market changes.</div>'
    return f"""{TRADE_CSS}<section class="card ti-hero"><div><div class="identity-kicker">Trade Intelligence v1 / Unified Intelligence Platform</div><h2>{escape(unified.title)}</h2><p>{escape(unified.recommendation)}</p><span class="pill">{unified.confidence.score}% {escape(unified.confidence.level)} confidence</span></div><form class="ti-selector" method="get"><label for="front_office">Active Front Office</label><select id="front_office" name="front_office" onchange="this.form.submit()">{options}</select></form></section><div class="ti-list">{cards}</div>"""
