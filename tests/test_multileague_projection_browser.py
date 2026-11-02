"""Rendered one-QB evidence at the required sizes, with disposable accounts."""
import json
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tests import test_multileague_projection_compatibility as projection_fixtures
from tests import test_roster_diagnostic_http as http_fixtures
from src.core.intelligence.roster_diagnostics import diagnose_league
from src.core.intelligence.team_strength import prepare_for_data
from tools.validation.browser_runtime import launch_chromium


class MultiLeagueProjectionBrowserTests(unittest.TestCase):
    def test_supported_and_missing_required_slots_at_all_sizes(self):
        http = http_fixtures.DiagnosticHTTPTests()
        http.setUp()
        self.addCleanup(http.doCleanups)
        fixture = projection_fixtures.MultiLeagueProjectionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.data['league'].update(league_id='league-1', name='Disposable one-QB league')
        for team in fixture.data['teams']:
            team.update(owner='Disposable manager', team_name='Example franchise ' + str(team['roster_id']))
        http.f.f.data.clear()
        http.f.f.data.update(fixture.data)
        measurements = []
        with patch('src.core.projection_intelligence.projection_service', fixture.service), sync_playwright() as playwright:
            browser = launch_chromium(playwright, headless=True)
            try:
                for state, missing in [('complete', None), ('missing-k', '1-8'), ('missing-def', '1-9')]:
                    feed = [row for row in fixture.feed if row['player_id'] != missing]
                    snapshot = fixture.service.publish_horizon({8: feed}, data=fixture.data,
                        league_id='league-1', season=2026, current_week=8)
                    with patch('services.global_evidence.retained_global_evidence', return_value=None):
                        prepare_for_data(fixture.service, fixture.data)
                    row = diagnose_league(fixture.data, snapshot, projection_reader=fixture.service)['teams']['1']
                    self.assertEqual(row['optimal_points'], 115 if state == 'complete' else None)
                    for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                        context = browser.new_context(viewport={'width': width, 'height': height},
                                                      has_touch=True, is_mobile=width < 1000)
                        try:
                            context.add_cookies([{'name': 'dtos_strategy', 'value': http.f.cookie, 'url': 'https://dtos.test/'}])
                            page = context.new_page()
                            page.route('**/*', http.f.transport)
                            response = page.goto('https://dtos.test/teams/1')
                            self.assertEqual(response.status, 200)
                            detail = page.locator('#positional-depth')
                            detail.wait_for()
                            summary = detail.locator('summary').first
                            summary.focus()
                            page.keyboard.press('Enter')
                            self.assertTrue(summary.evaluate('(node) => node.parentElement.open'))
                            text = detail.inner_text()
                            message = 'Required starting positions lack compatible eligible projections:'
                            if state == 'complete':
                                self.assertNotIn(message, text)
                                self.assertNotIn('Compatible league/week/scoring projection publication unavailable', text)
                            else:
                                self.assertIn(message + (' K' if state == 'missing-k' else ' DEF'), text)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            summary.tap()
                            self.assertFalse(summary.evaluate('(node) => node.parentElement.open'))
                            summary.tap()
                            self.assertTrue(summary.evaluate('(node) => node.parentElement.open'))
                            measurements.append(dict(state=state, width=width, height=height,
                                document_width=page.evaluate('document.documentElement.scrollWidth'),
                                keyboard=True, touch=True, status=response.status))
                        finally:
                            context.close()
            finally:
                browser.close()
        print('DTOS_MULTILEAGUE_BROWSER ' + json.dumps(measurements))
