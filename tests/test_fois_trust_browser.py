"""Actual FOIS route rendering with controlled evidence, responsive Chromium."""
from dataclasses import replace
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.front_offices import create_front_offices_router
from tests import test_fois_presentation as fois
from tests.test_gm_behavioral_intelligence_v1126 import trade, profile
from tests.test_trade_intelligence import fixture_data
from tools.validation.browser_runtime import launch_chromium


class FOISTrustBrowserTests(unittest.TestCase):
    def inspect(self, pages, callback):
        styles = {p.name: p.read_text() for p in Path('static/css').glob('*.css')}
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 480), (320, 568), (375, 480), (375, 667),
                                      (390, 480), (390, 844), (1280, 900)):
                    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=width < 600) as context:
                        def transport(route):
                            from urllib.parse import urlsplit
                            url = urlsplit(route.request.url)
                            if url.path in pages:
                                route.fulfill(content_type='text/html', body=pages[url.path])
                            elif url.path.endswith('.css'):
                                route.fulfill(content_type='text/css', body=styles.get(Path(url.path).name, ''))
                            else:
                                route.fulfill(status=404, body='')
                        context.route('**/*', transport)
                        page = context.new_page()
                        for path in pages:
                            page.goto('http://fixture' + path)
                            callback(page, path, width)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1, (path, width))
                            output = os.environ.get('DTOS_FOIS_TRUST_CAPTURE')
                            if output:
                                Path(output).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(output) / f'{path.replace("/", "-")}-{width}-{height}.png'), full_page=True)
            finally:
                browser.close()

    def test_actual_own_and_opponent_profiles_evidence_and_keyboard(self):
        import dtos_app
        fixture = fois.FOISPresentationTests()
        fixture.setUp()
        try:
            code = 'MARKET_LOOKUP_UNAVAILABLE_TIME_BOUNDARY'
            rows = fixture._persist_profiles('active-league', 2)
            for index, row in enumerate(rows):
                behavioral = profile(tuple(trade(f'd{n}') for n in range(6)), league='active-league', gm=row.gm_id).contract()
                category = replace(row.category_scores[0], details={'process': {'limitations': {code: 3}}})
                fixture.repository.save(replace(row, category_scores=(category, *row.category_scores[1:]),
                    gm_behavioral_profile=behavioral), f'behavior-{index}')
            pages = {}
            with patch.object(fois, '_page', side_effect=dtos_app.page), fixture._client() as client:
                pages['/fois'] = client.get('/fois').text
                for row in rows:
                    path = '/fois/gms/' + row.gm_id
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    pages[path] = response.text
            def check(page, path, width):
                if path == '/fois':
                    for card in page.locator('.fois-leader').all():
                        self.assertLessEqual(card.locator('h3').bounding_box()['y'] + card.locator('h3').bounding_box()['height'],
                            card.locator('.fois-score').bounding_box()['y'] + 1) if width < 600 else None
                    return
                self.assertIn('Management behavior and evidence', page.inner_text('body'))
                summary = page.get_by_text('Supporting evidence and limitations', exact=True)
                summary.click()
                self.assertTrue(summary.evaluate('e=>e.parentElement.open'))
                summary.click()
                summary.focus()
                page.keyboard.press('Enter')
                self.assertTrue(summary.evaluate('e=>e.parentElement.open'))
                self.assertIn(code, page.inner_text('.dtos-explanation'))
                evidence = page.locator('.fois-behavior').first
                control = evidence.locator('summary')
                control.click()
                self.assertTrue(evidence.evaluate('e=>e.open'))
                control.click()
                control.focus()
                page.keyboard.press('Enter')
                self.assertTrue(evidence.evaluate('e=>e.open'))
                self.assertNotEqual(control.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                self.assertIn('independent supported transactions', evidence.inner_text())
                page.keyboard.press('Enter')
                self.assertFalse(evidence.evaluate('e=>e.open'))
                self.assertNotIn('Acceptance: 65', page.inner_text('body'))
            self.inspect(pages, check)
        finally:
            fixture.tearDown()

    def test_actual_front_offices_no_fake_switch_or_probability(self):
        import dtos_app
        data = fixture_data()
        data['transactions'] = [{'type': 'trade', 'roster_ids': [1, 2]} for _ in range(6)]
        async def noop():
            return None
        app = FastAPI()
        app.include_router(create_front_offices_router(ensure_fresh=noop, require_data=lambda: data, page=dtos_app.page))
        with TestClient(app) as client:
            response = client.get('/front-offices?front_office=1')
        self.assertEqual(response.status_code, 200)
        def check(page, path, width):
            self.assertEqual(page.locator('select#front_office').count(), 0)
            self.assertIn('Your controlled franchise', page.inner_text('body'))
            self.assertNotIn('Values youth', page.inner_text('body'))
            self.assertNotIn('Acceptance: ', page.inner_text('body'))
            self.assertIn('uncalibrated', page.inner_text('body').casefold())
            summary = page.get_by_text('Show Full Dossier Evidence', exact=True)
            summary.focus()
            page.keyboard.press('Enter')
            self.assertTrue(summary.evaluate('e=>e.parentElement.open'))
            page.keyboard.press('Enter')
            self.assertFalse(summary.evaluate('e=>e.parentElement.open'))
            link = page.get_by_role('link', name='View league Executive Profiles')
            link.click(trial=True)
        self.inspect({'/front-offices': response.text}, check)
