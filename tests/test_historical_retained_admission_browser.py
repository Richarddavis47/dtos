"""Actual isolated history routes; author-run Chromium, not physical Safari."""
from copy import deepcopy
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.history import create_history_router
from tests import test_historical_retained_admission as controls
from tools.validation.browser_runtime import launch_chromium


class HistoricalRetainedAdmissionBrowserTests(unittest.TestCase):
    def test_retained_recovery_and_qualified_history_at_phone_widths(self):
        import dtos_app
        fixture = controls.HistoricalRetainedAdmissionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        prepared = [controls.evidence.active_source(index) for index in (0, 1)]
        data = prepared[0][0]
        app = FastAPI()
        app.include_router(create_history_router(league_id=controls.evidence.DAY,
            require_data=lambda: data, league_resolver=lambda: data['league']['league_id'], page=dtos_app.page))
        measurements = []
        with TestClient(app) as client, patch.dict(dtos_app.STATE, {'data': data}), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True, args=['--no-sandbox'])
            try:
                for original, source in prepared:
                    for case in ('supported', 'unverified_completion', 'missing_scoring'):
                        data = deepcopy(original)
                        league = data['league']['league_id']
                        if case == 'unverified_completion':
                            data['league']['settings']['last_scored_leg'] = '5'
                        fixture.retained(data, source, future=True)
                        if case == 'missing_scoring':
                            data['league']['scoring_settings'] = data['scoring_settings'] = {}
                        fixture.store.update_current(league, data)
                        dtos_app.STATE['data'] = data
                        expected = next(r['players_points']['11563'] for r in source['week5'] if '11563' in r['players_points'])
                        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                            page = browser.new_page(viewport={'width': width, 'height': height})
                            def transport(route):
                                url = urlsplit(route.request.url)
                                if url.netloc != 'fixture':
                                    route.fulfill(status=404)
                                    return
                                if url.path.startswith('/static/') and Path(url.path.lstrip('/')).is_file():
                                    route.fulfill(path=str(Path(url.path.lstrip('/'))))
                                    return
                                response = client.get(url.path)
                                route.fulfill(status=response.status_code, body=response.content,
                                              content_type=response.headers.get('content-type', 'text/html'))
                            page.route('**/*', transport)
                            response = page.goto('http://fixture/history/player/11563')
                            self.assertEqual(response.status, 200)
                            main = page.locator('main')
                            text = main.inner_text()
                            self.assertIn('Bo Nix', text)
                            self.assertNotIn('999', text)
                            if case == 'supported':
                                self.assertIn(f'{expected} points', text)
                            else:
                                self.assertNotIn(f'{expected} points', text)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            action = main.get_by_role('link', name='Back to connected Player Dossier')
                            action.focus()
                            self.assertNotEqual(action.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                            measurements.append({'league': league, 'case': case, 'viewport': [width, height],
                                'document_width': page.evaluate('document.documentElement.scrollWidth'),
                                'main_height': main.bounding_box()['height'], 'focus_visible': True,
                                'synthetic_future_score_visible': False})
                            page.close()
            finally:
                browser.close()
        target = os.environ.get('DTOS_RETAINED_ADMISSION_BROWSER_EVIDENCE')
        if target:
            Path(target).write_text(json.dumps(measurements, indent=2))
