"""Isolated rendered historical production; not live or physical-device proof."""
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
from tests import test_historical_player_evidence as evidence
from tools.validation.browser_runtime import launch_chromium


class HistoricalPlayerEvidenceBrowserTests(unittest.TestCase):
    def test_actual_history_route_scoring_at_phone_and_desktop_widths(self):
        import dtos_app
        fixture = evidence.HistoricalPlayerEvidenceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        sources = [fixture.publish(index) for index in (0, 1)]
        data, _ = sources[0]
        app = FastAPI()
        app.include_router(create_history_router(league_id=evidence.DAY, require_data=lambda: data,
                           league_resolver=lambda: data['league']['league_id'], page=dtos_app.page))
        measurements = []
        with TestClient(app) as client, patch.dict(dtos_app.STATE, {'data': data}), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True, args=['--no-sandbox'])
            try:
                for index, league in ((0, evidence.DAY), (1, evidence.ARK)):
                    data, source = sources[index]
                    dtos_app.STATE['data'] = data
                    expected = next(row['players_points']['11563'] for row in source['week5'] if '11563' in row['players_points'])
                    for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                        page = browser.new_page(viewport={'width': width, 'height': height})
                        def transport(route):
                            url = urlsplit(route.request.url)
                            if url.netloc != 'fixture':
                                route.fulfill(status=404)
                                return
                            if url.path.startswith('/static/'):
                                path = Path(url.path.lstrip('/'))
                                if path.is_file():
                                    route.fulfill(path=str(path))
                                    return
                            response = client.get(url.path)
                            route.fulfill(status=response.status_code, body=response.content,
                                          content_type=response.headers.get('content-type', 'text/html'))
                        page.route('**/*', transport)
                        response = page.goto('http://fixture/history/player/11563')
                        self.assertEqual(response.status, 200)
                        main = page.locator('main')
                        self.assertIn('Bo Nix', main.inner_text())
                        self.assertIn(f'{expected} points', main.inner_text())
                        self.assertIn('Weekly gaps are not connected or converted to zero', main.inner_text())
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        action = main.get_by_role('link', name='Back to connected Player Dossier')
                        action.focus()
                        self.assertNotEqual(action.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                        measurements.append({'league': league, 'viewport': [width, height],
                                             'document_width': page.evaluate('document.documentElement.scrollWidth'),
                                             'points': expected, 'main_height': main.bounding_box()['height'],
                                             'focus_visible': True})
                        page.close()
            finally:
                browser.close()
        target = os.environ.get('DTOS_PLAYER_WEEK_BROWSER_EVIDENCE')
        if target:
            Path(target).write_text(json.dumps(measurements, indent=2))
