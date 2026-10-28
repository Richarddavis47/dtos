"""Disposable ten-franchise Week 8 publisher and private HTTP application.

No production league records or provider responses are embedded here. Numbers
and players are synthetic; the canonical scoring/publication paths are real.
"""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from routes.transactions import create_transactions_router
from src.core.intelligence.team_strength import prepare_for_data
from tests import test_roster_diagnostic_http as fixtures


def prepared(owner):
    f = fixtures.DiagnosticHTTPTests()
    f.setUp()
    owner.addCleanup(f.doCleanups)
    data, service = f.f.f.data, f.f.source.reader
    template = deepcopy(data['teams'][0])
    data['week'] = 8
    data['league'].update(name='Disposable Week 8 League', season=2026,
        roster_positions=['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPER_FLEX'] + ['BN'] * 4,
        scoring_settings={'pass_yd': .04, 'rush_yd': .1, 'rec_yd': .1, 'rec': 1})
    data['league']['settings'].update(leg=8, last_scored_leg=7,
                                    playoff_week_start=14, playoff_teams=4)
    data['scoring_settings'] = data['league']['scoring_settings']
    data['nfl_state'] = {'season': '2026', 'week': 8, 'season_type': 'regular'}
    data['teams'], data['players'] = [], {}
    payload = []
    for rid in range(1, 11):
        team = {**deepcopy(template), 'roster_id': rid,
                'owner': f'Manager {rid}', 'team_name': f'Franchise {rid}',
                'owner_id': f'fixture-owner-{rid}', 'picks_owned': [], 'players': []}
        for label, pos, points in [('q', 'QB', 20), ('r', 'RB', 12), ('w', 'WR', 15),
                                   ('t', 'TE', 9), ('f', 'WR', 10), ('s', 'RB', 7),
                                   ('u', 'WR', None)]:
            pid = f'{rid}-{label}'
            fantasy = ['DB', 'WR'] if rid == 10 and label == 'w' else [pos]
            primary = 'DB' if len(fantasy) == 2 else pos
            player = dict(id=pid, player_id=pid, name=f'Player {pid}',
                full_name=f'Player {pid}', position=primary, fantasy_positions=fantasy,
                team='BUF', status='Active', age=25,
                roster_slot='Starter' if label != 'u' else 'Bench')
            data['players'][pid] = dict(player)
            team['players'].append(dict(player))
            if rid >= 8 and label == 'q':
                points = None
            stat, weight = ('pass_yd', .04) if pos == 'QB' else ('rush_yd', .1) if pos == 'RB' else ('rec_yd', .1)
            payload.append(dict(player_id=pid, season=2026, week=8,
                player={'position': primary, 'fantasy_positions': fantasy},
                team='BUF', opponent='NYJ', updated_at=datetime.now(timezone.utc).isoformat(),
                stats={stat: points / weight} if points is not None else {'adp_dd_ppr': 1000}))
        data['teams'].append(team)
    # One known-bye bench record and one current Out record; neither is zeroed.
    for label, status in [('bye', 'Active'), ('out', 'Out')]:
        pid = '1-' + label
        player = dict(id=pid, player_id=pid, name=f'Player {label}', full_name=f'Player {label}',
            position='QB', fantasy_positions=['QB'], team='BUF', status=status,
            injury_status='Out' if status == 'Out' else None, age=25, roster_slot='Bench')
        data['players'][pid] = dict(player)
        data['teams'][0]['players'].append(dict(player))
        payload.append(dict(player_id=pid, season=2026, week=8, team='BUF',
            player={'position': 'QB', 'fantasy_positions': ['QB']},
            updated_at=datetime.now(timezone.utc).isoformat(), stats={'pass_yd': 1000}))
    # An ADP-only record with an explicitly unassigned NFL team.
    data['players']['1-u']['team'] = None
    next(p for p in data['teams'][0]['players'] if p['id'] == '1-u')['team'] = None
    next(p for p in payload if p['player_id'] == '1-u').update(team=None, opponent=None)
    byes = {'season': 2026, 'reference': 'frozen-disposable-schedule', 'player_weeks': {'1-bye': 8}}
    service.publish_horizon({8: payload}, data=data, league_id='league-1', season=2026, current_week=8)
    with patch('services.global_evidence.retained_global_evidence', return_value=None):
        prepare_for_data(service, data, bye_evidence=byes)
    # Serve the actual lightweight weekly player route under the fixture's auth.
    import dtos_app
    f.f.f.client.app.include_router(create_transactions_router(
        ensure_fresh=AsyncMock(), refresh_transactions=AsyncMock(),
        require_data=lambda: data, state={'data': data}, page=dtos_app.page))
    owner.enterContext(patch('routes.transactions.current_league_context',
                            return_value=type('Context', (), {'projection': service})()))
    return f, data, service
