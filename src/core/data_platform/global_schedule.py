"""Bounded shared schedule derivation; no league copy or request-time provider."""
from .global_evidence import GlobalEvidenceStore


def team_schedule(store: GlobalEvidenceStore, team: str, *, season: int, as_of: str) -> dict:
    facts = store.read('schedule', None, season=season, as_of=as_of)
    games = []
    regular_weeks = set()
    team_weeks: dict[str, list[int]] = {}
    for fact in facts:
        row = fact['values']
        home, away = row.get('home_team'), row.get('away_team')
        week = fact['week']
        if row.get('game_type') == 'REG' and isinstance(week, int) and home and away:
            regular_weeks.add(week)
            team_weeks.setdefault(home, []).append(week)
            team_weeks.setdefault(away, []).append(week)
        if team in (home, away):
            games.append({'game_id': row.get('game_id'), 'week': week,
                          'game_type': row.get('game_type'), 'kickoff': row.get('kickoff'),
                          'opponent': away if team == home else home, 'home': team == home,
                          'evidence_fingerprint': fact['fingerprint']})
    # A hole in a partial feed is not a bye. Only the complete current NFL
    # schedule shape supports this derivation; a changed league format remains
    # unavailable rather than inventing a bye or imposing a terminal season.
    complete_shape = (len(team_weeks) == 32 and len(regular_weeks) in {17, 18}
                      and regular_weeks == set(range(1, max(regular_weeks, default=0) + 1))
                      and all(len(weeks) == len(set(weeks)) == len(regular_weeks) - 1
                              for weeks in team_weeks.values()))
    missing = regular_weeks - set(team_weeks.get(team, []))
    bye = next(iter(missing)) if complete_shape and team in team_weeks and len(missing) == 1 else None
    return {'team': team, 'season': season, 'as_of': as_of,
            'games': sorted(games, key=lambda row: (row['kickoff'] or '', row['game_id'] or '')),
            'availability': 'cached' if games else 'unavailable', 'bye_week': bye,
            'bye_availability': 'derived' if bye is not None else 'unavailable',
            'bye_basis': 'complete_32_team_regular_schedule_shape' if bye is not None else None,
            'provider_calls': 0, 'storage': 'shared_global_schedule'}
