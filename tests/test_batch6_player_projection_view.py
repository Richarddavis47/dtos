import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from services.player_projection_view import player_projection_view
from services.matchup_season import season_week_view
from src.ui.player_projections import player_projection_panel
from tests.test_batch6_matchup_season import fixture
from services.player_projection_view import player_projection_views
from src.ui.design_system import player_summary
from routes.transactions import create_transactions_router


class PlayerProjectionViewTests(unittest.TestCase):
    def prepared(self):
        data, original, calls = fixture()
        pinned = {**original.snapshot(), 'horizon_snapshot_ids': {'2': 'p2', '3': 'p3', '5': 'p5'}}
        return data, SimpleNamespace(snapshot=lambda: pinned, week_snapshot=original.week_snapshot), calls

    def test_dynamic_horizon_exact_matchup_parity_and_local_week(self):
        data, service, calls = self.prepared()
        before = copy.deepcopy(data)
        view = player_projection_view(data, '2', service, 3)
        self.assertEqual(view['weeks'], [2, 3, 5])
        self.assertEqual(view['value'], 27.335)
        self.assertEqual(view['display'], '27.33')
        matchup = season_week_view(data, 3, service)['groups']['1'][1]['lineup'][0]
        self.assertEqual(view['value'], matchup['projection'])
        self.assertEqual(view['display'], matchup['projection_display'])
        self.assertEqual(data, before)
        self.assertEqual([call[0] for call in calls], [3, 3])

    def test_zero_missing_withdrawal_and_outside_horizon(self):
        data, service, calls = self.prepared()
        self.assertEqual(player_projection_view(data, '1', service, 3)['display'], '0.00')
        self.assertIsNone(player_projection_view(data, 'unknown', service, 3)['value'])
        count = len(calls)
        self.assertEqual(player_projection_view(data, '2', service, 4)['availability'], 'unavailable')
        self.assertEqual(len(calls), count)
        service.snapshot()['horizon_snapshot_ids'].pop('3')
        self.assertIsNone(player_projection_view(data, '2', service, 3)['value'])

    def test_wrong_league_scoring_and_generation_rejected(self):
        data, service, _ = self.prepared()
        data['league']['league_id'] = 'foreign'
        self.assertIsNone(player_projection_view(data, '2', service, 3)['value'])
        data['league']['league_id'] = 'A'
        data['scoring_settings'] = {'pass_td': 6}
        self.assertIsNone(player_projection_view(data, '2', service, 3)['value'])
        data.pop('scoring_settings')
        service.week_snapshot = lambda week, **kw: {**service.snapshot(), 'week': week, 'horizon_generation': 'wrong'}
        self.assertIsNone(player_projection_view(data, '2', service, 3)['value'])

    def test_navigation_scoped_and_no_wide_table(self):
        data, service, _ = self.prepared()
        body = player_projection_panel(player_projection_view(data, '2', service, 3), 4)
        self.assertIn('27.33', body)
        self.assertIn('week=5', body)
        self.assertIn('front_office=4', body)
        self.assertNotIn('<table', body)
        self.assertNotIn('Week 18', body)

    def test_card_list_reads_one_week_and_preserves_exact_value(self):
        data, service, calls = self.prepared()
        views = player_projection_views(data, ['1', '2', 'missing'], service, 3)
        self.assertEqual(len(calls), 1)
        for pid, expected in [('1', '0.00'), ('2', '27.33'), ('missing', 'Unavailable')]:
            body = player_summary(player_id=pid, name=pid, position='QB', nfl_team=None, projection=views[pid])
            self.assertIn(f'Week 3 · Sleeper {expected}', body)
            self.assertNotIn('<select', body)

    def test_active_week_endpoint_never_builds_dossier_intelligence(self):
        data, service, _ = self.prepared()
        before = copy.deepcopy(data)
        app = FastAPI()
        async def fresh():
            pass
        app.include_router(create_transactions_router(ensure_fresh=fresh, refresh_transactions=fresh,
            require_data=lambda: data, state={}, page=lambda title, body: HTMLResponse(body)))
        with patch('routes.transactions.current_league_context', return_value=SimpleNamespace(projection=service)), \
                patch('routes.transactions.build_player_dossier', side_effect=AssertionError('full dossier construction')):
            client = TestClient(app)
            response = client.get('/players/2/projections?week=3')
            self.assertEqual(response.status_code, 200)
            self.assertIn('27.33', response.text)
            self.assertEqual(client.get('/players/2/projections?week=19').status_code, 422)
            self.assertEqual(client.get('/players/not-present/projections?week=3').status_code, 404)
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()
