"""Team directory and Front Office Headquarters presentation routes."""
from __future__ import annotations

from html import escape
import json
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from config import LEAGUE_ID
from services.asset_intelligence import contextual_player_url
from services.team_headquarters import build_team_directory, build_team_headquarters
from src.core.historical_memory.read_model import historical_graph
from src.core.history_context import canonical_history_store
from src.core.request_execution import run_manager_read
from src.ui import player_summary
from src.ui.badges import champion_badge, defending_champion, you_badge
from src.platform.league_context import current_league_context
from src.core.projection_intelligence import projection_service
from services.player_projection_view import player_projection_views
from src.core.history_context.results import number
from src.platform.account_context import current_account
from services.trade_workspace_context import workspace_context
from services.strategy_session import COOKIE, selected_strategy

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
.thq-strength-detail summary{min-height:44px;display:flex;align-items:center;cursor:pointer}
.thq-strength-detail a,.thq-optimal a,.thq-depth a{display:inline-flex;align-items:center;min-height:44px;overflow-wrap:anywhere}
.thq-strength-detail summary:focus-visible,.thq-table-scroll:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.thq-table-scroll{max-width:100%;overflow-x:auto}.thq-table-scroll table{width:100%;min-width:450px}
.thq-section{overflow-wrap:anywhere}.thq-optimal{padding-left:20px}
.thq-content{min-width:0;max-width:100%;overflow-wrap:anywhere}.thq-title h2{overflow-wrap:anywhere}.thq-identity>div{min-width:0}
.thq-strategy{min-width:0;max-width:350px}.thq-strategy label{display:block}.thq-strategy select{width:100%;max-width:100%;min-height:44px}
.thq-content a:focus-visible,.thq-content summary:focus-visible,.thq-content select:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.thq-player{display:block}.thq-player>div,.thq-player .player-identity{min-width:0}.thq-player .thq-action{margin-top:6px}
.thq-pick>div{min-width:0}.thq-pick .thq-actions{margin-top:8px}.thq-kpi p{font-size:13px;line-height:1.5}
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


def _points(value: Any) -> str:
    score = number(value)
    return "Unavailable" if score is None else f"{score:.2f}"


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
        + ''.join(f'<article class="thq-kpi"><span>{label}</span><b>{_display(value)}</b></article>' for label, value in (("Weekly Ceiling (points)", assessment.weekly_ceiling), ("Weekly Floor (points)", assessment.weekly_floor)))
        + f'<p class="muted">Evidence generation: {escape(assessment.generation)}. Actual starters are not replaced by the optimizer.</p></div>'
    )


def _team_intelligence(view: dict[str, Any]) -> str:
    card = view["team_intelligence"]
    grades = (card.overall, card.market_asset_strength, card.production_quality, card.dynasty, card.starting_lineup, card.depth, *card.positions.values(), card.draft_capital, card.youth, card.future_outlook, card.roster_flexibility, card.asset_liquidity)
    return "".join(
        f'<article class="thq-grade"><div class="thq-grade-head"><div><h3>{escape(item.category)}</h3><div class="thq-grade-score">{("Unavailable — see evidence or model limitation" if item.score is None else f"Score {item.score}/100 · #{item.rank} of {item.league_size} · {str(item.percentile) + "th percentile" if item.percentile is not None else "Percentile unavailable"}")}</div></div><div class="thq-grade-mark">{escape(item.grade)}</div></div><p class="ds-grade-context">Meaning: this grade compares only the explicitly named dimension, not overall dynasty value.</p><details><summary>Show Reasoning</summary><div class="thq-reasoning"><ul>{"".join(f"<li>{escape(reason)}</li>" for reason in item.reasons or card.explanation)}</ul></div></details></article>'
        for item in grades
    )


def _roster_rooms(view: dict[str, Any]) -> str:
    labels = {"QB": "Quarterbacks", "RB": "Running Backs", "WR": "Wide Receivers", "TE": "Tight Ends", "Other": "Other Players"}
    rooms = []
    groups = {**view["roster_groups"], "Other": view["other_players"]}
    for position, players in groups.items():
        if position == "Other" and not players:
            continue
        rows = []
        for player in players:
            pid = str(player["id"])
            target = contextual_player_url(pid, from_team=view['team']['roster_id'], week=view['overview']['projection_week'])
            quote_value = player.get('intelligence')
            price = quote_value.market_value if quote_value is not None else None
            projection = view['projection_views'].get(pid)
            market = f'{price:g}' if price is not None else 'Unavailable'
            action = ('<a class="thq-action" href="' + escape('/trades/shop?' + urlencode({'front_office': view['team']['roster_id'], 'asset_id': pid, 'owner_roster_id': view['team']['roster_id']})) + '" aria-label="Shop ' + escape(player['name']) + '">Shop</a>') if view['can_shop'] else ''
            rows.append(f'<article class="thq-player"><div><a href="{escape(target)}">{player_summary(player_id=pid, name=str(player["name"]), position=str(player.get("position") or "Other"), nfl_team=str(player.get("team") or "Unknown"), context=player.get("availability_status") or "Status unavailable", projection=projection)}</a><div class="thq-player-meta">Canonical Market: {market} · {escape(str(player.get("roster_slot") or "Assignment unavailable"))}</div>{action}</div></article>')
        rooms.append(f'<section class="thq-room"><div class="thq-room-head"><span>{labels[position]}</span><span>{len(players)} players</span></div>{"".join(rows) or "<p class=muted>No players currently rostered.</p>"}</section>')
    return "".join(rooms)


def _key_players(view):
    players = [p for room in view['roster_groups'].values() for p in room]
    priced = [p for p in players if p.get('intelligence') is not None and p['intelligence'].market_value is not None]
    leaders = sorted(priced, key=lambda p: p['intelligence'].market_value, reverse=True)[:3]
    if not leaders:
        return '<p>Key Market assets cannot be identified without supported canonical prices. The full roster remains available above.</p>'
    return '<p>Highest supported canonical Market values; this does not rank weekly production.</p><div class="thq-actions">' + ''.join(
        f'<a class="thq-action" href="{escape(contextual_player_url(str(p["id"]), from_team=view["team"]["roster_id"], week=view["overview"]["projection_week"]))}">{escape(p["name"])} · {p["intelligence"].market_value:g}</a>' for p in leaders
    ) + '</div>'


def _draft_capital(view: dict[str, Any]) -> str:
    from src.core.historical_memory.graph import canonical_pick_id
    prepared = (view['team_intelligence'].future_capital_evidence or {}).get('picks') or ()
    by_id = {(str(row['identity'].get('year', row['identity'].get('season'))),
              str(row['identity'].get('round')), str(row['identity'].get('original_roster_id'))): row for row in prepared}
    sections = []
    for year, picks in sorted(view["picks_by_year"].items(), key=lambda item: str(item[0])):
        rows = []
        for pick in picks:
            original = pick.get('original_roster_id')
            owner = pick.get('current_owner_id')
            exact = original is not None and owner is not None and year is not None and pick.get('round') is not None
            facts = by_id.get((str(year), str(pick.get('round')), str(original)), {})
            identity, market = facts.get('identity', {}), facts.get('market', {})
            price = market.get('normalized_market_price')
            value = f'{price:g}' if price is not None else 'Unavailable'
            title = f'{year} Round {pick.get("round", "?")} · {pick.get("original_team") or "Original franchise unavailable"}'
            actions = ''
            if exact:
                dossier = '/picks/' + canonical_pick_id(year, pick['round'], original) + '?' + urlencode({'front_office': view['team']['roster_id'], 'from_team': view['team']['roster_id']})
                actions = f'<a class="thq-action" href="{escape(dossier)}">Pick dossier</a>'
                if view['can_shop'] and int(owner) == view['team']['roster_id']:
                    shop = '/trades/shop?' + urlencode({'front_office': owner, 'asset_id': f'{year}-R{pick["round"]}-{original}', 'owner_roster_id': owner})
                    actions += f'<a class="thq-action" href="{escape(shop)}" aria-label="Shop {escape(title)}">Shop Asset</a>'
            rows.append(f'<article class="thq-pick"><div><b>{escape(title)}</b><small>{"Acquired · " if pick.get("is_traded") else ""}Original franchise: {escape(str(pick.get("original_team") or "Unavailable"))} · Current owner: {escape(str(pick.get("current_owner") or view["team"]["team_name"]))}</small><small>Market: {value} · Range: {escape(str(identity.get("projected_range") or "Unavailable"))} · Confidence: {escape(str(identity.get("projected_range_confidence") or "Unavailable"))}</small><div class="thq-actions">{actions}</div></div></article>')
        sections.append(f'<section class="thq-pick-year"><h3>{escape(str(year))}</h3>{"".join(rows)}</section>')
    return "".join(sections) or '<p class="muted">No owned future pick evidence is available.</p>'


def _positional_depth(view):
    rows = []
    for position, facts in view['overview']['positions'].items():
        points = _points(facts['starting_points'])
        backup = _points(facts['best_reserve_points'])
        rows.append(f'<article class="thq-kpi"><h3>{position}</h3><p>{facts["starting_count"]} players in {escape(facts["lineup_basis"])} · {points} Sleeper-projected points</p><small>{facts["required_slots"]} required slots · {facts["eligible_flex_slots"]} eligible flex slots</small><p>Reserve projection coverage: <b>{facts["reserve_covered"]}/{facts["reserve_expected"]}</b> · {escape(facts["availability"])}. Best supported reserve: {backup} points.</p><details><summary>Lineup eligibility and surplus</summary><p>Surplus not established: player quantity and bench placement alone do not prove expendability.</p></details></article>')
    return '<div class="thq-cards">' + ''.join(rows) + '</div>'


def _timeline(view: dict[str, Any], graph=None) -> str:
    def event_url(event):
        resolver = getattr(graph, 'trade_reference', None)
        resolved = resolver(str(event['id'])) if callable(resolver) else None
        return resolved['url'] if isinstance(resolved, dict) and isinstance(resolved.get('url'), str) else '/transactions?q=' + quote(str(event['id']))
    rows = "".join(
        f'<article class="thq-event"><time>{escape(event["timestamp"])}</time><span class="thq-event-type">{escape(event["type"])}</span><span class="thq-event-assets">{escape(event["actions"])} · {escape(", ".join(str(asset["label"]) for asset in event["assets"]) or "No asset detail available")}</span><a href="{escape(event_url(event))}">View</a></article>'
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
            performance = (f'<div class="metric"><b>{outlook["playoff_odds"]}%</b><span>Playoff Odds</span></div><div class="metric"><b>{outlook["championship_odds"]}%</b><span>Championship Odds</span></div>' if outlook["preseason"] else f'<div class="metric"><b>{_points(team.get("points_for"))}</b><span>Points For</span></div><div class="metric"><b>{_points(team.get('max_points'))}</b><span>Max PF</span></div>')
            cards.append(
                f'<a class="card team team-link" href="/teams/{team["roster_id"]}"><div class="team-head">{_franchise_portrait(team)}<div><div class="identity-kicker">Owner: {escape(team["owner"])}</div><h3 class="franchise-name">{escape(team["team_name"])}{you_badge(data, int(team["roster_id"]))}</h3></div><div class="rank-badge">{escape(outlook["grade"])}</div></div>{result}<div class="summary-grid">{performance}<div class="metric"><b>{len(team["players"])}</b><span>Players</span></div><div class="metric"><b>{firsts}</b><span>Future 1sts</span></div></div><p class="muted">{starters} starters · {len(team.get("picks_owned", []))} total future picks</p><span class="team-open">Open Team HQ <span aria-hidden="true">→</span></span></a>'
            )
        return page("Teams", '<h2>League Franchises</h2><p class="muted">Select a team to open its Front Office Headquarters.</p><div class="grid">' + "".join(cards) + "</div>")

    @router.get("/teams/{roster_id}", response_class=HTMLResponse)
    async def team_detail_page(roster_id: int, request: Request) -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        account = current_account()
        editable = account is None or (account.membership is not None and account.membership.roster_id == roster_id)
        league_id = str((data.get('league') or {}).get('league_id') or LEAGUE_ID)
        strategy = selected_strategy(request.cookies.get(COOKIE), league_id, roster_id) if editable else ''
        view = await run_manager_read(
            lambda: build_team_headquarters(
                data, roster_id, state.get("last_sync"), strategy=strategy,
            ),
        )
        if view is None:
            raise HTTPException(404, "Team not found")
        team = view["team"]
        franchise_history_url = '/history/team/' + quote(str((data.get('league') or {}).get('league_id') or '') + ':franchise:' + str(roster_id), safe='')
        view['can_shop'] = editable
        active_context = current_league_context()
        service = active_context.projection if active_context else projection_service
        pinned_service = SimpleNamespace(snapshot=lambda: view['projection_snapshot'], week_snapshot=service.week_snapshot)
        view['projection_views'] = await run_manager_read(lambda: player_projection_views(data,
            [str(player['id']) for players in (*view['roster_groups'].values(), view['other_players']) for player in players], pinned_service))
        avatar = _franchise_portrait(team)
        summary = "".join(f'<article><h3>{escape(label)}</h3><p>{escape(text)}</p></article>' for label, text in view["summary"].items())
        performance = view["performance"]
        performance_metrics = (
            (("Projected Wins", _display(view["team_intelligence"].projected_wins)), ("Power Ranking", _display(view["rank"])), ("Championship Odds", _display(view["team_intelligence"].championship_odds)), ("Playoff Odds", _display(view["team_intelligence"].playoff_odds)))
            if view["preseason"] else
            (("Record", performance["record"]), ("Points For", _points(performance["points_for"])), ("Points Against", _points(performance["points_against"])), ("Max PF", _points(performance['max_points'])), ("League Standing", performance["standing"]))
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
        assessment = view['assessment']
        selected_league = str((data.get("league") or {}).get("league_id") or LEAGUE_ID)
        def prepare_history():
            model = historical_graph(canonical_history_store, selected_league, data)
            return model.franchise_history(str(team['roster_id'])), _timeline(view, model)
        franchise_history, activity_html = await run_manager_read(prepare_history)
        historical_seasons = len({row["season"] for row in franchise_history["standings"]})
        historical_transactions = len(franchise_history["transactions"])
        starters = [player for player in team.get("players") or [] if player.get("roster_slot") == "Starter"]
        card_projections = view['projection_views']
        starter_cards = "".join(
            f'<a class="card" href="{escape(contextual_player_url(str(player.get("id") or ""), from_team=roster_id, section="my-team-advanced", week=view["overview"]["projection_week"]))}">{player_summary(player_id=str(player.get("id") or ""), name=str(player.get("name") or "Unknown player"), position=str(player.get("position") or ""), nfl_team=str(player.get("team") or player.get("nfl_team") or "Free Agent"), context="Submitted starter", projection=card_projections.get(str(player.get("id") or "")))}</a>'
            for player in starters
        ) or '<div class="ds-empty"><b>No starting lineup is available.</b>Sleeper has not supplied a current starter assignment.</div>'
        from src.ui.team_strength import strength_panel
        multi_horizon_html = strength_panel(assessment.multi_horizon_strength, league_id=assessment.league_id,
                                           roster_id=assessment.roster_id, players=team.get('players'), from_team=roster_id)
        binding = workspace_context(data, roster_id)
        context_json = escape(json.dumps(binding, separators=(',', ':')), quote=True)
        options = ''.join(f'<option value="{escape(value)}" {"selected" if value == strategy else ""}>{escape(value or "Use supported competitive window")}</option>' for value in ('', 'WIN NOW', 'RETOOL', 'REBUILD'))
        strategy_control = f'<label for="my-team-strategy">Your strategy</label><select id="my-team-strategy">{options}</select><p id="my-team-strategy-feedback" role="status"></p>' if editable else '<p>Viewing another franchise; its manager strategy is not inferred from holdings.</p>'
        own_team = account.membership.roster_id if account and account.membership else roster_id
        scope_notice = '' if editable else f'<nav class="thq-actions" aria-label="Read-only franchise navigation"><a class="thq-action" href="/">Back to Home</a><a class="thq-action" href="/teams/{own_team}">My Team</a><span>Read-only franchise evaluation</span></nav>'
        trade_shortcuts = (f'<a class="thq-action" href="/trades/calculator?front_office={roster_id}">Trade Calculator</a><a class="thq-action" href="/trades?front_office={roster_id}">Trade opportunities</a>') if editable else ''
        overview = view['overview']
        roster_summary = ' · '.join(f'{count} {slot.lower()}' for slot, count in overview['slots'].items())
        status_notes = ' · '.join(overview['statuses']) or 'No additional availability warning is established from the supplied status facts.'
        playoff = overview['playoff']
        playoff_note = ('Currently inside the supported playoff-position group.' if roster_id in playoff['qualifiers'] else 'Currently outside the supported playoff-position group.') if playoff['kind'] else playoff['reason']
        body = f"""
{TEAM_HQ_CSS}
<style>
.thq-name-row{{display:flex;flex-wrap:wrap;align-items:center;gap:6px}}.thq-name-row>details[open]{{flex-basis:100%}}.thq-header{{margin-bottom:12px;gap:12px}}.thq-header .thq-avatar{{width:48px;height:48px}}.thq-title h1{{font-size:22px;margin:4px 0}}.thq-title p{{margin:4px 0}}.thq-actions{{margin:8px 0;gap:6px}}.thq-section{{margin-top:16px}}.thq-room-head{{padding:4px 10px;font-size:14px}}.thq-player{{padding:8px 10px}}.thq-player>div{{position:relative;padding-right:52px}}.thq-player>div>.thq-action{{position:absolute;right:0;top:0;padding:8px;min-height:44px}}.thq-player .player-summary{{gap:8px}}.thq-player .player-summary img{{width:40px;height:40px}}.thq-player-meta{{font-size:14px;margin-top:4px}}.thq-roster{{gap:10px}}.thq-strategy small{{display:none}}.thq-strategy{{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:6px}}.thq-strategy label{{margin:0}}.thq-strategy select{{min-width:0;margin:0}}#my-team-strategy-feedback{{grid-column:1/-1}}.thq-header{{padding:12px}}#my-team-strategy-feedback:empty{{display:none}}.thq-actions[aria-label="Roster sections"]{{flex-wrap:nowrap;overflow-x:auto;max-width:100%;padding-bottom:4px}}.thq-actions[aria-label="Roster sections"] .thq-action{{flex:0 0 auto;padding:8px 10px;font-size:14px}}.thq-player .player-portrait{{width:40px;height:40px;flex-basis:40px}}body:has([data-my-team-context]) .ds-header-side{{display:none}}body:has([data-my-team-context]) .ds-page-header{{display:none}}body:has([data-my-team-context]) .ds-page-header h1{{font-size:20px}}
@media(max-width:760px){{.thq-header>div:last-child{{margin-top:8px}}.thq-header .thq-title p{{font-size:14px}}.thq-identity{{gap:8px}}}}
</style>
<section class="thq-content" data-my-team-context="{context_json}">
{scope_notice}
<header class="thq-header"><div class="thq-identity">{avatar}<div class="thq-title"><div class="identity-kicker">Owner: {escape(team['owner'])}</div><div class="thq-name-row"><h1>{escape(team['team_name'])}{you_badge(data, roster_id)}</h1>{champion_badge(defending_champion(data), roster_id)}</div><p>{escape(performance["record"])} · {escape(performance["standing"])}</p></div></div><div class="thq-strategy">{strategy_control}<small>League evidence updated: {escape(view['last_updated'])}</small></div></header>
<nav class="thq-actions" aria-label="Roster sections"><a class="thq-action" href="#full-roster">View full roster</a><a class="thq-action" href="#positional-depth">Depth</a><a class="thq-action" href="#draft-capital">Draft capital</a>{trade_shortcuts}</nav>
<section class="thq-section" id="full-roster"><details class="thq-strength-detail" id="my-team-roster" open><summary>Full Roster</summary><div class="thq-roster">{_roster_rooms(view)}</div></details><details class="thq-strength-detail" id="my-team-key-players"><summary>Key players · canonical Market assets</summary>{_key_players(view)}</details></section>
<section class="thq-section" id="draft-capital"><div class="thq-section-head"><h2>Draft Capital</h2><span>Exact original franchise and current ownership</span></div><div class="thq-picks">{_draft_capital(view)}</div><p class="muted">Pick outlook follows the original franchise. Unknown range means no supported interval is published; picks have no weekly projection.</p></section>
<section class="thq-section" data-dtos-component="recommendation"><div class="thq-section-head"><h2>Your roster at a glance</h2><span>Supported facts first</span></div><div class="thq-summary"><article><h3>Biggest supported strength</h3><p>{escape(overview['strength'])}</p></article><article><h3>Biggest depth risk</h3><p>{escape(overview['risk'])}</p></article><article><h3>Current league position</h3><p>{escape(performance['record'])} · {escape(performance['standing'])}</p><p>{escape(overview['standing_reason'] or 'Ranking evidence is incomplete.')}</p><p>{escape(playoff_note or 'Playoff positioning unavailable.')}</p></article></div><details id="my-team-status" class="thq-strength-detail"><summary>Player availability and source limitations</summary><p>{escape(status_notes)}</p><p>No injury probability is estimated. Missing projections and prices remain unavailable.</p></details></section>
<section class="thq-section" id="positional-depth"><div class="thq-section-head"><h2>Starter strength and positional depth</h2><span>Week {escape(str(overview['projection_week'] or 'unavailable'))} · DTOS-derived lineup contributions using Sleeper projections</span></div>{_positional_depth(view)}</section>
<section class="thq-section"><details class="thq-strength-detail" id="my-team-advanced"><summary>Advanced intelligence · Market, production and legal-lineup evidence</summary><div class="thq-evidence-body"><p>League evidence updated: {escape(view["last_updated"])}. Selected strategy overrides inferred direction and never changes Market prices.</p><p>Comparison ranks include only franchises with complete evidence for that named dimension. Coverage is evidence support, not an outcome probability. Overall dynasty utility and competitive-window aggregates remain unavailable without an approved model.</p><div class="thq-grades">{_team_intelligence(view)}</div>{_decision_horizons(view)}{multi_horizon_html}<h3>Submitted Starting Lineup</h3><p>Sleeper assignments remain separate from the DTOS optimal legal lineup.</p><details class="thq-strength-detail"><summary>View {len(starters)} submitted starters</summary><div class="thq-starters">{starter_cards}</div></details><h3>Roster facts</h3><p>{escape(roster_summary)} · {view['snapshot']['total_picks']} owned picks</p><div class="thq-cards">{_asset_cards(view['snapshot'])}</div><h3>Current Team Performance</h3><div class="thq-performance">{performance_cards}</div><div class="thq-summary">{summary}</div><h3>Activity</h3><div class="thq-timeline">{activity_html}</div><h3>Franchise History</h3><p>{historical_seasons} retained seasons · {historical_transactions} transactions. Historical FOIS grades are retained / NOT REVALIDATED.</p><a class="thq-action" href="{franchise_history_url}">Franchise History</a><a class="thq-action" href="/history">League History</a><a class="thq-action" href="/front-offices?front_office={roster_id}">Front Office Dossier</a><details><summary>Unsupported forecasts and future models</summary><div class="thq-future-grid">{future}</div></details></div></details></section>
</section><script src="/static/js/strategy_session.js" defer></script>
"""
        return page(f'{team["team_name"]} Headquarters', body)

    return router
