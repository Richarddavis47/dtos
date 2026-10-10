"""Compact standings from official evidence; never infer ranks or qualification."""
from html import escape

from services.matchup_season import number
from src.core.intelligence.season_calendar import season_calendar
from src.ui.badges import champion_badge, defending_champion, official_ranks, standing_badge, streak_badge, you_badge
from src.ui.intelligence_presentation import league_is_preseason, record_evidence


def playoff_boundary(data, ranks):
    settings = (data.get('league') or {}).get('settings') or {}
    count = settings.get('playoff_teams')
    if not ranks:
        return None, 'Playoff boundary unavailable: official standings ranks are not supplied.'
    if type(count) is not int or not 0 < count < len(ranks):
        return None, 'Playoff boundary unavailable: qualification count is not established.'
    # Division, custom and unknown qualification formats need more than a rank.
    if type(settings.get('divisions')) is not int or settings['divisions'] != 0 or settings.get('playoff_type') != 0:
        return None, 'Playoff boundary unavailable: division/wildcard or custom qualification rules are not established here.'
    return count, f'Current top {count} official positions under this league’s standard qualification rules. This is not a clinch or final seed.'


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
    ranks = official_ranks(data)
    preseason = league_is_preseason(data)
    champion = defending_champion(data) if champion is None else champion
    teams = sorted(data.get('teams') or [], key=lambda t: (ranks.get(int(t['roster_id']), 999), int(t['roster_id'])))
    boundary, explanation = playoff_boundary(data, ranks)
    rows = []
    for index, team in enumerate(teams):
        rid = int(team['roster_id'])
        if boundary is not None and index == boundary:
            rows.append(f'<tr class="playoff-boundary"><td colspan="4">Playoff-position boundary · top {boundary}</td></tr>')
        own = you_badge(data, rid)
        rank = standing_badge(ranks.get(rid)) if ranks else '<span class="standing-rank">Rank unavailable</span>'
        avatar = str(team.get('avatar') or '')
        image = f'<img class="matchup-avatar" src="https://sleepercdn.com/avatars/thumbs/{escape(avatar)}" alt="" loading="lazy">' if avatar and all(c.isalnum() or c in {'-', '_' } for c in avatar) else ''
        record = record_evidence(team.get('wins'), team.get('losses'), team.get('ties'), season_started=not preseason)
        values = [number(team.get(field)) for field in ('points_for', 'points_against')]
        points = ['Not started' if preseason else 'Unavailable' if v is None else f'{v:.2f}' for v in values]
        indicators = rank + champion_badge(champion, rid) + completed_streak(data, rid)
        rows.append(f'<tr class="{"standings-you" if own else ""}" data-roster-id="{rid}"><td><div class="standings-team">{image}<div><a href="/teams/{rid}">{escape(str(team.get("team_name") or "Franchise"))}</a>{own}<div class="standing-indicators">{indicators}</div></div></div></td><td>{escape(record)}</td><td>{points[0]}</td><td>{points[1]}</td></tr>')
    context = 'Current-season results—not FOIS. ' + ('Official Sleeper-reported standings; distinct from DTOS team assessments.' if ranks else 'Official records and scoring. Official rank unavailable; list order is not playoff seeding.')
    return ('<link rel="stylesheet" href="/static/css/matchups.css"><section class="card standings-panel" aria-label="League standings">'
            f'<p>{context}</p><table class="compact-standings"><thead><tr><th scope="col">Franchise / rank</th><th scope="col">Record</th><th scope="col">PF</th><th scope="col">PA</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<details><summary>Standings and playoff evidence</summary><p>{escape(explanation)}</p><p>PF: Points For. PA: Points Against. W/L badges are completed-game streaks. Rank movement is unavailable without comparable official rank observations. Medals require official placement; trophies require this league’s preceding championship evidence.</p></details></section>')
