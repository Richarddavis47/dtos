"""Manager-first Home and League presentation routes."""
from __future__ import annotations

from html import escape
from datetime import datetime, timezone
import json
from typing import Any, Awaitable, Callable, Hashable

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from services.team_headquarters import build_team_directory
from services.transactions import normalize_transactions
from services.home_trade_news import recent_candidates, news_identity, build_news, capture_news_data
from src.ui.home_trade_opportunities import section as opportunity_section, CSS as OPPORTUNITY_CSS
from src.ui.home_trade_news import render_news, NEWS_CSS
from services.matchup_season import current_matchup_groups
from services.standings import standings_order
from src.ui.intelligence_presentation import league_is_preseason, record_evidence
from src.ui.badges import champion_badge, defending_champion, standing_badge, you_badge
from src.platform.account_context import current_account
from src.ui.render_cache import GenerationRenderCache
from src.ui.front_office_brief import CSS as BRIEF_CSS
from src.ui.standings import render_standings
from src.platform.league_context import current_league_context
from src.core.request_execution import run_manager_read
from src.platform.request_diagnostics import diagnosed, span

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]
GenerationProvider = Callable[[], Hashable]


home_body_render_cache = GenerationRenderCache(
    "manager_home_body", max_entries=24, max_bytes=2_097_152,
)


trade_news_render_cache = GenerationRenderCache("home_trade_news", max_entries=24, max_bytes=2_097_152)

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
    if not options:
        return '<p class="muted">Franchise evaluation is unavailable until league rosters are supported.</p>'
    initial = int((selected or (data.get("teams") or [{}])[0]).get("roster_id") or 0)
    return f'''<details class="ds-home-detail"><summary>View another franchise</summary><form method="get" action="/teams/{initial}" class="card" onsubmit="this.action='/teams/'+this.elements.roster_id.value"><label for="front-office">Selected franchise</label><select id="front-office" name="roster_id">{options}</select><button class="btn" type="submit">View franchise</button></form><p class="muted">Opens a read-only team evaluation. Your Home and trade workspace stay with your controlled franchise.</p><noscript><a href="/league">Open League to choose a franchise</a></noscript></details>'''


def create_home_router(
    *, ensure_fresh: EnsureFresh, require_data: RequireData, page: PageRenderer,
    generation_provider: GenerationProvider | None = None,
) -> APIRouter:
    """Create the manager briefing and league-wide hub."""
    router = APIRouter(tags=["manager-experience"])

    @router.get("/", response_class=HTMLResponse)
    async def home(front_office: int | None = Query(None)) -> HTMLResponse:
        with span('home_freshness'):
            await ensure_fresh()
        # Prepared evidence still performs synchronous reads, fingerprints and
        # single-flight cache waits. Keep those off the HTTP event loop while
        # propagating the authenticated account/league context to the worker.
        return await run_manager_read(lambda: render_home(front_office))

    @diagnosed('home_render')
    def render_home(front_office: int | None) -> HTMLResponse:
        data = require_data()
        retained_generation = (
            generation_provider() if generation_provider is not None
            else (str((data.get("league") or {}).get("league_id") or "default"), id(data))
        )
        generation = repr(retained_generation)
        directory = build_team_directory(data, prepared_only=True) if data.get('teams') else {}
        champion = defending_champion(data)
        account = current_account()
        viewer = account.membership.roster_id if account and account.membership else None
        front_office = front_office if front_office is not None else viewer
        cache_key = (retained_generation, front_office, repr(directory), champion, viewer, data.get("week"))

        def render_body() -> bytes:
            return _home_body(data, front_office, directory, champion).encode("utf-8")

        body = home_body_render_cache.get_or_build(
            cache_key, generation, render_body,
        ).decode("utf-8")
        selected = _selected_team(data, front_office)
        active = current_league_context()
        rid = selected.get('roster_id') if selected else None
        now = datetime.now(timezone.utc)
        news_data = capture_news_data(data)
        candidates, limitations = recent_candidates(news_data, now=now)
        news_key = (news_identity(news_data, candidates, now), viewer, tuple(limitations))
        news = trade_news_render_cache.get_or_build(news_key, str(retained_generation),
            lambda: json.dumps(build_news(news_data, candidates, limitations, now=now)).encode()).decode()
        body = body.replace('<!--home-opportunities-->', '<style>' + OPPORTUNITY_CSS + BRIEF_CSS + '</style>' + opportunity_section(int(rid or 0)))
        body = body.replace('<!--home-trade-news-->', '<style>' + NEWS_CSS + '</style>' + render_news(json.loads(news), viewer=viewer))
        # Outside the body cache: optional analytics can fail or recover without
        # changing roster/Market facts. No generation is triggered by this read.
        if active is not None and active.fois_state in {'pending', 'unavailable', 'retained'}:
            state = active.runtime.lifecycle.get('fois_generation')
            wording = ('FOIS is temporarily unavailable.' if state == 'failed' else
                       'FOIS is being prepared.' if active.fois_state == 'pending' else
                       'Current FOIS is unavailable.')
            retained = ' Previous grades are retained, not revalidated.' if active.fois_state == 'retained' else ''
            body += ('<p class="muted" role="status" data-fois-availability="' + active.fois_state + '">'
                     + wording + retained + ' Your roster, Market and Trade remain usable. '
                     '<a href="/fois">Review FOIS status</a></p>')
        if rid:
            from services.trade_workspace_context import workspace_context
            context = escape(json.dumps(workspace_context(data, int(rid))), quote=True)
            body += f'<div id="trade-home-boundary" hidden data-workspace-context="{context}"></div><script src="/static/js/trade_workspace.js" defer></script>'
        return page("Home", body)

    def _home_body(data: dict[str, Any], front_office: int | None, directory: dict, champion=None) -> str:
        teams = data.get("teams") or []
        team = _selected_team(data, front_office)
        selector = _team_selector(data, team)
        if team is None:
            return selector + '<div class="ds-empty"><b>No franchise is available.</b>The current Sleeper context has no team roster to brief.</div>'

        roster_id = int(team.get("roster_id") or 0)
        outlook = directory.get(roster_id, {})
        preseason = league_is_preseason(data)
        record = record_evidence(team.get("wins"), team.get("losses"), team.get("ties"), season_started=not preseason)
        ranking_label = "preseason outlook" if preseason else "current league outlook"
        competitive = f'#{outlook.get("rank", "—")} in the {ranking_label}' if outlook.get("rank") else f'{ranking_label.title()} not yet available'
        header = f'''<div class="ux-command-grid"><article class="ux-feature"><p class="identity-kicker">Your front office · {escape(str(team.get("owner") or "Unassigned"))}</p><h2>{escape(str(team.get("team_name") or "Franchise"))}{you_badge(data, roster_id)}</h2><div class="ds-badges">{standing_badge(standings_order(data)["ranks"].get(roster_id), derived=True)}{champion_badge(champion, roster_id)}</div><p class="ux-feature-copy"><b>{escape("Preseason · official record not started" if preseason else "Official record: " + record)}</b></p><div class="ux-feature-actions"><a class="ux-primary-action" href="/teams/{roster_id}">Open My Team</a><a class="ux-secondary-action" href="/trades?front_office={roster_id}">Build or explore a trade</a></div><p class="ux-feature-copy">DTOS strength assessment: {escape(competitive)}.</p><details class="ds-home-detail"><summary>Assessment context</summary><p>DTOS organizes current league evidence around this franchise’s decisions. Strength assessments remain separate from official standings.</p></details></article><aside class="card ux-signal-rail home-secondary-rail"><div class="identity-kicker">Right now</div><a class="ux-signal" href="/league"><span class="ux-signal-icon">#</span><span><b>{escape(str(outlook.get("rank") or "—"))}</b><small>{escape(ranking_label)}</small></span><span aria-hidden="true">→</span></a><a class="ux-signal" href="/teams/{roster_id}#full-roster"><span class="ux-signal-icon">◎</span><span><b>{len(team.get("players") or [])} players</b><small>{len(team.get("picks_owned") or [])} future picks</small></span><span aria-hidden="true">→</span></a><a class="ux-signal" href="/trades?front_office={roster_id}"><span class="ux-signal-icon">⇄</span><span><b>Trade desk</b><small>Build, Shop or Trade For</small></span><span aria-hidden="true">→</span></a></aside></div>{selector}'''

        actions = [
            ("Review my assets", "See your current players, lineup and exact owned picks.", f"/teams/{roster_id}#full-roster"),
            ("Check this week's matchup", "Compare actual scoring and available projections without invented odds.", "/matchups"),
            ("Explore a trade", "Use the existing Trade Intelligence workflow for this front office.", f"/trades?front_office={roster_id}"),
        ]
        action_html = '<div class="card ux-action-list">' + "".join(
            f'<a class="ux-action" href="{href}"><span><b>{escape(title)}</b><p>{escape(reason)}</p></span><span aria-hidden="true">→</span></a>'
            for title, reason, href in actions[:2]
        ) + "</div>"

        rankings = sorted(
            ((int(team_row.get("roster_id") or 0), team_row, directory.get(int(team_row.get("roster_id") or 0), {})) for team_row in teams
             if directory.get(int(team_row.get("roster_id") or 0), {}).get("rank") is not None),
            key=lambda row: (int(row[2].get("rank") or 999), str(row[1].get("team_name") or "")),
        )[:5]
        rank_html = '<div class="podium-grid">' + "".join(
            f'<a class="podium-card" data-rank="{int(view["rank"])}" href="/teams/{rid}"><span class="podium-rank">#{escape(str(view["rank"]))}</span><h3>{escape(str(row.get("team_name") or "Team"))}</h3><p>{escape("Canonical team assessment" if preseason else record_evidence(row.get("wins"), row.get("losses"), row.get("ties"), season_started=True))}</p></a>'
            for index, (rid, row, view) in enumerate(rankings[:3], start=1)
        ) + '</div>' + ('<p>Canonical team assessment rankings unavailable.</p>' if not rankings else '') + '<p><a href="/teams">Open team assessments →</a></p>'

        matchups = []
        for matchup_id, sides in sorted(current_matchup_groups(data).items())[:5]:
            names = " vs ".join(str(side.get("team") or "Unassigned") for side in sides[:2])
            matchups.append(f'<a class="ux-action" href="/matchups/{escape(str(matchup_id))}"><span><b>{escape(names)}</b><p>Week {escape(str(data.get("week") or "—"))} matchup</p></span><span>→</span></a>')
        matchup_html = '<div class="card ux-action-list">' + ("".join(matchups) or '<p class="muted">No current matchup pairing is available.</p>') + "</div>"

        recent = normalize_transactions(data)[:5]
        activity_html = '<div class="card">' + ("".join(
            f'<p><b>{escape(str(item.get("type_label") or "League activity"))}</b><br><span class="muted">{escape(str(item.get("timestamp") or "Time unavailable"))}</span></p>'
            for item in recent
        ) or '<p class="muted">No cached league activity is available.</p>') + '<a href="/transactions">View league activity →</a></div>'

        assets = team.get("players") or []
        assets_html = f'<div class="card"><p><b>{len(assets)}</b> rostered players · <b>{len(team.get("picks_owned") or [])}</b> future picks</p><a href="/teams/{roster_id}#full-roster">Review my assets →</a></div>'
        from services.weekly_report import weekly_facts
        report_week = data.get("week") or 1
        facts = weekly_facts(data, report_week)
        report_state = {"completed": "Final", "in_progress": "In progress", "preview": "Preview"}.get(facts["state"], "Unavailable")
        body = (
            header + '<!--home-opportunities--><!--home-trade-news-->' + _section('Standings', 'Official records and scoring · not DTOS power rankings', render_standings(data, champion=champion))
            + _section("Weekly Report", report_state + " · current week evidence", f'<div class="card ux-recap"><a href="/reports/weekly?week={report_week}">Open Week {report_week} report · {report_state} →</a></div>')
            + _section("Explore", "Useful destinations—not personalized Attention recommendations", action_html)
            + '<details class="ds-home-detail"><summary>DTOS team assessment · not official standings</summary>' + _section("Team Assessment Rankings", "Canonical team assessment · not standings or FOIS GM rankings", rank_html) + '</details>'
            + _section("Matchups this week", "Current Sleeper matchup evidence", matchup_html)
            + '<details class="ds-home-detail"><summary>Market and league activity</summary>' + _section("Market Movers", "Meaningful movement only", '<div class="card"><p class="muted">Market movement is shown only when timestamped comparable observations cross the established threshold.</p><a href="/market#market-movers">Review market evidence →</a></div>')
            + _section("League Activity", "Recent cached transactions", activity_html)
            + _section("My Assets", "Roster and draft capital", assets_html) + '</details>'
        )
        return body

    @router.get("/league", response_class=HTMLResponse)
    async def league(request: Request) -> HTMLResponse:
        await ensure_fresh()
        return await run_manager_read(lambda: render_league(request))

    def render_league(request: Request) -> HTMLResponse:
        data = require_data()
        teams = data.get("teams") or []
        preseason = league_is_preseason(data)
        visual_standings = render_standings(data)
        preseason_analysis = ''
        if preseason:
            directory = build_team_directory(data, prepared_only=True) if teams else {}
            ordered = sorted(teams, key=lambda t: directory.get(int(t['roster_id']), {}).get('rank') or 999)
            rows = ''.join(f'<li><a href="/teams/{int(t["roster_id"])}">{escape(str(t.get("team_name") or "Franchise"))}</a> · DTOS assessment rank {escape(str(directory.get(int(t["roster_id"]), {}).get("rank") or "Unavailable"))}</li>' for t in ordered)
            preseason_analysis = '<details><summary>Preseason Rankings · DTOS assessment, not official standings</summary><ul>' + rows + '</ul></details>'
        from src.core.intelligence.orchestrator import intelligence_orchestrator
        from src.ui.league_gm_diagnostics import league_observations
        account = current_account()
        active_id = int(account.membership.roster_id) if account and account.membership else int(teams[0]['roster_id']) if teams else 0
        observations_html = ''
        if active_id:
            from services.strategy_session import COOKIE, selected_strategy
            strategy = selected_strategy(request.cookies.get(COOKIE), str((data.get('league') or {}).get('league_id') or ''), active_id)
            intelligence = intelligence_orchestrator.analyze(data, active_id,
                user_preferences={'strategy': strategy}, include_trade_opportunities=False)
            observations_html = league_observations(intelligence, data, active_id)
        destinations = (
            ("Weekly Report", "Prepared league recap and supported changes", "/reports/weekly"),
            ("Matchups", "Weekly competition and starter evidence", "/matchups"),
            ("FOIS", "General-manager performance and confidence", "/fois"),
            ("Transactions", "Trades, waivers, adds, and drops", "/transactions"),
            ("Draft Capital", "League pick ownership", "/picks"),
            ("History", "Verified seasons, standings, and evidence", "/history"),
        )
        links = '<div class="grid">' + "".join(f'<a class="card" href="{href}"><h3>{title}</h3><p class="muted">{description}</p></a>' for title, description, href in destinations) + "</div>"
        body = (
            _section("Preseason League Briefing" if preseason else "League Recap", "A league-wide view, separate from your personal front office", f'<div class="card ux-recap"><p>{escape("Regular-season games have not started. Review roster direction, recent activity, market movement, and Week 1 preparation." if preseason else f"{len(teams)} franchises · Week {data.get('week') or '—'} · Season {(data.get('league') or {}).get('season') or '—'}")}</p></div>')
            + observations_html + _section("Standings", "League-specific Sleeper records and scoring", visual_standings) + preseason_analysis
            + _section("League Intelligence", "Competition, management, activity, and history", links)
        )
        return page("League", body)

    return router
