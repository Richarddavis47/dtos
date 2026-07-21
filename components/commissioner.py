"""Reusable server-rendered Commissioner Desk components."""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote

from models.commissioner import RecommendationPriority

COMMISSIONER_DESK_CSS = """
<style>
:root{color-scheme:dark}.cd-shell{display:grid;gap:18px}.cd-header{background:linear-gradient(135deg,#152b45,#0b1727 62%,#10283a);border:1px solid var(--line);border-radius:18px;padding:20px}.cd-header-top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.cd-brand small,.cd-eyebrow{display:block;color:var(--accent);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.11em}.cd-brand h1{font-size:29px;margin:3px 0}.cd-brand p{margin:0;color:var(--muted)}.cd-sync{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}.cd-sync-meta{text-align:right;font-size:10px;color:var(--muted)}.cd-sync form{margin:0}.cd-context{display:grid;grid-template-columns:repeat(2,minmax(210px,1fr));gap:10px;margin-top:17px}.cd-context label{display:block;font-size:9px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}.cd-context select{width:100%;background:#091625;color:var(--text);border:1px solid #34506d;border-radius:10px;padding:10px}.cd-nav{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.cd-nav a{border:1px solid var(--line);border-radius:999px;padding:7px 10px;color:var(--muted);font-size:11px}.cd-nav a:first-child{color:var(--accent);border-color:rgba(110,231,183,.45)}
.cd-section{display:grid;gap:10px}.cd-section-head{display:flex;justify-content:space-between;gap:12px;align-items:end}.cd-section-head h2{margin:0;font-size:21px}.cd-section-head p{margin:3px 0 0;color:var(--muted);font-size:11px}.cd-chip{border:1px solid var(--line);border-radius:999px;padding:5px 9px;color:var(--muted);font-size:9px}.cd-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.cd-card{background:rgba(16,29,45,.96);border:1px solid var(--line);border-radius:14px;padding:14px}.cd-card h3{font-size:13px;margin:0 0 7px}.cd-card p{color:var(--muted);font-size:11px;line-height:1.55;margin:0}.cd-kicker{font-size:9px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.07em}.cd-counts{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.cd-count{background:#0b1727;border:1px solid var(--line);border-radius:11px;padding:10px}.cd-count b{display:block;font-size:20px}.cd-count span{font-size:9px;color:var(--muted)}.cd-events{display:grid;gap:7px}.cd-event{display:grid;grid-template-columns:130px 110px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 12px;background:#101d2d;border:1px solid var(--line);border-radius:11px}.cd-event time,.cd-event p{font-size:10px;color:var(--muted);margin:0}.cd-event b{font-size:11px}.cd-event a{font-size:10px;color:var(--accent)}.cd-empty{padding:18px;border:1px dashed var(--line);border-radius:12px;color:var(--muted);text-align:center}.cd-unavailable{font-size:10px;color:var(--muted);margin:8px 0 0;padding-left:18px}
.cd-headlines{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.cd-headline{position:relative;padding-left:16px}.cd-headline:before{content:"";position:absolute;left:0;top:3px;bottom:3px;width:3px;border-radius:4px;background:var(--accent)}.cd-evidence{margin-top:8px!important;font-size:9px!important}.cd-office{display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:9px}.cd-office-main{background:linear-gradient(150deg,#142a43,#0b1727);border-color:#38516d}.cd-grade{font-size:33px;font-weight:950;color:var(--gold)}.cd-status{display:inline-block;margin-top:8px;border:1px solid rgba(110,231,183,.45);border-radius:999px;padding:5px 8px;color:var(--accent);font-size:10px;font-weight:900}.cd-metric b{display:block;font-size:20px;margin-top:5px}.cd-metric span{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.cd-recommendations{display:grid;gap:9px}.cd-rec{display:grid;grid-template-columns:100px minmax(0,1fr) 100px;gap:12px;align-items:start}.cd-priority{font-size:10px;font-weight:950;text-transform:uppercase}.cd-priority.high{color:#fca5a5}.cd-priority.medium{color:var(--gold)}.cd-priority.low{color:var(--accent)}.cd-confidence{text-align:right}.cd-confidence b{display:block;font-size:20px}.cd-rec details{grid-column:2/-1;border-top:1px solid var(--line);padding-top:8px}.cd-rec summary{cursor:pointer;color:var(--accent);font-size:10px;font-weight:850}.cd-reason{font-size:10px;color:var(--muted);line-height:1.55}.cd-reason ul{padding-left:17px}.cd-intelligence{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.cd-intel b{font-size:20px;display:block;margin-top:4px}.cd-intel span{font-size:9px;color:var(--muted)}
.cd-snapshots{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.cd-snapshot{background:#101d2d;border:1px solid var(--line);border-radius:14px;overflow:hidden}.cd-snapshot summary{cursor:pointer;padding:13px 14px;font-weight:900;display:flex;justify-content:space-between}.cd-snapshot summary:after{content:"+";color:var(--accent)}.cd-snapshot[open] summary:after{content:"−"}.cd-snapshot-body{padding:0 14px 14px;overflow:auto}.cd-mini-row{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid rgba(38,55,76,.65);font-size:10px}.cd-mini-row span{color:var(--muted)}.cd-personality{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.cd-placeholder{border-style:dashed}.cd-placeholder b{display:block;margin-bottom:5px}.cd-footer-note{color:var(--muted);font-size:10px;text-align:center}
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
  const syncForm = document.querySelector('.cd-sync form');
  syncForm.addEventListener('submit', async event => {
    event.preventDefault();
    const button = syncForm.querySelector('button');
    button.disabled = true;
    button.textContent = 'Synchronizing…';
    try { await fetch('/sync', { method: 'POST', headers: { 'Accept': 'application/json' } }); }
    finally { window.location.reload(); }
  });
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
    health = view["snapshot"]["health"]
    return f"""
<header class="cd-header"><div class="cd-header-top"><div class="cd-brand"><small>DTOS · Front Office Operating System</small><h1>Commissioner Desk</h1><p>{escape(active_league.name)} executive briefing</p></div><div class="cd-sync"><div class="cd-sync-meta">Last synchronization<br><b>{escape(health['last_sync'])}</b></div><form method="post" action="/sync"><button class="btn" type="submit">Sync League</button></form></div></div>
<div class="cd-context"><div><label for="active-league">Active League</label><select id="active-league" name="league">{leagues}</select></div><div><label for="active-front-office">Active Front Office</label><select id="active-front-office" name="front_office">{offices}</select></div></div>
<nav class="cd-nav" aria-label="Quick navigation"><a href="/">Commissioner Desk</a><a href="/teams">Team Headquarters</a><a href="/front-offices">Front Office Intelligence</a><a href="/trades">Trade Intelligence</a><a href="/transactions">Transactions</a><a href="/matchups">Matchups</a><a href="/picks">Draft Picks</a><a href="/settings">Settings</a><a href="/api/status">API</a></nav></header>
"""


def since_last_visit(view: dict[str, Any]) -> str:
    briefing = view["briefing"]
    labels = ("Trade", "Waiver Claim", "Add", "Drop", "Draft Pick Movement", "League Event")
    counts = "".join(f'<div class="cd-count"><b>{briefing.counts.get(label, 0)}</b><span>{escape(label)}s</span></div>' for label in labels)
    events = "".join(
        f'<article class="cd-event"><time>{escape(event.occurred_at)}</time><b>{escape(event.event_type.value)}</b><p><strong>{escape(event.title)}</strong> · {escape(event.detail)}</p>{f"<a href=\"/transactions?q={quote(event.source_id)}\">Open</a>" if event.source_id else ""}</article>'
        for event in briefing.events[:12]
    ) or '<div class="cd-empty"><b>No verified changes in this briefing window.</b><br>DTOS will surface new cached league activity here after the next visit or synchronization.</div>'
    unavailable = "".join(f"<li>{escape(item)}</li>" for item in briefing.unavailable)
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What changed?</h2><p>Since your last Commissioner Desk visit · {escape(briefing.since_label)}</p></div><span class="cd-chip">Objective cached events</span></div><div class="cd-counts">{counts}</div><div class="cd-events">{events}</div><details class="cd-card"><summary>Data not yet available</summary><ul class="cd-unavailable">{unavailable}</ul></details></section>'


def league_headlines(view: dict[str, Any]) -> str:
    cards = "".join(f'<article class="cd-card cd-headline"><span class="cd-kicker">{escape(item.category)}</span><h3>{escape(item.title)}</h3><p>{escape(item.detail)}</p><p class="cd-evidence">Evidence: {escape(item.evidence)}</p></article>' for item in view["headlines"])
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What matters?</h2><p>Around the League · deterministic headlines only</p></div><span class="cd-chip">No speculation</span></div><div class="cd-headlines">{cards or "<div class=\"cd-empty\">No verified league headlines are available.</div>"}</div></section>'


def front_office_summary(view: dict[str, Any]) -> str:
    office = view["active_front_office"]
    summary = view["front_office_summary"]
    current = summary["current_outlook"]
    future = summary["future_outlook"]
    depth = summary["depth"]
    assets = summary["asset_health"]
    return f"""
<section class="cd-section"><div class="cd-section-head"><div><h2>Your Front Office</h2><p>{escape(office.owner_name)} · {escape(office.team_name)}</p></div><a class="cd-chip" href="/teams/{office.roster_id}">Open Team Headquarters</a></div>
<div class="cd-office"><article class="cd-card cd-office-main"><span class="cd-kicker">Current Championship Outlook</span><div class="cd-grade">{escape(current.grade)} · {current.score}</div><p>{escape(current.summary)}</p><span class="cd-status">{escape(summary['competitive_window'])}</span><details><summary>Show Window Reasoning</summary><p>{escape(summary['window_explanation'])}</p></details></article>
<article class="cd-card cd-metric"><span>Future Outlook</span><b>{escape(future.grade)} · {future.score}</b><p>Evaluated independently from current results</p></article><article class="cd-card cd-metric"><span>Record</span><b>{escape(summary['record'])}</b><p>Current Sleeper record</p></article><article class="cd-card cd-metric"><span>Power Ranking</span><b>#{summary['power_ranking']}</b><p>Current standings order</p></article><article class="cd-card cd-metric"><span>Depth Analysis</span><b>{escape(depth.grade)} · {depth.score}</b><p>Core position coverage</p></article><article class="cd-card cd-metric"><span>Asset Health</span><b>{escape(assets.grade)} · {assets.score}</b><p>Draft capital, flexibility, and balance</p></article></div></section>
"""


def recommendation_panel(view: dict[str, Any]) -> str:
    icons = {RecommendationPriority.HIGH: "🔴", RecommendationPriority.MEDIUM: "🟡", RecommendationPriority.LOW: "🟢"}
    cards = []
    for recommendation in view["recommendations"]:
        metrics = "".join(f"<li>{escape(metric)}</li>" for metric in recommendation.supporting_metrics)
        cards.append(
            f'<article class="cd-card cd-rec"><div class="cd-priority {recommendation.priority.value.lower()}">{icons[recommendation.priority]} {escape(recommendation.priority.value)} Priority<br><span>{escape(recommendation.category.value)}</span></div><div><h3>{escape(recommendation.title)}</h3><p>{escape(recommendation.summary)}</p></div><div class="cd-confidence"><b>{recommendation.confidence.value}%</b><span class="muted">Confidence</span></div><details><summary>Show Reasoning</summary><div class="cd-reason"><p>{escape(recommendation.reasoning)}</p><b>Supporting data</b><ul>{metrics}</ul><p>Future explanation hook: {escape(str(recommendation.future_explanation_hook.get("engine") or "unassigned"))}</p></div></details></article>'
        )
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What should I do?</h2><p>Prioritized Front Office recommendations for {escape(view["active_front_office"].owner_name)}</p></div><span class="cd-chip">Confidence + evidence</span></div><div class="cd-recommendations">{"".join(cards)}</div></section>'


def unified_recommendation_panel(view: dict[str, Any]) -> str:
    recommendation = view["unified_recommendation"]
    supporting = "".join(f"<li>{escape(item)}</li>" for item in recommendation.why)
    counterarguments = "".join(f"<li>{escape(item)}</li>" for item in recommendation.why_not)
    assumptions = "".join(f"<li>{escape(item)}</li>" for item in recommendation.assumptions)
    changes = "".join(f"<li>{escape(item)}</li>" for item in recommendation.change_conditions)
    sources = " / ".join(recommendation.sources)
    card = f'<article class="cd-card cd-rec"><div class="cd-priority {escape(recommendation.priority.lower())}">{escape(recommendation.priority)} Priority<br><span>Unified Intelligence</span></div><div><h3>{escape(recommendation.title)}</h3><p>{escape(recommendation.recommendation)}</p></div><div class="cd-confidence"><b>{recommendation.confidence.score}%</b><span class="muted">{escape(recommendation.confidence.level)} Confidence</span></div><details><summary>Show Reasoning</summary><div class="cd-reason"><p><b>Current:</b> {escape(recommendation.current_outlook)}</p><p><b>Future:</b> {escape(recommendation.future_outlook)}</p><b>Why</b><ul>{supporting}</ul><b>Why not</b><ul>{counterarguments}</ul><b>Assumptions</b><ul>{assumptions}</ul><b>What could change this</b><ul>{changes}</ul><p>Sources: {escape(sources)}</p></div></details></article>'
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>What should I do?</h2><p>One unified recommendation for {escape(view["active_front_office"].owner_name)}</p></div><span class="cd-chip">Four engines / one answer</span></div><div class="cd-recommendations">{card}</div></section>'


def league_intelligence(view: dict[str, Any]) -> str:
    intelligence = view["league_intelligence"]
    values = (
        ("Average Roster Age", intelligence["average_roster_age"] if intelligence["average_roster_age"] is not None else "Unavailable"),
        ("Draft Capital Concentration", f'{intelligence["draft_concentration"]}%' if intelligence["draft_concentration"] is not None else "Unavailable"),
        ("Recent Transactions", intelligence["recent_activity"]), ("Foundation Contenders", intelligence["contenders"]),
        ("Foundation Rebuilders", intelligence["rebuilders"]), ("Trending Up", intelligence["trending_up"]), ("Trending Down", intelligence["trending_down"]),
    )
    cards = "".join(f'<article class="cd-card cd-intel"><span>{escape(label)}</span><b>{escape(str(value))}</b></article>' for label, value in values)
    return f'<section class="cd-section"><div class="cd-section-head"><div><h2>League Intelligence</h2><p>Current structure and activity, with historical limits disclosed</p></div></div><div class="cd-intelligence">{cards}</div></section>'


def league_snapshot(view: dict[str, Any]) -> str:
    snapshot = view["snapshot"]
    standings = "".join(f'<div class="cd-mini-row"><b>#{rank} {escape(team["team_name"])}</b><span>{team["wins"]}-{team["losses"]}-{team["ties"]} · {team["points_for"]:.2f} PF</span></div>' for rank, team in enumerate(snapshot["standings"], 1))
    transactions = "".join(f'<div class="cd-mini-row"><b>{escape(item["type_label"])}</b><span>{escape(item["timestamp"])}</span></div>' for item in snapshot["transactions"]) or '<p class="muted">No cached transactions.</p>'
    matchups = []
    for matchup_id, sides in sorted(snapshot["matchups"].items(), key=lambda item: str(item[0])):
        names = " vs ".join(escape(str(side.get("team") or "TBD")) for side in sides)
        matchups.append(f'<div class="cd-mini-row"><b>Matchup {escape(str(matchup_id))}</b><span>{names}</span></div>')
    leader = snapshot["leader"]
    leaders = f'<div class="cd-mini-row"><b>Standings Leader</b><span>{escape(str(leader.get("team_name"))) if leader else "Unavailable"}</span></div>'
    health = snapshot["health"]
    health_html = f'<div class="cd-mini-row"><b>{escape(health["status"])}</b><span>Last sync {escape(health["last_sync"])}</span></div>' + (f'<p class="warn">{escape(health["error"])}</p>' if health["error"] else "")
    sections = (("Standings", standings), ("Recent Transactions", transactions), ("Upcoming Matchups", "".join(matchups) or '<p class="muted">No matchup assignments.</p>'), ("League Leaders", leaders), ("League Health", health_html))
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
        + league_headlines(view)
        + front_office_summary(view)
        + unified_recommendation_panel(view)
        + league_intelligence(view)
        + league_snapshot(view)
        + league_personality(view)
        + '<p class="cd-footer-note">Facts before interpretation · Explainable recommendations · Uncertainty disclosed</p></div>'
        + PERSISTENCE_SCRIPT
    )
