from copy import deepcopy
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.weekly_report import create_weekly_report_router
from src.core.history_context.season_cache import SleeperSeasonCache
from tests.test_batch6_matchup_season import fixture


class ReportRouteTests(unittest.TestCase):
    def test_report_is_not_a_dynamic_league_identity(self):
        from src.platform.account_context import league_path_identity
        self.assertIsNone(league_path_identity('/reports/weekly'))
        self.assertEqual(league_path_identity('/league/999'), '999')

    def setUp(self):
        self.data = fixture()[0]
        self.before = deepcopy(self.data)
        self.reads = []
        self.retained = None
        def read(league, season):
            self.reads.append((league, season))
            return self.retained
        app = FastAPI()
        app.include_router(create_weekly_report_router(require_data=lambda: self.data,
            page=lambda title, body: HTMLResponse(body), cache=SimpleNamespace(read=read)))
        self.client = TestClient(app)

    def test_current_read_and_week_switch_do_not_mutate_or_read_archive(self):
        for week in (1, 3, 1):
            response = self.client.get(f'/reports/weekly?week={week}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(f'Week {week}', response.text)
        self.assertEqual(self.data, self.before)
        self.assertEqual(self.reads, [])

    def test_a_b_a_exact_restoration(self):
        first = self.client.get('/reports/weekly?week=1').text
        self.data = fixture('B')[0]
        second = self.client.get('/reports/weekly?week=1').text
        self.assertNotIn('A team', second)
        self.assertNotEqual(first, second)
        self.data = self.before
        self.assertEqual(self.client.get('/reports/weekly?week=1').text, first)

    def test_missing_historical_archive_intentional_state(self):
        response = self.client.get('/reports/weekly?season=2025&week=16')
        self.assertIn('Unavailable', response.text)
        self.assertEqual(self.reads, [('A', 2025)])

    def test_historical_links_and_no_current_team_labels(self):
        old = deepcopy(self.data['league'])
        old.update(league_id='old-A', season='2025', status='complete')
        old['settings'].update(leg=17, last_scored_leg=17)
        self.retained = SleeperSeasonCache.normalize('A', 2025, {'league': old,
            'rosters': [{'roster_id': 1}, {'roster_id': 2}],
            'matchups': {'1': self.data['season_matchups']['weeks']['1']['rows']}})
        response = self.client.get('/reports/weekly?season=2025&week=1')
        self.assertIn('/history/2025', response.text)
        self.assertNotIn('/matchups/1', response.text)
        self.assertNotIn('A team', response.text)
        self.assertEqual(self.data, self.before)

    def test_foreign_archive_is_not_used(self):
        self.retained = SleeperSeasonCache.normalize('B', 2025, {'league': {'season': '2025'}})
        self.assertIn('Unavailable', self.client.get('/reports/weekly?season=2025&week=1').text)

    def test_query_validation_and_html_escaping(self):
        self.assertEqual(self.client.get('/reports/weekly?week=19').status_code, 422)
        self.data['league']['name'] = '<script>bad()</script>'
        body = self.client.get('/reports/weekly?week=1').text
        self.assertNotIn('<script>bad()', body)
        self.assertIn('&lt;script&gt;', body)
