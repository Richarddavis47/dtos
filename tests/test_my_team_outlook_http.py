"""Actual authenticated My Team routes and prepared strength display controls."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from routes.teams import create_teams_router
from src.ui.team_strength import strength_panel
from tests.test_roster_diagnostic_http import DiagnosticHTTPTests


class MyTeamOutlookHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = DiagnosticHTTPTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.publish(datetime.now(timezone.utc).isoformat())
        self.client = self.f.f.f.client
        self.data = self.f.f.f.data

    def directory(self):
        # Authenticated /teams intentionally redirects to the owner's HQ.
        # Exercise the actual directory router independently of that alias.
        app = FastAPI()
        app.include_router(create_teams_router(ensure_fresh=AsyncMock(),
            require_data=lambda: self.data, state={'data': self.data}, page=lambda title, body: body))
        with TestClient(app) as client:
            return client.get('/teams')

    def test_actual_my_team_takeaway_precedes_roster_and_capital(self):
        response = self.client.get('/teams/1')
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('id="my-team-outlook"', html)
        self.assertLess(html.index('id="my-team-outlook"'), html.index('id="full-roster"'))
        self.assertLess(html.index('id="my-team-outlook"'), html.index('id="draft-capital"'))
        self.assertEqual(html.count('Your roster at a glance'), 1)
        self.assertIn('Why this outlook?', html)

    def test_preseason_directory_never_prints_null_percentages(self):
        for team in self.data['teams']:
            team.update(wins=0, losses=0, ties=0)
        response = self.directory()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('None%', response.text)
        self.assertIn('Forecast unavailable', response.text)

    def test_supported_numeric_zero_probability_remains_zero(self):
        directory = {t['roster_id']: dict(preseason=True, rank=None, projected_wins=None,
            playoff_odds=0, championship_odds=0, grade='Unavailable') for t in self.data['teams']}
        with patch('routes.teams.build_team_directory', return_value=directory):
            response = self.directory()
        self.assertEqual(response.status_code, 200)
        self.assertIn('<b>0%</b>', response.text)

    def test_source_published_stale_and_missing_scoring_remain_qualified(self):
        self.f.publish('2020-01-01T00:00:00+00:00')
        stale = self.client.get('/teams/1')
        primary = stale.text.split('id="my-team-outlook"', 1)[1].split('id="full-roster"', 1)[0]
        self.assertIn('Provisional', primary)
        self.assertIn('not a fresh team verdict', primary)
        self.data['league'].pop('scoring_settings', None)
        self.data.pop('scoring_settings', None)
        self.f.publish()
        missing = self.client.get('/teams/1')
        self.assertEqual(missing.status_code, 200)
        primary = missing.text.split('id="my-team-outlook"', 1)[1].split('id="full-roster"', 1)[0]
        self.assertIn('Current optimal-lineup comparison unavailable', primary)
        self.assertIn('missing or incompatible projections are not zero', primary)

    def test_source_supported_fresh_evidence_has_normal_current_presentation(self):
        for team in self.data['teams']:
            for player in team['players']:
                player['status'] = 'Active'
                self.data['players'][player['id']]['status'] = 'Active'
        self.f.publish(datetime.now(timezone.utc).isoformat())
        response = self.client.get('/teams/1')
        self.assertEqual(response.status_code, 200)
        primary = response.text.split('id="my-team-outlook"', 1)[1].split('<details', 1)[0]
        self.assertIn('Week 2 optimal projected lineup', primary)
        self.assertNotIn('Provisional:', primary)
        self.assertIn('Supported positional strength: QB', primary)

    def test_projected_depth_change_uses_display_precision_only(self):
        profile = deepcopy(self.data['team_strength']['teams']['1'])
        row = profile['weekly'][3]
        row['total_change_since_previous_week'] = -4.84900000000002
        row['previous_optimal_players_on_known_bye'] = ['a']
        before = deepcopy(profile)
        html = strength_panel(profile)
        self.assertNotIn('-4.84900000000002', html)
        self.assertIn('-4.85', html)
        self.assertEqual(profile, before)

    def test_depth_negative_zero_is_normalized_and_missing_stays_unavailable(self):
        profile = deepcopy(self.data['team_strength']['teams']['1'])
        row = profile['weekly'][3]
        row['previous_optimal_players_on_known_bye'] = ['a']
        for value, expected in ((-.00001, '0'), (0, '0'), (None, 'Unavailable')):
            with self.subTest(value=value):
                row['total_change_since_previous_week'] = value
                html = strength_panel(profile)
                self.assertIn('Whole-lineup projected change: ' + expected + '.', html)
                self.assertNotIn('-0.00', html)
