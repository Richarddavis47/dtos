"""Team directory and Front Office Headquarters presentation routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.team_headquarters import CORE_POSITIONS, build_team_headquarters

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]

TEAM_HQ_CSS = """
<style>
.thq-header{display:flex;justify-content:space-between;gap:18px;align-items:center;background:linear-gradient(135deg,#142a43,#0b1727);border:1px solid var(--line);border-radius:18px;padding:20px;margin-bottom:15px}.thq-identity{display:flex;gap:15px;align-items:center}.thq-avatar{width:72px;height:72px;border-radius:18px;object-fit:cover;background:#1b3048;border:1px solid #39536f}.thq-avatar-fallback{display:grid;place-items:center;font-size:25px;font-weight:950;color:var(--accent)}.thq-title h2{margin:2px 0 4px}.thq-meta{display:flex;gap:8px;flex-wrap:wrap;color:var(--muted);font-size:11px}.thq-badge{display:inline-block;border:1px solid rgba(245,196,81,.55);color:var(--gold);border-radius:999px;padding:6px 10px;font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.07em}.thq-updated{text-align:right;color:var(--muted);font-size:10px;margin-top:8px}
.thq-section{margin-top:18px}.thq-section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:9px}.thq-section-head h2{margin:0}.thq-section-head span{color:var(--muted);font-size:11px}.thq-cards{display:grid;grid-template-columns:repeat(7,minmax(115px,1fr));gap:9px}.thq-kpi,.thq-grade,.thq-future{background:linear-gradient(180deg,#13243a,#0c1929);border:1px solid var(--line);border-radius:14px;padding:13px}.thq-kpi span,.thq-grade span,.thq-future span{display:block;font-size:9px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.06em}.thq-kpi b{display:block;font-size:22px;margin-top:5px}.thq-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.thq-summary article{background:#101d2d;border:1px solid var(--line);border-radius:13px;padding:13px}.thq-summary h3{font-size:11px;color:var(--accent);text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px}.thq-summary p{font-size:12px;color:#c7d2e0;margin:0;line-height:1.55}
.thq-grades{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.thq-grade-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.thq-grade h3{margin:0;font-size:13px}.thq-grade-mark{font-size:25px;font-weight:950;color:var(--accent)}.thq-grade-score{color:var(--muted);font-size:10px}.thq-grade details{margin-top:9px;border-top:1px solid var(--line);padding-top:8px}.thq-grade summary{cursor:pointer;font-size:10px;font-weight:850;color:var(--gold)}.thq-reasoning{font-size:10px;color:var(--muted);line-height:1.5}.thq-reasoning b{color:var(--text)}
.thq-dimensions{display:grid;gap:4px;margin-top:8px}.thq-dimension{display:flex;justify-content:space-between;font-size:10px;color:var(--muted)}.thq-tier{display:block;margin-top:5px;color:var(--gold);font-size:9px;font-weight:900;text-transform:uppercase}.thq-intel{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}
.thq-roster{display:grid;grid-template-columns:repeat(2,1fr);gap:11px}.thq-room{background:#101d2d;border:1px solid var(--line);border-radius:14px;overflow:hidden}.thq-room-head{display:flex;justify-content:space-between;background:#0b1727;padding:11px 13px;font-weight:900}.thq-player{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;padding:10px 13px;border-top:1px solid rgba(38,55,76,.7)}.thq-player a{font-weight:800}.thq-player-meta{font-size:10px;color:var(--muted);margin-top:3px}.thq-status{font-size:9px;font-weight:900;border:1px solid var(--line);border-radius:999px;padding:4px 7px;align-self:center}.thq-status.starter{color:var(--accent);border-color:rgba(110,231,183,.45)}
.thq-picks{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.thq-pick-year{background:#101d2d;border:1px solid var(--line);border-radius:14px;padding:13px}.thq-pick-year h3{margin:0 0 8px;color:var(--accent)}.thq-pick{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid rgba(38,55,76,.65)}.thq-pick small{display:block;color:var(--muted);margin-top:2px}.thq-performance{display:grid;grid-template-columns:repeat(6,1fr);gap:9px}.thq-timeline{display:grid;gap:8px}.thq-event{display:grid;grid-template-columns:145px 105px minmax(0,1fr) auto;gap:10px;align-items:center;background:#101d2d;border:1px solid var(--line);border-radius:12px;padding:11px 13px}.thq-event-type{font-weight:900;color:var(--accent)}.thq-event-assets{color:var(--muted);font-size:11px}.thq-event a{font-size:10px}.thq-future-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}.thq-future b{display:block;margin:8px 0 3px}.thq-future small{color:var(--muted)}.thq-actions{display:flex;gap:9px;flex-wrap:wrap}.thq-action{display:inline-block;border:1px solid var(--line);border-radius:10px;background:#172940;color:var(--text);padding:10px 13px;font-weight:850}.thq-action.placeholder{color:var(--muted);border-style:dashed;cursor:not-allowed}
@media(max-width:1100px){.thq-cards{grid-template-columns:repeat(4,1fr)}.thq-summary{grid-template-columns:repeat(2,1fr)}.thq-future-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.thq-header{display:block}.thq-header>div:last-child{margin-top:12px;text-align:left}.thq-updated{text-align:left}.thq-cards,.thq-grades,.thq-roster,.thq-picks,.thq-performance,.thq-future-grid{grid-template-columns:repeat(2,1fr)}.thq-event{grid-template-columns:1fr 1fr}.thq-event-assets{grid-column:1/-1}.thq-summary{grid-template-columns:1fr}}
@media(max-width:460px){.thq-cards,.thq-grades,.thq-roster,.thq-picks,.thq-performance,.thq-future-grid{grid-template-columns:1fr}.thq-avatar{width:58px;height:58px}}
</style>
"""


def _display(value: Any) -> str:
    return "Unavailable" if value is None else str(value)


def _player_tier(player: dict[str, Any]) -> str:
    intelligence = player.get("intelligence")
    if intelligence is None:
        return ""
    return f'<span class="thq-tier">{escape(intelligence.tier)} · {escape(intelligence.overall_grade)} · {escape(intelligence.recommended_action)}</span>'


def _asset_cards(snapshot: dict[str, Any]) -> str:
    metrics = (
        ("Total Players", snapshot["total_players"]),
        ("Draft Picks Owned", snapshot["total_picks"]),
        ("1st Round Picks", snapshot["first_round_picks"]),
        ("Average Roster Age", _display(snapshot["average_age"])),
        ("Average Starter Age", _display(snapshot["average_starter_age"])),
        ("Players Age 24 and Under", snapshot["young_players"]),
        ("Players Age 28 and Older", snapshot["veteran_players"]),
    )
    return "".join(f'<article class="thq-kpi"><span>{escape(label)}</span><b>{escape(str(value))}</b></article>' for label, value in metrics)


def _grade_cards(grades: dict[str, dict[str, Any]]) -> str:
    cards = []
    for name, grade in grades.items():
        dimensions = "".join(
            f'<div class="thq-dimension"><span>{escape(item.name)}</span><b>{escape(item.grade)}</b></div>'
            for item in grade.get("dimensions", ())
        )
        cards.append(
            f'<article class="thq-grade"><div class="thq-grade-head"><div><h3>{escape(name)}</h3><div class="thq-grade-score">{grade["score"]}/100</div></div><div class="thq-grade-mark">{escape(grade["grade"])}</div></div>'
            f'{f"<div class=\"thq-dimensions\">{dimensions}</div>" if dimensions else ""}'
            f'<details><summary>Show Reasoning</summary><div class="thq-reasoning"><p><b>Data used:</b> {escape(grade["data"])}</p><p><b>Calculation:</b> {escape(grade["calculation"])}</p><p><b>Why:</b> {escape(grade["why"])}</p></div></details></article>'
        )
    return "".join(cards)


def _decision_horizons(view: dict[str, Any]) -> str:
    decision = view["decision"]
    evaluations = (
        decision.current_outlook,
        decision.future_outlook,
        decision.depth,
        decision.asset_health,
    )
    cards = []
    for evaluation in evaluations:
        factors = "".join(
            f'<li><b>{escape(factor.name)}:</b> {escape(factor.value)} · {escape(factor.explanation)}</li>'
            for factor in evaluation.factors
        )
        limits = "".join(f"<li>{escape(item)}</li>" for item in evaluation.limitations)
        cards.append(
            f'<article class="thq-grade"><div class="thq-grade-head"><div><h3>{escape(evaluation.horizon.value)}</h3><div class="thq-grade-score">{evaluation.score}/100 · {evaluation.confidence}% confidence</div></div><div class="thq-grade-mark">{escape(evaluation.grade)}</div></div><p class="muted">{escape(evaluation.summary)}</p><details><summary>Show Reasoning</summary><div class="thq-reasoning"><b>Factors</b><ul>{factors}</ul>{f"<b>Known limitations</b><ul>{limits}</ul>" if limits else ""}</div></details></article>'
        )
    return "".join(cards)


def _roster_rooms(view: dict[str, Any]) -> str:
    labels = {"QB": "Quarterbacks", "RB": "Running Backs", "WR": "Wide Receivers", "TE": "Tight Ends"}
    rooms = []
    for position in CORE_POSITIONS:
        players = view["roster_groups"][position]
        rows = "".join(
            f'<div class="thq-player"><div><a href="/players/{quote(str(player["id"]))}">{escape(str(player["name"]))}</a>'
            f'<div class="thq-player-meta">{escape(position)} · {escape(str(player.get("team") or "Free Agent"))} · Age {escape(_display(player.get("age")))} · Bye {escape(_display(player.get("bye_week")))}</div>'
            f'{_player_tier(player)}</div>'
            f'<span class="thq-status {"starter" if player.get("roster_slot") == "Starter" else ""}">{escape(str(player.get("roster_slot") or "Bench"))}</span></div>'
            for player in players
        ) or '<div class="thq-player"><span class="muted">No players currently rostered.</span></div>'
        rooms.append(f'<section class="thq-room"><div class="thq-room-head"><span>{labels[position]}</span><span>{len(players)}</span></div>{rows}</section>')
    if view["other_players"]:
        rows = "".join(
            f'<div class="thq-player"><div><a href="/players/{quote(str(player["id"]))}">{escape(str(player["name"]))}</a><div class="thq-player-meta">{escape(str(player.get("position") or "Other"))} · {escape(str(player.get("team") or "Free Agent"))} · Age {escape(_display(player.get("age")))}</div></div><span class="thq-status">{escape(str(player.get("roster_slot") or "Bench"))}</span></div>'
            for player in view["other_players"]
        )
        rooms.append(f'<section class="thq-room"><div class="thq-room-head"><span>Other Positions</span><span>{len(view["other_players"])}</span></div>{rows}</section>')
    return "".join(rooms)


def _draft_capital(view: dict[str, Any]) -> str:
    sections = []
    for year, picks in sorted(view["picks_by_year"].items(), key=lambda item: str(item[0])):
        rows = "".join(
            f'<div class="thq-pick"><div><b>Round {int(pick.get("round") or 0)}</b><small>{"Acquired · Original owner: " + escape(str(pick.get("original_team") or "Unknown")) if pick.get("is_traded") else "Original team pick"}</small></div><span class="pill">{"Acquired" if pick.get("is_traded") else "Own"}</span></div>'
            for pick in picks
        )
        sections.append(f'<section class="thq-pick-year"><h3>{escape(str(year))}</h3>{rows}</section>')
    return "".join(sections) or '<div class="card muted">No future draft picks are available in the current league data.</div>'


def _timeline(view: dict[str, Any]) -> str:
    rows = "".join(
        f'<article class="thq-event"><time>{escape(event["timestamp"])}</time><span class="thq-event-type">{escape(event["type"])}</span><span class="thq-event-assets">{escape(event["actions"])} · {escape(", ".join(str(asset["label"]) for asset in event["assets"]) or "No asset detail available")}</span><a href="/transactions?q={quote(str(event["id"]))}">View</a></article>'
        for event in view["timeline"]
    )
    return rows or '<div class="card muted">No recent cached transactions involve this team.</div>'


def create_teams_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    state: dict[str, Any],
    page: PageRenderer,
) -> APIRouter:
    """Create Team directory and Headquarters routes."""
    router = APIRouter(tags=["teams"])

    @router.get("/teams", response_class=HTMLResponse)
    async def teams_page() -> HTMLResponse:
        await ensure_fresh()
        teams = require_data()["teams"]
        cards = []
        for rank, team in enumerate(teams, 1):
            starters = sum(player.get("roster_slot") == "Starter" for player in team.get("players") or [])
            firsts = team.get("pick_counts", {}).get("1", 0)
            cards.append(
                f'<a class="card team team-link" href="/teams/{team["roster_id"]}"><div class="team-head"><div><div class="identity-kicker">Owner: {escape(team["owner"])}</div><h3 class="franchise-name">{escape(team["team_name"])}</h3></div><div class="rank-badge">#{rank}</div></div><p class="record">{team["wins"]}-{team["losses"]}-{team["ties"]}</p><div class="summary-grid"><div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div><div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div><div class="metric"><b>{len(team["players"])}</b><span>Players</span></div><div class="metric"><b>{firsts}</b><span>Future 1sts</span></div></div><p class="muted">{starters} starters · {len(team.get("picks_owned", []))} total future picks</p></a>'
            )
        return page("Teams", '<h2>League Franchises</h2><p class="muted">Select a team to open its Front Office Headquarters.</p><div class="grid">' + "".join(cards) + "</div>")

    @router.get("/teams/{roster_id}", response_class=HTMLResponse)
    async def team_detail_page(roster_id: int) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        view = build_team_headquarters(data, roster_id, state.get("last_sync"))
        if view is None:
            raise HTTPException(404, "Team not found")
        team = view["team"]
        avatar = (
            f'<img class="thq-avatar" src="https://sleepercdn.com/avatars/thumbs/{quote(str(team["avatar"]))}" alt="{escape(team["team_name"])} logo">'
            if team.get("avatar")
            else f'<div class="thq-avatar thq-avatar-fallback">{escape("".join(part[:1] for part in team["team_name"].split()[:2]).upper() or "DT")}</div>'
        )
        summary = "".join(f'<article><h3>{escape(label)}</h3><p>{escape(text)}</p></article>' for label, text in view["summary"].items())
        performance = view["performance"]
        performance_cards = "".join(
            f'<article class="thq-kpi"><span>{escape(label)}</span><b>{escape(str(value))}</b></article>'
            for label, value in (
                ("Record", performance["record"]), ("Points For", f'{performance["points_for"]:.2f}'),
                ("Points Against", f'{performance["points_against"]:.2f}'), ("Max PF", f'{performance["max_points"]:.2f}'),
                ("Current Streak", performance["streak"]), ("League Standing", performance["standing"]),
            )
        )
        future = "".join(
            f'<article class="thq-future"><span>{escape(label)}</span><b>{escape(value)}</b><small>{escape(note)}</small></article>'
            for label, value, note in (
                ("Competitive Window", view["decision"].window.value, "Decision Engine v1"),
                ("Current Outlook", f'{view["decision"].current_outlook.score}/100', "Decision Engine v1"),
                ("Future Outlook", f'{view["decision"].future_outlook.score}/100', "Decision Engine v1"),
                ("Organization", view["front_office_intelligence"].competitive_window, "Front Office Intelligence v1"),
                ("Youth Grade", view["grades"]["Youth"]["grade"] + " foundation", "Deterministic roster age model"),
                ("Draft Capital Grade", view["grades"]["Draft Capital"]["grade"] + " foundation", "Deterministic pick inventory model"),
            )
        )
        roster = view["roster_intelligence"]
        intelligence_cards = "".join(
            f'<article class="thq-kpi"><span>{escape(label)}</span><b>{escape(_display(value))}</b></article>'
            for label, value in (
                ("Team Identity", roster.identity),
                ("Strongest Position", roster.strongest_position),
                ("Weakest Position", roster.weakest_position),
                ("Elite Assets", roster.metrics["Elite Assets"]),
                ("Trade Chips", roster.metrics["Trade Chips"]),
                ("Roster Flexibility", f'{roster.metrics["Roster Flexibility"]}/100'),
                ("Weekly Ceiling", f'{roster.metrics["Weekly Ceiling"]}/100'),
                ("Weekly Floor", f'{roster.metrics["Weekly Floor"]}/100'),
                ("Positional Balance", f'{roster.metrics["Positional Balance"]}/100'),
                ("Positional Advantages", ", ".join(roster.positional_advantages) or "None identified"),
            )
        )
        league_rankings = "".join(
            f'<article class="thq-kpi"><span>{escape(label)}</span><b>#{rank} of {roster.rooms["QB"].league_size}</b></article>'
            for label, rank in roster.metrics["League Rankings"].items()
        )
        body = f"""
{TEAM_HQ_CSS}
<a class="back" href="/teams">← All Teams</a>
<header class="thq-header"><div class="thq-identity">{avatar}<div class="thq-title"><div class="identity-kicker">Owner: {escape(team['owner'])}</div><h2>{escape(team['team_name'])}</h2><div class="thq-meta"><span>Record {performance['record']}</span><span>·</span><span>League Rank #{view['rank']}</span></div></div></div><div><span class="thq-badge">{escape(view['decision'].window.value)}</span><div class="thq-updated">Last Updated<br><b>{escape(view['last_updated'])}</b></div></div></header>
<section class="thq-section"><div class="thq-section-head"><h2>Asset Snapshot</h2><span>Objective roster and pick inventory</span></div><div class="thq-cards">{_asset_cards(view['snapshot'])}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Front Office Summary</h2><span>Deterministic · No generated claims</span></div><div class="thq-summary">{summary}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Decision Horizons</h2><span>Current and future remain independent</span></div><div class="thq-grades">{_decision_horizons(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Roster Intelligence</h2><span>{escape(roster.identity)} · {escape(roster.identity_reasoning)}</span></div><div class="thq-intel">{intelligence_cards}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>League Value Rankings</h2><span>Independent dimensions · No combined overall rank</span></div><div class="thq-intel">{league_rankings}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Position Room Intelligence</h2><span>Quality-first, explainable evaluation</span></div><div class="thq-grades">{_grade_cards(view['grades'])}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Roster</h2><span>Position rooms and current lineup designation</span></div><div class="thq-roster">{_roster_rooms(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Draft Capital</h2><span>Every currently owned future pick</span></div><div class="thq-picks">{_draft_capital(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Current Team Performance</h2><span>Sleeper league data</span></div><div class="thq-performance">{performance_cards}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Team Timeline</h2><span>Newest cached activity first</span></div><div class="thq-timeline">{_timeline(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Future Outlook</h2><span>Stable integration points for future intelligence</span></div><div class="thq-future-grid">{future}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Quick Actions</h2></div><div class="thq-actions"><a class="thq-action" href="/transactions?team={team['roster_id']}">Transactions</a><a class="thq-action" href="/front-offices?front_office={team['roster_id']}">Front Office Dossier</a><a class="thq-action" href="/trades?front_office={team['roster_id']}">Trade Intelligence</a><span class="thq-action placeholder" aria-disabled="true">Compare Teams · Coming Soon</span><span class="thq-action placeholder" aria-disabled="true">League History · Coming Soon</span></div></section>
"""
        return page(team["team_name"], body)

    return router
