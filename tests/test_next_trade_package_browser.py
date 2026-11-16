"""Real authenticated fixture routes; retained replay, Chromium phone emulation."""
from copy import deepcopy
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests.test_history_followthrough import FollowThroughFixture, ROOT, LATER, source


class NextTradePackageBrowserTests(unittest.TestCase):
    def test_history_package_later_review_contextual_back_and_disclosure(self):
        f = FollowThroughFixture(self)
        folder = os.getenv('DTOS_NEXT_PACKAGE_EVIDENCE')
        destination = Path(folder) if folder else None
        if destination:
            destination.mkdir(parents=True, exist_ok=True)
        root, later = '/trades/history/' + ROOT, '/trades/history/' + LATER + '?from_trade=' + ROOT
        history = '/history/team/' + source.DAY + ':franchise:4?events_page=2'
        records, requests = [], []
        before = deepcopy(f.data)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=width < 500)
                    def transport(route):
                        parsed = urlsplit(route.request.url)
                        if parsed.netloc != 'fixture':
                            route.fulfill(status=404)
                            return
                        path = parsed.path + ('?' + parsed.query if parsed.query else '')
                        requests.append(path)
                        result = (f.static if path.startswith('/static/') else f.client).get(path)
                        route.fulfill(status=result.status_code, body=result.content,
                                      content_type=result.headers.get('content-type', 'text/html'))
                    page.route('**/*', transport)
                    response = page.goto('http://fixture' + history)
                    self.assertEqual(response.status, 200)
                    page.locator('.franchise-timeline a[href="' + root + '"]').click()
                    page.wait_for_url('**' + root)
                    package = page.locator('.next-exchange')
                    self.assertEqual(package.count(), 1)
                    self.assertIn('Denzel Boston', package.inner_text())
                    details = package.locator('details').first
                    summary = details.locator('summary').first
                    self.assertFalse(details.evaluate('e=>e.open'))
                    if destination:
                        page.screenshot(path=str(destination / f'package-collapsed-{width}.png'), full_page=True)
                    summary.focus()
                    self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                    count = len(requests)
                    summary.press('Enter')
                    self.assertTrue(details.evaluate('e=>e.open'))
                    self.assertEqual(len(requests), count)
                    self.assertIn('2029 Round 2', details.inner_text())
                    self.assertIn('originally', details.inner_text())
                    self.assertIn('Sent', details.inner_text())
                    self.assertIn('Received', details.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    if destination:
                        page.screenshot(path=str(destination / f'package-expanded-{width}.png'), full_page=True)
                    if width < 500:
                        summary.tap()
                        self.assertFalse(details.evaluate('e=>e.open'))
                        summary.tap()
                    package.get_by_role('link', name='Review the full later trade').click()
                    page.wait_for_url('**' + later)
                    page.locator('#dtos-back').click()
                    page.wait_for_url('**' + root)
                    page.locator('#dtos-back').click()
                    page.wait_for_url('**' + history)
                    self.assertIn('page 2 of', page.locator('.franchise-timeline').inner_text())
                    records.append({'width': width, 'height': height, 'extra_disclosure_requests': 0,
                                    'keyboard': True, 'touch_emulated': width < 500, 'pagination_retained': True})
                    page.close()
            finally:
                browser.close()
        self.assertEqual(f.data, before)
        if destination:
            (destination / 'browser.json').write_text(json.dumps({'evidence': 'retained partial replay plus disposable pagination, not live',
                'physical_device_tested': False, 'records': records, 'requests': requests}, indent=2))

    def test_partial_package_phone_preserves_supported_directions(self):
        f = FollowThroughFixture(self)
        facts = deepcopy(f.facts)
        later = next(row for bucket in facts['transactions'].values() for row in bucket
                     if row['transaction_id'] == LATER)
        later['adds']['unresolved-fixture-player'] = 4
        f.source.publish(facts)
        from src.ui.trade_timeline import render_timeline
        graph = f.graph()
        model = graph.trade_timeline(ROOT)
        page_html = render_timeline(model, graph.trade_dossier(ROOT))
        folder = os.getenv('DTOS_NEXT_PACKAGE_EVIDENCE')
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page = browser.new_page(viewport={'width': width, 'height': height})
                    page.set_content('<style>body{margin:12px;background:#071b12;color:white;font:16px sans-serif}a{color:#86efac}</style>' + page_html)
                    package = page.locator('.next-exchange')
                    self.assertIn('full package return is unknown', package.inner_text())
                    package.locator('details').first.locator('summary').first.click()
                    self.assertIn('2029 Round 2', package.inner_text())
                    self.assertIn('Denzel Boston', package.inner_text())
                    self.assertNotIn('The full return was for this package', package.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    if folder:
                        page.screenshot(path=str(Path(folder) / f'package-partial-expanded-{width}.png'), full_page=True)
                    page.close()
            finally:
                browser.close()
