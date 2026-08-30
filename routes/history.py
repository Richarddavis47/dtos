"""Minimal, honest historical league and player views."""
from __future__ import annotations

import asyncio
from datetime import date
from html import escape
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.history import (
    data_quality,
    history_records,
    import_completeness,
    import_status,
    player_career,
    provider_coverage,
    season_archive,
    season_archive_section,
    season_index,
)

PageRenderer = Callable[[str, str], HTMLResponse]


def create_history_router(
    *, league_id: str, page: PageRenderer,
    league_resolver: Callable[[], str] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["history"])

    def selected_league() -> str:
        return league_resolver() if league_resolver else league_id

    @router.get("/history", response_class=HTMLResponse)
    async def league_history_page() -> HTMLResponse:
        selected = selected_league()
        seasons = history_records(selected, "league_season", limit=20)
        standings = history_records(selected, "season_standing", limit=100)
        quality = data_quality(selected)
        status = import_status(selected)
        completeness = import_completeness(selected)
        providers = provider_coverage()
        latest_job = status["jobs"][0] if status["jobs"] else {}
        progress = status["canonical_history_progress"]
        latest_progress = status.get("latest_job_progress") or {}
        completed_seasons = ", ".join(map(str, progress["completed_seasons"])) or "None yet"
        pending_seasons = ", ".join(map(str, progress["pending_seasons"])) or "None"
        percentage = (
            f" ({progress['percentage']}%)"
            if progress["percentage"] is not None else ""
        )
        pending_detail = (
            f'<p><b>Pending:</b> {escape(pending_seasons)} — '
            f'{escape(str(progress["pending_reason"]))}</p>'
            if progress["pending_seasons"] else ""
        )
        season_cards = "".join(
            f'<article class="card"><h3><a href="/history/{row["season"]}">{row["season"]}</a></h3><p>{escape(str(row["payload"].get("league_name") or "Sleeper League"))}</p><p class="muted">{"Current Season" if int(row["season"]) == date.today().year else "Open standings, results, draft, transactions, and player leaders."}</p></article>'
            for row in seasons["records"]
        ) or '<article class="card"><p class="muted">Historical import is waiting or no season records are available.</p></article>'
        body = f"""
<h2>League History</h2>
<p class="muted">Immutable Sleeper evidence with season-specific settings. Missing provider data remains explicitly unavailable.</p>
<div class="summary-grid"><article class="metric"><b>{seasons['count']}</b><span>Seasons</span></article><article class="metric"><b>{standings['count']}</b><span>Standing Records</span></article><article class="metric"><b>{quality['blocking_count']}</b><span>Blocking Issues</span></article><article class="metric"><b>{escape(progress['status'])}</b><span>Enrichment Status</span></article></div>
<div class="card"><h3>Historical Import Reliability</h3><p><b>Historical coverage:</b> {escape(progress['display_status'])} <code>{escape(progress['status'])}</code></p><p><b>Progress:</b> {progress['completed_steps']}/{progress['total_steps']} seasons{percentage}</p><p><b>Completed:</b> {escape(completed_seasons)}</p>{pending_detail}<p><b>Current refresh job:</b> {escape(str(latest_progress.get('current_season') or latest_job.get('current_season') or 'waiting'))} {escape(str(latest_progress.get('current_data_type') or 'player_week'))} Â· {latest_progress.get('completed_steps', 0)}/{latest_progress.get('total_steps', 0)} {escape(str(latest_progress.get('status') or 'waiting'))}</p><p><b>Foundation import:</b> {escape(str(completeness['status']).title())}</p><p><b>Overall historical readiness:</b> {escape('Ready with expected current-season evidence pending' if progress['status'] == 'completed_with_pending' else progress['display_status'])}</p><p class="muted">Current segment: {escape(str(progress.get('current_season') or 'waiting'))} / {escape(str(progress.get('current_data_type') or 'player_week'))}. Progress consistent: {str(progress['consistent']).lower()}. Retry count: {escape(str(latest_job.get('retry_count') or 0))}. Last progress: {escape(str(latest_job.get('last_progress_at') or 'No persisted progress yet'))}.</p><p>Provider coverage: {escape(', '.join(item['name'] for item in providers['providers']))}</p></div>
<h3>Season Memory</h3><div class="grid">{season_cards}</div>
<p><a class="btn" href="/api/crawl/history">Open Historical API</a> <a class="btn" href="/api/history/coverage">Historical Coverage</a> <a class="btn" href="/search">Search Historical Assets</a></p>
"""
        return page("League History", body)

    @router.get("/api/history/seasons")
    async def history_season_index() -> dict:
        return season_index(selected_league())

    @router.get("/api/history/seasons/{season}")
    async def history_season_api(season: int) -> dict:
        archive = await asyncio.to_thread(season_archive, selected_league(), season)
        if not archive["standings"] and not archive["weeks"]:
            raise HTTPException(404, "No historical season evidence is available.")
        return archive

    @router.get("/api/history/seasons/{season}/standings")
    async def history_season_standings(season: int) -> dict:
        section = await asyncio.to_thread(
            season_archive_section, selected_league(), season, "standings",
        )
        return {"season": season, "standings": section["standings"]}

    @router.get("/api/history/seasons/{season}/playoffs")
    async def history_season_playoffs(season: int) -> dict:
        section = await asyncio.to_thread(
            season_archive_section, selected_league(), season, "playoffs",
        )
        return {"season": season, "playoffs": {
            "result": section["result"], "brackets": section["brackets"],
        }}

    @router.get("/api/history/seasons/{season}/weeks")
    async def history_season_weeks(season: int) -> dict:
        section = await asyncio.to_thread(
            season_archive_section, selected_league(), season, "weeks",
        )
        return {"season": season, "weeks": section["weeks"]}

    @router.get("/api/history/seasons/{season}/transactions")
    async def history_season_transactions(season: int) -> dict:
        section = await asyncio.to_thread(
            season_archive_section, selected_league(), season, "transactions",
        )
        return {"season": season, "transactions": section["records"]}

    @router.get("/api/history/seasons/{season}/draft")
    async def history_season_draft(season: int) -> dict:
        section = await asyncio.to_thread(
            season_archive_section, selected_league(), season, "draft",
        )
        return {"season": season, "draft": {
            "drafts": section["drafts"], "picks": section["picks"],
        }}

    @router.get("/api/history/seasons/{season}/leaders")
    async def history_season_leaders(season: int) -> dict:
        section = await asyncio.to_thread(
            season_archive_section, selected_league(), season, "leaders",
        )
        return {"season": season, "leaders": section["leaders"]}

    @router.get("/history/{season:int}", response_class=HTMLResponse)
    async def history_season_page(season: int) -> HTMLResponse:
        archive = await history_season_api(season)
        standings = "".join(
            "<tr>"
            f'<td><span class="podium-rank">#{row.get("rank") or "—"}</span></td>'
            f'<td><a href="/history/team/{escape(str(row.get("franchise_id") or ""))}">{escape(row["team_name"])}</a></td>'
            f'<td>{escape(row["gm_name"])}</td>'
            f'<td>{row.get("wins") if row.get("wins") is not None else "—"}-{row.get("losses") if row.get("losses") is not None else "—"}</td>'
            f'<td>{row.get("points_for") if row.get("points_for") is not None else "Unavailable"}</td>'
            f'<td>{row.get("points_against") if row.get("points_against") is not None else "Unavailable"}</td>'
            f'<td>{row.get("postseason_finish") or "—"}</td></tr>'
            for row in archive["standings"]
        )
        weeks = "".join(
            f'<details><summary>Week {week["week"]} — {len(week["matchups"])} matchups</summary>'
            + "".join(
                "<p>" + " vs ".join(
                    f'{escape(team["team_name"])} {team.get("score") if team.get("score") is not None else "Unavailable"}'
                    for team in matchup["teams"]
                ) + "</p>"
                for matchup in week["matchups"]
            ) + "</details>"
            for week in archive["weeks"]
        ) or '<p class="muted">Weekly matchup evidence is unavailable.</p>'
        leaders = "".join(
            f'<li><a href="/history/player/{escape(row["player_id"])}">{escape(row["player_name"])}</a> — {escape(str(row.get("position") or "Unknown"))} — {row["fantasy_points"]}</li>'
            for row in archive["leaders"][:12]
        ) or '<li>Historical player scoring is unavailable.</li>'
        champion = archive.get("champion") or {}
        runner_up = archive.get("runner_up") or {}
        status_detail = ", ".join(
            name.replace("_", " ").title()
            for name, available in archive["availability"].items() if available
        ) or "No supported historical segments are available."
        body = f"""
<a class="back" href="/history">← History Index</a><h2>{season} Season Archive</h2>
<p><b>Status:</b> {escape(archive['display_status'])}</p><p class="muted">{escape(status_detail)}</p>
<div class="summary-grid"><article class="metric"><b class="{'status-trophy' if champion.get('team_name') else ''}">{escape(str(champion.get('team_name') or 'Pending / unavailable'))}</b><span>Champion</span></article><article class="metric"><b>{escape(str(runner_up.get('team_name') or 'Pending / unavailable'))}</b><span>Runner-up</span></article><article class="metric"><b>{archive['counts']['matchups']}</b><span>Matchups</span></article><article class="metric"><b>{archive['counts']['transactions']}</b><span>Transactions</span></article></div>
<section class="card"><h3>Final Standings</h3><table><thead><tr><th>Rank</th><th>Team</th><th>GM</th><th>Record</th><th>PF</th><th>PA</th><th>Postseason</th></tr></thead><tbody>{standings}</tbody></table></section>
<section class="card"><h3>Weekly Results</h3>{weeks}</section>
<section class="card"><h3>Season Leaders</h3><ol>{leaders}</ol></section>
<div class="grid"><article class="card"><h3>Draft</h3><p>{archive['counts']['draft_picks']} recorded selections.</p><a href="/api/history/seasons/{season}/draft">Open draft archive</a></article><article class="card"><h3>Transactions</h3><p>{archive['counts']['transactions']} recorded moves.</p><a href="/api/history/seasons/{season}/transactions">Open transaction archive</a></article><article class="card"><h3>Postseason</h3><p>{'Verified results available.' if archive['availability']['playoffs'] else 'Verified bracket results unavailable.'}</p><a href="/api/history/seasons/{season}/playoffs">Open postseason evidence</a></article></div>
"""
        return page(f"{season} Season Archive", body)

    @router.get("/history/player/{player_id}", response_class=HTMLResponse)
    async def player_history_page(player_id: str) -> HTMLResponse:
        career = player_career(selected_league(), player_id)
        if not career["weekly_record_count"]:
            raise HTTPException(404, "No historical player observations are available.")
        seasons = "".join(
            f'<article class="card"><h3>{escape(season)}</h3><p><b>{summary["season_total"]}</b> points · {summary["points_per_game"]} PPG</p><p>Floor {summary["floor"]} · Ceiling {summary["ceiling"]} · Consistency {summary["consistency_score"]}</p></article>'
            for season, summary in career["seasons"].items()
        )
        return page(
            f"{career.get('player_name') or 'Player'} — Historical Performance",
            f'<a class="back" href="/players/{escape(player_id)}">← Back to connected Player Dossier</a><h2>Historical Performance</h2><p class="muted">Weekly gaps are not connected or converted to zero.</p><div class="grid">{seasons}</div><div class="card"><h3>Usage</h3><p>{escape(career["usage"]["reason"])}</p></div>',
        )

    @router.get("/history/team/{franchise_id:path}", response_class=HTMLResponse)
    async def team_history_page(franchise_id: str) -> HTMLResponse:
        selected = selected_league()
        snapshots = history_records(selected, "team_intelligence_snapshot", franchise_id=franchise_id, limit=100)
        identities = history_records(selected, "franchise_identity", franchise_id=franchise_id, limit=100)
        if not snapshots["count"] and not identities["count"]:
            raise HTTPException(404, "No historical franchise observations are available.")
        names = "".join(
            f'<li>{row["season"]}: {escape(str(row["payload"].get("dtos_display_name")))}</li>'
            for row in identities["records"]
        )
        trajectory = "".join(
            f'<article class="card"><h3>{row["season"]} Week {row["week"]}</h3><p>{escape(str(row["payload"].get("current_window")))}</p></article>'
            for row in snapshots["records"]
        ) or '<article class="card"><p class="muted">No Team Intelligence snapshots exist for this historical roster state.</p></article>'
        current_name = next((str(row["payload"].get("dtos_display_name")) for row in identities["records"] if row["payload"].get("dtos_display_name")), "Franchise")
        return page(f"{current_name} — Franchise History", f'<h2>Franchise History</h2><ul>{names}</ul><h3>Competitive Direction Over Time</h3><div class="grid">{trajectory}</div>')

    return router
