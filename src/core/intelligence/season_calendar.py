"""League-season calendar from retained Sleeper settings, not team defaults."""
import hashlib
import json

METHOD = 'sleeper-nfl-calendar-v1'


def season_calendar(league: dict) -> dict:
    settings = league.get('settings') or {}
    fields = ('leg', 'last_scored_leg', 'start_week', 'playoff_week_start',
              'playoff_teams', 'playoff_round_type', 'playoff_type')
    source = {key: settings.get(key) for key in fields}
    identity = {'league_id': str(league.get('league_id') or ''), 'season': league.get('season'),
                'sport': league.get('sport'), 'status': league.get('status'), 'settings': source, 'method': METHOD}
    reference = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    result = {'league_id': identity['league_id'], 'season': identity['season'], 'reference': reference,
              'source': 'Sleeper league settings', 'source_fields': source, 'methodology': METHOD,
              'availability': 'unavailable', 'regular_season_weeks': None, 'playoff_rounds': None,
              'current_week': source['leg'], 'reason': 'UNSUPPORTED_OR_INCOMPLETE_CALENDAR',
              'locked_bye_roster_ids': [], 'playoff_opponent': None}
    if league.get('sport') != 'nfl' or not identity['league_id']:
        return result
    if any(type(source[key]) is not int for key in fields):
        return result
    start, current, completed = source['start_week'], source['leg'], source['last_scored_leg']
    first, teams, kind = source['playoff_week_start'], source['playoff_teams'], source['playoff_round_type']
    # Completed Sleeper seasons retain leg == last_scored_leg. This does not
    # authorize an in-season current week to be treated as final.
    completed_season = league.get('status') == 'complete' and completed == current
    if (not 1 <= start <= current <= 18 or not 0 <= completed <= 18 or (completed >= current and not completed_season)
            or not start < first <= 18 or teams not in (4, 6, 8)
            or kind not in (0, 1, 2) or source['playoff_type'] != 0):
        return result
    # Public Sleeper web mapping: 0 single-week, 1 two-week final, 2 all two-week.
    # Standard supported winner brackets: 4 teams -> 2 rounds, 6/8 -> 3 rounds.
    count = 2 if teams == 4 else 3
    rounds, week = [], first
    for ordinal in range(count):
        length = 2 if kind == 2 or (kind == 1 and ordinal == count - 1) else 1
        rounds.append(list(range(week, week + length)))
        week += length
    if week - 1 > 18:
        return result
    result.update(availability='supported', reason=None, regular_season_weeks=list(range(start, first)),
                  remaining_regular_season_weeks=list(range(max(current, completed + 1), first)),
                  playoff_rounds=rounds, first_round_bye_slots=2 if teams == 6 else 0,
                  bye_meaning='structural slots only; no projected team is guaranteed qualification',
                  round_membership={str(w): i + 1 for i, weeks in enumerate(rounds) for w in weeks})
    return result
