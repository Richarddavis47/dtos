"""Actual Home/League/My Team/history routers consume the same canonical result."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from routes.home import create_home_router
from routes.teams import create_teams_router
from tests import test_championship_evidence_consistency as fixtures
from tests.test_historical_tracker_phase2 import DAY, ARK, prepared
from tests.test_trade_intelligence import fixture_data
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_runtime import launch_chromium


class ChampionshipEvidenceBrowserTests(unittest.TestCase):
    def setUp(self):
        import dtos_app
        self.application = dtos_app
        self.released_client = TestClient(dtos_app.app)
        self.base = fixtures.ChampionshipEvidenceConsistencyTests()
        self.base.setUp()
        self.fixture = self.base.fixture
        self.fixture.page_renderer = dtos_app.page
        rich = fixture_data()
        self.fixture.data.update({k: v for k, v in rich.items() if k != 'league'})
        self.fixture.data['week'] = 1
        self.fixture.data['league']['roster_positions'] = rich['league']['roster_positions']
        self.fixture.fixture.store.update_current(DAY, self.fixture.data)
        stack = self.fixture.stack
        stack.enter_context(patch('routes.teams.canonical_history_store', self.fixture.fixture.store))
        stack.enter_context(patch('routes.home.current_league_context', return_value=None))
        stack.enter_context(patch('routes.teams.current_league_context', return_value=None))
        stack.enter_context(patch.object(dtos_app, 'current_league_context', return_value=None))
        stack.enter_context(patch('routes.home.build_team_directory', return_value={}))
        stack.enter_context(patch('routes.home.pick_changes', return_value=([], {})))
        stack.enter_context(patch('routes.home.attention_state', return_value={'items': [], 'coverage': {}}))
        stack.enter_context(patch('services.global_evidence.retained_global_evidence', return_value=None))
        stack.enter_context(patch('services.sleeper.sleeper_get', side_effect=AssertionError('Reads cannot fetch providers')))
        common = dict(ensure_fresh=prepared, require_data=lambda: self.fixture.data, page=dtos_app.page)
        self.fixture.app.include_router(create_home_router(**common))
        self.fixture.app.include_router(create_teams_router(**common, state={}))
        self.fixture.client._transport.raise_server_exceptions = True
        self.measurements = []

    def tearDown(self):
        self.base.tearDown()

    def transport(self, route):
        url = urlsplit(route.request.url)
        if url.hostname == 'sleepercdn.com':
            return route.fulfill(status=200, content_type='image/png', body=image_bytes('championship'))
        if url.hostname != 'fixture':
            return route.fulfill(status=404)
        client = self.released_client if url.path.startswith("/static/") else self.fixture.client
        result = client.get(url.path + ('?' + url.query if url.query else ''))
        route.fulfill(status=result.status_code, content_type=result.headers.get('content-type', 'text/html'), body=result.content)

    def test_http_all_consumers_agree_and_warm_home_loses_conflicted_trophy(self):
        for opponent, supported in [(2, True), (999, False), (2, True)]:
            self.base.publish([{'m': 1, 'p': 1, 't1': 1, 't2': opponent, 'w': 1, 'l': opponent}])
            for path in ('/', '/league', '/teams/1', '/history/2026'):
                response = self.fixture.client.get(path)
                self.assertEqual(response.status_code, 200, (path, response.text[:200]))
                if path == '/history/2026':
                    self.assertEqual("Pending / unavailable</h3>" not in response.text, supported)
                else:
                    self.assertEqual('data-badge="champion"' in response.text, supported, path)
            self.assertEqual(self.base.result()['champion_roster_id'], 1 if supported else None)

    def test_responsive_keyboard_disclosure_valid_conflicting_and_league_switch(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.route('**/*', self.transport)
            for opponent, supported in [(2, True), (999, False)]:
                self.base.publish([{'m': 1, 'p': 1, 't1': 1, 't2': opponent, 'w': 1, 'l': opponent}])
                for width, height in [(320, 432), (375, 667), (390, 844), (390, 432), (1165, 800)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for path in ('/', '/league', '/teams/1', '/history/2026'):
                        response = page.goto('http://fixture' + path)
                        self.assertEqual(response.status, 200, path)
                        trophies = page.locator('[data-badge="champion"]')
                        if path != '/history/2026':
                            self.assertEqual(trophies.count() > 0, supported, path)
                            if supported:
                                summary = trophies.first.locator(':scope > summary')
                                summary.focus()
                                self.assertNotEqual(summary.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                                summary.press('Enter')
                                self.assertIn('2026 defending champion', trophies.first.inner_text())
                                self.assertIn('completed season', trophies.first.inner_text())
                        else:
                            self.assertEqual(page.locator('.season-champion h3').inner_text() != 'Pending / unavailable', supported)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width, (path, page.evaluate("[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth).slice(0,10).map(e=>[e.tagName,e.className,e.textContent.slice(0,90),e.getBoundingClientRect().right])")))
                        self.measurements.append({'path': path, 'width': width, 'height': height, 'supported': supported})
            original = self.fixture.data['league']
            self.base.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}])
            for league, supported in [(original, True), ({**original, 'league_id': ARK, 'previous_league_id': None}, False), (original, True)]:
                self.fixture.data['league'] = league
                for path in ('/', '/league', '/teams/1'):
                    self.assertEqual(page.goto('http://fixture' + path).status, 200)
                    self.assertEqual(page.locator('[data-badge="champion"]').count() > 0, supported)
            self.fixture.data['league'] = original
            browser.close()
        target = Path('.validation/championship-consistency')
        target.mkdir(parents=True, exist_ok=True)
        (target / 'browser-geometry.json').write_text(json.dumps(self.measurements, indent=2))
