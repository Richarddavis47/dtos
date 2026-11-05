"""Actual cached runtime publication through canonical, rendered history.

Source-compatible disposable leagues; no live owner data or source requests.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from routes.history import create_history_router
from services import league_preparation
from src.core.history_context import store as history_module
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.league_runtime import LeagueRuntime
from tests.test_league_runtime import league_data


def publication(league='2100000000000000001', season=2032, week=8):
    data = league_data(league)
    data['league'].update(season=str(season), status='in_season', settings={'leg': week})
    data.update(week=week, normalized_players={}, players={}, traded_picks=[],
                season_transactions={str(w): [] for w in range(1, week+1)}, transactions=[])
    data['teams'] = [dict(roster_id=i, owner_id=f'owner-{league}-{i}',
                          team_name=f'Franchise {i}', players=[]) for i in (1, 2)]
    data['season_transactions']['2'] = [dict(transaction_id='observed-trade',
        type='trade', status='complete', roster_ids=[1, 2], adds={'player-one': 1},
        drops={'player-one': 2}, draft_picks=[])]
    return data


class CurrentSeasonRuntimeHistoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import dtos_app
        self.app_module = dtos_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = CanonicalHistoryStore()
        self.cache = SleeperSeasonCache(self.folder/'seasons')
        self.enterContext(patch.object(history_module, 'sleeper_season_cache', self.cache))
        self.enterContext(patch.object(dtos_app, 'canonical_history_store', self.store))
        self.enterContext(patch('services.history.historical_store', self.store))
        self.enterContext(patch('src.core.historical_memory.read_model.historical_read_model_cache', HistoricalReadModelCache()))
        self.enterContext(patch('services.league_maintenance.ensure_periodic_refresh'))
        self.sync = self.enterContext(patch.object(dtos_app, 'sync_sleeper_league', side_effect=AssertionError('No source refresh on restore')))
        self.projection = Mock()
        self.projection.snapshot.return_value = None
        self.enterContext(patch.object(dtos_app, 'ProjectionService', return_value=self.projection))
        self.enterContext(patch.object(dtos_app, 'AssetMarketCache', return_value=Mock()))
        self.data = publication()
        self.runtime = LeagueRuntime(self.data['league']['league_id'])
        self.path = self.folder/'cache.json'
        self.enterContext(patch.object(league_preparation, 'league_cache_file', return_value=self.path))
        app = FastAPI()
        app.include_router(create_history_router(league_id=self.runtime.league_id,
            league_resolver=lambda:self.runtime.league_id,
            require_data=lambda:self.runtime.state['data'],
            page=lambda title,body:HTMLResponse(body)))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    async def restore(self):
        self.path.write_text(json.dumps(dict(data=self.data,last_sync=datetime.now(timezone.utc).isoformat())))
        await self.app_module._hydrate_league_runtime(self.runtime)

    def page(self):
        response = self.client.get('/history/team/'+self.runtime.league_id+':franchise:1')
        self.assertEqual(response.status_code,200,response.text[:300])
        return response.text

    async def test_restored_weekly_buckets_are_registered_and_rendered(self):
        await self.restore()
        self.sync.assert_not_called()
        html = self.page()
        self.assertIn('2032 · Partial transaction coverage',html)
        self.assertIn('8 of 19 supported source weeks retrieved',html)
        self.assertIn('observed-trade',html)
        self.assertIs(self.store._current[self.runtime.league_id],self.runtime.state['data'])

    async def test_eviction_releases_history_reference_and_reopening_registers_again(self):
        await self.restore()
        first = self.runtime.state['data']
        self.assertIs(self.store._current.get(self.runtime.league_id),first)
        await self.runtime.close()
        self.assertNotIn(self.runtime.league_id,self.store._current)
        self.runtime = LeagueRuntime(self.data['league']['league_id'])
        await self.restore()
        self.assertIn('observed-trade',self.page())
        self.assertIsNot(self.runtime.state['data'],first)

    async def test_old_flat_activity_is_retained_without_inventing_acquired_weeks(self):
        self.data['transactions'] = self.data.pop('season_transactions')['2']
        await self.restore()
        html = self.page()
        self.assertIn('observed-trade',html)
        self.assertIn('0 of 19 supported source weeks retrieved',html)
        self.assertNotIn('No completed transaction activity in the fully acquired',html)
