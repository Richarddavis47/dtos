"""Isolated actual Market routes + released theme in responsive Chromium, not Safari."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tests.test_market_trend_current_integration import CurrentMarketHTTPTests
from tools.validation.browser_runtime import launch_chromium


class MarketTrendCurrentBrowserTests(unittest.TestCase):
    def test_dated_current_comparison_disclosure_and_phone_geometry(self):
        import dtos_app
        fixture = CurrentMarketHTTPTests()
        fixture.page_renderer = dtos_app.page
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        measurements = []
        with patch.dict(dtos_app.STATE, {'data': fixture.data}), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True, args=['--no-sandbox'])
            try:
                for league in ('1313066632158924800', '1319750579458686976'):
                    fixture.data['league']['league_id'] = league
                    # Settle the existing bounded publication before measuring
                    # the page, rather than treating honest warming as failure.
                    fixture.cache.get(fixture.data, fixture.state, fixture.history, league)
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
                            response = fixture.client.get(url.path + ('?' + url.query if url.query else ''))
                            route.fulfill(status=response.status_code, body=response.content,
                                          content_type=response.headers.get('content-type', 'text/html'))
                        page.route('**/*', transport)
                        self.assertEqual(page.goto('http://fixture/market?selected=player%3A1').status, 200)
                        summary = page.get_by_text('Observed trends and comparison details', exact=True)
                        self.assertFalse(summary.evaluate('(e)=>e.parentElement.open'))
                        summary.focus()
                        self.assertNotEqual(summary.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                        summary.press('Enter')
                        self.assertTrue(summary.evaluate('(e)=>e.parentElement.open'))
                        trend = page.locator('section.card').filter(has=page.locator('p.eyebrow', has_text='Observed Market Trend'))
                        text = trend.inner_text()
                        self.assertIn('+100.00 Market points', text)
                        self.assertIn('Historical to current publication', text)
                        self.assertIn('2026-07-01', text)
                        self.assertIn('2026-08-31', text)
                        self.assertIn('freshness is not established', text)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        box = trend.bounding_box()
                        measurements.append({'league': league, 'viewport': [width, height],
                            'document_width': page.evaluate('document.documentElement.scrollWidth'),
                            'trend_height': round(box['height'], 2),
                            'summary_height': round(summary.bounding_box()['height'], 2),
                            'keyboard_focus': True, 'disclosure_initially_closed': True,
                            'comparison': '+100.00', 'source_state': 'unknown source clock explicitly qualified'})
                        summary.click()
                        self.assertFalse(summary.evaluate('(e)=>e.parentElement.open'))
                        page.close()
            finally:
                browser.close()
        target = os.environ.get('DTOS_TREND_BROWSER_EVIDENCE')
        if target:
            Path(target).write_text(json.dumps(measurements, indent=2))
