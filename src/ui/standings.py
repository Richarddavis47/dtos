"""Shared record/PF standings with explicit statistical provenance."""
from html import escape

from services.matchup_season import number
from services.standings import playoff_position, reconstructed_movement, standings_order
from src.core.intelligence.season_calendar import season_calendar
from src.ui.badges import champion_badge, defending_champion, official_ranks, streak_badge, you_badge, movement_badge
from src.ui.intelligence_presentation import league_is_preseason, record_evidence


def playoff_boundary(data, ranks):
    # Compatibility signature; qualification needs complete statistical evidence.
    order = standings_order(data)
    result = playoff_position(data, order)
    return result['boundary'], result['reason']


def completed_streak(data, roster_id):
    league = data.get('league') or {}
    prepared = data.get('season_matchups') or {}
    calendar = season_calendar(league)
    if (prepared.get('league_id') != str(league.get('league_id')) or prepared.get('season') != str(league.get('season'))
            or prepared.get('calendar_reference') != calendar['reference']):
        return ''
    completed = (league.get('settings') or {}).get('last_scored_leg')
    if type(completed) is not int:
        return ''
    results, weeks = [], []
    unknown_start = False
    for week in calendar.get('regular_season_weeks') or []:
        if week > completed:
            break
        evidence = (prepared.get('weeks') or {}).get(str(week)) or {}
        rows = evidence.get('rows') or []
        own = next((r for r in rows if r.get('roster_id') == roster_id), None)
        if evidence.get('availability') != 'available' or not own or own.get('matchup_id') is None:
            results, weeks = [], []
            unknown_start = True
            continue
        pair = [r for r in rows if r.get('matchup_id') == own['matchup_id']]
        scores = [number(r.get('custom_points') if r.get('custom_points') is not None else r.get('points')) for r in pair]
        if len(pair) != 2 or any(score is None for score in scores):
            results, weeks = [], []
            unknown_start = True
            continue
        a, b = scores if pair[0]['roster_id'] == roster_id else reversed(scores)
        results.append('W' if a > b else 'L' if a < b else 'T')
        weeks.append(week)
    if unknown_start and results and len(set(results)) == 1:
        return ''  # A missing predecessor cannot establish the complete streak.
    return streak_badge(results, f'completed Weeks {weeks[0]}–{weeks[-1]}') if weeks else ''


def render_standings(data, *, champion=None):
    order = standings_order(data)
    ranks = order['ranks']
    source_ranks = official_ranks(data)
    preseason = league_is_preseason(data)
    champion = defending_champion(data) if champion is None else champion
    teams = order['teams']
    position = playoff_position(data, order)
    boundary, explanation = position['boundary'], position['reason']
    movement = reconstructed_movement(data, order)
    rows = []
    evidence_rows = []
    for index, team in enumerate(teams):
        rid = int(team['roster_id'])
        if boundary is not None and index == boundary:
            rows.append(f'<tr class="playoff-boundary"><td colspan="4">Current playoff-position cutoff · top {boundary}</td></tr>')
        own = you_badge(data, rid)
        placement = order['placements'].get(rid)
        rank_text = f'#{ranks[rid]}' if rid in ranks else f'Tied {placement[0]}–{placement[1]}' if placement else 'Rank unavailable'
        rank = f'<span class="standing-rank">{rank_text}</span>'
        avatar = str(team.get('avatar') or '')
        image = f'<img class="matchup-avatar" src="https://sleepercdn.com/avatars/thumbs/{escape(avatar)}" alt="" loading="lazy">' if avatar and all(c.isalnum() or c in {'-', '_'} for c in avatar) else ''
        record = 'Not started' if preseason else record_evidence(team.get('wins'), team.get('losses'), team.get('ties'), season_started=True)
        values = [number(team.get(field)) for field in ('points_for', 'points_against')]
        points = ['Not started' if preseason else 'Unavailable' if v is None else f'{v:.2f}' for v in values]
        qualified = ''
        if position['kind'] in {'divisions', 'bracket'} and rid in position['qualifiers']:
            qualified = '<span class="standing-position">' + ('Published bracket participant' if position['kind'] == 'bracket' else 'Current playoff position') + '</span>'
        streak = completed_streak(data, rid)
        change = movement_badge(ranks.get(rid), movement['ranks'].get(rid), movement['period'], derived=True)
        indicators = champion_badge(champion, rid) + streak + change
        if source_ranks:
            indicators += f'<p>Sleeper-supplied rank #{source_ranks[rid]}; statistical order remains separate from final seeding.</p>'
        inline = {1: '🥇', 2: '🥈', 3: '🥉'}.get(ranks.get(rid), '')
        if champion and champion[1] == rid:
            inline += f'<a href="#standing-evidence-{rid}" aria-label="Defending champion evidence for {escape(str(team.get("team_name") or "Franchise"))}">🏆</a>'
        for badge in (streak, change):
            if badge:
                label = badge.split('<summary>', 1)[1].split('</summary>', 1)[0]
                inline += f'<a href="#standing-evidence-{rid}" aria-label="Streak or movement evidence for {escape(str(team.get("team_name") or "Franchise"))}">{label}</a>'
        if indicators:
            evidence_rows.append(f'<div id="standing-evidence-{rid}"><h3>{escape(str(team.get("team_name") or "Franchise"))}</h3><div class="standing-indicators">{indicators}</div></div>')
        rows.append(f'<tr class="{"standings-you" if own else ""}" data-roster-id="{rid}"><td><div class="standings-team">{image}<div>{rank}<a href="/teams/{rid}">{escape(str(team.get("team_name") or "Franchise"))}</a>{own}<span class="standing-inline">{inline}</span>{qualified}</div></div></td><td data-label="Record">{escape(record)}</td><td data-label="PF">{points[0]}</td><td data-label="PA">{points[1]}</td></tr>')
    context = 'Current-season results—not FOIS. ' + order['provenance'] + ' DTOS-organized from source facts, not Sleeper-supplied playoff seeds.'
    limitation = f'<p class="muted">{escape(order["reason"])}</p>' if order['reason'] else ''
    return ('<link rel="stylesheet" href="/static/css/matchups.css"><section class="card standings-panel" aria-label="League standings">'
            f'<p class="muted">Sleeper records and points · DTOS-organized order</p>{limitation}<table class="compact-standings"><thead><tr><th scope="col">Franchise / rank</th><th scope="col">Record</th><th scope="col">PF</th><th scope="col">PA</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<details id="standings-evidence"><summary>Standings and playoff evidence</summary><p>{escape(context)}</p>{"".join(evidence_rows)}<p>{escape(explanation)}</p><p>{escape(movement["reason"])}</p><p>PF: source cumulative Points For. PA: source cumulative Points Against, not a ranking tiebreak. Equal opportunities and equal tie counts are ordered by wins then PF. Other record comparisons require verified rules. W/L badges are completed head-to-head streaks. Medals identify resolved statistical positions; trophies require this league’s preceding championship evidence.</p></details></section>'
            "<script>document.querySelectorAll('.standings-panel a[href^=\"#standing-evidence-\"]').forEach(a=>a.addEventListener('click',()=>{document.getElementById('standings-evidence').open=true;}));</script>")
