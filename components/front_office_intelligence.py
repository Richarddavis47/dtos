"""Server-rendered Front Office Intelligence dossier components."""
from __future__ import annotations

from html import escape


CSS = """<style>
.foi-hero{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}.foi-hero select{background:#0b1727;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px}.foi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.foi-card{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:13px;padding:13px}.foi-card h3{margin:4px 0}.foi-score{font-size:28px;color:var(--gold);font-weight:950}.foi-evidence summary{color:var(--accent);cursor:pointer;font-weight:800}.foi-evidence li{margin:7px 0;color:var(--muted)}@media(max-width:760px){.foi-grid{grid-template-columns:1fr}}
</style>"""


def _evidence(items) -> str:
    return "".join(f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)} <small>Source: {escape(item.source)}</small></li>" for item in items)


def front_office_center(view: dict) -> str:
    active = view["active"]
    unified = view["unified_recommendation"]
    options = "".join(f'<option value="{item.roster_id}" {"selected" if item.roster_id == active.roster_id else ""}>{escape(item.owner_name)} — {escape(item.team_name)}</option>' for item in view["reports"])
    preferences = "".join(f"<li>{escape(item.label)} <span class=\"pill\">{escape(item.strength)}</span></li>" for item in active.asset_preferences)
    compatibility = "".join(f'<article class="foi-card"><span class="identity-kicker">{escape(item.difficulty)}</span><h3>{escape(next(report.team_name for report in view["reports"] if report.roster_id in {item.first_roster_id, item.second_roster_id} and report.roster_id != active.roster_id))}</h3><div class="foi-score">{item.score}%</div><p class="muted">Themes: {escape(", ".join(item.best_trade_themes))}</p><p>Acceptance: {item.forecast.acceptance_probability if item.forecast.acceptance_probability is not None else "Unavailable — insufficient history"}</p><details class="foi-evidence"><summary>Show Evidence & Forecast</summary><p>{escape(item.forecast.opening_recommendation)}</p><p>{escape(item.forecast.expected_counter)}</p><ul>{_evidence(item.evidence)}</ul></details></article>' for item in view["compatibilities"])
    return f'''{CSS}<section class="card foi-hero"><div><div class="identity-kicker">Front Office Intelligence v1 / Unified Intelligence Platform</div><h2>{escape(active.team_name)}</h2><p>{escape(active.executive_summary)}</p><p><b>{escape(unified.title)}:</b> {escape(unified.recommendation)} <span class="pill">{unified.confidence.score}% confidence</span></p></div><form method="get"><label for="front_office">Front Office</label><select id="front_office" name="front_office" onchange="this.form.submit()">{options}</select></form></section>
<section class="foi-grid"><article class="foi-card"><span class="identity-kicker">Competitive Window</span><h3>{escape(active.competitive_window)}</h3><p>{escape(" · ".join(active.philosophies))}</p></article><article class="foi-card"><span class="identity-kicker">Negotiation Style</span><h3>{escape(active.negotiation_style)}</h3><p>{active.activity.trades} trades · {active.activity.waivers} waivers · {active.activity.adds} adds · {active.activity.drops} drops</p></article><article class="foi-card"><span class="identity-kicker">Evidence Confidence</span><div class="foi-score">{active.confidence}%</div><p>Confidence grows only with observable cached league history.</p></article><article class="foi-card"><h3>Asset Preferences</h3><ul>{preferences}</ul></article><article class="foi-card"><h3>Strategic Strengths</h3><p>{escape(", ".join(active.strengths))}</p></article><article class="foi-card"><h3>Observable Constraints</h3><p>{escape(", ".join(active.constraints))}</p></article></section>
<details class="card foi-evidence"><summary>Show Full Dossier Evidence</summary><ul>{_evidence(active.evidence)}</ul><p class="muted">DTOS models fantasy-football actions only. It does not infer personality, character, or private intent.</p></details><h2>Trade Compatibility</h2><section class="foi-grid">{compatibility}</section>'''
