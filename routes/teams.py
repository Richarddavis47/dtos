"""Team routes for DTOS.

This router is migrated from the v0.8.5 application without changing the
existing Teams UI or Sleeper-backed behavior.
"""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_teams_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the Teams router using shared application dependencies."""
    router = APIRouter(tags=["teams"])

    @router.get("/teams", response_class=HTMLResponse)
    async def teams_page() -> HTMLResponse:
        await ensure_fresh()
        teams = require_data()["teams"]
        cards = []
        for rank, team in enumerate(teams, 1):
            starters = sum(1 for p in team["players"] if p["roster_slot"] == "Starter")
            pos_counts = {pos: sum(1 for p in team["players"] if p["position"] == pos) for pos in ("QB", "RB", "WR", "TE")}
            firsts = team.get("pick_counts", {}).get("1", 0)
            cards.append(
                f'<a class="card team team-link" href="/teams/{team["roster_id"]}">'
                f'<div class="team-head"><div><div class="identity-kicker">Owner: {escape(team["owner"])}</div>'
                f'<h3 class="franchise-name">{escape(team["team_name"])}</h3></div><div class="rank-badge">#{rank}</div></div>'
                f'<p class="record">{team["wins"]}-{team["losses"]}-{team["ties"]}</p>'
                f'<div class="summary-grid">'
                f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div>'
                f'<div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>'
                f'<div class="metric"><b>{len(team["players"])}</b><span>Players</span></div>'
                f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
                f'</div><div class="position-strip">'
                + ''.join(f'<div class="position-count"><b>{pos_counts[pos]}</b><span>{pos}</span></div>' for pos in ("QB","RB","WR","TE"))
                + f'</div><p class="muted" style="margin-bottom:0">{starters} starters · {len(team.get("picks_owned", []))} total future picks</p></a>'
            )
        return page(
            "Teams",
            '<h2>League Franchises</h2><p class="muted">Select a team for its complete roster, draft capital and front-office summary.</p><div class="grid">'
            + "".join(cards)
            + "</div>",
        )


    @router.get("/teams/{roster_id}", response_class=HTMLResponse)
    async def team_detail_page(roster_id: int) -> HTMLResponse:
        await ensure_fresh()
        teams = require_data()["teams"]
        team = next((t for t in teams if int(t["roster_id"]) == roster_id), None)
        if not team:
            raise HTTPException(404, "Team not found")

        rank = next((i for i, t in enumerate(teams, 1) if int(t["roster_id"]) == roster_id), "—")
        pos_order = ("QB", "RB", "WR", "TE", "K", "DEF", "—")
        pos_counts = {pos: sum(1 for p in team["players"] if p["position"] == pos) for pos in ("QB", "RB", "WR", "TE")}

        roster_html = []
        for slot in ("Starter", "Bench", "IR", "Taxi"):
            slot_players = [p for p in team["players"] if p["roster_slot"] == slot]
            if not slot_players:
                continue
            if slot == "Starter":
                ordered = sorted(slot_players, key=lambda p: (p.get("starter_index") is None, p.get("starter_index") or 0))
                rows = "".join(
                    f'<div class="lineup-row"><div class="lineup-slot">{escape(p.get("starter_slot") or p["position"])}</div>'
                    f'<div class="lineup-player"><div><b>{escape(p["name"])}</b><div class="muted">{escape(p["position"])} · {escape(p["team"])}</div></div>'
                    f'<div class="lineup-meta">STARTER</div></div></div>'
                    for p in ordered
                )
                roster_html.append(
                    f'<section class="roster-section"><div class="section-title"><span class="slot-label">Starting Lineup</span>'
                    f'<span class="muted">{len(slot_players)} starters</span></div><div class="sleeper-lineup">{rows}</div></section>'
                )
                continue
            groups = []
            present_positions = [pos for pos in pos_order if any(p["position"] == pos for p in slot_players)]
            other_positions = sorted({p["position"] for p in slot_players if p["position"] not in pos_order})
            for pos in present_positions + other_positions:
                players = [p for p in slot_players if p["position"] == pos]
                rows = "".join(
                    f'<div class="player"><span class="player-name"><span class="pos-dot"></span>{escape(p["name"])}</span><span class="pill">{escape(p["position"])} · {escape(p["team"])}</span></div>'
                    for p in players
                )
                groups.append(f'<div class="position-block"><div class="position-head"><span>{escape(pos)}</span><span>{len(players)}</span></div>{rows}</div>')
            roster_html.append(
                f'<section class="roster-section"><div class="section-title"><span class="slot-label">{slot}</span>'
                f'<span class="muted">{len(slot_players)} players</span></div><div class="card players">{"".join(groups)}</div></section>'
            )

        total_picks = len(team.get("picks_owned", []))
        firsts = team.get("pick_counts", {}).get("1", 0)
        seconds = team.get("pick_counts", {}).get("2", 0)
        thirds = team.get("pick_counts", {}).get("3", 0)
        roster_size = max(1, len(team["players"]))
        # Transparent first-pass presentation metrics. These are UI summaries, not market-value models.
        position_strength = {pos: min(100, round(pos_counts[pos] / max(1, {"QB":3,"RB":8,"WR":10,"TE":4}[pos]) * 100)) for pos in ("QB","RB","WR","TE")}
        contender_score = min(99, round((position_strength["QB"] * .25 + position_strength["RB"] * .25 + position_strength["WR"] * .30 + position_strength["TE"] * .20)))
        dynasty_score = min(99, round(contender_score * .75 + min(100, total_picks * 7) * .25))
        overall_grade = "A" if contender_score >= 85 else "B" if contender_score >= 70 else "C" if contender_score >= 55 else "D"
        body = (
            f'<a class="back" href="/teams">← All Teams</a>'
            f'<section class="card"><div class="team-head"><div><div class="identity-kicker">Owner: {escape(team["owner"])}</div>'
            f'<h2 class="franchise-name">{escape(team["team_name"])}</h2><p class="owner-line">Franchise rank #{rank}</p></div>'
            f'<div class="rank-badge">#{rank}</div></div>'
            f'<div class="summary-grid">'
            f'<div class="metric"><b>{team["wins"]}-{team["losses"]}-{team["ties"]}</b><span>Record</span></div>'
            f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div>'
            f'<div class="metric"><b>{team["points_against"]:.2f}</b><span>Points Against</span></div>'
            f'<div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>'
            f'<div class="metric"><b>{len(team["players"])}</b><span>Total Players</span></div>'
            f'<div class="metric"><b>{total_picks}</b><span>Future Picks</span></div>'
            f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
            f'<div class="metric"><b>{seconds}</b><span>Future 2nds</span></div>'
            f'</div><div class="position-strip">'
            + ''.join(f'<div class="position-count"><b>{pos_counts[pos]}</b><span>{pos}</span></div>' for pos in ("QB","RB","WR","TE"))
            + '</div></section>'
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Front Office Analytics</span><span class="muted">Engine framework</span></div>'
            f'<div class="analytics-grid">'
            f'<div class="analytics-card"><b>#{rank}</b><span>Current Rank</span></div>'
            f'<div class="analytics-card"><b>{firsts}</b><span>1st-Round Assets</span></div>'
            f'<div class="analytics-card"><b>{thirds}</b><span>3rd-Round Assets</span></div>'
            f'<div class="analytics-card"><b>Coming Soon</b><span>Contender Score</span></div>'
            f'<div class="analytics-card"><b>Coming Soon</b><span>Dynasty Grade</span></div>'
            f'</div></section>'
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Team Report</span><span class="muted">At-a-glance roster profile</span></div>'
            f'<div class="team-report"><div class="report-card"><div class="grade">{overall_grade}</div><small>Overall Grade</small></div>'
            f'<div class="report-card"><div class="grade">{contender_score}</div><small>Contender Score</small></div>'
            f'<div class="report-card"><div class="grade">{dynasty_score}</div><small>Dynasty Score</small></div></div>'
            f'<div class="card">' + ''.join(
                f'<div class="progress-row"><div class="progress-label"><span>{pos} Room</span><b>{position_strength[pos]}</b></div><div class="progress-track"><div class="progress-fill" style="width:{position_strength[pos]}%"></div></div></div>'
                for pos in ("QB","RB","WR","TE")
            ) + '</div></section>'
        )

        owned_by_year = {}
        for pick in team.get("picks_owned", []):
            owned_by_year.setdefault(pick["season"], []).append(pick)
        owned_sections = []
        for season, picks in sorted(owned_by_year.items()):
            rows = "".join(
                f'<div class="pick-row {"acquired" if pick["is_traded"] else "own"}"><div><b>Round {pick["round"]}</b>'
                f'<div class="pick-origin">Original: {escape(pick["original_team"])}</div>'
                f'<div class="pick-status {"acquired" if pick["is_traded"] else "own"}">{"Acquired" if pick["is_traded"] else "Own"}</div></div>'
                f'<span class="pill">{season}</span></div>'
                for pick in sorted(picks, key=lambda item: (item["round"], item["original_team"]))
            )
            owned_sections.append(
                f'<details class="pick-year"><summary class="pick-summary"><span><b>{season}</b></span><span class="muted">{len(picks)} picks</span></summary>'
                f'<div class="card pick-list">{rows}</div></details>'
            )

        away_rows = "".join(
            f'<div class="pick-row traded-away"><div><b>{pick["season"]} Round {pick["round"]}</b>'
            f'<div class="pick-origin">Original: {escape(team["team_name"])}</div>'
            f'<div class="pick-status away">Current owner: {escape(pick["current_owner"])}</div></div>'
            f'<span class="pill">Traded</span></div>'
            for pick in sorted(team.get("picks_traded_away", []), key=lambda item: (item["season"], item["round"]))
        )
        draft_capital = (
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Draft Capital</span>'
            f'<span class="muted">Green = own · Blue = acquired · Red = traded away</span></div>'
            f'<div class="card"><div class="summary-grid">'
            f'<div class="metric"><b>{total_picks}</b><span>Total Picks</span></div>'
            f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
            f'<div class="metric"><b>{seconds}</b><span>Future 2nds</span></div>'
            f'<div class="metric"><b>{thirds}</b><span>Future 3rds</span></div></div></div>'
            f'{"".join(owned_sections)}'
            + (f'<details class="pick-year"><summary class="pick-summary"><span class="away"><b>Original Picks Traded Away</b></span><span class="muted">{len(team.get("picks_traded_away", []))} picks</span></summary>'
               f'<div class="card pick-list">{away_rows}</div></details>' if away_rows else '')
            + '</section>'
        )
        body += draft_capital + "".join(roster_html)
        return page(team["team_name"], body)


        return page(f'{left["team"]} vs {right["team"]}', body)



    return router
