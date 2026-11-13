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
from services.team_assessment_presentation import MODEL_NOTE, weekly_comparison, prepared_comparison
from src.ui.customer_experience import plain_reason, readable_time
from src.ui.intelligence_presentation import record_evidence
from src.core.historical_memory.read_model import historical_graph
from src.core.history_context import canonical_history_store
from src.core.request_execution import run_manager_read
from src.ui import player_summary
from src.ui.my_team_outlook import outlook_panel
from src.ui.league_gm_diagnostics import team_observations
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
.thq-event a{display:inline-flex;min-width:44px;min-height:44px;align-items:center;white-space:nowrap;color:var(--accent)}
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
.thq-strategy{min-width:0;max-width:350px;width:min(100%,350px);flex-shrink:0}.thq-strategy label{display:block}.thq-strategy select{width:100%;max-width:100%;min-height:44px}
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
 .thq-event{grid-template-columns:minmax(0,1fr);gap:6px}.thq-event-assets{grid-column:auto}.thq-event time{overflow-wrap:normal}.thq-event a{justify-self:start}
 .thq-kpi b{font-size:21px}
}
@media(max-width:460px){.thq-starters,.thq-grades{grid-template-columns:1fr}.thq-intel{grid-template-columns:1fr}#positional-depth .thq-cards{grid-template-columns:1fr}}
</style>
"""


def _display(value: Any) -> str:
    return "Unavailable" if value is None else str(value)


def _forecast(value: Any) -> str:
    return "Forecast unavailable" if number(value) is None else f"{value}%"


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


def _present_label(value) -> bool:
    """Omit only explicit empty/unknown display sentinels, never numeric zero."""
    return value is not None and str(value).strip().casefold() not in {
        '', 'unknown', 'unavailable', 'none', 'null', 'n/a', '—', '--', 'not available', 'not_available',
    }


def _roster_projection_coverage(view: dict[str, Any]) -> str:
    """Compact evidence count for the roster's existing disclosure heading."""
    players = [player for group in view['roster_groups'].values() for player in group]
    players.extend(view['other_players'])
    supported = sum(number((view['projection_views'].get(str(player['id'])) or {}).get('value')) is not None
                    for player in players)
    return f'{supported}/{len(players)} projections'


def _roster_rooms(view: dict[str, Any]) -> str:
    labels = {"QB": "Quarterbacks", "RB": "Running Backs", "WR": "Wide Receivers", "TE": "Tight Ends", "Other": "Other Players"}
    rooms, source_rows = [], []
    groups = {**view["roster_groups"], "Other": view["other_players"]}
    total = projected = reported = priced = 0
    weeks = set()
    for position, players in groups.items():
        if position == "Other" and not players:
            continue
        rows = []
        for player in players:
            total += 1
            pid = str(player["id"])
            target = contextual_player_url(pid, from_team=view['team']['roster_id'], week=view['overview']['projection_week'])
            quote_value = player.get('intelligence')
            price = quote_value.market_value if quote_value is not None else None
            projection = view['projection_views'].get(pid)
            has_projection = projection is not None and number(projection.get('value')) is not None
            has_status = _present_label(player.get('availability_status'))
            projected += has_projection
            reported += has_status
            priced += price is not None
            if projection and projection.get('week') is not None:
                weeks.add(projection['week'])
            # A numeric observation and its precision remain unchanged. The
            # repeated long precision explanation belongs in the source list.
            compact_projection = {**projection, 'display_reason': None} if has_projection else None
            status = str(player['availability_status']) if has_status else 'Participation unconfirmed' if has_projection else None
            action = ('<a class="thq-action" href="' + escape('/trades/shop?' + urlencode({'front_office': view['team']['roster_id'], 'asset_id': pid, 'owner_roster_id': view['team']['roster_id']})) + '" aria-label="Shop ' + escape(player['name']) + '">Shop</a>') if view['can_shop'] else ''
            metadata = ([f'Market value: {price:g}'] if price is not None else []) + ([str(player['roster_slot'])] if _present_label(player.get('roster_slot')) else [])
            participation = ('<p class="player-participation-note">' + escape(plain_reason(projection['participation_note'])) + '</p>') if projection and projection.get('participation_note') else ''
            precision = '<small class="player-projection-qualification">Sleeper display precision unverified.</small>' if has_projection and projection.get('display_reason') else ''
            rows.append(f'<article class="thq-player"><div><a href="{escape(target)}">{player_summary(player_id=pid, name=str(player["name"]), position=str(player.get("position") or "Other"), nfl_team=str(player.get("team") or "Unknown"), context=status, projection=compact_projection)}</a>{participation}{precision}<div class="thq-player-meta">{escape(" · ".join(metadata))}</div>{action}</div></article>')
            facts = [f'Reported availability: {player["availability_status"]}.' if has_status else 'Availability not reported; participation remains unknown.']
            if has_projection:
                facts.append(f'Week {projection["week"]} Sleeper projection: {projection["display"]}.')
            else:
                facts.append((projection or {}).get('reason') or 'No supported weekly Sleeper projection is available for this player.')
            if price is None:
                facts.append('No supported Market price is available for this player.')
            facts.extend(projection[key] for key in ('participation_note', 'display_reason') if projection and projection.get(key))
            source_rows.append('<li data-roster-player-evidence="' + escape(pid, quote=True) + '"><b>' + escape(player['name']) + '</b>: ' + escape(' '.join(facts)) + '</li>')
        rooms.append(f'<section class="thq-room"><div class="thq-room-head"><span>{labels[position]}</span><span>{len(players)} players</span></div>{"".join(rows) or "<p class=muted>No players currently rostered.</p>"}</section>')
    week = 'Week ' + str(next(iter(weeks))) if len(weeks) == 1 else 'Weekly'
    summary = (f'<aside id="roster-evidence-summary" role="note"><p>{escape(week)} projections: <b>{projected}/{total}</b> available · '
               f'Availability: <b>{reported}/{total}</b> reported · Market prices: <b>{priced}/{total}</b> available.</p>'
               '<p>Unreported availability remains unknown. A projection does not confirm playing time; missing projections or prices are not zero.</p>'
               '<details><summary>Player-by-player availability and projection coverage</summary><ul>' + ''.join(source_rows) + '</ul></details></aside>')
    # Keep the roster itself close to its heading on a phone. The heading has
    # the compact projection count; the one full coverage explanation follows
    # the players, while player-specific playing-time risks remain beside them.
    return "".join(rooms) + summary


def _key_players(view):
    players = [p for room in view['roster_groups'].values() for p in room]
    priced = [p for p in players if p.get('intelligence') is not None and p['intelligence'].market_value is not None]
    leaders = sorted(priced, key=lambda p: p['intelligence'].market_value, reverse=True)[:3]
    if not leaders:
        return '<p>Market values are needed to identify the highest-valued players. The full roster remains available above.</p>'
    return '<p>Highest available Market values; weekly production is shown separately.</p><div class="thq-actions">' + ''.join(
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
                actions = f'<a class="thq-action" href="{escape(dossier)}">View pick</a>'
                if view['can_shop'] and int(owner) == view['team']['roster_id']:
                    shop = '/trades/shop?' + urlencode({'front_office': owner, 'asset_id': f'{year}-R{pick["round"]}-{original}', 'owner_roster_id': owner})
                    actions += f'<a class="thq-action" href="{escape(shop)}" aria-label="Shop {escape(title)}">Shop pick</a>'
            market = f'Market value: {value}' if price is not None else 'Market price not available'
            range_note = (' · Projected range: ' + str(identity['projected_range'])) if _present_label(identity.get('projected_range')) else ''
            if range_note and _present_label(identity.get('projected_range_confidence')):
                range_note += ' · ' + str(identity['projected_range_confidence'])
            own = str(original) == str(view['team']['roster_id']) if original is not None else None
            origin_label = 'Your original pick' if own else 'Acquired pick' if own is False else 'Original franchise unresolved'
            rows.append(f'<article class="thq-pick"><div><b>{escape(title)}</b><small>{origin_label} · Owned by: {escape(str(pick.get("current_owner") or view["team"]["team_name"]))}</small><small>{escape(market + range_note)}</small><div class="thq-actions">{actions}</div></div></article>')
        sections.append(f'<section class="thq-pick-year"><h3>{escape(str(year))}</h3>{"".join(rows)}</section>')
    return "".join(sections) or '<p class="muted">No owned future pick evidence is available.</p>'


def _positional_depth(view):
    from src.ui.intelligence_presentation import projection_evidence_summary

    # Group only identical qualifications. Position-specific findings and the
    # original detailed evidence stay attached to their respective cards.
    qualifications = {}
    for position, facts in view['overview']['positions'].items():
        evidence = (facts.get('diagnostic') or {}).get('evidence') or {}
        qualification = projection_evidence_summary(evidence, concise=True)
        qualifications.setdefault(qualification, []).append(position)
    shared = ''.join(
        f'<p><strong>{escape(" · ".join(positions))}:</strong> {escape(plain_reason(qualification))}</p>'
        for qualification, positions in qualifications.items() if len(positions) > 1
    )
    missing_points = [position for position, facts in view['overview']['positions'].items() if number(facts.get('starting_points')) is None]
    missing_backups = [position for position, facts in view['overview']['positions'].items() if number(facts.get('best_reserve_points')) is None]
    missing = ('<p>Starting-point contributions are not established at ' + escape(', '.join(missing_points)) + '.</p>') if missing_points else ''
    if missing_backups:
        missing += '<p>Backup point comparisons are incomplete at ' + escape(', '.join(missing_backups)) + '. Missing evidence does not prove weak backups.</p>'
    shared_html = f'<div id="depth-evidence-notes" role="note">{shared}{missing}</div>' if shared or missing else ''
    rows = []
    for position, facts in view['overview']['positions'].items():
        points = _points(facts['starting_points'])
        backup = _points(facts['best_reserve_points'])
        diagnostic = facts.get('diagnostic') or {}
        explanation = diagnostic.get('interpretation') or 'Surplus not established: player quantity and bench placement alone do not prove expendability.'
        evidence = diagnostic.get('evidence') or {}
        for limitation in evidence.get('limitations') or []:
            explanation = explanation.replace(limitation, '').strip()
        qualification = projection_evidence_summary(evidence, concise=True)
        qualification_html = (f'<p><strong>{escape(plain_reason(qualification))}</strong></p>'
                              if len(qualifications[qualification]) == 1 else '')
        candidates = diagnostic.get('surplus_assets') or []
        if not candidates and 'Surplus not established' not in explanation:
            explanation += ' Surplus not established: current evidence does not identify an expendable asset.'
        names = {str(p.get('id') or p.get('player_id')): str(p.get('name') or p.get('full_name') or p.get('id')) for p in view['team'].get('players') or []}
        expendable = ', '.join(names.get(p['player_id'], 'Player identity unavailable') for p in candidates)
        from src.ui.roster_diagnostic_evidence import evidence_html
        details = evidence_html(diagnostic, view['team'].get('players') or [], {key: (view.get('projection_snapshot') or {}).get(key) for key in ('league_id', 'season', 'week', 'projection_snapshot_id', 'scoring_profile_id', 'horizon_snapshot_ids')})
        if not evidence.get('calculation_supported'):
            lead = 'A depth comparison is not ready; missing evidence does not prove weak backups.'
        elif diagnostic.get('quality_depth_need'):
            lead = 'Backup production needs review before you move a starter.'
        elif diagnostic.get('resilience_need'):
            lead = 'Some starter absences lack supported backup cover.'
        elif diagnostic.get('starter_need'):
            lead = 'A supported addition could improve this position’s starting contribution.'
        elif expendable:
            lead = 'Possible movable depth is identified; review the removal cost before trading.'
        else:
            lead = 'Review this position’s starting contribution and backup options.'
        lead_html = '<p>' + escape(lead) + '</p>' if evidence.get('calculation_supported') or len(qualifications[qualification]) == 1 else ''
        starting = f'{facts["starting_count"]} players in {escape(facts["lineup_basis"])}'
        if number(facts.get('starting_points')) is not None:
            starting += f' · {points} Sleeper-projected points'
        reserve = (f'<p>Backup projections: <b>{facts["reserve_covered"]}/{facts["reserve_expected"]}</b> covered.'
                   + (f' Best supported backup: {backup} points.' if number(facts.get('best_reserve_points')) is not None else '') + '</p>') if facts['reserve_expected'] else ''
        rows.append(f'<article class="thq-kpi"><h3>{position}</h3>{lead_html}{qualification_html}<p>{starting}</p>{reserve}{"<p>Review before moving: " + escape(expendable) + "</p>" if expendable else ""}<details><summary>Replacement options and calculations</summary><p>{escape(explanation)}</p><p>{facts["required_slots"]} required slots · {facts["eligible_flex_slots"]} eligible flex slots · {escape(facts["availability"])}</p><p>Current-week evidence; not a sale recommendation or long-term value grade. Scenarios must not be summed.</p>{details}</details></article>')
    return shared_html + '<div class="thq-cards">' + ''.join(rows) + '</div>'


def _timeline(view: dict[str, Any], graph=None) -> str:
    def event_url(event):
        resolver = getattr(graph, 'trade_reference', None)
        resolved = resolver(str(event['id'])) if callable(resolver) else None
        return resolved['url'] if isinstance(resolved, dict) and isinstance(resolved.get('url'), str) else '/transactions?q=' + quote(str(event['id']))
    rows = "".join(
        f'<article class="thq-event"><time>{escape(readable_time(event["timestamp"]))}</time><span class="thq-event-type">{escape(event["type"])}</span><span class="thq-event-assets">{escape(event["actions"])} · {escape(", ".join(str(asset["label"]) for asset in event["assets"]) or "No asset detail available")}</span><a href="{escape(event_url(event))}">View</a></article>'
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
            if outlook["preseason"]:
                known = [("Team assessment rank", outlook.get("rank")), ("Projected wins", outlook.get("projected_wins"))]
                result = '<p class="record">' + (' · '.join(escape(f"{label}: {value}") for label, value in known if value is not None) or 'Preseason · official record not started') + '</p>'
                performance = ''.join(f'<div class="metric"><b>{escape(_forecast(value))}</b><span>{escape(label)}</span></div>'
                    for label, value in (("Playoff Odds", outlook.get("playoff_odds")), ("Championship Odds", outlook.get("championship_odds"))) if number(value) is not None)
            else:
                result = f'<p class="record">{escape(record_evidence(team.get("wins"), team.get("losses"), team.get("ties"), season_started=True))}</p>'
                performance = f'<div class="metric"><b>{_points(team.get("points_for"))}</b><span>Points For</span></div><div class="metric"><b>{_points(team.get("max_points"))}</b><span>Max PF</span></div>'
            comparison = '<p class="muted">' + escape(outlook.get('weekly_comparison') or 'This week’s projected lineup comparison is not ready.') + '</p>'
            grade = (f'<div class="rank-badge">{escape(outlook["grade"])}</div>'
                     if outlook.get('grade') and outlook['grade'] != 'Unavailable' else '')
            cards.append(
                f'<a class="card team team-link" href="/teams/{team["roster_id"]}"><div class="team-head">{_franchise_portrait(team)}<div><div class="identity-kicker">Manager: {escape(team["owner"])}</div><h3 class="franchise-name">{escape(team["team_name"])}{you_badge(data, int(team["roster_id"]))}</h3></div>{grade}</div>{result}{comparison}<div class="summary-grid">{performance}<div class="metric"><b>{len(team["players"])}</b><span>Players</span></div><div class="metric"><b>{firsts}</b><span>Future 1sts</span></div></div><p class="muted">{starters} starters · {len(team.get("picks_owned", []))} total future picks</p><span class="team-open">View team <span aria-hidden="true">→</span></span></a>'
            )
        return page("Teams", '<h2>League Franchises</h2><p class="muted">Choose a team to see its roster, projected lineup and draft picks.</p><div class="grid">' + "".join(cards) + "</div>")

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
        pinned_service = SimpleNamespace(snapshot=lambda: view['projection_snapshot'], week_snapshot=service.week_snapshot,
                                         refresh_evidence=getattr(service, 'refresh_evidence', lambda snapshot: {}))
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
        lineup_alert = ''
        # Reuse prepared facts only, and only for the authenticated controlled
        # franchise. Unknown lock evidence never adds a positive alert.
        if (account and account.membership and account.membership.roster_id == roster_id
                and str(account.membership.league_id) == league_id):
            from src.core.intelligence.team_strength import compatible_profile
            prepared_strength = compatible_profile(data, view['projection_snapshot']) or {}
            if prepared_strength.get('lineup_review_schedule'):
                from services.matchup_season import season_week_view
                from src.ui.lineup_review import review_panel
                week_view = await run_manager_read(lambda: season_week_view(data, data['week'], pinned_service))
                own_side = next((side for sides in week_view['groups'].values() for side in sides
                                 if side['roster_id'] == roster_id), {})
                review = own_side.get('lineup_review') or {}
                if review.get('actionable'):
                    lineup_alert = ('<link rel="stylesheet" href="/static/css/matchups.css">'
                                    + review_panel(review) + '<script src="/static/lineup-review.js" defer></script>')
        starter_cards = "".join(
            f'<a class="card" href="{escape(contextual_player_url(str(player.get("id") or ""), from_team=roster_id, section="my-team-advanced", week=view["overview"]["projection_week"]))}">{player_summary(player_id=str(player.get("id") or ""), name=str(player.get("name") or "Unknown player"), position=str(player.get("position") or ""), nfl_team=str(player.get("team") or player.get("nfl_team") or "Free Agent"), context="Submitted starter", projection=card_projections.get(str(player.get("id") or "")))}</a>'
            for player in starters
        ) or '<div class="ds-empty"><b>No starting lineup is available.</b>Sleeper has not supplied a current starter assignment.</div>'
        from src.ui.team_strength import strength_panel
        multi_horizon_html = strength_panel(assessment.multi_horizon_strength, league_id=assessment.league_id,
                                           roster_id=assessment.roster_id, players=team.get('players'), from_team=roster_id)
        binding = workspace_context(data, roster_id)
        context_json = escape(json.dumps(binding, separators=(',', ':')), quote=True)
        options = ''.join(f'<option value="{escape(value)}" {"selected" if value == strategy else ""}>{escape(value.title() if value else "No goal")}</option>' for value in ('', 'WIN NOW', 'RETOOL', 'REBUILD'))
        if editable:
            from services.strategy_session import strategy_scope
            revision = getattr(account, "franchise_goal_revision", 0) if account else 0
            scope = strategy_scope()
            feedback = 'Franchise goal saved for this account, league and team.' if revision > 0 and request.query_params.get('goal_saved') == '1' else ''
            hint = ('Your saved franchise goal. Trade choices stay separate.' if revision else
                    'Save explicitly for your account. Trade choices stay separate.')
            strategy_control = (f'<form method="post" action="/account/franchise-goal" id="my-team-goal-form">'
                f'<label for="my-team-strategy">Franchise goal</label><select id="my-team-strategy" name="strategy" aria-describedby="my-team-goal-help">{options}</select>'
                f'<input type="hidden" name="csrf_token" value="{escape(account.csrf_token if account else "")}">'
                f'<input type="hidden" name="expected_revision" value="{revision}">'
                f'<input type="hidden" name="league_id" value="{escape(league_id)}">'
                f'<input type="hidden" name="roster_id" value="{roster_id}">'
                f'<input type="hidden" name="strategy_scope" value="{escape(scope)}">'
                f'<button type="submit" class="thq-action" id="my-team-save-goal" {"" if account else "disabled"}>Save goal</button>'
                f'<p id="my-team-goal-help">{hint}</p><p id="my-team-strategy-feedback" role="status">{feedback}</p></form>')
        else:
            strategy_control = '<p>Viewing another franchise; its manager strategy is not inferred from holdings.</p>'
        own_team = account.membership.roster_id if account and account.membership else roster_id
        scope_notice = '' if editable else f'<nav class="thq-actions" aria-label="Read-only franchise navigation"><a class="thq-action" href="/">Back to Home</a><a class="thq-action" href="/teams/{own_team}">My Team</a><span>Read-only franchise evaluation</span></nav>'
        overview = view['overview']
        roster_summary = ' · '.join(f'{count} {slot.lower()}' for slot, count in overview['slots'].items())
        view["outlook"]["details"].extend(overview["statuses"])
        assessment_outlook = view['outlook']
        comparison = prepared_comparison(data, view['projection_snapshot'])
        from services.team_trade_need import prepared_need
        assessment_outlook = {**assessment_outlook, 'trade_need': prepared_need(data, roster_id, comparison) if editable else None}
        if view['team_intelligence'].overall.score is None:
            assessment_outlook = {
                **assessment_outlook,
                'brief': weekly_comparison(view['team_intelligence'], data.get('week'), compact=True,
                                           diagnostics=comparison),
                'position': f"Standing {overview['standing']} by Sleeper record/PF. " + weekly_comparison(
                    view['team_intelligence'], data.get('week'), diagnostics=comparison),
                'details': [MODEL_NOTE, *assessment_outlook['details']],
            }
        body = f"""
{TEAM_HQ_CSS}
<style>
.thq-outlook{{padding:12px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--surface);overflow-wrap:anywhere}}.thq-outlook h2{{font-size:18px;margin:0 0 8px}}.thq-outlook p{{font-size:14px;line-height:1.5;margin:6px 0}}.thq-outlook li{{font-size:14px;line-height:1.5;margin:6px 0}}.thq-outlook .thq-strength-detail{{margin:0}}.thq-outlook .thq-strength-detail>summary{{display:list-item;list-style:disclosure-closed inside}}.thq-outlook .thq-strength-detail[open]>summary{{list-style-type:disclosure-open}}.thq-outlook summary h2{{display:inline;font-size:18px;margin:0}}.thq-outlook summary p{{line-height:1.4;margin:4px 0}}.thq-outlook .thq-actions{{margin:6px 0 0}}.thq-name-row{{display:flex;flex-wrap:wrap;align-items:center;gap:6px}}.thq-name-row>details[open]{{flex-basis:100%}}.thq-header{{margin-bottom:12px;gap:12px}}.thq-header .thq-avatar,.thq-header .franchise-portrait{{width:48px;height:48px;flex-basis:48px;font-size:23px}}.thq-title h1{{font-size:22px;margin:0}}.thq-title p{{margin:0}}.thq-actions{{margin:8px 0;gap:6px}}.thq-section{{margin-top:16px}}.thq-room-head{{padding:4px 10px;font-size:14px}}.thq-player{{padding:8px 10px}}.thq-player>div{{position:relative;padding-right:52px}}.thq-player>div>.thq-action{{position:absolute;right:0;top:0;padding:8px;min-height:44px}}.thq-player .player-summary{{gap:8px}}.thq-player .player-summary img{{width:40px;height:40px}}.thq-player-meta{{font-size:14px;margin-top:4px}}.thq-roster{{gap:10px}}.thq-strategy small{{display:none}}.thq-strategy{{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:6px}}.thq-strategy label{{margin:0}}.thq-strategy select{{min-width:0;margin:0}}#my-team-strategy-feedback{{grid-column:1/-1}}.thq-header{{padding:8px}}#my-team-strategy-feedback:empty{{display:none}}.thq-actions[aria-label="Roster sections"]{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));overflow:visible;max-width:100%;padding-bottom:4px}}.thq-outlook-next:empty{{display:none}}.thq-outlook-next{{margin:6px 0}}.thq-actions[aria-label="Roster sections"] .thq-action{{min-width:0;padding:8px 6px;font-size:14px;background:var(--surface);color:var(--text)}}.thq-outlook-next>.thq-action{{background:var(--accent);color:#0c1908;border-color:var(--accent)}}.thq-player .player-portrait{{width:40px;height:40px;flex-basis:40px}}.thq-player .player-headshot,.thq-player .player-headshot-fallback{{width:100%;height:100%}}body:has([data-my-team-context]) .ds-header-side{{display:none}}body:has([data-my-team-context]) .ds-page-header{{display:none}}body:has([data-my-team-context]) .ds-page-header h1{{font-size:20px}}
@media(max-width:760px){{.thq-header{{padding:8px}}#full-roster{{margin-top:12px}}.thq-outlook a,.thq-outlook summary{{scroll-margin-bottom:100px}}body:has([data-my-team-context]) .wrap{{padding-top:8px}}body:has([data-my-team-context]) .account-context{{padding:4px 0;margin-bottom:4px}}.thq-header .thq-title h1,.thq-header .thq-title p{{margin:0}}.thq-header .identity-kicker{{line-height:1.2}}.thq-outlook{{padding:8px}}body:has([data-my-team-context]) .brand p{{display:none}}body:has([data-my-team-context]) .secondary-nav{{margin-bottom:4px}}.thq-header>div:last-child{{margin-top:8px}}.thq-header .thq-title p{{font-size:14px}}.thq-identity{{gap:8px}}}}
.thq-strategy{{display:block}}#my-team-goal-form{{display:grid;grid-template-columns:60px minmax(104px,1fr) auto;gap:6px;align-items:center}}#my-team-strategy-feedback{{grid-column:1/-1}}#my-team-goal-help{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}}#my-team-save-goal{{min-height:44px;min-width:0;padding:8px;white-space:nowrap}}

@media(max-width:360px){{.thq-strategy{{grid-template-columns:56px minmax(0,1fr)}}.thq-strategy label{{white-space:normal;overflow-wrap:normal;line-height:1.3}}.thq-strategy select{{padding-left:4px;padding-right:4px}}}}
</style>
<section class="thq-content" data-my-team-context="{context_json}">
{scope_notice}
<header class="thq-header"><div class="thq-identity">{avatar}<div class="thq-title"><div class="identity-kicker">Manager: {escape(team['owner'])}</div><div class="thq-name-row"><h1>{escape(team['team_name'])}{you_badge(data, roster_id)}</h1>{champion_badge(defending_champion(data), roster_id)}</div><p>{escape(performance["record"])} · {escape(performance["standing"])}</p></div></div><div class="thq-strategy">{strategy_control}<small>League evidence updated: {escape(view['last_updated'])}</small></div></header>
{outlook_panel(assessment_outlook, editable=editable, roster_id=roster_id)}
{lineup_alert}
<section class="thq-section" id="full-roster"><details class="thq-strength-detail" id="my-team-roster" open><summary>Full Roster · {escape(_roster_projection_coverage(view))}</summary><div class="thq-roster">{_roster_rooms(view)}</div></details><details class="thq-strength-detail" id="my-team-key-players"><summary>Key players by Market value</summary>{_key_players(view)}</details></section>
<section class="thq-section" id="draft-capital"><div class="thq-section-head"><h2>Draft Capital</h2><span>Your owned future picks</span></div><div class="thq-picks">{_draft_capital(view)}</div><p class="muted">Pick details preserve the original franchise and current owner. A pick’s future draft position is unknown unless a supported range is shown.</p></section>

<section class="thq-section" id="positional-depth"><div class="thq-section-head"><h2>Starter strength and positional depth</h2><span>{escape('Week ' + str(overview['projection_week']) + ' · ' if overview['projection_week'] is not None else 'Current roster · ')}Lineup and backup projections from Sleeper</span></div>{_positional_depth(view)}</section>
<section class="thq-section">{team_observations(view.get("league_observations"), roster_id)}</section>
<section class="thq-section"><details class="thq-strength-detail" id="my-team-advanced"><summary>Calculations and sources</summary><div class="thq-evidence-body"><p>League evidence updated: {escape(view["last_updated"])}. Selected strategy overrides inferred direction and never changes Market prices.</p><p>Comparison ranks include only franchises with complete evidence for that named dimension. Coverage is evidence support, not an outcome probability. Overall dynasty utility and competitive-window aggregates remain unavailable without an approved model.</p><div class="thq-grades">{_team_intelligence(view)}</div>{_decision_horizons(view)}{multi_horizon_html}<h3>Submitted Starting Lineup</h3><p>Sleeper assignments remain separate from the DTOS optimal legal lineup.</p><details class="thq-strength-detail"><summary>View {len(starters)} submitted starters</summary><div class="thq-starters">{starter_cards}</div></details><h3>Roster facts</h3><p>{escape(roster_summary)} · {view['snapshot']['total_picks']} owned picks</p><div class="thq-cards">{_asset_cards(view['snapshot'])}</div><h3>Current Team Performance</h3><div class="thq-performance">{performance_cards}</div><div class="thq-summary">{summary}</div><h3>Activity</h3><div class="thq-timeline">{activity_html}</div><h3>Franchise History</h3><p>{historical_seasons} retained seasons · {historical_transactions} transactions. Historical FOIS grades are RETAINED / NOT REVALIDATED.</p><a class="thq-action" href="{franchise_history_url}">Franchise History</a><a class="thq-action" href="/history">League History</a><a class="thq-action" href="/front-offices?front_office={roster_id}">View franchise analysis</a><details><summary>About future forecasts</summary><div class="thq-future-grid">{future}</div></details></div></details></section>
</section><script src="/static/js/strategy_session.js" defer></script>
"""
        return page(f'{team["team_name"]} Headquarters', body)

    return router
