"""Actual matchup HTTP on narrow phones: readable identities and unchanged facts."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright

from routes.matchups import create_matchups_router
from tests.test_matchups_phone import phone_fixture
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_runtime import launch_chromium


class SourceContinuityPhoneTests(TestCase):
    def test_matchup_identity_scores_and_keyboard_at_required_widths(self):
        import dtos_app
        f = phone_fixture(self)
        data = f.data
        data['players']['a']['full_name'] = 'A long supported quarterback name'
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda: data, page=dtos_app.page))
        app.mount('/static', StaticFiles(directory='static'), name='static')
        context = SimpleNamespace(projection=f.reader, data=data, state={'data': data})
        account = SimpleNamespace(membership=SimpleNamespace(league_id='league-1', roster_id=1))
        evidence = Path(os.environ['DTOS_PHASE2_EVIDENCE']) if os.getenv('DTOS_PHASE2_EVIDENCE') else None
        if evidence:
            evidence.mkdir(parents=True, exist_ok=True)
        metrics = []
        with patch('routes.matchups.current_league_context', return_value=context), patch('routes.matchups.current_account', return_value=account), patch.object(dtos_app, 'current_league_context', return_value=context), patch('src.ui.badges.current_account', return_value=account), patch('services.sleeper.sleeper_get', side_effect=AssertionError('No request-time provider calls')), sync_playwright() as p:
            browser = launch_chromium(p, headless=True)
            try:
                with TestClient(app) as client:
                    for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                        with browser.new_context(viewport={'width': width, 'height': height}, has_touch=width < 500) as bc:
                            def transport(route):
                                url = urlsplit(route.request.url)
                                if url.hostname == 'sleepercdn.com':
                                    route.fulfill(status=200, content_type='image/png', body=image_bytes('matchups'))
                                elif url.hostname == 'dtos.test':
                                    response = client.get(url.path + ('?' + url.query if url.query else ''))
                                    route.fulfill(status=response.status_code, content_type=response.headers.get('content-type', 'text/html'), body=response.content)
                                else:
                                    route.abort()
                            bc.route('**/*', transport)
                            page = bc.new_page()
                            page.goto('https://dtos.test/matchups/2?week=2')
                            first = page.get_by_role('link', name='Open A long supported quarterback name player dossier', exact=True)
                            first.focus()
                            first.press('Tab')
                            page.keyboard.press('Shift+Tab')
                            self.assertTrue(first.evaluate('e=>e===document.activeElement'))
                            self.assertNotEqual(first.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            disclosure = page.get_by_text('Source and coverage', exact=True)
                            disclosure.focus()
                            disclosure.press('Enter')
                            self.assertTrue(disclosure.evaluate('e=>e.parentElement.open'))
                            if width < 500:
                                box = disclosure.bounding_box()
                                page.touchscreen.tap(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                self.assertFalse(disclosure.evaluate('e=>e.parentElement.open'))
                            first.scroll_into_view_if_needed()
                            row = page.evaluate('''() => ({viewport:[innerWidth,innerHeight], overflow:document.documentElement.scrollWidth-innerWidth, cells:[...document.querySelectorAll('.matchup-player:not(.empty)')].map(e=>({width:e.getBoundingClientRect().width,overflow:e.scrollWidth-e.clientWidth,text:e.innerText})), scores:[...document.querySelectorAll('[data-dtos-semantic-field="pregame_projection"]')].map(e=>({value:e.dataset.dtosValue,canonical:e.dataset.canonicalValue}))})''')
                            metrics.append(row)
                            self.assertLessEqual(row['overflow'], 0)
                            self.assertTrue(all(c['overflow'] <= 1 for c in row['cells']))
                            self.assertIn('10.00', page.locator('.matchup-player-points').first.inner_text())
                            if evidence:
                                page.screenshot(path=str(evidence / f'matchup-{width}.png'), full_page=True)
                                (evidence / f'matchup-{width}.json').write_text(json.dumps(row, indent=2))
                # This fails on build 2202 even though document overflow is zero.
                self.assertGreaterEqual(min(c['width'] for c in metrics[0]['cells']), 200, metrics[0])
            finally:
                browser.close()
