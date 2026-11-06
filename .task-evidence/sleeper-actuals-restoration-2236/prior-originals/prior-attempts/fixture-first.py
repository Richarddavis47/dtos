"""Retained native scores bind before either cache path exposes consumers."""
from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from services import league_preparation, sleeper
from src.core.league_runtime import LeagueRuntime
from src.core.player_value_projection.canonical_production import prepared_production_context
from tests import test_current_production_coverage as views


class ActualRestorationTests(unittest.TestCase):
    def fixture(self):
        f = views.ProductionViewFixture(self)
        data = copy.deepcopy(f.f.data)
        data['canonical_player_production'].pop('sleeper_actuals')
        old = asdict(prepared_production_context(data['canonical_player_production'],
            league_id=data['league']['league_id'], player_id='1', data=data))
        data['valuation_intelligence']['assets']['player:1']['canonical_production'] = old
        return f, data

    def write(self, data):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory)/'cache.json'
        path.write_text(json.dumps({'data':data, 'last_sync':datetime.now(timezone.utc).isoformat()}))
        return path

    def restore(self, data, *, default=False, publish=None):
        path = self.write(data)
        lid = str(data['league']['league_id'])
        if default:
            state = {}
            with patch.object(sleeper, 'league_cache_file', return_value=path):
                sleeper.load_cache(state=state, league_id=lid)
            return state['data']
        runtime = LeagueRuntime(lid)
        with patch.object(league_preparation, 'league_cache_file', return_value=path):
            self.assertTrue(league_preparation.restore_cached_runtime(runtime, publish or Mock(),
                expected_season=int(data['league']['season'])))
        return runtime.state['data']

    def profile(self, data):
        return prepared_production_context(data['canonical_player_production'],
            league_id=data['league']['league_id'], player_id='1', data=data)

    def render(self, f, data):
        f.f.data = data
        f.f.state['data'] = data
        f.f.cache.clear()
        return [f.f.client.get(path) for path in ('/players/1?front_office=4',
            '/market?selected=player%3A1', '/api/market/assets/player:1')]

    def test_matched_default_and_connected_restoration_reach_rendered_consumers(self):
        f, data = self.fixture()
        expected = data['season_matchups']['weeks']['1']['rows'][0]['players_points']['1']
        snapshots = []
        for default in (True, False):
            with self.subTest(default=default):
                restored = self.restore(data, default=default)
                context = self.profile(restored)
                self.assertEqual(context.observations[0]['points'], expected)
                snapshots.append(asdict(context))
                dossier, market, api = self.render(f, restored)
                self.assertTrue(all(r.status_code == 200 for r in (dossier, market, api)))
                for response in (dossier, market):
                    self.assertIn('18.00 fantasy points per score observation', response.text)
                    self.assertNotIn('Compatible Sleeper actual results are not prepared', response.text)
                actual = api.json()['valuation']['canonical_production']
                self.assertEqual(actual['observations'][0]['points'], expected)
                self.assertEqual(actual['source_generation'], data['season_matchups']['semantic_generation'])
        self.assertEqual(*snapshots)
