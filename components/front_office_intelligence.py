"""Server-rendered Front Office Intelligence dossier components."""
from __future__ import annotations

from html import escape

from src.ui import recommendation_panel
from src.ui.customer_experience import plain_reason, source_details


CSS = """<style>
.foi-hero{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;margin-bottom:20px}.foi-hero h2{font-size:30px;margin:8px 0}.foi-hero p{max-width:720px;color:var(--text-secondary)}.foi-hero form{display:grid;gap:8px}.foi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:20px 0}.foi-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:18px}.foi-card h3{font-size:20px;margin:8px 0}.foi-card p{font-size:14px;color:var(--text-secondary)}.foi-score{font-size:32px;color:var(--blue);font-weight:700}.foi-evidence summary{color:var(--accent);cursor:pointer;min-height:44px;display:flex;align-items:center}.foi-evidence li{overflow-wrap:anywhere;word-break:normal;margin:8px 0;color:var(--text-secondary);line-height:1.6}@media(max-width:760px){.foi-grid{grid-template-columns:1fr}.foi-hero h2{font-size:26px}}
</style>"""


def _evidence(items) -> str:
    return "".join(f"<li><b>{escape(item.factor)}:</b> {escape(item.observed_value)} — {escape(item.explanation)} <small>Source: {escape(item.source)}</small></li>" for item in items)


def _profile_summary(active) -> str:
    """Describe admitted facts without turning an unknown outlook into a label."""
    if active.competitive_window.classification.value != "Unavailable":
        return plain_reason(active.executive_summary)
    return (f"{active.team_name}: roster and completed-trade observations are shown separately. "
            "There is not enough supported evidence to establish a competitive outlook.")


def front_office_center(view: dict) -> str:
    active = view["active"]
    unified = view["unified_recommendation"]
    preferences = "".join(f"<li>{escape(item.label)} <span class=\"pill\">{escape(item.strength)}</span></li>" for item in active.asset_preferences)
    from src.core.gm_behavioral_intelligence.activity import activity_text
    activity = activity_text(active.activity.observed_activity)
    summary = _profile_summary(active)
    window = active.competitive_window
    window_label = window.classification.value if window.classification.value != "Unavailable" else "Outlook not established"
    reasons = "".join(f"<li>{escape(plain_reason(item))}</li>" for item in window.reasons)
    strengths = ", ".join(escape(plain_reason(item)) for item in active.strengths)
    constraints = ", ".join(escape(plain_reason(item)) for item in active.constraints)
    compatibility = []
    for item in view["compatibilities"]:
        partner = next(report for report in view["reports"] if report.roster_id in {item.first_roster_id, item.second_roster_id} and report.roster_id != active.roster_id)
        detail = (f'<p>Possible approach (inference): {escape(item.forecast.opening_recommendation)}</p>'
                  f'<p>{escape(item.forecast.expected_counter)}</p><ul>{_evidence(item.evidence)}</ul>')
        compatibility.append(f'<article class="foi-card"><h3>{escape(partner.team_name)}</h3>'
                             f'<p>Roster-context fit: {item.score}/100 · {escape(item.difficulty)}</p>'
                             f'<p>{escape(", ".join(item.best_trade_themes))}</p>'
                             + source_details(detail, summary="Why this partner may fit") + '</article>')
    primary = recommendation_panel(title=unified.title, recommendation=unified.recommendation, confidence=unified.confidence.score, primary_reason=plain_reason(unified.why[0]) if unified.why else summary, evidence=unified.why, expected_impact=f"Current: {unified.current_outlook} Future: {unified.future_outlook}", action_label="Open My Team", action_href=f"/teams/{active.roster_id}", limitations=unified.why_not)
    profile_details = (f'<p>Original assessment: {escape(active.executive_summary)}</p>'
                       f'<p>Profile evidence confidence: {active.confidence}%.</p>'
                       '<p>This describes support from roster, pick and activity records. It is not an acceptance probability.</p>'
                       f'<h3>Current roster composition</h3><ul>{preferences}</ul><ul>{_evidence(active.evidence)}</ul>'
                       '<p>DTOS describes observed fantasy-football activity, not personality or private intent.</p>')
    return (CSS + f'<section class="card foi-hero"><div><div class="identity-kicker">Franchise Management Profile</div>'
            f'<h2><a href="/teams/{active.roster_id}">{escape(active.team_name)}</a></h2><p>{escape(summary)}</p></div>'
            '<a class="secondary" href="/fois">Manager grades</a></section>' + primary
            + f'<section class="foi-grid"><article class="foi-card"><h3>{escape(window_label)}</h3>'
            + source_details(f'<ul>{reasons}</ul>', summary="Outlook evidence") + '</article>'
            + f'<article class="foi-card"><h3>Observed franchise activity</h3><p>{escape(activity)}</p></article>'
            + f'<article class="foi-card"><h3>Roster strengths and needs</h3><p><b>Strengths:</b> {strengths}</p><p><b>Needs:</b> {constraints}</p></article></section>'
            + source_details(profile_details, summary="Profile calculations and sources")
            + '<h2>Potential trade partners</h2><p>Fit is an inference from roster context, not a qualified offer or a prediction of acceptance.</p>'
            + '<section class="foi-grid">' + ''.join(compatibility) + '</section>')
