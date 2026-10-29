"""Released application script with rendered routers and real browser requests."""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from tools.validation.browser_runtime import launch_chromium
from tests import test_historical_tracker_phase2 as fixtures


class HistoryFinalSourceBrowserTests(unittest.TestCase):
    def setUp(self):
        import dtos_app
        self.application = dtos_app
        self.fixture = fixtures.TrackerPhase2Tests()
        self.fixture.page_renderer = dtos_app.page
        self.fixture.setUp()
        self.released_client = TestClient(dtos_app.app)
        self.measurements = []
        self.pending = []
        self.behavior = None

    def tearDown(self):
        self.fixture.tearDown()

    def transport(self, route):
        url = urlsplit(route.request.url)
        if url.netloc != 'fixture':
            return route.fulfill(status=404)
        if url.path == '/static/js/history-production.js':
            result = self.released_client.get(url.path)
        elif '/production' in url.path and self.behavior:
            if self.behavior == 'pending':
                self.pending.append(route)
                return
            if self.behavior == 'interrupted':
                return route.abort('aborted')
            return route.fulfill(status=503, content_type='text/html', body='Provider temporarily unavailable')
        else:
            result = self.fixture.client.get(url.path + ('?' + url.query if url.query else ''))
        route.fulfill(status=result.status_code, content_type=result.headers.get('content-type', 'text/html'), body=result.content)

    def browser(self, pw):
        browser = launch_chromium(pw, headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 320, 'height': 568})
        page.route('**/*', self.transport)
        return browser, page

    def open(self, page, trade=fixtures.ROOT):
        page.goto('http://fixture/trades/history/' + trade)
        disclosure = page.locator('details[data-production-endpoint]')
        summary = disclosure.locator(':scope > summary')
        summary.focus()
        self.assertNotEqual(summary.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
        summary.press('Enter')
        return disclosure

    def pending_route(self, page, previous_count):
        # aria-busy is set before fetch reaches the interception callback.
        # Wait for that actual request, including when testing a second fetch.
        deadline = time.monotonic() + 5
        while len(self.pending) == previous_count and time.monotonic() < deadline:
            page.wait_for_timeout(10)
        self.assertEqual(len(self.pending), previous_count + 1)
        return self.pending[-1]

    def test_released_asset_loaded_and_production_terminal_at_phone_and_desktop_widths(self):
        data = self.fixture.data
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), patch.dict(self.application.STATE, {'data': data, 'last_sync': '2026-10-13T02:00:00Z'}), sync_playwright() as pw:
            browser, page = self.browser(pw)
            for width, height in [(320, 568), (375, 667), (390, 844), (390, 432), (1165, 800)]:
                page.set_viewport_size({'width': width, 'height': height})
                for trade in (fixtures.ROOT, fixtures.FAAB, '1414718106177122304'):
                    response = []
                    page.on('response', lambda r: response.append(r.status) if r.url.endswith('/history-production.js') else None)
                    disclosure = self.open(page, trade)
                    disclosure.get_by_text('Complete holding-period benefit: Unavailable.', exact=False).first.wait_for()
                    self.assertIn(200, response)
                    self.assertEqual(disclosure.get_attribute('data-loaded'), 'true')
                    self.assertNotIn('Open to retrieve', disclosure.inner_text())
                    self.assertIn('DTOS Sleeper retrieval/sync observations', page.locator('main').inner_text())
                    self.assertIn('2026-10-13T02:00:00Z', page.locator('main').inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    self.measurements.append({'trade': trade, 'width': width, 'height': height,
                                              'documentWidth': page.evaluate('document.documentElement.scrollWidth')})
                    disclosure.locator(':scope > summary').click()
                    disclosure.locator(':scope > summary').click()
                    self.assertEqual(disclosure.get_attribute('data-loaded'), 'true')
                    if trade == fixtures.FAAB:
                        self.assertEqual(page.locator('.timeline-faab').count(), 1)
                        self.assertIn('100 FAAB', page.locator('.timeline-faab').inner_text())
            page.reload()
            self.open(page)
            page.goto('http://fixture/trades/history/' + fixtures.FAAB)
            page.go_back()
            page.locator('details[data-production-endpoint] summary').click()
            page.get_by_text('Complete holding-period benefit: Unavailable.', exact=False).first.wait_for()
            browser.close()
        target = Path('.validation/history-final-source')
        target.mkdir(parents=True, exist_ok=True)
        (target / 'browser-geometry.json').write_text(json.dumps(self.measurements, indent=2))

    def test_http_error_interrupted_request_timeout_and_retry(self):
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), sync_playwright() as pw:
            browser, page = self.browser(pw)
            for behavior in ('error', 'interrupted', 'pending'):
                self.behavior = behavior
                page.clock.install()
                disclosure = self.open(page)
                if behavior == 'pending':
                    page.wait_for_function("document.querySelector('[data-production-content]').getAttribute('aria-busy') === 'true'")
                    page.clock.fast_forward(15001)
                retry = disclosure.get_by_role('button', name='Retry supported production')
                retry.wait_for()
                if behavior == 'pending':
                    self.assertIn('timed out', disclosure.inner_text())
                self.assertIsNone(disclosure.locator('[data-production-content]').get_attribute('aria-busy'))
                self.behavior = None
                retry.focus()
                self.assertNotEqual(retry.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                retry.press('Enter')
                disclosure.get_by_text('Complete holding-period benefit: Unavailable.', exact=False).first.wait_for()
            browser.close()

    def test_no_scores_zero_unknown_role_missing_and_conflicting_scores(self):
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), sync_playwright() as pw:
            browser, page = self.browser(pw)
            for starters, points, expected in [('absent', 0, 'Unknown role: 0.00'), ([], 0, 'Explicit bench: 0.00'),
                                               (['13346'], None, 'Started: Unavailable'), (['13346'], 10, 'Started: 10.00')]:
                self.fixture.scores(starters, points)
                disclosure = self.open(page, '1414718106177122304')
                disclosure.get_by_text(expected, exact=False).first.wait_for()
                self.assertNotIn('170.00', disclosure.inner_text())
            facts = self.fixture.fixture.cache.read(fixtures.DAY, 2026).facts.copy()
            facts['matchups']['1'].append({**facts['matchups']['1'][0], 'players_points': {'13346': 20}})
            self.fixture.publish(facts)
            disclosure = self.open(page, '1414718106177122304')
            disclosure.get_by_text('Observed weeks and independent ownership intervals', exact=True).first.click()
            disclosure.get_by_text('score conflict', exact=False).first.wait_for()
            self.assertIn('Known observed roster subtotal: Unavailable', disclosure.inner_text())
            facts['matchups'] = {}
            self.fixture.publish(facts)
            disclosure = self.open(page, '1414718106177122304')
            disclosure.get_by_text('0 scored / 0 observed', exact=False).first.wait_for()
            browser.close()

    def test_pending_old_trade_response_cannot_replace_new_context(self):
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), sync_playwright() as pw:
            browser, page = self.browser(pw)
            self.behavior = 'pending'
            previous_count = len(self.pending)
            disclosure = self.open(page)
            page.wait_for_function("document.querySelector('[data-production-content]').getAttribute('aria-busy') === 'true'")
            route = self.pending_route(page, previous_count)
            old = self.fixture.client.get(urlsplit(route.request.url).path).text
            page.evaluate("history.pushState({}, '', '/trades/history/965057520920260608')")
            route.fulfill(status=200, content_type='text/html', body=old)
            page.wait_for_function("!document.querySelector('[data-production-content]').hasAttribute('aria-busy')")
            self.assertIsNone(disclosure.get_attribute('data-loaded'))
            self.assertIn('Trade context changed', disclosure.inner_text())
            self.behavior = None
            disclosure = self.open(page, fixtures.FAAB)
            disclosure.get_by_text('Complete holding-period benefit: Unavailable.', exact=False).first.wait_for()
            self.assertEqual(disclosure.get_attribute('data-trade'), fixtures.FAAB)
            self.assertEqual(page.locator('.timeline-faab').count(), 1)
            self.behavior = 'pending'
            previous_count = len(self.pending)
            disclosure = self.open(page)
            page.wait_for_function("document.querySelector('[data-production-content]').getAttribute('aria-busy') === 'true'")
            route = self.pending_route(page, previous_count)
            body = self.fixture.client.get(urlsplit(route.request.url).path).text
            page.evaluate("history.replaceState({}, '', location.pathname + '#production')")
            route.fulfill(status=200, content_type='text/html', body=body)
            page.wait_for_function("document.querySelector('[data-production-endpoint]').dataset.loaded === 'true'")
            browser.close()


if __name__ == '__main__':
    unittest.main()
