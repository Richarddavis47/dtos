"""Minimal, honest historical league and player views."""
from __future__ import annotations

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
)

PageRenderer = Callable[[str, str], HTMLResponse]


def create_history_router(*, league_id: str, page: PageRenderer) -> APIRouter:
    router = APIRouter(tags=["history"])

    @router.get("/history", response_class=HTMLResponse)
    async def league_history_page() -> HTMLResponse:
        seasons = history_records(league_id, "league_season", limit=20)
        standings = history_records(league_id, "season_standing", limit=100)
        quality = data_quality(league_id)
        status = import_status(league_id)
        completeness = import_completeness(league_id)
        providers = provider_coverage()
        latest_job = status["jobs"][0] if status["jobs"] else {}
        progress = (
            round(
                100 * latest_job.get("completed_steps", 0)
                / latest_job["total_steps"],
            )
            if latest_job.get("total_steps") else None
        )
        season_cards = "".join(
            f'<article class="card"><h3>{row["season"]}</h3><p>{escape(str(row["payload"].get("league_name") or "Sleeper League"))}</p><p class="muted">Scoring and roster settings preserved with provenance.</p></article>'
            for row in seasons["records"]
        ) or '<article class="card"><p class="muted">Historical import is waiting or no season records are available.</p></article>'
        body = f"""
<h2>League History</h2>
<p class="muted">Immutable Sleeper evidence with season-specific settings. Missing provider data remains explicitly unavailable.</p>
<div class="summary-grid"><article class="metric"><b>{seasons['count']}</b><span>Seasons</span></article><article class="metric"><b>{standings['count']}</b><span>Standing Records</span></article><article class="metric"><b>{quality['blocking_count']}</b><span>Blocking Issues</span></article><article class="metric"><b>{escape(str(status['latest'].get('status')))}</b><span>Import Status</span></article></div>
<div class="card"><h3>Historical Import Reliability</h3><p><b>{escape(completeness['status'])}</b> · {escape(str(progress if progress is not None else 'Unknown'))}% step progress</p><p class="muted">Current segment: {escape(str(latest_job.get('current_season') or 'waiting'))} / {escape(str(latest_job.get('current_data_type') or 'waiting'))}. Retry count: {escape(str(latest_job.get('retry_count') or 0))}. Last progress: {escape(str(latest_job.get('last_progress_at') or 'No persisted progress yet'))}.</p><p>Provider coverage: {escape(', '.join(item['name'] for item in providers['providers']))}</p></div>
<h3>Season Memory</h3><div class="grid">{season_cards}</div>
<p><a class="btn" href="/api/crawl/history">Open Historical API</a></p>
"""
        return page("League History", body)

    @router.get("/history/player/{player_id}", response_class=HTMLResponse)
    async def player_history_page(player_id: str) -> HTMLResponse:
        career = player_career(league_id, player_id)
        if not career["weekly_record_count"]:
            raise HTTPException(404, "No historical player observations are available.")
        seasons = "".join(
            f'<article class="card"><h3>{escape(season)}</h3><p><b>{summary["season_total"]}</b> points · {summary["points_per_game"]} PPG</p><p>Floor {summary["floor"]} · Ceiling {summary["ceiling"]} · Consistency {summary["consistency_score"]}</p></article>'
            for season, summary in career["seasons"].items()
        )
        return page(
            f"{career.get('player_name') or 'Player'} — Historical Performance",
            f'<h2>Historical Performance</h2><p class="muted">Weekly gaps are not connected or converted to zero.</p><div class="grid">{seasons}</div><div class="card"><h3>Usage</h3><p>{escape(career["usage"]["reason"])}</p></div>',
        )

    @router.get("/history/team/{franchise_id:path}", response_class=HTMLResponse)
    async def team_history_page(franchise_id: str) -> HTMLResponse:
        snapshots = history_records(league_id, "team_intelligence_snapshot", franchise_id=franchise_id, limit=100)
        identities = history_records(league_id, "franchise_identity", franchise_id=franchise_id, limit=100)
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
