from types import SimpleNamespace as NS
import unittest
from services.team_assessment_presentation import weekly_comparison, MODEL_NOTE


class AssessmentCoverageTests(unittest.TestCase):
    def card(self, available=True, qualified='provisional'):
        return NS(league_id='fixture', starting_lineup=NS(rank=1),
                  competitive_window=NS(production_profile={
                      'projection_generation': 'g',
                      'current_week_comparison': {'league_id': 'fixture', 'week': 9,
                          'projection_generation': 'g', 'supported_count': 11, 'league_size': 12,
                          'required_slots': ['QB'] * 10},
                      'weekly': {9: {'available': available,
                          'optimal': {'projected_points': 153.3408 if available else None},
                          'coverage': {'supported_slots': 10 if available else 9,
                                       'unsupported_slots': [] if available else ['DEF']},
                          'reserve_capacity': {'qualification': {'conclusion_state': qualified}}}}}))

    def test_complete_provisional_comparison(self):
        text = weekly_comparison(self.card(), 9)
        for word in ['Provisional', 'Week 9', '153.34 points', '10/10', '#1 among 11', '11 of 12']:
            self.assertIn(word, text)

    def test_partial_does_not_publish_a_rank_or_total(self):
        text = weekly_comparison(self.card(False), 9)
        self.assertIn('9/10', text)
        self.assertIn('DEF', text)
        self.assertNotIn('#1', text)
        self.assertNotIn('153.34', text)

    def test_generation_conflict(self):
        card = self.card()
        card.competitive_window.production_profile['projection_generation'] = 'other'
        self.assertIn('needs compatible', weekly_comparison(card, 9))

    def test_missing_and_wrong_week(self):
        self.assertIn('needs compatible', weekly_comparison(self.card(), 10))
        card = self.card()
        card.competitive_window.production_profile = {}
        self.assertIn('needs compatible', weekly_comparison(card, 9))

    def test_zero_and_current(self):
        card = self.card(qualified='current')
        card.competitive_window.production_profile['weekly'][9]['optimal']['projected_points'] = 0
        text = weekly_comparison(card, 9)
        self.assertIn('0.00 points', text)
        self.assertNotIn('Provisional', text)
        self.assertIn('validated overall team grade', MODEL_NOTE)

    def test_home_rendered_complete_partial_missing_and_existing_overall(self):
        from unittest.mock import AsyncMock, patch
        from fastapi.responses import HTMLResponse
        from routes.home import create_home_router
        from tests.test_trade_workspace_batch1 import AuthenticatedTradeBoundaryTests
        f = AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        app, data = f.client.app, f.data
        state = [0]
        app.include_router(create_home_router(ensure_fresh=AsyncMock(), require_data=lambda: data,
            page=lambda title, body: HTMLResponse(body), generation_provider=lambda: (self.id(), state[0])))
        for index, card in enumerate([self.card(), self.card(False), None]):
            state[0] = index
            text = weekly_comparison(card, 9) if card else 'Compatible weekly lineup evidence is not prepared for this league.'
            directory = {t['roster_id']: {'rank': None, 'weekly_comparison': text} for t in data['teams']}
            with patch('routes.home.build_team_directory', return_value=directory):
                response = f.client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(text, response.text)
            self.assertNotIn('Canonical team assessment rankings unavailable', response.text)
        state[0] = 4
        directory = {t['roster_id']: {'rank': i + 1} for i, t in enumerate(data['teams'])}
        with patch('routes.home.build_team_directory', return_value=directory):
            self.assertIn('<h2>Team Assessment Rankings</h2>', f.client.get('/').text)

    def test_my_team_rendered_complete_partial_and_missing(self):
        from unittest.mock import patch
        from tests.test_my_team_outlook_http import MyTeamOutlookHTTPTests
        f = MyTeamOutlookHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        for card in [self.card(), self.card(False), None]:
            text = weekly_comparison(card, 9) if card else 'Week 9 comparison needs compatible projections.'
            with patch('routes.teams.weekly_comparison', return_value=text):
                response = f.client.get('/teams/1')
            self.assertEqual(response.status_code, 200)
            self.assertIn(text, response.text)
            self.assertIn(MODEL_NOTE, response.text)
            self.assertLess(response.text.index('<h2>Projected lineup comparison'), response.text.index('id="full-roster"'))
