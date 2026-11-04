"""Migrate legacy test inputs to the actual prepared Matchups contract."""
import asyncio
import copy
from types import SimpleNamespace

from services.matchup_season import prepare_season_matchups


def prepared_fixture(data, summary):
    result = copy.deepcopy(data)
    selected = int(data.get('week') or 1)
    sides = [side for group in data['matchups'].values() for side in group]
    final = any(side.get('status') == 'final' for side in sides)
    league_id = str(data.get('league_id') or (data.get('league') or {}).get('league_id') or 'A')
    result['league'] = {'league_id': league_id, 'season': '2026', 'sport': 'nfl', 'status': 'in_season',
        'settings': {'leg': selected + 1 if final else selected, 'last_scored_leg': selected if final else selected - 1,
                     'start_week': 1, 'playoff_week_start': 15, 'playoff_teams': 6, 'playoff_round_type': 0, 'playoff_type': 0}}
    result['teams'] = [{'roster_id': side['roster_id'], 'team_name': side['team']} for side in sides]
    result['players'] = {p['id']: {'full_name': p['name'], 'position': p.get('position')} for side in sides for p in side.get('lineup') or []}
    expected = max(len(side.get('lineup') or []) for side in sides)
    for side in summary['sides']:
        coverage = str(side.get('canonical_projection_coverage') or side.get('sleeper_coverage') or '')
        if '/' in coverage:
            expected = max(expected, int(coverage.split('/')[1]))
    result['roster_positions'] = ['QB'] * expected
    rows = [{'roster_id': side['roster_id'], 'matchup_id': int(mid), 'points': side['points'],
             'starters': [p['id'] for p in side.get('lineup') or []],
             'starters_points': [p['points'] for p in side.get('lineup') or []],
             'players': [p['id'] for p in side.get('lineup') or []]} for mid, group in data['matchups'].items() for side in group]
    async def fetch(path):
        return rows if '/matchups/' in path else []
    result['season_matchups'] = asyncio.run(prepare_season_matchups(result['league'], selected, rows, fetch, observed_at='fixture'))
    snapshot = {'league_id': league_id, 'season': 2026, 'week': selected, 'horizon_generation': 'fixture',
                'projection_snapshot_id': 'fixture-week', 'players': {p['player_id']: p for side in summary['sides'] for p in side.get('players') or []}}
    service = SimpleNamespace(snapshot=lambda: snapshot, week_snapshot=lambda week, **kw: snapshot if week == selected else None)
    return result, service
