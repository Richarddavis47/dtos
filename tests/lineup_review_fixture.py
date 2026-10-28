"""Synthetic publication -> existing preparation -> authorized matchup HTTP."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from routes.matchups import create_matchups_router
from services.matchup_season import prepare_season_matchups
from src.core.intelligence.team_strength import prepare_for_data
from src.core.projection_intelligence.service import ProjectionService


def prepared(owner, *, empty=False, league_id='lineup-A', points=None, slots=None):
    tmp = TemporaryDirectory()
    owner.addCleanup(tmp.cleanup)
    now = datetime.now(timezone.utc)
    league = dict(league_id=league_id, name='Disposable Lineup League', season='2026', sport='nfl', status='in_season',
        roster_positions=slots or ['QB', 'RB', 'FLEX', 'SUPER_FLEX', 'BN'], scoring_settings={'pass_yd': .04, 'rush_yd': .1},
        settings=dict(leg=8, last_scored_leg=7, start_week=1, playoff_week_start=15, playoff_teams=4,
                      playoff_round_type=0, playoff_type=0, best_ball=0, sub_start_time_eligibility=0))
    data = dict(league=league, week=8, roster_positions=league['roster_positions'],
                scoring_settings=league['scoring_settings'], teams=[], players={})
    values = {'q': 10, 'bq': 25, 'r': 12, 'w': 14, 's': 11}
    values.update(points or {})
    payloads, rows = {8: [], 9: []}, []
    for rid in (1, 2):
        roster = dict(roster_id=rid, team_name=f'Fixture team {rid}', owner=f'Fixture manager {rid}', players=[])
        starters = [f'{rid}-q', f'{rid}-r', f'{rid}-w', f'{rid}-s']
        if empty and rid == 1:
            starters[0] = '0'
        for label, pos in [('q', 'QB'), ('bq', 'QB'), ('r', 'RB'), ('w', 'WR'), ('s', 'RB')]:
            pid = f'{rid}-{label}'
            player = dict(id=pid, player_id=pid, full_name=f'Example {label.upper()} {rid}', name=f'Example {label.upper()} {rid}',
                          position=pos, fantasy_positions=[pos], team='BUF', status='Active',
                          roster_slot='Starter' if pid in starters else 'Bench',
                          starter_index=starters.index(pid) if pid in starters else None)
            data['players'][pid] = deepcopy(player)
            roster['players'].append(player)
            for week in payloads:
                value = values[label]
                stat, scale = ('pass_yd', .04) if pos == 'QB' else ('rush_yd', .1)
                payloads[week].append(dict(player_id=pid, week=week, season=2026, team='BUF', opponent='NYJ',
                    player=dict(position=pos, fantasy_positions=[pos]), updated_at=now.isoformat(),
                    stats={stat: (value + (week - 8) * 2) / scale} if value is not None else {'adp_dd_ppr': 1000}))
        data['teams'].append(roster)
        rows.append(dict(roster_id=rid, matchup_id=1, starters=starters,
                         players=[p['id'] for p in roster['players']], points=0, starters_points=[0]*4))
    async def fetch(path):
        return deepcopy(rows) if '/matchups/' in path else []
    data['season_matchups'] = asyncio.run(prepare_season_matchups(league, 8, rows, fetch, observed_at=now.isoformat()))
    service = ProjectionService(Path(tmp.name, 'projections.sqlite'), league_id=league_id)
    service.publish_horizon(payloads, data=data, league_id=league_id, season=2026, current_week=8)
    # Controlled public schedule facts enter the actual existing preparation
    # handoff; no production catalog or private account data enters this fixture.
    facts = [dict(family='schedule', season=2026, week=week, provider='nflverse', fingerprint=f'fixture-game-{week}',
                  values=dict(home_team='BUF', away_team='NYJ', game_type='REG',
                              game_id=f'fixture-game-{week}', kickoff=(now + timedelta(hours=2, days=7*(week-8))).isoformat()))
             for week in (8, 9)]
    store = SimpleNamespace(read=lambda *a, **kw: deepcopy(facts))
    with patch('services.global_evidence.retained_global_evidence', return_value=store):
        prepare_for_data(service, data)
    return data, service, datetime.now(timezone.utc)


def http(owner, data, service, *, membership_league=None, roster_id=1):
    from dtos_app import CSS
    app = FastAPI()
    app.include_router(create_matchups_router(ensure_fresh=AsyncMock(), require_data=lambda: data,
        page=lambda title, body: HTMLResponse('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1">'
              + f'<style>{CSS}</style></head><body><main class="wrap"><h1>{title}</h1>{body}</main></body></html>')))
    owner.enterContext(patch('routes.matchups.current_league_context', return_value=SimpleNamespace(projection=service)))
    owner.enterContext(patch('routes.matchups.current_account', return_value=SimpleNamespace(
        membership=SimpleNamespace(league_id=membership_league or data['league']['league_id'], roster_id=roster_id))))
    client = TestClient(app)
    owner.addCleanup(client.close)
    return client
