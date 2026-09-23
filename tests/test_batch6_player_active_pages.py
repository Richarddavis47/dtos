"""Bounded active parent-page timing; no live provider or production state."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
from time import perf_counter
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.transactions import create_transactions_router
from routes.teams import create_teams_router
from src.core.data_platform import DataPlatform, SnapshotWarehouse, data_platform
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from tests.test_trade_intelligence import fixture_data


class ActivePlayerPagesTests(unittest.TestCase):
    def test_parent_open_and_week_read_are_scoped_and_measured(self):
        data = fixture_data()
        data['league']['season'] = 2026
        data['week'] = 2
        pid = data['teams'][0]['players'][0]['id']
        snapshot = {'league_id': 'league-1', 'season': 2026, 'week': 2,
            'horizon_generation': 'fixture', 'horizon_snapshot_ids': {'2': 'w2', '3': 'w3'},
            'players': {pid: {'canonical_projection': 27.335, 'sleeper_web_display_projection': '27.33'}}}
        service = SimpleNamespace(snapshot=lambda: snapshot,
            week_snapshot=lambda week, **kw: {**snapshot, 'week': week})
        history = SimpleNamespace(player_dossier=lambda player: {'season_summaries': [], 'ownership_timeline': [],
            'league_origin': {}, 'identity': {'canonical_id': pid, 'resolution_status': 'resolved'}},
            franchise_history=lambda rid: {'standings': [], 'transactions': [], 'identities': [],
                                           'roster_snapshots': [], 'franchise_id': f'league-1:{rid}'})
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_transactions_router(ensure_fresh=fresh, refresh_transactions=fresh,
            require_data=lambda: data, state={}, page=lambda title, body: HTMLResponse(body)))
        app.include_router(create_teams_router(ensure_fresh=fresh, require_data=lambda: data, state={},
            page=lambda title, body: HTMLResponse(body)))
        engine = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache())
        with tempfile.TemporaryDirectory(prefix='dtos-player-parent-') as temp, ExitStack() as stack:
            warehouse = SnapshotWarehouse(Path(temp) / 'warehouse.json')
            platform = DataPlatform(registry=data_platform.registry, warehouse=warehouse)
            stack.enter_context(patch('routes.transactions.data_platform', platform))
            stack.enter_context(patch('routes.transactions.historical_graph', return_value=history))
            stack.enter_context(patch('routes.teams.historical_graph', return_value=history))
            for module in ('routes.transactions', 'routes.teams'):
                stack.enter_context(patch(module + '.current_league_context', return_value=SimpleNamespace(projection=service)))
            stack.enter_context(patch('services.asset_intelligence.intelligence_orchestrator', engine))
            client = stack.enter_context(TestClient(app))
            timings = {}
            for label, path in [('dossier_cold', f'/players/{pid}?week=2'),
                                ('dossier_warm', f'/players/{pid}?week=2'),
                                ('week_change', f'/players/{pid}/projections?week=3'),
                                ('team_hq_parent', '/teams/1')]:
                start = perf_counter()
                response = client.get(path)
                timings[label] = perf_counter() - start
                self.assertEqual(response.status_code, 200)
                self.assertIn('27.33', response.text)
            size = warehouse.path.stat().st_size if warehouse.path.exists() else 0
            count = len(warehouse._rows)
            for _ in range(10):
                self.assertEqual(client.get(f'/players/{pid}?week=3').status_code, 200)
                self.assertEqual(client.get(f'/players/{pid}/projections?week=2').status_code, 200)
            self.assertEqual(len(warehouse._rows), count)
            self.assertEqual(warehouse.path.stat().st_size if warehouse.path.exists() else 0, size)
            self.assertEqual(data['week'], 2)
            print({'scope': 'local 30-player/3-team fixture; canonical history intentionally empty',
                   'seconds': timings, 'repeat_parent_and_week_market_warehouse_growth': 0})
