"""Server-rendered Asset Intelligence dossier components."""
from __future__ import annotations

from html import escape
from urllib.parse import quote

from src.ui import player_summary, recommendation_panel

from src.core.asset_intelligence import AssetEvaluation, PlayerReport

ASSET_CSS = """
<style>
.ai-context{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:center}
.ai-context .ds-actions{justify-content:flex-start}.ai-context form{display:grid;gap:8px}
.ai-player-identity{margin:12px 0}.ai-player-identity .player-portrait,.ai-player-identity .player-headshot,.ai-player-identity .player-headshot-fallback{width:88px;height:88px;flex-basis:88px;border-radius:16px}
.ai-player-identity .player-summary-copy b{font-size:28px}.ai-player-identity .player-summary-copy span{font-size:14px}
.ai-values{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}
.ai-value{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:16px}
.ai-value b{font-size:30px;color:var(--blue);display:block;margin:8px 0}
.ai-value span{font-size:13px;color:var(--text-secondary)}.ai-value small{display:block;color:var(--muted);margin:6px 0}
.ai-sections{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0;align-items:start}
.ai-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:18px}
.ai-card h3{margin:0 0 12px;font-size:19px}.ai-card ul{padding-left:20px;margin:8px 0}.ai-card li{margin:8px 0;color:var(--text-secondary)}
.ai-evidence summary{cursor:pointer;color:var(--accent);font-size:13px;min-height:44px;display:flex;align-items:center}
.ai-evidence li{margin-bottom:8px}.ai-recommendation{border-color:#365334}.ai-priority{font-size:12px;color:var(--gold)}
@media(max-width:760px){.ai-context{grid-template-columns:1fr}.ai-values{grid-template-columns:repeat(2,minmax(0,1fr))}.ai-sections{grid-template-columns:1fr}.ai-player-identity .player-summary-copy b{font-size:24px}}
</style>
"""


def _evidence(evaluation: AssetEvaluation) -> str:
    rows = "".join(
        f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)} <small>Source: {escape(item.source)}</small></li>"
        for item in evaluation.evidence
    )
    limits = "".join(f"<li>{escape(item)}</li>" for item in evaluation.limitations)
    return f'<details class="ai-evidence"><summary>Supporting Evidence</summary><ul>{rows}</ul>{f"<b>Limitations</b><ul>{limits}</ul>" if limits else ""}</details>'


def player_dossier(report: PlayerReport, selected_team: dict, teams: list[dict]) -> str:
    profile = report.profile
    options = "".join(
        f'<option value="{int(team.get("roster_id") or 0)}" {"selected" if int(team.get("roster_id") or 0) == int(selected_team.get("roster_id") or 0) else ""}>{escape(str(team.get("owner") or team.get("team_name")))}</option>'
        for team in teams
    )
    values = "".join(
        f'<article class="ai-value"><span>{escape(value.name)}</span><b>{value.score}</b><small>{value.confidence}% confidence</small>{_evidence(value)}</article>'
        for value in (report.core_values.dynasty, report.core_values.redraft, report.core_values.market, report.core_values.team_fit)
    )
    snapshot = (("Asset Tier", report.archetypes[0]), ("Position", profile.position), ("NFL Team", profile.nfl_team), ("Age", str(profile.age or "Sleeper metadata does not provide age.")), ("Experience", str(profile.experience if profile.experience is not None else "Sleeper metadata does not provide NFL experience.")), ("Contract", profile.contract_status if profile.contract_status != "Unavailable" else "No supported provider supplies contract data."), ("Injury", profile.injury_status), ("Bye", profile.bye_week if profile.bye_week != "Unavailable" else "Sleeper metadata does not currently provide a bye week."))
    snapshot_html = "".join(f"<li><b>{escape(label)}:</b> {escape(value)}</li>" for label, value in snapshot)
    strengths = "".join(f"<li>{escape(item)}</li>" for item in report.strengths)
    weaknesses = "".join(f"<li>{escape(item)}</li>" for item in report.weaknesses)
    risk_evidence = "".join(f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)}</li>" for item in report.risk.evidence)
    opportunity = "".join(f"<li><b>{escape(label)}:</b> {value.score}/100 — {escape(value.summary)}</li>" for label, value in report.opportunity.items())
    recommendation_evidence = tuple(f"{item.factor}: {item.observed_value} — {item.explanation}" for item in report.recommendation.evidence)
    active_roster_id = int(selected_team.get("roster_id") or 0)
    player_id = str(profile.player_id)
    owner_roster_id = next(
        (
            int(team.get("roster_id") or 0)
            for team in teams
            if player_id in {
                str(item.get("id") or item.get("player_id")) if isinstance(item, dict) else str(item)
                for item in team.get("players", ())
            }
        ),
        0,
    )
    owned = owner_roster_id == active_roster_id
    trade_workflow = "shop" if owned else "trade-for"
    trade_action = "Shop Asset" if owned else "Trade For"
    trade_href = (
        f"/trades/{trade_workflow}?front_office={active_roster_id}"
        f"&asset_id={quote(player_id, safe='')}&owner_roster_id={owner_roster_id}"
    )
    primary_recommendation = recommendation_panel(title=report.recommendation.action, recommendation=report.recommendation.summary, confidence=report.recommendation.confidence, primary_reason=recommendation_evidence[0] if recommendation_evidence else report.executive_summary, evidence=recommendation_evidence, expected_impact="Aligns this player's role and value with the selected Front Office direction.", action_label=trade_action, action_href=trade_href, limitations=tuple(report.risk.limitations))
    value = report.value_profile
    integrated = ""
    if value is not None:
        card = value.intelligence_card
        market_range = f"{value.market_range[0]:.0f}–{value.market_range[1]:.0f}" if value.market_range else "No enabled market provider returned a value."
        projection = value.projection
        production = next((window.fantasy_points for window in value.production.windows if window.label == "Season Average"), None)
        providers = ", ".join(f"{item.provider}: raw {item.raw_value:g} → {item.normalized_value}/1000" for item in card.provider_evidence) if card and card.provider_evidence else "No calibrated provider evidence."
        calibration = f'{escape(card.calibration_status.value)} · {card.confidence_score}% confidence' if card else "insufficient_data"
        warning = "" if card and card.calibration_status.value == "calibrated" else "Experimental — market calibration incomplete."
        integrated = f'''<p class="muted"><b>Calibration:</b> {calibration}. {escape(warning)}</p><section class="ai-sections"><article class="ai-card"><h3>Unified Value · canonical 0–1000</h3><ul><li><b>DTOS Intrinsic:</b> {value.dtos_dynasty.value}</li><li><b>Market Consensus:</b> {value.market_consensus.value if value.market_consensus.value is not None else "Unavailable"} ({escape(value.market_consensus.status.value)})</li><li><b>Normalized Market Range:</b> {escape(market_range)}</li><li><b>Canonical Value Gap:</b> {value.value_gap if value.value_gap is not None else "Unavailable"}</li><li><b>Win-Now / Rebuild:</b> {value.contender.value} / {value.rebuilder.value}</li><li><b>Liquidity (0–100):</b> {value.trade_liquidity.value}</li><li><b>Posture:</b> {escape(value.market_posture)}</li><li><b>Provider Evidence:</b> {escape(providers)}</li></ul></article><article class="ai-card"><h3>Weekly Outlook · {escape(projection.status.value)}</h3><ul><li><b>Projection:</b> {projection.projected_points}</li><li><b>Floor / Median / Ceiling:</b> {projection.floor} / {projection.median} / {projection.ceiling}</li><li><b>Role:</b> {escape(value.lineup.role)}</li><li><b>Above Replacement:</b> {value.lineup.points_above_replacement:+.2f}</li><li><b>Above Current Starter:</b> {value.lineup.points_above_current_starter:+.2f}</li><li><b>Source:</b> {escape(projection.source)}</li></ul></article><article class="ai-card"><h3>Production</h3><ul><li><b>Season Average:</b> {production if production is not None else "Unavailable"}</li><li><b>Consistency:</b> {value.production.consistency if value.production.consistency is not None else "Unavailable"}</li><li><b>Trend:</b> {escape(value.production.trend)}</li><li><b>Status:</b> {escape(value.production.status.value)}</li></ul></article><article class="ai-card"><h3>Positional Context</h3><ul><li><b>Dynasty Rank:</b> {value.positional.dynasty_rank}</li><li><b>Weekly Rank:</b> {value.positional.weekly_rank}</li><li><b>Tier:</b> {escape(value.positional.tier)}</li><li><b>Scarcity:</b> {value.positional.scarcity}/100</li><li><b>Replacement Gap:</b> {value.positional.replacement_gap:+.2f}</li></ul><details class="ai-evidence"><summary>Supporting Evidence</summary><ul>{"".join(f"<li>{escape(item)}</li>" for item in value.evidence)}</ul></details></article></section>'''
        production_reason = value.production.limitations[0] if value.production.limitations else "No supported production-stat provider is configured."
        integrated = integrated.replace("Season Average:</b> Unavailable", f"Season Average:</b> {escape(production_reason)}")
        integrated = integrated.replace("Consistency:</b> Unavailable", f"Consistency:</b> {escape(production_reason)}")
        integrated = integrated.replace("Trend:</b> Unavailable", f"Trend:</b> {escape(production_reason)}")
    return f"""
{ASSET_CSS}
<section class="card ai-context"><div><div class="identity-kicker">Player Dossier</div><div class="ai-player-identity">{player_summary(player_id=player_id, name=profile.name, position=profile.position, nfl_team=profile.nfl_team)}</div><p class="muted">{escape(report.executive_summary)}</p><div class="ds-actions"><a class="ds-action primary" href="{trade_href}">{trade_action}</a>{f'<a class="ds-action" href="/teams/{owner_roster_id}">View owning franchise</a>' if owner_roster_id else '<span class="pill">Unrostered in this league</span>'}</div></div><form method="get"><label for="front_office">Active Front Office</label><select id="front_office" name="front_office" onchange="this.form.submit()">{options}</select></form></section>
{primary_recommendation}
<section class="ai-values">{values}</section>
{integrated}
<section class="ai-sections"><article class="ai-card"><h3>Player Snapshot</h3><ul>{snapshot_html}</ul><p><b>Archetypes:</b> {escape(", ".join(report.archetypes))}</p></article><article class="ai-card"><h3>Opportunity Analysis</h3><ul>{opportunity}</ul></article><article class="ai-card"><h3>Strength Analysis</h3><ul>{strengths}</ul></article><article class="ai-card"><h3>Weakness Analysis</h3><ul>{weaknesses}</ul></article><article class="ai-card"><h3>Risk Analysis · {escape(report.risk.level)} ({report.risk.score}/100)</h3><details class="ai-evidence"><summary>Supporting Evidence</summary><ul>{risk_evidence}</ul></details></article></section>
"""
