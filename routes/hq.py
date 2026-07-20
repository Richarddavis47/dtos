"""DTOS HQ dashboard routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_hq_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the Front Office HQ router using shared app dependencies."""
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def home() -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        league = data["league"]
        teams = data["teams"]
        nfl = data["nfl_state"]
        leader = teams[0] if teams else None

        standings_rows = "".join(
            f'<tr><td>{rank}</td><td><b>{escape(team["team_name"])}</b></td>'
            f'<td>{escape(team["owner"])}</td>'
            f'<td>{team["wins"]}-{team["losses"]}-{team["ties"]}</td>'
            f'<td>{team["points_for"]}</td></tr>'
            for rank, team in enumerate(teams, 1)
        )

        body = f"""
<section class="grid">
<div class="card"><div class="muted">League</div><div class="stat">{escape(league.get('name') or 'Day Traders')}</div><p class="muted">{len(teams)} teams · {escape(str(league.get('season') or ''))} season</p></div>
<div class="card"><div class="muted">NFL State</div><div class="stat">Week {escape(str(data['week']))}</div><p class="muted">{escape(str(nfl.get('season_type') or ''))}</p></div>
<div class="card"><div class="muted">Current Leader</div><div class="stat">{escape(leader['team_name'] if leader else '—')}</div><p class="record">{leader['wins'] if leader else 0}-{leader['losses'] if leader else 0}</p></div>
<div class="card"><div class="muted">Data Health</div><div class="stat good">Live</div><p class="muted">Scoring settings, rosters, owners, picks, matchups and transactions synced.</p></div>
</section>
<h2>Standings</h2><div class="card"><table><thead><tr><th>#</th><th>Team</th><th>Owner</th><th>Record</th><th>PF</th></tr></thead><tbody>{standings_rows}</tbody></table></div>
"""
        return page("Front Office HQ", body)

    return router
