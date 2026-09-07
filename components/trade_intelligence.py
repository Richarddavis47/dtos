"""Server-rendered Trade Intelligence components."""
from __future__ import annotations

from html import escape
import json
from urllib.parse import quote
from typing import TYPE_CHECKING

from src.ui import recommendation_panel
from components.trade_workspace import trade_workspace

# Preserve the public renderer entry point used by the modular trade router.
trade_workflow = trade_workspace

if TYPE_CHECKING:
    from src.core.trade_intelligence import TradeDossier

TRADE_CSS = """
<style>
.ti-hero{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding:18px;margin-bottom:12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg)}
.ti-hero h2{font-size:26px;margin:4px 0}.ti-hero p{font-size:14px;color:var(--text-secondary);max-width:620px;margin:8px 0}
.ti-selector label{display:grid;gap:6px;font-size:12px;color:var(--muted)}
#trade-builder>label{display:grid;gap:6px;font-size:13px;color:var(--text-secondary);margin-bottom:14px}#trade-builder>label select{width:100%}
.ti-workflows{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;padding:4px;margin:12px 0 20px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md)}
.ti-workflow{display:block;padding:12px;text-align:center;border-radius:var(--radius-sm)}
.ti-workflow:hover{background:var(--surface-interactive)}
.ti-workflow b{display:block;color:var(--accent);font-size:14px}
.ti-workflow span{font-size:12px;color:var(--muted)}
.ti-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.ti-action{display:inline-flex;justify-content:center;align-items:center;min-height:44px;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);color:var(--text);font-weight:650;cursor:pointer}
.ti-actions .ti-action:first-child,#trade-run{background:var(--accent);color:#0c1908;border-color:var(--accent)}
.ti-list{display:grid;gap:16px;margin-top:20px}
@media(min-width:1100px){.ti-list{grid-template-columns:repeat(2,minmax(0,1fr));align-items:start}.ti-list>.ti-empty{grid-column:1/-1}}
.ti-card{border:1px solid #365334;border-radius:var(--radius-lg);background:var(--surface);overflow:hidden}
.ti-head{padding:16px 18px 8px}
.ti-head h3{font-size:19px;margin:10px 0 0}
.ti-opportunity-label{display:flex;justify-content:space-between;gap:12px;align-items:center}
.ti-priority{display:inline-flex;padding:4px 8px;background:rgba(128,223,66,.09);color:var(--positive);border-radius:6px;font-size:11px;font-weight:700}
.ti-confidence{font-size:12px;color:var(--text-secondary);text-align:right}
.ti-score{font-size:24px;color:var(--blue)}.ti-score small{font-size:12px;color:var(--muted);display:block}
.ti-franchises{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding:12px 18px}
.ti-franchise:last-child{text-align:right}.ti-franchise b,.ti-franchise span{display:block}.ti-franchise span{font-size:12px;color:var(--muted)}
.ti-arrow{display:grid;place-items:center;color:var(--accent);font-size:22px}
.ti-assets{display:grid;grid-template-columns:minmax(0,1fr) 20px minmax(0,1fr);gap:8px;margin:0;padding:0 18px}
.ti-package{min-width:0;padding:10px;background:var(--background);border:1px solid var(--border);border-radius:var(--radius-md)}
.ti-package>span:first-child{display:block;color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.ti-proposal-asset{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:8px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.ti-proposal-asset:last-child{border:0}
.ti-proposal-asset img,.ti-proposal-asset .ti-pick-icon{width:44px;height:44px;border-radius:8px;object-fit:cover;background:var(--surface-interactive)}
.ti-pick-icon{display:grid;place-items:center;font-size:10px;color:var(--gold)}
.ti-proposal-asset b{font-size:14px}.ti-proposal-asset small{display:block;font-size:11px;color:var(--muted)}
.ti-proposal-asset strong{font-size:17px;color:var(--blue);font-variant-numeric:tabular-nums}
a.ti-proposal-asset:hover b{color:var(--accent)}
.ti-values{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:12px 18px;color:var(--muted);font-size:12px}
.ti-bilateral{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
.ti-reason{padding:14px 18px;color:var(--text-secondary);font-size:13px;line-height:1.55}
.ti-reason+.ti-reason{border-left:1px solid var(--border)}
.ti-reason span{display:block;margin-bottom:6px;color:var(--text);font-weight:650}
.ti-details{padding:0 18px 16px}
.ti-details summary{cursor:pointer}
.ti-card-action{display:block;text-align:center;list-style:none;padding:12px;margin:14px 0 0;background:var(--accent);color:#0c1908;font-weight:700;border-radius:var(--radius-sm);min-height:44px}
.ti-card-action::-webkit-details-marker{display:none}
.ti-card-action:after{content:" +";margin-left:8px}
details[open]>.ti-card-action:after{content:" −"}
.ti-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.ti-metric,.ti-section{padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md)}
.ti-metric b{display:block}.ti-metric span{font-size:12px;color:var(--muted)}
.ti-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ti-section h4{margin:0 0 8px}
.ti-builder{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;margin-top:16px}
.ti-builder label{display:grid;gap:6px;font-size:13px;color:var(--muted)}
.ti-builder input,.ti-builder select{width:100%}
.ti-side{padding:16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);min-width:0}
.ti-side h4{margin:0 0 12px;font-size:16px}
.ti-picker{display:grid;gap:8px}
.ti-chips{display:flex;flex-wrap:wrap;gap:8px;min-height:44px;margin-top:10px}
.ti-chip{display:inline-flex;align-items:center;gap:8px;padding:4px 8px 4px 12px;background:var(--surface-elevated);border:1px solid var(--border);border-radius:var(--radius-sm)}
.ti-chip button{background:transparent;border:0;color:var(--muted);min-width:36px}
.ti-assist{display:grid;gap:8px;margin-top:12px}
.ti-assist[hidden],.ti-result[hidden]{display:none}
.ti-quick{display:flex;gap:8px;flex-wrap:wrap}.ti-quick button{padding:8px 12px}
.ti-result{margin-top:16px;padding:16px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--surface)}
.ti-result h4{margin:0 0 8px}.ti-result p{margin:8px 0}
.ti-empty{padding:28px;text-align:center;color:var(--muted);line-height:1.6}
.ti-empty h3{color:var(--text);font-size:22px}.ti-empty .ti-actions{justify-content:center}
@media(max-width:760px){
 .ti-hero{padding:16px}.ti-hero h2{font-size:24px}
 .ti-workflow{padding:12px 4px}.ti-workflow b{font-size:12px}.ti-workflow span{display:none}
 .ti-builder{grid-template-columns:1fr}.ti-grid{grid-template-columns:1fr}
 .ti-head{padding:14px 14px 8px}.ti-head h3{font-size:18px}
 .ti-franchises{padding:12px 14px}.ti-assets{padding:0 12px;gap:6px;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
 .ti-assets>.ti-arrow{display:none}.ti-package{padding:8px}
 .ti-proposal-asset{grid-template-columns:36px minmax(0,1fr);gap:6px}
 .ti-proposal-asset img,.ti-proposal-asset .ti-pick-icon{width:36px;height:40px}
 .ti-proposal-asset b{font-size:12px}.ti-proposal-asset small{font-size:11px}
 .ti-proposal-asset strong{grid-column:2;font-size:16px}
 .ti-reason{padding:12px;font-size:12px}.ti-details{padding:0 12px 12px}
 .ti-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
 .ti-values{padding:12px}.ti-confidence{font-size:11px}
}
</style>
"""
def _assets(assets) -> str:
    return " + ".join(escape(asset.label) for asset in assets)


def manager_context_selection(teams: list[dict], *, workflow: str | None = None) -> str:
    """Render an explicit franchise chooser instead of guessing manager identity."""
    destination = "/trades" if not workflow else f"/trades/{escape(workflow, quote=True)}"
    options = "".join(
        f'<option value="{int(team.get("roster_id") or 0)}">{escape(str(team.get("team_name") or team.get("owner") or "Unassigned Franchise"))}</option>'
        for team in teams
    )
    return f'''{TRADE_CSS}<section class="card ti-hero"><div><div class="identity-kicker">Trade Center · Manager Context</div><h2>Choose your franchise</h2><p>DTOS needs an explicit league-scoped manager before it can use ownership, roster fit, or bilateral trade intelligence.</p></div></section><section class="card"><form method="get" action="{destination}"><label for="front_office">Controlled franchise</label><select id="front_office" name="front_office" required><option value="" selected disabled>Choose a franchise</option>{options}</select><div class="ti-actions"><button class="ti-action" type="submit">Continue to Trade Center</button></div></form><p class="muted">No commissioner, first-roster, or named-manager fallback is applied.</p></section>'''


def _evidence(dossier: TradeDossier) -> str:
    return "".join(
        f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)} <small>Source: {escape(item.source)}</small></li>"
        for item in dossier.recommendation.evidence
    )


def trade_card(dossier: TradeDossier, value_impact: dict | None = None) -> str:
    rec, impact, plan = dossier.recommendation, dossier.impact, dossier.negotiation
    strengths = "".join(f"<li>{escape(item)}</li>" for item in dossier.strengths)
    weaknesses = "".join(f"<li>{escape(item)}</li>" for item in dossier.weaknesses)
    risks = "".join(f"<li>{escape(item)}</li>" for item in dossier.risks)
    alternatives = ", ".join(plan.alternative_targets) or "No equivalent cached target"
    market = dossier.market
    market_section = ""
    if market is not None:
        gain = f"{market.market_gain_loss:+d}" if market.market_gain_loss is not None else "Unavailable"
        market_section = f'<section class="ti-section"><h4>Market Intelligence</h4><p><b>Market gain/loss:</b> {gain}</p><p><b>Current consensus:</b> {escape(market.current_consensus)}</p><p><b>Expected movement:</b> {escape(market.expected_movement)}</p><p><b>Potential arbitrage:</b> {escape(market.potential_arbitrage)}</p></section>'
    integrated = ""
    if value_impact:
        integrated = f'<section class="ti-section"><h4>Player Value & Projection Impact</h4><p><b>DTOS Dynasty:</b> {value_impact["dtos_dynasty"]:+.1f}</p><p><b>Market Consensus:</b> {value_impact["market"]:+.1f}</p><p><b>Contender Value:</b> {value_impact["contender"]:+.1f}</p><p><b>Rebuilder Value:</b> {value_impact["rebuild"]:+.1f}</p><p><b>Projected Weekly:</b> {value_impact["weekly"]:+.2f} points</p></section>'
    return f"""
<article class="ti-card"><div class="ti-head"><div><div class="ti-priority">{escape(rec.priority.value)} · {escape(rec.trade_type.value)} · {escape(dossier.proposal.package_type)}</div><h3>{escape(rec.title)}</h3><p class="muted">{escape(dossier.executive_summary)}</p></div><div class="pill">{dossier.partner.compatibility_score}% compatibility<br>{escape(dossier.partner.difficulty)}</div><div class="ti-score">{rec.expected_value:+d}<small>Expected Value</small></div></div>
<div class="ti-assets"><div class="ti-package"><span>Send</span><b>{_assets(dossier.proposal.assets_sent)}</b></div><div class="ti-arrow">→</div><div class="ti-package"><span>Receive</span><b>{_assets(dossier.proposal.assets_received)}</b></div></div>
<div class="ti-metrics"><div class="ti-metric"><b>{impact.current_outlook:+d}</b><span>Current Outlook</span></div><div class="ti-metric"><b>{impact.future_outlook:+d}</b><span>Future Outlook</span></div><div class="ti-metric"><b>{impact.positional_depth:+d}</b><span>Depth</span></div><div class="ti-metric"><b>{impact.asset_value:+d}</b><span>Asset Value</span></div><div class="ti-metric"><b>{rec.confidence}%</b><span>Confidence</span></div></div>
<div class="ti-actions"><a class="ti-action" href="/trades/create?front_office={dossier.proposal.active_roster_id}">Open Trade Builder</a></div>
<details class="ti-details"><summary>Open Trade Dossier</summary><div class="ti-grid"><section class="ti-section"><h4>Why Both Sides Improve</h4><p><b>Active:</b> {escape(dossier.why_active_improves)}</p><p><b>Partner:</b> {escape(dossier.why_partner_improves)}</p><p>{escape(dossier.why_realistic)}</p><p>{escape(dossier.why_now)}</p></section><section class="ti-section"><h4>Strengths</h4><ul>{strengths}</ul><h4>Weaknesses</h4><ul>{weaknesses}</ul></section><section class="ti-section"><h4>Risk</h4><ul>{risks}</ul><p>Acceptance likelihood: <b>{rec.acceptance_likelihood if rec.acceptance_likelihood is not None else 'Unavailable'}</b></p></section><section class="ti-section"><h4>Negotiation Plan</h4><p><b>Opening:</b> {escape(plan.opening_offer)}</p><p><b>Minimum offer:</b> {escape(plan.minimum_offer)}</p><p><b>Maximum offer:</b> {escape(plan.maximum_offer)}</p><p><b>Likely counter:</b> {escape(plan.likely_counter)}</p><p><b>Walk-away:</b> {escape(plan.walk_away_point)}</p><p><b>Fallback:</b> {escape(plan.fallback_offer)}</p><p><b>Alternatives:</b> {escape(alternatives)}</p></section>{market_section}{integrated}<section class="ti-section"><h4>Supporting Evidence</h4><ul>{_evidence(dossier)}</ul></section></div></details></article>
"""


def _canonical_card(row: dict) -> str:
    evaluation, proposal = row["evaluation"], row["proposal"]
    values = evaluation["values"]
    presentation = row.get("proposal_presentation") or {}

    def package(items: list[dict], fallback: tuple[str, ...]) -> str:
        if not items:
            return " + ".join(escape(str(item)) for item in fallback)
        rendered = []
        for item in items:
            kind = str(item.get("kind") or "asset")
            image = (
                f'<img src="{escape(str(item.get("headshot_url")), quote=True)}" alt="" loading="lazy">'
                if kind == "player" and item.get("headshot_url") else
                '<span class="ti-pick-icon" aria-hidden="true">PICK</span>'
            )
            context = " · ".join(filter(None, (
                str(item.get("position") or ""),
                str(item.get("positional_rank") or item.get("projected_range") or ""),
            )))
            identity = str(item.get("asset_id") or "")
            href = f'/players/{quote(identity.removeprefix("player:"), safe="")}' if kind == "player" and identity else None
            tag = "a" if href else "span"
            destination = f' href="{escape(href, quote=True)}"' if href else ""
            value = item.get("market_value")
            shown_value = f"{int(value):,}" if value is not None else "Unavailable"
            rendered.append(
                f'<{tag}{destination} class="ti-proposal-asset {"ti-player-tile" if kind == "player" else "ti-pick-tile"}">'
                f'{image}<span><b>{escape(str(item.get("label") or item.get("asset_id") or "Asset"))}</b>'
                f'<small>{escape(context)}</small></span><strong>{shown_value}</strong></{tag}>'
            )
        return "".join(rendered)

    sent = package(list(presentation.get("send") or ()), tuple(proposal["assets_sent"]))
    received = package(list(presentation.get("receive") or ()), tuple(proposal["assets_received"]))
    best_for = evaluation.get("dimensions", {}).get("best_for", {}).get("active", "UNRESOLVED")
    confidence = evaluation.get("dimensions", {}).get("confidence", {}).get("assessment", "UNRESOLVED")
    partner = str(row.get("partner_team_name") or proposal.get("partner_team_name") or "Trade partner")
    active = str(row.get("active_team_name") or "Your franchise")
    historical = evaluation.get("dimensions", {}).get("historical_counterparty_evidence", {})
    history_reasons = "".join(
        f"<li>{escape(str(reason))}</li>" for reason in historical.get("reasons", ())
    )
    dimensions = evaluation.get("dimensions") or {}
    impact_strip = '<div class="ti-impact-strip">' + "".join(
        f'<div><span>{label}</span><b>{escape(str((dimensions.get(key) or {}).get("assessment") or "Unavailable"))}</b></div>'
        for key, label in (("value_fairness", "Market fairness"), ("strategic_fit", "Roster fit"), ("counterparty_plausibility", "Counterparty"), ("confidence", "Evidence"))
    ) + '</div>'
    edit_action = '<button type="button" class="ti-action" data-trade-proposal="' + escape(json.dumps(proposal), quote=True) + '">Edit Trade</button>'
    return f'''<article class="ti-card"><div class="ti-head"><div class="ti-opportunity-label"><div class="ti-priority">{escape(str(evaluation["recommendation"]))} · {escape(str(best_for))}</div><div class="ti-confidence">{escape(str(confidence))} confidence</div></div><h3>Trade with {escape(partner)}</h3></div><div class="ti-franchises"><div class="ti-franchise"><b>{escape(active)}</b><span>Your franchise</span></div><div class="ti-arrow">⇄</div><div class="ti-franchise"><b>{escape(partner)}</b><span>Trade partner</span></div></div><div class="ti-assets"><div class="ti-package"><span>You send</span>{sent}</div><div class="ti-arrow">→</div><div class="ti-package"><span>You receive</span>{received}</div></div><div class="ti-values"><span>Neutral market: <b>{values["sent"]}</b> sent / <b>{values["received"]}</b> received</span><span>{escape(str(evaluation["perspectives"]["bilateral_reality"]))}</span></div>{impact_strip}<div class="ti-bilateral"><div class="ti-reason"><span>Why you should consider this</span>{escape(str(evaluation["why_you_would_do_it"]))}</div><div class="ti-reason"><span>Why they should consider this</span>{escape(str(evaluation["why_they_would_do_it"]))}</div></div><details class="ti-details"><summary class="ti-card-action">View trade details</summary><h4>Evidence and constraints</h4><p><b>Assessment:</b> {escape(str(evaluation["dominant_reason"]))}</p><p><b>Why now:</b> {escape(str(evaluation.get("why_now") or "No supported timing signal."))}</p><p><b>Historical counterparty evidence:</b> {escape(str(historical.get("assessment") or "INSUFFICIENT EVIDENCE"))} · {escape(str(historical.get("confidence") or "LOW"))} confidence</p><ul>{history_reasons}</ul><p>Package quality, optimal legal lineup effects, counterparty plausibility, and evidence confidence are included in the canonical evaluation. Historical evidence is context, not a promise of acceptance.</p></details>{edit_action}</article>'''


def trade_center(view: dict) -> str:
    active = view["active_team"]
    unified = view["unified_recommendation"]
    active_id = int(active.get("roster_id") or 0)
    options = "".join(
        f'<option value="{int(team.get("roster_id") or 0)}" {"selected" if int(team.get("roster_id") or 0) == active_id else ""}>{escape(str(team.get("owner") or team.get("team_name")))}</option>'
        for team in view["teams"]
    )
    workflows = "".join(
        f'<a class="ti-workflow" href="/trades/{identifier}?front_office={active_id}"><b>{label}</b><span>{description}</span></a>'
        for identifier, label, description in (
            ("create", "Create Trade", "Build, evaluate, and improve a bilateral proposal."),
            ("trade-for", "Trade For", "Pursue an asset another franchise owns."),
            ("shop", "Shop Asset", "Search the league for legitimate markets."),
            ("recommended", "Recommended Trades", "Only worthwhile bilateral opportunities."),
        )
    )
    cards = "".join(_canonical_card({**row, "active_team_name": active.get("team_name") or row.get("active_team_name") or "Your franchise"}) for row in view.get("canonical_results", ()))
    if not cards:
        cards = '<div class="card ti-empty"><div><div class="ds-eyebrow">No clean trade right now</div><h3>No realistic bilateral opportunity clears every gate.</h3><p>DTOS checked neutral market value, roster effects, package quality, counterparty fit, and evidence confidence. Try building a proposal or targeting a specific asset.</p><div class="ti-actions"><a class="ti-action" href="/trades/create">Create a Trade</a><a class="ti-action" href="/trades/trade-for">Trade For a Player</a></div></div></div>'
    first = (view.get("canonical_results") or [None])[0]
    if first:
        evaluation = first["evaluation"]
        primary_title = "A bilateral trade is worth reviewing"
        primary_recommendation = str(evaluation["recommendation"])
        primary_reason = str(evaluation["dominant_reason"])
        primary_evidence = (
            str(evaluation["why_you_would_do_it"]),
            str(evaluation["why_they_would_do_it"]),
        )
        expected_impact = str(evaluation["perspectives"]["bilateral_reality"])
    else:
        primary_title = "No trade needs your attention right now"
        primary_recommendation = "KEEP SEARCHING"
        primary_reason = "No current package clears neutral-market, roster-fit, package-quality, and counterparty gates."
        primary_evidence = ("DTOS completed the current bilateral search without filling a recommendation quota.",)
        expected_impact = "Your roster remains unchanged."
    primary = recommendation_panel(
        title=primary_title, recommendation=primary_recommendation,
        confidence=unified.confidence.score,
        primary_reason=primary_reason,
        evidence=primary_evidence,
        expected_impact=expected_impact,
        action_label="Review Recommended Offers", action_href="#recommended-offers",
        limitations=unified.why_not,
    )
    return f'''{TRADE_CSS}<section class="card ti-hero"><div><div class="identity-kicker">Trade Center</div><h2>{escape(str(active.get("team_name") or active.get("owner") or "Unassigned Franchise"))}</h2><p>Neutral market value and team-specific fit are evaluated separately.</p></div><form class="ti-selector" method="get"><label>Active Front Office<select name="front_office" onchange="this.form.submit()">{options}</select></label></form></section><nav class="ti-workflows">{workflows}</nav>{primary}<div class="ti-list" id="recommended-offers">{cards}</div><script src="/static/js/trade_workspace.js" defer></script>'''
