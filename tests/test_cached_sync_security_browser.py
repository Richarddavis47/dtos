"""Actual authenticated fixture HTTP -> Chromium; not physical Safari acceptance."""
from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_cached_sync_security as fixtures


class CachedSyncBrowserTests(unittest.TestCase):
    def test_customer_warning_and_existing_keyboard_recovery_at_four_viewports(self):
        import dtos_app
        f = fixtures.CachedSyncHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.f.app.add_api_route('/market/sync-recovery',
                             lambda: dtos_app.page('Saved league data', '<h2>Previously loaded roster remains available</h2>'))
        before = json.dumps(f.f.states, sort_keys=True)
        root = os.getenv('DTOS_SYNC_SECURITY_EVIDENCE')
        evidence = Path(root) if root else None
        if evidence:
            evidence.mkdir(parents=True, exist_ok=True)
        rows = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    context = browser.new_context(viewport={'width': width, 'height': height})
                    try:
                        page = context.new_page()
                        def route(request):
                            response = f.f.client.get(request.request.url.replace('https://dtos.test', ''),
                                                      follow_redirects=False)
                            request.fulfill(status=response.status_code, body=response.content,
                                            headers={key: value for key, value in response.headers.items()
                                                     if key.lower() not in ('content-length', 'content-encoding')})
                        page.route('https://dtos.test/**', route)
                        response = page.goto('https://dtos.test/market/sync-recovery')
                        self.assertEqual(response.status, 200)
                        text = page.locator('body').inner_text()
                        for marker in fixtures.FORBIDDEN:
                            self.assertNotIn(marker, text)
                        warning = page.locator('.error')
                        self.assertTrue(warning.is_visible())
                        self.assertIn('last successfully loaded', warning.inner_text())
                        self.assertIn('may be out of date', warning.inner_text())
                        self.assertTrue(page.locator('h2').is_visible())
                        self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                        summary = page.locator('.account-context > summary')
                        for _ in range(12):
                            page.keyboard.press('Tab')
                            if summary.evaluate('(el) => el === document.activeElement'):
                                break
                        self.assertTrue(summary.evaluate('(el) => el === document.activeElement'))
                        self.assertNotEqual(summary.evaluate('(el) => getComputedStyle(el).outlineStyle'), 'none')
                        page.keyboard.press('Enter')
                        self.assertTrue(page.locator('.account-context').evaluate('(el) => el.open'))
                        page.keyboard.press('Enter')
                        self.assertFalse(page.locator('.account-context').evaluate('(el) => el.open'))
                        summary.click()
                        self.assertTrue(page.locator('.account-context').evaluate('(el) => el.open'))
                        summary.click()
                        self.assertFalse(page.locator('.account-context').evaluate('(el) => el.open'))
                        self.assertEqual(page.locator('form[action="/sync"]').count(), 1)
                        if evidence:
                            page.screenshot(path=str(evidence / f'safe-sync-{width}x{height}.png'), full_page=True)
                        rows.append({'width': width, 'height': height, 'status': response.status,
                                     'warning': warning.inner_text(), 'warning_box': warning.bounding_box(),
                                     'overflow': False, 'keyboard_pointer_disclosure': 'passed'})
                    finally:
                        context.close()
            finally:
                browser.close()
        self.assertEqual(before, json.dumps(f.f.states, sort_keys=True))
        f.f.no_work.assert_not_called()
        if evidence:
            (evidence / 'results.json').write_text(json.dumps(rows, indent=2))


if __name__ == '__main__':
    unittest.main()
