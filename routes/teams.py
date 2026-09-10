"""Team directory and Front Office Headquarters presentation routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from config import LEAGUE_ID
from services.team_headquarters import CORE_POSITIONS, build_team_directory, build_team_headquarters
from src.core.historical_memory.read_model import historical_graph
from src.core.history_context import canonical_history_store
from src.core.request_execution import run_manager_read
from src.ui import player_summary, recommendation_panel

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]

TEAM_HQ_CSS = """
<style>
.thq-header{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:22px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);margin-bottom:20px}
.thq-identity{display:flex;align-items:center;gap:16px;min-width:0}
.thq-avatar{width:88px;height:88px;border-radius:18px;object-fit:cover;background:var(--surface-interactive);flex-shrink:0}
.thq-avatar-fallback{display:grid;place-items:center;color:var(--accent);font-size:26px;font-weight:700}
.thq-title{min-width:0}.thq-title h2{font-size:clamp(25px,3vw,38px);letter-spacing:-.035em;margin:6px 0}
.thq-meta{display:flex;gap:8px;flex-wrap:wrap;color:var(--text-secondary);font-size:13px}
.thq-badge{display:inline-flex;padding:6px 10px;border:1px solid #5d663e;border-radius:999px;color:var(--gold);font-size:12px;font-weight:650}
.thq-updated{color:var(--muted);font-size:11px;margin-top:10px;text-align:right}
.thq-section{margin:28px 0}
.thq-section-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:12px}
.thq-section-head h2{font-size:22px;margin:0}.thq-section-head span{font-size:12px;color:var(--muted)}
.thq-starters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.thq-starters>.card{padding:12px}
.thq-cards,.thq-performance,.thq-intel{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.thq-kpi,.thq-grade,.thq-future{padding:14px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);min-width:0}
.thq-kpi span,.thq-future span{display:block;font-size:12px;color:var(--muted);line-height:1.4}
.thq-kpi b{display:block;margin-top:8px;font-size:24px;font-weight:650;color:var(--blue);line-height:1.25;overflow-wrap:anywhere}
.thq-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.thq-summary article{padding:16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md)}
.thq-summary h3{font-size:14px;margin:0 0 8px}.thq-summary p{color:var(--text-secondary);font-size:13px;margin:0}
.thq-grades{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.thq-grade-head{display:flex;justify-content:space-between;align-items:center;gap:12px}
.thq-grade h3{font-size:15px;margin:0}.thq-grade-mark{font-size:32px;font-weight:700;color:var(--accent)}
.thq-grade-score{font-size:12px;color:var(--muted)}
.thq-grade details{margin-top:12px;border-top:1px solid var(--border);padding-top:10px}
.thq-grade summary,.thq-evidence summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-size:13px}
.thq-reasoning{font-size:13px;color:var(--text-secondary);line-height:1.6}
.thq-dimensions{display:grid;gap:6px;margin-top:8px}.thq-dimension{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--muted)}
.thq-tier{display:block;margin-top:6px;color:var(--gold);font-size:11px}
.thq-roster{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:start}
.thq-room{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden}
.thq-room-head{display:flex;justify-content:space-between;gap:10px;padding:14px;font-weight:650;background:var(--surface-elevated)}
.thq-player{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;padding:12px 14px;border-top:1px solid var(--border)}
.thq-player-meta{font-size:11px;color:var(--muted);margin-top:6px}
.thq-status{padding:4px 8px;border:1px solid var(--border);border-radius:6px;font-size:11px}
.thq-status.starter{color:var(--accent);border-color:#365334}
.thq-picks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.thq-pick-year{padding:16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg)}
.thq-pick-year h3{font-size:22px;color:var(--gold);margin:0 0 12px}
.thq-pick{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-top:1px solid var(--border)}
.thq-pick small{display:block;color:var(--muted);margin-top:4px;font-size:12px}
.thq-timeline{display:grid;gap:8px}.thq-event{display:grid;grid-template-columns:145px 100px minmax(0,1fr) auto;gap:12px;align-items:center;padding:14px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--surface)}
.thq-event-type{color:var(--accent);font-weight:650}.thq-event-assets{color:var(--text-secondary);font-size:13px}
.thq-event a{display:inline-flex;min-height:44px;align-items:center;color:var(--accent)}
.thq-future-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.thq-future b{display:block;margin:8px 0}.thq-future small{color:var(--muted)}
.thq-actions{display:flex;gap:8px;flex-wrap:wrap}
.thq-action{display:inline-flex;min-height:44px;align-items:center;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);font-weight:650}
.thq-actions .thq-action:nth-child(3){background:var(--accent);color:#0c1908}
.thq-evidence>summary{padding:12px 16px;border:1px solid var(--border);border-radius:var(--radius-md);color:var(--text-secondary)}
.thq-evidence-body{padding:16px;border:1px solid var(--border)}
.thq-recommendation{padding:18px;border-left:3px solid var(--accent);background:var(--surface)}
@media(max-width:900px){.thq-starters{grid-template-columns:repeat(2,minmax(0,1fr))}.thq-grades{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){
 .thq-header{display:block;padding:18px}.thq-header>div:last-child{margin-top:12px}
 .thq-avatar{width:72px;height:72px}.thq-title h2{font-size:26px}
 .thq-updated{text-align:left}.thq-section-head{display:block}.thq-section-head span{display:block;margin-top:4px}
 .thq-cards,.thq-performance,.thq-intel{grid-template-columns:repeat(2,minmax(0,1fr))}
 .thq-roster,.thq-picks,.thq-summary,.thq-future-grid{grid-template-columns:1fr}
 .thq-event{grid-template-columns:1fr auto}.thq-event-assets{grid-column:1/-1}
 .thq-kpi b{font-size:21px}
}
@media(max-width:460px){.thq-starters,.thq-grades{grid-template-columns:1fr}.thq-intel{grid-template-columns:1fr}}
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


def _decision_horizons(view: dict[str, Any]) -> str:
    """Supporting evidence shares the headline's exact generation, not old grades."""
    assessment = view["assessment"]
    evidence = assessment.roster_evidence
    rows = (
        ("Actual starters · projected points", evidence.actual_lineup_projection),
        ("Optimal legal lineup · projected points", evidence.optimal_lineup_projection),
        ("Projection coverage", f"{evidence.projection_covered}/{evidence.roster_count}"),
    )
    return (
        '<div class="thq-evidence-dimensions">'
        + "".join(f'<p><b>{escape(label)}:</b> {escape(str(value) if value is not None else "Unavailable")}</p>' for label, value in rows)
        + f'<p class="muted">Evidence generation: {escape(assessment.generation)}. Actual starters are not replaced by the optimizer.</p></div>'
    )


def _team_intelligence(view: dict[str, Any]) -> str:
    card = view["team_intelligence"]
    grades = (card.overall, card.market_asset_strength, card.production_quality, card.dynasty, card.starting_lineup, card.depth, *card.positions.values(), card.draft_capital, card.youth, card.future_outlook, card.roster_flexibility, card.asset_liquidity)
    return "".join(
        f'<article class="thq-grade"><div class="thq-grade-head"><div><h3>{escape(item.category)}</h3><div class="thq-grade-score">{("Unavailable — insufficient evidence" if item.score is None else f"Score {item.score}/100 · #{item.rank} of {item.league_size} · {item.percentile}th percentile")}</div></div><div class="thq-grade-mark">{escape(item.grade)}</div></div><p class="ds-grade-context">Meaning: this grade compares only the explicitly named dimension, not overall dynasty value.</p><details><summary>Show Reasoning</summary><div class="thq-reasoning"><ul>{"".join(f"<li>{escape(reason)}</li>" for reason in item.reasons or card.explanation)}</ul></div></details></article>'
        for item in grades
    )


def _roster_rooms(view: dict[str, Any]) -> str:
    labels = {"QB": "Quarterbacks", "RB": "Running Backs", "WR": "Wide Receivers", "TE": "Tight Ends"}
    rooms = []
    for position in CORE_POSITIONS:
        players = view["roster_groups"][position]
        room_grade = view["assessment"].team.positions[position].grade
        rows = "".join(
            f'<div class="thq-player"><div><a href="/players/{quote(str(player["id"]))}">{player_summary(player_id=str(player["id"]), name=str(player["name"]), position=position, nfl_team=str(player.get("team") or "Free Agent"), context=(f"Age {player.get('age')}" if player.get("age") is not None else None))}</a>'
            f'<div class="thq-player-meta">{f"Bye {escape(str(player.get('bye_week')))}" if player.get("bye_week") not in (None, "", "Unavailable") else "Player profile and recommendation available"}</div>'
            f'{_player_tier(player)}</div>'
            f'<span class="thq-status {"starter" if player.get("roster_slot") == "Starter" else ""}">{escape(str(player.get("roster_slot") or "Bench"))}</span></div>'
            for player in players
        ) or '<div class="thq-player"><span class="muted">No players currently rostered.</span></div>'
        rooms.append(f'<section class="thq-room"><div class="thq-room-head"><span>{labels[position]}</span><span>{room_grade} · {len(players)} players</span></div>{rows}</section>')
    if view["other_players"]:
        rows = "".join(
            f'<div class="thq-player"><div><a href="/players/{quote(str(player["id"]))}">{player_summary(player_id=str(player["id"]), name=str(player["name"]), position=str(player.get("position") or "Other"), nfl_team=str(player.get("team") or "Free Agent"), context=(f"Age {player.get('age')}" if player.get("age") is not None else None))}</a><div class="thq-player-meta">Player profile and recommendation available</div></div><span class="thq-status">{escape(str(player.get("roster_slot") or "Bench"))}</span></div>'
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


def _franchise_portrait(team: dict[str, Any]) -> str:
    name = str(team.get("team_name") or "Franchise")
    initials = "".join(part[:1] for part in name.split()[:2]).upper() or "DT"
    image = (f'<img src="https://sleepercdn.com/avatars/thumbs/{quote(str(team["avatar"]), safe="")}" alt="{escape(name)} logo" loading="lazy" onerror="this.hidden=true">' if team.get("avatar") else "")
    return f'<span class="franchise-portrait">{image}<span aria-hidden="true">{escape(initials)}</span></span>'


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
        data = require_data()
        teams = data["teams"]
        directory = build_team_directory(data)
        cards = []
        for team in teams:
            starters = sum(player.get("roster_slot") == "Starter" for player in team.get("players") or [])
            firsts = team.get("pick_counts", {}).get("1", 0)
            outlook = directory[int(team["roster_id"])]
            result = (f'<p class="record">Projected finish: {_display(outlook["rank"])} · Projected wins: {_display(outlook["projected_wins"])}</p>' if outlook["preseason"] else f'<p class="record">{team["wins"]}-{team["losses"]}-{team["ties"]}</p>')
            performance = (f'<div class="metric"><b>{outlook["playoff_odds"]}%</b><span>Playoff Odds</span></div><div class="metric"><b>{outlook["championship_odds"]}%</b><span>Championship Odds</span></div>' if outlook["preseason"] else f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div><div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>')
            cards.append(
                f'<a class="card team team-link" href="/teams/{team["roster_id"]}"><div class="team-head">{_franchise_portrait(team)}<div><div class="identity-kicker">Owner: {escape(team["owner"])}</div><h3 class="franchise-name">{escape(team["team_name"])}</h3></div><div class="rank-badge">{escape(outlook["grade"])}</div></div>{result}<div class="summary-grid">{performance}<div class="metric"><b>{len(team["players"])}</b><span>Players</span></div><div class="metric"><b>{firsts}</b><span>Future 1sts</span></div></div><p class="muted">{starters} starters · {len(team.get("picks_owned", []))} total future picks</p><span class="team-open">Open Team HQ <span aria-hidden="true">→</span></span></a>'
            )
        return page("Teams", '<h2>League Franchises</h2><p class="muted">Select a team to open its Front Office Headquarters.</p><div class="grid">' + "".join(cards) + "</div>")

    @router.get("/teams/{roster_id}", response_class=HTMLResponse)
    async def team_detail_page(roster_id: int) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        view = await run_manager_read(
            lambda: build_team_headquarters(
                data, roster_id, state.get("last_sync"),
            ),
        )
        if view is None:
            raise HTTPException(404, "Team not found")
        team = view["team"]
        avatar = _franchise_portrait(team)
        summary = "".join(f'<article><h3>{escape(label)}</h3><p>{escape(text)}</p></article>' for label, text in view["summary"].items())
        performance = view["performance"]
        performance_metrics = (
            (("Projected Wins", _display(view["team_intelligence"].projected_wins)), ("Power Ranking", _display(view["rank"])), ("Championship Odds", _display(view["team_intelligence"].championship_odds)), ("Playoff Odds", _display(view["team_intelligence"].playoff_odds)))
            if view["preseason"] else
            (("Record", performance["record"]), ("Points For", f'{performance["points_for"]:.2f}'), ("Points Against", f'{performance["points_against"]:.2f}'), ("Max PF", f'{performance["max_points"]:.2f}'), ("League Standing", performance["standing"]))
        )
        performance_cards = "".join(
            f'<article class="thq-kpi"><span>{escape(label)}</span><b>{escape(str(value))}</b></article>'
            for label, value in performance_metrics
        )
        future = "".join(
            f'<article class="thq-future"><span>{escape(label)}</span><b>{escape(value)}</b><small>{escape(note)}</small></article>'
            for label, value, note in (
                ("Current Outlook", _display(view["team_intelligence"].current_strength), "League-relative Team Intelligence"),
                ("Future Outlook", _display(view["team_intelligence"].future_strength), "League-relative Team Intelligence"),
                ("Projected Wins", _display(_display(view["team_intelligence"].projected_wins)), "No supported wins forecast"),
                ("Playoff Odds", _display(view["team_intelligence"].playoff_odds), "No supported probability model"),
                ("Championship Odds", _display(view["team_intelligence"].championship_odds), "No supported probability model"),
                ("Longevity Context", view["grades"]["Youth"]["grade"], "Canonical position-specific lifecycle evidence"),
                ("Future Capital", view["grades"]["Draft Capital"]["grade"], "Canonical pick evidence; not a forecast"),
            )
        )
        roster = view["roster_intelligence"]
        assessment = view["assessment"]
        intelligence_cards = "".join(
            f'<article class="thq-kpi"><span>{escape(label)}</span><b>{escape(_display(value))}</b></article>'
            for label, value in (
                ("Team Identity", assessment.team.competitive_window.classification.value),
                ("Strongest Position", max((p for p in assessment.team.positions if assessment.team.positions[p].score is not None), key=lambda p: assessment.team.positions[p].score, default='Unavailable')),
                ("Weakest Position", min((p for p in assessment.team.positions if assessment.team.positions[p].score is not None), key=lambda p: assessment.team.positions[p].score, default='Unavailable')),
                ("Elite Assets", roster.metrics["Elite Assets"]),
                ("Trade Chips", roster.metrics["Trade Chips"]),
                ("Roster Flexibility", _display(roster.metrics["Roster Flexibility"])),
                ("Projected Starter Points", assessment.projected_points),
                ("Weekly Ceiling (points)", assessment.weekly_ceiling),
                ("Weekly Floor (points)", assessment.weekly_floor),
                ("Positional Balance", _display(roster.metrics["Positional Balance"])),
                ("Positional Advantages", ", ".join(roster.positional_advantages) or "None identified"),
            )
        )
        league_rankings = "".join(
            f'<article class="thq-kpi"><span>{escape(label)}</span><b>#{rank} of {roster.rooms["QB"].league_size}</b></article>'
            for label, rank in roster.metrics["League Rankings"].items()
            if label not in {"Projected Weekly Starter Points", "Projected Floor", "Projected Ceiling"}
        )
        recommendation = view["unified_recommendation"]
        selected_league = str((data.get("league") or {}).get("league_id") or LEAGUE_ID)
        franchise_history = await run_manager_read(
            lambda: historical_graph(
                canonical_history_store, selected_league, data,
            ).franchise_history(str(team["roster_id"])),
        )
        historical_seasons = len({row["season"] for row in franchise_history["standings"]})
        historical_transactions = len(franchise_history["transactions"])
        recommendation_card = recommendation_panel(title=recommendation.title, recommendation=recommendation.recommendation, confidence=recommendation.confidence.score, primary_reason=recommendation.why[0] if recommendation.why else recommendation.current_outlook, evidence=recommendation.why, expected_impact=f"Current: {recommendation.current_outlook} Future: {recommendation.future_outlook}", action_label="Open Trade Center", action_href=f'/trades?front_office={team["roster_id"]}', limitations=recommendation.why_not)
        starters = [player for player in team.get("players") or [] if player.get("roster_slot") == "Starter"]
        starter_cards = "".join(
            f'<a class="card" href="/players/{quote(str(player.get("id") or ""))}">{player_summary(player_id=str(player.get("id") or ""), name=str(player.get("name") or "Unknown player"), position=str(player.get("position") or ""), nfl_team=str(player.get("team") or player.get("nfl_team") or "Free Agent"), context="Starter")}</a>'
            for player in starters
        ) or '<div class="ds-empty"><b>No starting lineup is available.</b>Sleeper has not supplied a current starter assignment.</div>'
        body = f"""
{TEAM_HQ_CSS}
<a class="back" href="/teams">← All Teams</a>
<header class="thq-header"><div class="thq-identity">{avatar}<div class="thq-title"><div class="identity-kicker">Owner: {escape(team['owner'])}</div><h2>{escape(team['team_name'])}</h2><div class="thq-meta"><span>Overall Grade {view['team_intelligence'].overall.grade}</span><span>·</span><span>Assessment rank {_display(view['rank'])}</span><span>·</span><span>{_display(view['team_intelligence'].overall.percentile)} percentile</span></div></div></div><div><span class="thq-badge">{escape(view['competitive_window'].classification.value)}</span><div class="thq-updated">Last Updated<br><b>{escape(view['last_updated'])}</b></div></div></header>
<section class="thq-section"><div class="thq-section-head"><h2>DTOS Team Assessment</h2><span>Answer and action first</span></div>{recommendation_card}</section>
<section class="thq-section"><div class="thq-section-head"><h2>Starting Lineup</h2><span>The players carrying this franchise now</span></div><div class="thq-starters">{starter_cards}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Strengths &amp; Needs</h2><span>Current and future league-relative evidence</span></div><div class="thq-intel">{intelligence_cards}{league_rankings}</div><p class="muted">{escape(' '.join(assessment.limitations))}</p><p class="muted">Projection week: {escape(str(assessment.projection_week or 'Unavailable'))} · Coverage: {assessment.projected_starter_count}/{assessment.starter_count} starters · As of: {escape(assessment.projection_as_of or 'Unavailable')}</p></section>
<section class="thq-section" id="assets"><div class="thq-section-head"><h2>Core Assets</h2><span>Roster construction and flexibility</span></div><div class="thq-cards">{_asset_cards(view['snapshot'])}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Full Roster</h2><span>Position rooms and current lineup designation</span></div><div class="thq-roster">{_roster_rooms(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Draft Capital</h2><span>Current pick ownership</span></div><div class="thq-picks">{_draft_capital(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>{'Preseason Outlook' if view['preseason'] else 'Current Team Performance'}</h2><span>{'Deterministic projections' if view['preseason'] else 'Sleeper league data'}</span></div><div class="thq-performance">{performance_cards}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Activity</h2><span>Newest cached transactions first</span></div><div class="thq-timeline">{_timeline(view)}</div></section>
<section class="thq-section"><div class="thq-section-head"><h2>Franchise History</h2><span>Verified Sleeper evidence across renamed teams and manager eras</span></div><div class="thq-performance"><article class="thq-kpi"><span>Imported Seasons</span><b>{historical_seasons}</b></article><article class="thq-kpi"><span>Archived Transactions</span><b>{historical_transactions}</b></article><article class="thq-kpi"><span>Identity Records</span><b>{len(franchise_history["identities"])}</b></article><article class="thq-kpi"><span>Roster Snapshots</span><b>{len(franchise_history["roster_snapshots"])}</b></article></div><p><a class="thq-action" href="/history/team/{escape(franchise_history["franchise_id"])}">Open complete franchise history</a></p></section>
<section class="thq-section"><details class="thq-evidence"><summary>Deeper Team Intelligence</summary><div class="thq-evidence-body"><div class="thq-summary">{summary}</div><h3>League-Relative Team Intelligence</h3><div class="thq-grades">{_team_intelligence(view)}</div><h3>Why DTOS Recommends This</h3><p class="muted">Supporting Evidence</p><div class="thq-grades">{_decision_horizons(view)}</div><div class="thq-future-grid">{future}</div></div></details></section>
<section class="thq-section"><div class="thq-section-head"><h2>Quick Actions</h2></div><div class="thq-actions"><a class="thq-action" href="/transactions?team={team['roster_id']}">Transactions</a><a class="thq-action" href="/front-offices?front_office={team['roster_id']}">Front Office Dossier</a><a class="thq-action" href="/trades?front_office={team['roster_id']}">Trade Intelligence</a><a class="thq-action" href="/history">League History</a></div></section>
"""
        return page(f'{team["team_name"]} Headquarters', body)

    return router
