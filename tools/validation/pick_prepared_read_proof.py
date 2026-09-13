"""Bounded authenticated candidate read proof using already prepared source inputs.

No production endpoint, production code execution, or durable evidence copy.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.accounts import create_accounts_router
from routes.draft import create_draft_router
from src.core.accounts import AccountService, AccountStore
from src.core.league_runtime import CanonicalLeagueContext, LeagueRuntimeManager
from src.core.intelligence.pick_context import pick_portfolio
from src.platform.account_context import AccountContextMiddleware
from src.platform.league_context import LeagueContextMiddleware, current_league_context


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def authenticated_prepared_reads(contexts):
    prepared = {}
    for source in contexts:
        data = deepcopy(source)
        for team in data['teams']:
            team.setdefault('team_name', f"Franchise {team['roster_id']}")
        data['traded_picks'] = [dict(p, season=str(p['year']), roster_id=p['original_roster_id'],
                                   owner_id=p['current_owner_id']) for p in data['pick_ledger']
                                if p['original_roster_id'] != p['current_owner_id']]
        prepared[str(data['league']['league_id'])] = data

    async def hydrate(runtime):
        runtime.canonical_context = CanonicalLeagueContext(runtime, None, None, None, None)
        return prepared[runtime.league_id]

    async def ready():
        assert current_league_context().data

    manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
    with tempfile.TemporaryDirectory() as directory:
        service = AccountService(AccountStore(Path(directory) / 'accounts.sqlite3'))
        account, _ = service.create_account('candidate-parity', 'Candidate parity', 'local-only test password')
        for league_id, data in prepared.items():
            service.store.upsert_membership(account, data['league'], 'fixture-user',
                data['teams'][0]['roster_id'], 'Source identity panel', 'active')
        token, csrf = service.new_session(account)
        app = FastAPI()
        app.include_router(create_accounts_router(service=service, runtime_manager=manager))
        app.include_router(create_draft_router(ensure_fresh=ready,
            require_data=lambda: current_league_context().data,
            page=lambda title, body: HTMLResponse(body)))

        @app.get('/api/parity-proof')
        async def snapshot():
            # Local diagnostic app only; never registered in DTOS production.
            context = current_league_context()
            data = context.data
            return {'league': data['league'], 'picks': data['pick_ledger'],
                'market': data['market_data'],
                'portfolios': {str(t['roster_id']): pick_portfolio(t['picks_owned'],
                    league_id=context.league_id, generation='prepared-proof') for t in data['teams']}}

        app.add_middleware(LeagueContextMiddleware, manager=manager,
                           default_league_id='0', import_enabled=True)
        app.add_middleware(AccountContextMiddleware, service=service, required=True)
        results = []
        ids = list(prepared)
        with patch('services.asset_intelligence.intelligence_orchestrator.analyze',
                   side_effect=AssertionError('Prepared Picks read invoked full analysis')):
            with TestClient(app) as client:
                client.cookies.set('dtos_session', token)
                for stage, league_id in [('cold_but_prepared', ids[0]), ('warm', ids[0]),
                                          ('league_switch', ids[1]), ('restoration', ids[0])]:
                    switched = client.post('/api/account/active-league', json={'league_id': league_id},
                                           headers={'X-CSRF-Token': csrf})
                    assert switched.status_code == 200
                    started = perf_counter()
                    response = client.get('/picks')
                    elapsed = (perf_counter() - started) * 1000
                    assert response.status_code == 200
                    assert 'Dynasty Value' not in response.text and '/100' not in response.text
                    snap = client.get('/api/parity-proof')
                    assert snap.status_code == 200
                    results.append({'stage': stage, 'league_id': league_id,
                        'read_ms': round(elapsed, 3), 'http_status': response.status_code,
                        'semantic_digest': _digest(snap.json()), 'html_digest': _digest(response.text),
                        'pick_count': len(snap.json()['picks']),
                        'rounds': snap.json()['league']['settings']['draft_rounds']})
        assert results[0]['semantic_digest'] == results[1]['semantic_digest'] == results[3]['semantic_digest']
        assert results[0]['html_digest'] == results[1]['html_digest'] == results[3]['html_digest']
        assert results[0]['semantic_digest'] != results[2]['semantic_digest']
        return {'scope': 'source-backed candidate routes + real account/league middleware; local TestClient, not deployed production',
                'preparation_in_read': False, 'full_analysis_in_read': False,
                'foIS_scope': 'prior accepted cross-league FOIS proof reused; not recomputed or simulated here',
                'reads': results}
