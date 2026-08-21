"""Manager-first Home and League presentation routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable, Hashable

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from services.team_headquarters import build_team_directory
from services.transactions import normalize_transactions
from src.ui.intelligence_presentation import league_is_preseason, record_evidence
from src.ui.render_cache import GenerationRenderCache

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]
GenerationProvider = Callable[[], Hashable]


home_body_render_cache = GenerationRenderCache(
    "manager_home_body", max_entries=24, max_bytes=2_097_152,
)


def _section(title: str, context: str, content: str) -> str:
    return f'<section class="ux-section"><div class="ux-section-head"><h2>{escape(title)}</h2><p>{escape(context)}</p></div>{content}</section>'


def _selected_team(data: dict[str, Any], roster_id: int | None) -> dict[str, Any] | None:
    teams = data.get("teams") or []
    if roster_id is not None:
        return next((team for team in teams if int(team.get("roster_id") or 0) == roster_id), None)
    return teams[0] if teams else None


def _team_selector(data: dict[str, Any], selected: dict[str, Any] | None) -> str:
    options = "".join(
        f'<option value="{int(team.get("roster_id") or 0)}" {"selected" if selected is team else ""}>{escape(str(team.get("team_name") or team.get("owner") or "Team"))}</option>'
        for team in data.get("teams") or []
    )
    return f'<form method="get" action="/" class="card"><label for="front-office">Front office briefing</label><select id="front-office" name="front_office">{options}</select><button class="btn" type="submit">Open briefing</button></form>'


def create_home_router(
    *, ensure_fresh: EnsureFresh, require_data: RequireData, page: PageRenderer,
    generation_provider: GenerationProvider | None = None,
) -> APIRouter:
    """Create the manager briefing and league-wide hub."""
    router = APIRouter(tags=["manager-experience"])

    @router.get("/", response_class=HTMLResponse)
    async def home(front_office: int | None = Query(None)) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        retained_generation = (
            generation_provider() if generation_provider is not None
            else (str((data.get("league") or {}).get("league_id") or "default"), id(data))
        )
        generation = repr(retained_generation)
        cache_key = (retained_generation, front_office)

        def render_body() -> bytes:
            return _home_body(data, front_office).encode("utf-8")

        body = home_body_render_cache.get_or_build(
            cache_key, generation, render_body,
        ).decode("utf-8")
        return page("Home", body)

    def _home_body(data: dict[str, Any], front_office: int | None) -> str:
        teams = data.get("teams") or []
        team = _selected_team(data, front_office)
        directory = build_team_directory(data) if teams else {}
        selector = _team_selector(data, team)
        if team is None:
            return selector + '<div class="ds-empty"><b>No franchise is available.</b>The current Sleeper context has no team roster to brief.</div>'

        roster_id = int(team.get("roster_id") or 0)
        outlook = directory.get(roster_id, {})
        preseason = league_is_preseason(data)
        record = record_evidence(team.get("wins"), team.get("losses"), team.get("ties"), season_started=not preseason)
        ranking_label = "preseason outlook" if preseason else "current league outlook"
        competitive = f'#{outlook.get("rank", "—")} in the {ranking_label}' if outlook.get("rank") else f'{ranking_label.title()} not yet available'
        header = f'<article class="card ux-answer ux-competitive-header"><p class="identity-kicker">Your front office</p><h2>{escape(str(team.get("team_name") or "Franchise"))}</h2><p><b>{escape("Preseason" if preseason else record)}</b> · {escape(competitive)}</p><p class="muted">Owner: {escape(str(team.get("owner") or "Unassigned"))}{" · Week " + escape(str(data.get("week"))) if data.get("week") and not preseason else ""}</p></article>{selector}'

        actions = [
            ("Review your team direction", "See the current roster assessment, needs, and core assets.", f"/teams/{roster_id}"),
            ("Check this week's matchup", "Compare actual scoring and available projections without invented odds.", "/matchups"),
            ("Explore a trade", "Use the existing Trade Intelligence workflow for this front office.", f"/trades?front_office={roster_id}"),
        ]
        action_html = '<div class="card ux-action-list">' + "".join(
            f'<a class="ux-action" href="{href}"><span><b>{escape(title)}</b><p>{escape(reason)}</p></span><span aria-hidden="true">→</span></a>'
            for title, reason, href in actions
        ) + "</div>"

        rankings = sorted(
            ((int(team_row.get("roster_id") or 0), team_row, directory.get(int(team_row.get("roster_id") or 0), {})) for team_row in teams),
            key=lambda row: (int(row[2].get("rank") or 999), str(row[1].get("team_name") or "")),
        )[:5]
        rank_html = '<div class="grid ux-ranking-grid">' + "".join(
            f'<a class="card" href="/teams/{rid}"><b>#{view.get("rank", "—")} {escape(str(row.get("team_name") or "Team"))}</b><p class="muted">{escape("Preseason outlook" if preseason else record_evidence(row.get("wins"), row.get("losses"), row.get("ties"), season_started=True))}</p></a>'
            for rid, row, view in rankings
        ) + '</div><p><a href="/fois">Open separate FOIS general-manager rankings →</a></p>'

        matchups = []
        for matchup_id, sides in sorted((data.get("matchups") or {}).items())[:5]:
            names = " vs ".join(str(side.get("team") or "Unassigned") for side in sides[:2])
            matchups.append(f'<a class="ux-action" href="/matchups/{escape(str(matchup_id))}"><span><b>{escape(names)}</b><p>Week {escape(str(data.get("week") or "—"))} matchup</p></span><span>→</span></a>')
        matchup_html = '<div class="card ux-action-list">' + ("".join(matchups) or '<p class="muted">No current matchup pairing is available.</p>') + "</div>"

        recent = normalize_transactions(data)[:5]
        activity_html = '<div class="card">' + ("".join(
            f'<p><b>{escape(str(item.get("type_label") or "League activity"))}</b><br><span class="muted">{escape(str(item.get("timestamp") or "Time unavailable"))}</span></p>'
            for item in recent
        ) or '<p class="muted">No cached league activity is available.</p>') + '<a href="/transactions">View league activity →</a></div>'

        assets = team.get("players") or []
        assets_html = f'<div class="card"><p><b>{len(assets)}</b> rostered players · <b>{len(team.get("picks_owned") or [])}</b> future picks</p><a href="/teams/{roster_id}#assets">Review my assets →</a></div>'
        recap = (
            "The regular season has not started. DTOS is watching roster construction, recent league activity, market movement, and Week 1 preparation."
            if preseason else
            "Your current result and league position are summarized above. Recent transactions and matchup evidence provide the current front-office context."
        )
        body = (
            header
            + _section("Preseason Briefing" if preseason else "Weekly Recap", "What matters for your franchise now", f'<div class="card ux-recap"><p>{escape(recap)}</p><a href="/league">Open league briefing →</a></div>')
            + _section("What Should I Do?", "Highest-value next steps from existing intelligence", action_html)
            + _section("Rankings", ("Preseason team outlook and FOIS remain distinct" if preseason else "Current-season standings and FOIS remain distinct"), rank_html)
            + _section("This Week", "Current Sleeper matchup evidence", matchup_html)
            + _section("Market Movers", "Meaningful movement only", '<div class="card"><p class="muted">Market movement is shown only when timestamped comparable observations cross the established threshold.</p><a href="/market#market-movers">Review market evidence →</a></div>')
            + _section("League Activity", "Recent cached transactions", activity_html)
            + _section("My Assets", "Roster and draft capital", assets_html)
        )
        return body

    @router.get("/league", response_class=HTMLResponse)
    async def league() -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        teams = data.get("teams") or []
        preseason = league_is_preseason(data)
        directory = build_team_directory(data) if teams else {}
        if preseason:
            ordered = sorted(teams, key=lambda team: int(directory.get(int(team.get("roster_id") or 0), {}).get("rank") or 999))
            standings = "".join(
                f'<tr><td>{escape(str(directory.get(int(team.get("roster_id") or 0), {}).get("rank") or "—"))}</td><td><a href="/teams/{int(team.get("roster_id") or 0)}">{escape(str(team.get("team_name") or "Team"))}</a></td><td colspan="2">Preseason outlook</td></tr>'
                for team in ordered
            )
        else:
            standings = "".join(
                f'<tr><td>{index}</td><td><a href="/teams/{int(team.get("roster_id") or 0)}">{escape(str(team.get("team_name") or "Team"))}</a></td><td>{escape(record_evidence(team.get("wins"), team.get("losses"), team.get("ties"), season_started=True))}</td><td>{escape(f"{float(team['points_for']):.2f}" if team.get("points_for") is not None else "Unavailable")}</td></tr>'
                for index, team in enumerate(teams, start=1)
            )
        destinations = (
            ("Matchups", "Weekly competition and starter evidence", "/matchups"),
            ("FOIS", "General-manager performance and confidence", "/fois"),
            ("Transactions", "Trades, waivers, adds, and drops", "/transactions"),
            ("Draft Capital", "League pick ownership", "/picks"),
            ("History", "Verified seasons, standings, and evidence", "/history"),
        )
        links = '<div class="grid">' + "".join(f'<a class="card" href="{href}"><h3>{title}</h3><p class="muted">{description}</p></a>' for title, description, href in destinations) + "</div>"
        body = (
            _section("Preseason League Briefing" if preseason else "League Recap", "A league-wide view, separate from your personal front office", f'<div class="card ux-recap"><p>{escape("Regular-season games have not started. Review roster direction, recent activity, market movement, and Week 1 preparation." if preseason else f"{len(teams)} franchises · Week {data.get('week') or '—'} · Season {(data.get('league') or {}).get('season') or '—'}")}</p></div>')
            + _section("Preseason Rankings" if preseason else "Current Rankings", "Preseason team outlook—not current results or FOIS" if preseason else "Current-season results—not FOIS", f'<div class="card ds-table-wrap"><table><thead><tr><th>Rank</th><th>Franchise</th><th>{"State" if preseason else "Record"}</th><th>{"" if preseason else "Points"}</th></tr></thead><tbody>{standings}</tbody></table></div>')
            + _section("League Intelligence", "Competition, management, activity, and history", links)
        )
        return page("League", body)

    return router
