"""DTOS draft pick routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from services.asset_intelligence import build_pick_reports

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_draft_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the Draft Picks router using shared app dependencies."""
    router = APIRouter()

    @router.get("/picks", response_class=HTMLResponse)
    async def picks_page() -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        roster_names = {
            str(team["roster_id"]): team["team_name"] for team in data["teams"]
        }
        rows = []
        sorted_picks = sorted(
            data["traded_picks"],
            key=lambda item: (
                item.get("season", ""),
                item.get("round", 0),
                item.get("roster_id", 0),
            ),
        )
        for pick, report in build_pick_reports(data, sorted_picks):
            roster_id = str(pick.get("roster_id"))
            owner_id = str(pick.get("owner_id"))
            rows.append(
                f'<tr><td>{escape(str(pick.get("season", "")))}</td>'
                f'<td>{escape(str(pick.get("round", "")))}</td>'
                f'<td>{escape(roster_names.get(roster_id, roster_id))}</td>'
                f'<td>{escape(roster_names.get(owner_id, owner_id))}</td>'
                f'<td><b>{report.dynasty_value.score}/100</b><br><small>{escape(report.expected_range)}</small></td>'
                f'<td>{escape(report.risk.level)} ({report.risk.score})</td>'
                f'<td><b>{escape(report.recommendation.action)}</b><details><summary>Supporting Evidence</summary><p>{escape(report.recommendation.summary)}</p><ul>{"".join(f"<li>{escape(item.factor)}: {escape(item.observed_value)}</li>" for item in report.recommendation.evidence)}</ul></details></td></tr>'
            )

        body = (
            '<h2>Traded Draft Picks</h2><div class="card"><table><thead>'
            '<tr><th>Season</th><th>Round</th><th>Original Team</th>'
            '<th>Current Owner</th><th>Dynasty Value</th><th>Risk</th><th>Strategy</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table></div>"
        )
        return page("Draft Picks", body)

    return router
