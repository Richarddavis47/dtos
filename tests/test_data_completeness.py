"""Source-row recovery must preserve exact identity and missing versus zero."""
import copy
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse
from unittest.mock import AsyncMock
from routes.matchups import create_matchups_router
from services.matchup_season import source_player_actual, season_week_view
from src.ui.matchup_season import render_season_week
from tests.test_batch6_matchup_season import fixture


class SourceCompletenessTests(unittest.TestCase):
    def test_same_row_fallback_and_zero_precedence(self):
        row = {'starters_points': [None, 0, 'bad', True],
               'players_points': {'a': 12.345, 'b': 25, 'c': 4, 'd': 8, 'bench': 0}}
        before = copy.deepcopy(row)
        for pid, index, expected in [('a', 0, 12.345), ('b', 1, 0), ('c', 2, 4), ('d', 3, 8), ('bench', None, 0), ('unknown', 0, None)]:
            self.assertEqual(source_player_actual(row, pid, index), expected)
        self.assertEqual(row, before)
        self.assertIsNone(source_player_actual({'players_points': {'a': float('nan')}}, 'a'))

    def test_source_to_preparation_to_http_and_render(self):
        data, service, _ = fixture()
        row = data['season_matchups']['weeks']['1']['rows'][0]
        row['starters_points'] = [None]
        row['players_points'] = {'1': 13.75}
        # No current projections are used for historical actuals.
        view = season_week_view(data, 1, service)
        self.assertEqual(view['groups']['1'][0]['lineup'][0]['actual'], 13.75)
        app = FastAPI()

        app.include_router(create_matchups_router(ensure_fresh=AsyncMock(), require_data=lambda: data, page=lambda title, body: HTMLResponse(body)))

        with TestClient(app) as client:
            self.assertIn('13.75', client.get('/matchups/1?week=1').text)
        self.assertIn('13.75', render_season_week(view, matchup_id='1'))
        row['players_points'] = {}
        self.assertIsNone(season_week_view(data, 1, service)['groups']['1'][0]['lineup'][0]['actual'])
