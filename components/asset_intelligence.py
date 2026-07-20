"""Server-rendered Asset Intelligence dossier components."""
from __future__ import annotations

from html import escape

from src.core.asset_intelligence import AssetEvaluation, PlayerReport

ASSET_CSS = """
<style>
.ai-context{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.ai-context select{background:#0b1727;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:8px}
.ai-values{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:10px;margin:14px 0}.ai-value{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:13px;padding:13px}.ai-value b{font-size:25px;color:var(--gold);display:block}.ai-value span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}.ai-value small{display:block;color:var(--muted);margin-top:5px}
.ai-sections{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ai-card{background:#101d2d;border:1px solid var(--line);border-radius:14px;padding:14px}.ai-card h3{margin:0 0 8px}.ai-card ul{margin:7px 0;padding-left:20px}.ai-evidence summary{cursor:pointer;color:var(--accent);font-weight:800}.ai-evidence li{margin-bottom:7px}.ai-recommendation{border-color:rgba(110,231,183,.55)}.ai-priority{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--gold)}
@media(max-width:760px){.ai-values{grid-template-columns:repeat(2,1fr)}.ai-sections{grid-template-columns:1fr}}@media(max-width:430px){.ai-values{grid-template-columns:1fr}}
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
    snapshot = (("Position", profile.position), ("NFL Team", profile.nfl_team), ("Age", str(profile.age or "Unavailable")), ("Experience", str(profile.experience if profile.experience is not None else "Unavailable")), ("Contract", profile.contract_status), ("Injury", profile.injury_status), ("Bye", profile.bye_week))
    snapshot_html = "".join(f"<li><b>{escape(label)}:</b> {escape(value)}</li>" for label, value in snapshot)
    strengths = "".join(f"<li>{escape(item)}</li>" for item in report.strengths)
    weaknesses = "".join(f"<li>{escape(item)}</li>" for item in report.weaknesses)
    risk_evidence = "".join(f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)}</li>" for item in report.risk.evidence)
    opportunity = "".join(f"<li><b>{escape(label)}:</b> {value.score}/100 — {escape(value.summary)}</li>" for label, value in report.opportunity.items())
    rec_evidence = "".join(f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)}</li>" for item in report.recommendation.evidence)
    return f"""
{ASSET_CSS}
<section class="card ai-context"><div><div class="identity-kicker">Asset Intelligence v1 · Player Dossier</div><h2>{escape(profile.name)}</h2><p class="muted">{escape(report.executive_summary)}</p></div><form method="get"><label for="front_office">Active Front Office</label><select id="front_office" name="front_office" onchange="this.form.submit()">{options}</select></form></section>
<section class="ai-values">{values}</section>
<section class="ai-sections"><article class="ai-card"><h3>Player Snapshot</h3><ul>{snapshot_html}</ul><p><b>Archetypes:</b> {escape(", ".join(report.archetypes))}</p></article><article class="ai-card"><h3>Opportunity Analysis</h3><ul>{opportunity}</ul></article><article class="ai-card"><h3>Strength Analysis</h3><ul>{strengths}</ul></article><article class="ai-card"><h3>Weakness Analysis</h3><ul>{weaknesses}</ul></article><article class="ai-card"><h3>Risk Analysis · {escape(report.risk.level)} ({report.risk.score}/100)</h3><details class="ai-evidence"><summary>Supporting Evidence</summary><ul>{risk_evidence}</ul></details></article><article class="ai-card ai-recommendation"><div class="ai-priority">{escape(report.recommendation.priority)} Priority · {report.recommendation.confidence}% confidence</div><h3>{escape(report.recommendation.action)}</h3><p>{escape(report.recommendation.summary)}</p><details class="ai-evidence"><summary>Supporting Evidence</summary><ul>{rec_evidence}</ul></details></article></section>
"""
