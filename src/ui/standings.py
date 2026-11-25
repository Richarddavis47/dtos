"""Shared record/PF standings with explicit statistical provenance."""
from html import escape

from services.matchup_season import METHOD, number
from services.standings import playoff_position, reconstructed_movement, standings_order
from src.core.intelligence.season_calendar import season_calendar
from src.ui.badges import champion_badge, defending_champion, official_ranks, streak_badge, you_badge, movement_badge
from src.ui.intelligence_presentation import league_is_preseason, record_evidence


def playoff_boundary(data, ranks):
    # Compatibility signature; qualification needs complete statistical evidence.
    order = standings_order(data)
    result = playoff_position(data, order)
    return result['boundary'], result['reason']


def _streak_evidence(data, roster_id):
    league = data.get('league') or {}
    prepared = data.get('season_matchups') or {}
    calendar = season_calendar(league)
    if (prepared.get('league_id') != str(league.get('league_id')) or prepared.get('season') != str(league.get('season'))
            or prepared.get('calendar_reference') != calendar['reference'] or prepared.get('methodology') != METHOD):
        return [], None
    completed = (league.get('settings') or {}).get('last_scored_leg')
    if type(completed) is not int:
        return [], None
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
        if len(pair) != 2 or len({r.get('roster_id') for r in pair}) != 2 or any(score is None for score in scores):
            results, weeks = [], []
            unknown_start = True
            continue
        a, b = scores if pair[0]['roster_id'] == roster_id else reversed(scores)
        results.append('W' if a > b else 'L' if a < b else 'T')
        weeks.append(week)
    if unknown_start and results and len(set(results)) == 1:
        return [], None  # A missing predecessor cannot establish the complete streak.
    return results, f'completed Weeks {weeks[0]}–{weeks[-1]}' if weeks else None


def completed_streak(data, roster_id):
    results, period = _streak_evidence(data, roster_id)
    return streak_badge(results, period)


def _streak_cell(results):
    if not results:
        return '<span aria-label="Streak unavailable">—</span>'
    last = results[-1]
    count = 0
    for outcome in reversed(results):
        if outcome != last:
            break
        count += 1
    result = {"W": "win", "L": "loss", "T": "tie"}[last]
    return f'<span class="league-streak" role="img" data-result="{last}" aria-label="Head-to-head {result} streak: {count}">{last}{count}</span>'


def _movement_cell(current, previous):
    if current is None or previous is None:
        return '<span aria-label="Prior-week rank comparison unavailable">—</span>'
    delta = previous - current
    if delta == 0:
        return '<span aria-label="Rank unchanged">0</span>'
    direction, arrow, sign = ('up', '↑', '+') if delta > 0 else ('down', '↓', '−')
    return f'<span class="league-rank-change" role="img" data-direction="{direction}" aria-label="Rank {direction} {abs(delta)}"><span aria-hidden="true">{arrow}{sign}{abs(delta)}</span></span>'


def render_standings(data, *, champion=None, league_hub=False, playoff_href=None):
    order = standings_order(data)
    ranks = order['ranks']
    source_ranks = official_ranks(data)
    preseason = league_is_preseason(data)
    champion = defending_champion(data) if champion is None else champion
    teams = order['teams']
    position = playoff_position(data, order)
    boundary, explanation = position['boundary'], position['reason']
    movement = reconstructed_movement(data, order)
    if league_hub and source_ranks:
        if source_ranks != ranks:
            movement = {"ranks": {}, "period": None, "reason": "Prior-week placements do not reconcile to the official ranks."}
        ranks = source_ranks
        teams = sorted(teams, key=lambda team: ranks[int(team["roster_id"])])
    settings = (data.get('league') or {}).get('settings') or {}
    count = settings.get('playoff_teams')
    verified_count = count if type(count) is int and 0 < count <= len(teams) else None
    cutoff = ''
    if league_hub and verified_count is not None:
        if position['kind'] == 'standard' and not source_ranks:
            detail = 'Current top positions'
        else:
            link = f' <a href="{escape(playoff_href, quote=True)}">View playoff race</a>' if playoff_href else ''
            detail = 'Number of spots only.' + link
        cutoff = (f'<tr class="league-cutoff"><td colspan="6">Playoff cutoff · {verified_count} spots'
                  f'<small>{detail}</small></td></tr>')
    rows = []
    evidence_rows = []
    for index, team in enumerate(teams):
        rid = int(team['roster_id'])
        if league_hub and cutoff and index == verified_count:
            rows.append(cutoff)
        if not league_hub and boundary is not None and index == boundary:
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
        streak_results, streak_period = _streak_evidence(data, rid)
        streak = streak_badge(streak_results, streak_period)
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
        if league_hub:
            indicators = f'<p>Points Against: {points[1]}</p>' + indicators
        if indicators:
            evidence_rows.append(f'<div id="standing-evidence-{rid}"><h3>{escape(str(team.get("team_name") or "Franchise"))}</h3><div class="standing-indicators">{indicators}</div></div>')
        if league_hub:
            compact_rank = str(ranks[rid]) if rid in ranks else f'{placement[0]}–{placement[1]}' if placement else '—'
            rank_label = rank_text if placement or rid in ranks else 'Rank unavailable'
            record_text = record if record not in {'Not started', 'Record unavailable'} else '—'
            points_text = points[0] if points[0] not in {'Not started', 'Unavailable'} else '—'
            rows.append(
                f'<tr class="{"standings-you" if own else ""}" data-roster-id="{rid}">'
                f'<td class="league-rank" aria-label="{rank_label}">{compact_rank}</td>'
                f'<th scope="row" class="league-team"><a href="/teams/{rid}">{escape(str(team.get("team_name") or "Franchise"))}</a>{own}{qualified}</th>'
                f'<td class="league-record" aria-label="{escape(record)}">{record_text}</td>'
                f'<td class="league-pf" aria-label="Points For: {points[0]}">{points_text}</td>'
                f'<td>{_streak_cell(streak_results)}</td><td>{_movement_cell(ranks.get(rid), movement["ranks"].get(rid))}</td></tr>'
            )
            continue
        rows.append(f'<tr class="{"standings-you" if own else ""}" data-roster-id="{rid}"><td><div class="standings-team">{image}<div>{rank}<a href="/teams/{rid}">{escape(str(team.get("team_name") or "Franchise"))}</a>{own}<span class="standing-inline">{inline}</span>{qualified}</div></div></td><td data-label="Record">{escape(record)}</td><td data-label="PF">{points[0]}</td><td data-label="PA">{points[1]}</td></tr>')
    if cutoff and verified_count == len(teams):
        rows.append(cutoff)
    context = 'Current-season results—not FOIS. ' + order['provenance'] + ' DTOS-organized from source facts, not Sleeper-supplied playoff seeds.'
    limitation = f'<p class="muted">{escape(order["reason"])}</p>' if order['reason'] else ''
    details = (f'<details id="standings-evidence"><summary>Standings and playoff evidence</summary><p>{escape(context)}</p>{"".join(evidence_rows)}<p>{escape(explanation)}</p><p>{escape(movement["reason"])}</p><p>PF: source cumulative Points For. PA: source cumulative Points Against, not a ranking tiebreak. Equal opportunities and equal tie counts are ordered by wins then PF. Other record comparisons require verified rules. W/L badges are completed head-to-head streaks. Medals identify resolved statistical positions; trophies require this league’s preceding championship evidence.</p></details>')
    if league_hub:
        done = settings.get('last_scored_leg')
        reporting = f'Through completed Week {done}' if type(done) is int and 1 <= done <= 18 and not preseason else 'Reporting week unavailable'
        if preseason:
            reporting = 'Regular-season standings have not started'
        season = (data.get('league') or {}).get('season')
        if season:
            reporting = f'{escape(str(season))} season · {reporting}'
        source = 'Official Sleeper ranks' if source_ranks else 'Sleeper records and points · DTOS-organized order'
        previous = ('Rank change compares ' + movement['period'] + '. 0 means unchanged.'
                    if movement['period'] else 'Prior-week rank comparison unavailable.')
        count_status = 'No playoff spots are configured.' if type(count) is int and count == 0 else 'Playoff spot count could not be verified for this table.'
        count_note = f'<p class="muted">{count_status}</p>' if verified_count is None else ''
        return (
            '<section class="standings-panel league-standings" aria-labelledby="league-standings-title">'
            '<div class="league-section-heading"><h2 id="league-standings-title">Standings</h2>'
            '<a href="/teams">Team details</a></div>'
            f'<p class="muted league-reporting-week">{reporting} · {source}</p>{limitation}'
            '<table class="league-standings-table" aria-label="League standings"><colgroup>'
            '<col class="league-col-rank"><col><col class="league-col-record"><col class="league-col-pf">'
            '<col class="league-col-streak"><col class="league-col-change"></colgroup>'
            '<thead><tr><th scope="col">#</th><th scope="col">Team</th><th scope="col">Record</th>'
            '<th scope="col" aria-label="Points For">PF</th><th scope="col" aria-label="Head-to-head streak">Streak</th>'
            f'<th scope="col" aria-label="Rank change">Δ rank</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<p class="muted">{previous} — means unavailable.</p>{count_note}{details}</section>'
        )
    return ('<link rel="stylesheet" href="/static/css/matchups.css"><section class="card standings-panel" aria-label="League standings">'
            f'<p class="muted">Sleeper records and points · DTOS-organized order</p>{limitation}<table class="compact-standings"><thead><tr><th scope="col">Franchise / rank</th><th scope="col">Record</th><th scope="col">PF</th><th scope="col">PA</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'{details}</section>'
            "<script>document.querySelectorAll('.standings-panel a[href^=\"#standing-evidence-\"]').forEach(a=>a.addEventListener('click',()=>{document.getElementById('standings-evidence').open=true;}));</script>")
