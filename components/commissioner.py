"""Reusable server-rendered Commissioner Desk components."""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote

from models.commissioner import RecommendationPriority
from src.ui import recommendation_panel as shared_recommendation_panel
from src.ui.intelligence_presentation import exact_rank, available, percentile_label, manager_points
from src.ui.customer_experience import plain_reason, readable_time, source_details

COMMISSIONER_DESK_CSS = """
<style>
:root{color-scheme:dark}.cd-shell{display:grid;gap:18px}.cd-header{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px}.cd-header-top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.cd-brand small,.cd-eyebrow{display:block;color:var(--accent);font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.11em}.cd-brand h1{font-size:29px;margin:3px 0}.cd-brand p{margin:0;color:var(--muted)}.cd-sync{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}.cd-sync-meta{text-align:right;font-size:12px;color:var(--muted)}.cd-sync form{margin:0}.cd-context{display:grid;grid-template-columns:repeat(2,minmax(210px,1fr));gap:10px;margin-top:17px}.cd-context label{display:block;font-size:12px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}.cd-context select{width:100%;background:var(--surface-interactive);color:var(--text);border:1px solid #34506d;border-radius:10px;padding:10px}.cd-nav{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.cd-nav a{border:1px solid var(--line);border-radius:999px;padding:7px 10px;color:var(--muted);font-size:13px}.cd-nav a:first-child{color:var(--accent);border-color:rgba(110,231,183,.45)}
.cd-section{display:grid;gap:10px}.cd-section-head{display:flex;justify-content:space-between;gap:12px;align-items:end}.cd-section-head h2{margin:0;font-size:21px}.cd-section-head p{margin:3px 0 0;color:var(--muted);font-size:13px}.cd-chip{border:1px solid var(--line);border-radius:999px;padding:5px 9px;color:var(--muted);font-size:12px}.cd-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.cd-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px}.cd-card h3{font-size:17px;margin:0 0 7px}.cd-card p{color:var(--muted);font-size:13px;line-height:1.55;margin:0}.cd-kicker{font-size:12px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.07em}.cd-counts{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.cd-count{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:10px}.cd-count b{display:block;font-size:20px}.cd-count span{font-size:12px;color:var(--muted)}.cd-events{display:grid;gap:7px}.cd-event{display:grid;grid-template-columns:130px 110px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 12px;background:var(--surface);border:1px solid var(--line);border-radius:11px}.cd-event time,.cd-event p{font-size:12px;color:var(--muted);margin:0}.cd-event b{font-size:13px}.cd-event a{font-size:12px;color:var(--accent)}.cd-empty{padding:18px;border:1px dashed var(--line);border-radius:12px;color:var(--muted);text-align:center}.cd-unavailable{font-size:12px;color:var(--muted);margin:8px 0 0;padding-left:18px}
.cd-headlines{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.cd-headline{position:relative;padding-left:16px}.cd-headline:before{content:"";position:absolute;left:0;top:3px;bottom:3px;width:3px;border-radius:4px;background:var(--accent)}.cd-evidence{margin-top:8px!important;font-size:12px!important}.cd-office{display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:9px}.cd-office-main{background:linear-gradient(150deg,#142a43,#0b1727);border-color:#38516d}.cd-grade{font-size:33px;font-weight:950;color:var(--gold)}.cd-status{display:inline-block;margin-top:8px;border:1px solid rgba(110,231,183,.45);border-radius:999px;padding:5px 8px;color:var(--accent);font-size:12px;font-weight:900}.cd-metric b{display:block;font-size:20px;margin-top:5px}.cd-metric span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.cd-recommendations{display:grid;gap:9px}.cd-rec{display:grid;grid-template-columns:100px minmax(0,1fr) 100px;gap:12px;align-items:start}.cd-priority{font-size:12px;font-weight:950;text-transform:uppercase}.cd-priority.high{color:#fca5a5}.cd-priority.medium{color:var(--gold)}.cd-priority.low{color:var(--accent)}.cd-confidence{text-align:right}.cd-confidence b{display:block;font-size:20px}.cd-rec details{grid-column:2/-1;border-top:1px solid var(--line);padding-top:8px}.cd-rec summary{cursor:pointer;color:var(--accent);font-size:12px;font-weight:850}.cd-reason{font-size:12px;color:var(--muted);line-height:1.55}.cd-reason ul{padding-left:17px}.cd-intelligence{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.cd-intel b{font-size:20px;display:block;margin-top:4px}.cd-intel span{font-size:12px;color:var(--muted)}
.cd-snapshots{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.cd-snapshot{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden}.cd-snapshot summary{cursor:pointer;padding:13px 14px;font-weight:900;display:flex;justify-content:space-between}.cd-snapshot summary:after{content:"+";color:var(--accent)}.cd-snapshot[open] summary:after{content:"−"}.cd-snapshot-body{padding:0 14px 14px;overflow:auto}.cd-mini-row{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid rgba(38,55,76,.65);font-size:12px}.cd-mini-row span{color:var(--muted)}.cd-personality{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.cd-placeholder{border-style:dashed}.cd-placeholder b{display:block;margin-bottom:5px}.cd-footer-note{color:var(--muted);font-size:12px;text-align:center}
@media(max-width:950px){.cd-grid,.cd-intelligence{grid-template-columns:repeat(2,1fr)}.cd-office{grid-template-columns:repeat(2,1fr)}.cd-office-main{grid-column:1/-1}.cd-counts{grid-template-columns:repeat(3,1fr)}}
@media(max-width:650px){.cd-header-top{display:block}.cd-sync{justify-content:flex-start;margin-top:12px}.cd-sync-meta{text-align:left}.cd-context,.cd-grid,.cd-headlines,.cd-office,.cd-intelligence,.cd-snapshots,.cd-personality{grid-template-columns:1fr}.cd-counts{grid-template-columns:repeat(2,1fr)}.cd-event{grid-template-columns:1fr auto}.cd-event p{grid-column:1/-1}.cd-rec{grid-template-columns:1fr auto}.cd-rec details{grid-column:1/-1}.cd-confidence{text-align:right}.cd-section-head{display:block}.cd-chip{display:inline-block;margin-top:6px}}
</style>
"""

PERSISTENCE_SCRIPT = """
<script>
(() => {
  const keys = { league: 'dtos.activeLeague', office: 'dtos.activeFrontOffice', visit: 'dtos.lastCommissionerVisit' };
  const url = new URL(window.location.href);
  const league = document.getElementById('active-league');
  const office = document.getElementById('active-front-office');
  const valid = (select, value) => value && Array.from(select.options).some(option => option.value === value);
  let redirect = false;
  if (!url.searchParams.has('league') && valid(league, localStorage.getItem(keys.league))) { url.searchParams.set('league', localStorage.getItem(keys.league)); redirect = true; }
  if (!url.searchParams.has('front_office') && valid(office, localStorage.getItem(keys.office))) { url.searchParams.set('front_office', localStorage.getItem(keys.office)); redirect = true; }
  if (!url.searchParams.has('since') && localStorage.getItem(keys.visit)) { url.searchParams.set('since', localStorage.getItem(keys.visit)); redirect = true; }
  if (redirect) { window.location.replace(url.toString()); return; }
  localStorage.setItem(keys.league, league.value);
  localStorage.setItem(keys.office, office.value);
  localStorage.setItem(keys.visit, new Date().toISOString());
  const changeContext = (key, parameter, element) => element.addEventListener('change', () => {
    localStorage.setItem(key, element.value);
    const next = new URL(window.location.href);
    next.searchParams.set(parameter, element.value);
    window.location.assign(next.toString());
  });
  changeContext(keys.league, 'league', league);
  changeContext(keys.office, 'front_office', office);
})();
</script>
"""


def _option(value: str, label: str, selected: str) -> str:
    marker = " selected" if value == selected else ""
    return f'<option value="{escape(value)}"{marker}>{escape(label)}</option>'


def commissioner_header(view: dict[str, Any]) -> str:
    active_league = view["active_league"]
    active_office = view["active_front_office"]
    leagues = "".join(_option(item.league_id, f"{item.name} · {item.season}", active_league.league_id) for item in view["leagues"])
    offices = "".join(_option(str(item.roster_id), f"{item.owner_name} · {item.team_name}", str(active_office.roster_id)) for item in view["front_offices"])
    return f"""
<section class="cd-header"><p class="cd-briefing-intro">See what changed, what matters, and what to do next in {escape(active_league.name)}.</p>
<div class="cd-context"><div><label for="active-league">Active League</label><select id="active-league" name="league">{leagues}</select></div><div><label for="active-front-office">Active Front Office</label><select id="active-front-office" name="front_office">{offices}</select></div></div>
</section>
"""


def since_last_visit(view: dict[str, Any]) -> str:
    briefing = view["briefing"]
    labels = ("Trade", "Waiver Claim", "Add", "Drop", "Draft Pick Movement", "League Event")
    counts = "".join(f'<div class="cd-count"><b>{briefing.counts.get(label, 0)}</b><span>{escape(label)}s</span></div>' for label in labels)
    events = "".join(
        f'<article class="cd-event"><time>{escape(readable_time(event.occurred_at))}</time><b>{escape(event.event_type.value)}</b><p><strong>{escape(event.title)}</strong> · {escape(event.detail)}</p>{f"<a href=\"/transactions?q={quote(event.source_id)}\">Open</a>" if event.source_id else ""}</article>'
        for event in briefing.events[:12]
    ) or '<div class="cd-empty"><b>No changes observed in the available activity.</b><br>Unretrieved periods remain unknown. New activity appears after the league data updates.</div>'
    unavailable = "".join(f"<li>{escape(item)}</li>" for item in briefing.unavailable)
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What changed?</h2><p>Since your last Commissioner Desk visit · {escape(briefing.since_label)}</p></div><span class="cd-chip">Observed league activity</span></div><div class="cd-counts">{counts}</div><div class="cd-events">{events}</div><details class="cd-card"><summary>Data not yet available</summary><ul class="cd-unavailable">{unavailable}</ul></details></section>'


def league_headlines(view: dict[str, Any]) -> str:
    cards = []
    for item in view["headlines"]:
        title, detail, limitation = item.title, item.detail, ""
        if item.category == "Draft Capital":
            title = title.replace(" is tied for the largest future-pick inventory", " has one of the largest recorded pick lists").replace(" holds the largest future-pick inventory", " has the largest recorded pick list")
            detail = detail.replace("The franchise owns ", "The available records list ")
            limitation = '<p class="cd-evidence">This compares recorded holdings; the headline alone does not establish a complete pick inventory.</p>'
        evidence = source_details(f'<p>{escape(item.evidence)}</p>' + ('<p>No inventory-completeness receipt is attached to this headline.</p>' if limitation else ''), summary="Headline sources")
        cards.append(f'<article class="cd-card cd-headline"><span class="cd-kicker">{escape(item.category)}</span><h3>{escape(title)}</h3><p>{escape(detail)}</p>{limitation}{evidence}</article>')
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What matters?</h2><p>Observed activity around the league</p></div><span class="cd-chip">No speculation</span></div><div class="cd-headlines">{"".join(cards) or "<div class=\"cd-empty\">No supported league headlines are available.</div>"}</div></section>'


def front_office_summary(view: dict[str, Any]) -> str:
    office = view["active_front_office"]
    summary = view["front_office_summary"]
    current = summary["current_outlook"]
    evidence = summary.get("lineup_evidence")
    points = getattr(evidence, "optimal_lineup_projection", None)
    week = getattr(evidence, "projection_week", None)
    league_name = getattr(view.get("active_league"), "name", None) or "Selected league"
    context = f"{league_name} · Week {week}" if week is not None else f"{league_name} · Projection week not established"
    reasons = tuple(getattr(current, "reasons", ()) or ())
    limitations = tuple(getattr(evidence, "limitations", ()) or ())
    limitation = plain_reason((limitations or reasons or ("The available projections do not support this comparison.",))[0])
    coverage = f"Roster projections: {evidence.projection_covered}/{evidence.roster_count}." if evidence is not None else "Roster projection coverage is not established."
    comparison = (f"{current.league_size} of {len(view['front_offices'])} franchises comparable."
                  if view.get("front_offices") and current.percentile is not None else "League rank is withheld until a supported comparison is ready.")
    lineup = f"{manager_points(points)} projected points" if points is not None else "Lineup comparison not ready"
    rank = f"{exact_rank(current.rank, current.league_size)} · {percentile_label(current.percentile)}" if current.percentile is not None else ""
    calculation = ('<p>Independently optimized legal lineup; separate from your submitted Sleeper starters.</p><ul>'
                   + ''.join(f'<li>{escape(item)}</li>' for item in (*reasons, *limitations)) + '</ul>')
    cards = [f'<article class="cd-card cd-metric"><span>Record</span><b>{escape(summary["record"])}</b><p>Current Sleeper record</p></article>']
    if summary["power_ranking"] is not None:
        cards.append(f'<article class="cd-card cd-metric"><span>Projected lineup rank</span><b>{exact_rank(summary["power_ranking"])}</b><p>Within this league, separate from official standings</p></article>')
    unsupported = []
    for key, label in (("future_outlook", "Future outlook"), ("depth", "Depth score"), ("asset_health", "Asset score")):
        result = summary[key]
        if result.score is None:
            unsupported.append(label)
        else:
            cards.append(f'<article class="cd-card cd-metric"><span>{escape(label)}</span><b>{escape(result.grade)} · {result.score}</b></article>')
    additional = source_details('<p>No result is established for: ' + escape(', '.join(unsupported)) + '.</p><p>A missing assessment does not establish a roster weakness.</p>', summary="Other assessment limits") if unsupported else ""
    window = str(summary["competitive_window"])
    window_label = "Outlook not established" if window == "Unavailable" else window
    return (f'<section class="cd-section"><div class="cd-section-head"><div><h2>Selected Franchise</h2><p>{escape(office.owner_name)} · {escape(office.team_name)}</p></div><a class="cd-chip" href="/teams/{office.roster_id}">Open My Team</a></div>'
            f'<div class="cd-office"><article class="cd-card cd-office-main"><span class="cd-kicker">Optimal Projected Lineup</span><div class="cd-grade">{lineup}</div><p>{escape(context)}</p>'
            + (f'<p>{rank}</p>' if rank else '') + f'<p>{escape(comparison)} {escape(coverage)}</p>'
            + (f'<p class="muted">{escape(limitation)}</p>' if limitations or points is None else '')
            + source_details(calculation, summary="Lineup calculations and sources")
            + f'<p><b>{escape(window_label)}</b></p>'
            + source_details(f'<p>Competitive Window: {escape(summary["window_explanation"])}</p>', summary="Outlook evidence")
            + '</article>' + ''.join(cards) + '</div>' + additional + '</section>')


def recommendation_panel(view: dict[str, Any]) -> str:
    icons = {RecommendationPriority.HIGH: "🔴", RecommendationPriority.MEDIUM: "🟡", RecommendationPriority.LOW: "🟢"}
    cards = []
    for recommendation in view["recommendations"]:
        metrics = "".join(f"<li>{escape(metric)}</li>" for metric in recommendation.supporting_metrics)
        cards.append(
            f'<article class="cd-card cd-rec"><div class="cd-priority {recommendation.priority.value.lower()}">{icons[recommendation.priority]} {escape(recommendation.priority.value)} Priority<br><span>{escape(recommendation.category.value)}</span></div><div><h3>{escape(recommendation.title)}</h3><p>{escape(recommendation.summary)}</p></div><div class="cd-confidence"><b>{recommendation.confidence.value}%</b><span class="muted">Confidence</span></div><details><summary>Show Reasoning</summary><div class="cd-reason"><p>{escape(recommendation.reasoning)}</p><b>Supporting data</b><ul>{metrics}</ul></div></details></article>'
        )
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What should I do?</h2><p>Prioritized Front Office recommendations for {escape(view["active_front_office"].owner_name)}</p></div><span class="cd-chip">Confidence + evidence</span></div><div class="cd-recommendations">{"".join(cards)}</div></section>'


def unified_recommendation_panel(view: dict[str, Any]) -> str:
    recommendation = view["unified_recommendation"]
    card = shared_recommendation_panel(title=recommendation.title, recommendation=recommendation.recommendation, confidence=recommendation.confidence.score, primary_reason=recommendation.why[0] if recommendation.why else recommendation.current_outlook, evidence=recommendation.why, expected_impact=f"Current: {recommendation.current_outlook} Future: {recommendation.future_outlook}", action_label="Open Trade Center", action_href=f'/trades?front_office={view["active_front_office"].roster_id}', limitations=recommendation.why_not)
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What should I do?</h2><p>Next action for {escape(view["active_front_office"].owner_name)}</p></div><span class="cd-chip">Team evidence</span></div><div class="cd-recommendations">{card}</div></section>'


def league_intelligence(view: dict[str, Any]) -> str:
    intelligence = view["league_intelligence"]
    concentration = available(intelligence["draft_concentration"], reason="")
    values = (
        ("Average Roster Age", intelligence["average_roster_age"]),
        ("Draft Capital Concentration", concentration + '%' if concentration else None),
        ("Average Team Grade", intelligence["average_team_grade"]), ("League Strength", intelligence["league_strength"]),
        ("League Parity", intelligence["league_parity"]),
        ("Strongest Position Group", intelligence["strongest_position"]),
        ("Weakest Position Group", intelligence["weakest_position"]), ("Championship Favorite", intelligence["championship_favorite"]),
        ("Most recorded draft picks", intelligence["most_draft_capital"]), ("Fewest recorded draft picks", intelligence["least_draft_capital"]),
        ("Most Flexible Roster", intelligence["most_flexible_roster"]),
        ("Oldest Team", intelligence["oldest_team"]), ("Youngest Team", intelligence["youngest_team"]),
        ("Trending Up", intelligence["trending_up"]), ("Trending Down", intelligence["trending_down"]),
    )
    def supported(value):
        display = available(value, reason="").strip()
        return bool(display) and display not in {"Unknown", "Not established"} and not display.startswith("Unavailable")
    cards = "".join(f'<article class="cd-card cd-intel"><span>{escape(label)}</span><b>{escape(str(value))}</b></article>' for label, value in values if supported(value))
    missing = [label for label, value in values if not supported(value)]
    counts = [(available(intelligence[key], reason=""), label) for key, label in (("contenders", "contender"), ("rebuilders", "rebuild"))]
    count_text = ("Recorded classifications: " + "; ".join(f"{value} {label}" if value else f"{label} count not established" for value, label in counts) + "."
                  if any(value for value, _ in counts) else "Recorded classification counts are not established.")
    details = source_details(('<p>No supported result is available for: ' + escape(', '.join(missing)) + '.</p>' if missing else '') + '<p>These missing assessments do not establish a team weakness or a championship forecast.</p>' + f'<p>{escape(count_text)} These are not complete league counts when team classifications are missing.</p>', summary="League assessment limits")
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>League Intelligence</h2><p>Supported league facts</p></div></div><div class="cd-intelligence">{cards}</div>{details}</section>'


def league_opportunity_dashboard(view: dict[str, Any]) -> str:
    report = view["league_opportunity"]
    team_names = view["team_names"]
    cards = "".join(f'<article class="cd-card cd-intel"><span>{escape(label)}</span><b>{escape(value)}</b></article>' for label, value in report.dashboard.items())
    partners = [item for item in report.compatibilities if report.active_roster_id in {item.first_roster_id, item.second_roster_id}][:5]
    partner_rows = "".join(
        f'<div class="cd-mini-row"><b>{escape(team_names.get(item.second_roster_id if item.first_roster_id == report.active_roster_id else item.first_roster_id, "Unassigned Franchise"))} · {item.score}/100</b><span>{escape(", ".join(item.complementary_needs) or item.timeline_fit)}</span></div>'
        for item in partners
    ) or '<p class="muted">No supported partner fit is established from the available team evidence.</p>'
    opportunities = "".join(
        f'<div class="cd-mini-row"><b>{escape(item.player_name)} · {item.score}/100</b><span>{escape(team_names.get(item.owner_roster_id, "Unassigned Franchise"))} · {escape(item.availability)}</span></div>'
        for item in report.opportunities[:7]
    ) or '<p class="muted">No evidence-supported player opportunity is available.</p>'
    economy = "".join(f'<div class="cd-mini-row"><b>{escape(position)} · {escape(item.state)}</b><span>{item.demand} supported need contexts / {item.supply} conditional depth suppliers · no price premium inferred</span></div>' for position, item in report.economy.items())
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>League Opportunity Dashboard</h2><p>Roster needs and possible partners to investigate</p></div><span class="cd-chip">Roster context</span></div><div class="cd-intelligence">{cards}</div><div class="cd-snapshots"><details class="cd-snapshot" open><summary>Best Trade Partners</summary><div class="cd-snapshot-body">{partner_rows}</div></details><details class="cd-snapshot"><summary>Top Player Opportunities</summary><div class="cd-snapshot-body">{opportunities}</div></details><details class="cd-snapshot"><summary>League Economy</summary><div class="cd-snapshot-body">{economy}</div></details></div></section>'


def league_snapshot(view: dict[str, Any]) -> str:
    snapshot = view["snapshot"]
    standings = "".join(f'<div class="cd-mini-row"><b>#{rank} {escape(team["team_name"])}</b><span>{escape(snapshot["season_label"])} · {team["wins"]}-{team["losses"]}-{team["ties"]}</span></div>' for rank, team in enumerate(snapshot["standings"], 1))
    transactions = "".join(f'<div class="cd-mini-row"><b>{escape(item["type_label"])}</b><span>{escape(readable_time(item["timestamp"]))}</span></div>' for item in snapshot["transactions"]) or '<p class="muted">No cached transactions.</p>'
    matchups = []
    for matchup_id, sides in sorted(snapshot["matchups"].items(), key=lambda item: str(item[0])):
        names = " vs ".join(escape(str(side.get("team") or "TBD")) for side in sides)
        matchups.append(f'<div class="cd-mini-row"><b>Matchup {escape(str(matchup_id))}</b><span>{names}</span></div>')
    leader = snapshot["leader"]
    leaders = (f'<div class="cd-mini-row"><b>Projected Power Leader</b><span>{escape(str(leader.get("team_name"))) if leader else "No projected leader is available yet."}</span></div>' if snapshot["preseason"] else f'<div class="cd-mini-row"><b>{escape(snapshot["season_label"])} Leader</b><span>{escape(str(leader.get("team_name"))) if leader else "No current-season leader is available."}</span></div>')
    health = snapshot["health"]
    health_html = f'<div class="cd-mini-row"><b>{escape(health["status"])}</b><span>Last sync {escape(readable_time(health["last_sync"]))}</span></div>' + (f'<p class="warn">{escape(health["error"])}</p>' if health["error"] else "")
    sections = ((snapshot["season_label"], standings), ("Recent Transactions", transactions), ("Upcoming Matchups", "".join(matchups) or '<p class="muted">No matchup assignments.</p>'), ("League Leaders", leaders), ("League Health", health_html))
    cards = "".join(f'<details class="cd-snapshot"{" open" if index == 0 else ""}><summary>{escape(title)}</summary><div class="cd-snapshot-body">{body}</div></details>' for index, (title, body) in enumerate(sections))
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>League Snapshot</h2><p>Compact reference cards · expand only what you need</p></div></div><div class="cd-snapshots">{cards}</div></section>'


def league_personality(view: dict[str, Any]) -> str:
    league_name = view["active_league"].name
    cards = "".join(f'<article class="cd-card cd-placeholder"><b>{escape(label)}</b><p>Extension point for {escape(league_name)}. Coming in a future DTOS release.</p></article>' for label in ("Hall of Fame & Awards", "Rivalries & Records", "Commissioner Notes & Milestones"))
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>League Personality</h2><p>Future league-specific identity without hardcoded assumptions</p></div></div><div class="cd-personality">{cards}</div></section>'


def commissioner_desk(view: dict[str, Any]) -> str:
    """Compose the reusable Commissioner Desk component hierarchy."""
    return (
        COMMISSIONER_DESK_CSS
        + '<div class="cd-shell">'
        + commissioner_header(view)
        + since_last_visit(view)
        + unified_recommendation_panel(view)
        + front_office_summary(view)
        + league_headlines(view)
        + source_details(league_opportunity_dashboard(view) + league_intelligence(view), summary="Detailed Evidence · league assessments")
        + league_snapshot(view)
        + '<p class="cd-footer-note">Facts before interpretation · Explainable recommendations · Uncertainty disclosed</p></div>'
        + PERSISTENCE_SCRIPT
    )
