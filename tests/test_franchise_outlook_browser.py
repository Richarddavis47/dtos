"""Actual rendered prepared fixtures, not owner-live or physical Safari."""
from datetime import datetime, timezone
import os
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright
from tests import test_roster_diagnostic_http as fixtures
from tools.validation.browser_runtime import launch_chromium


class FranchiseOutlookBrowserTests(unittest.TestCase):
    def test_shared_summary_and_navigation_without_search(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        root = Path(os.environ['DTOS_FRANCHISE_OUTLOOK_EVIDENCE']) if os.environ.get('DTOS_FRANCHISE_OUTLOOK_EVIDENCE') else None
        if root:
            root.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320,432),(375,667),(390,844),(1280,900)):
                    page = f.f.browser_page(browser, width, height)
                    requests = []
                    page.on('request', lambda req: requests.append((req.method, req.url)))
                    try:
                        page.goto('https://dtos.test/teams/1')
                        page.wait_for_load_state('networkidle')
                        card = page.locator('#my-team-outlook')
                        self.assertIn('Main strength:', card.inner_text())
                        self.assertIn('Future flexibility:', card.inner_text())
                        self.assertNotIn('championship probability', card.inner_text())
                        self.assertFalse(page.locator('#my-team-outlook-evidence').evaluate('e=>e.open'))
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                        if root:
                            page.screenshot(path=str(root/f'my-team-{width}.png'),full_page=True)
                        summary=page.locator('#my-team-outlook-evidence>summary')
                        summary.focus()
                        summary.press('Enter')
                        self.assertTrue(page.locator('#my-team-outlook-evidence').evaluate('e=>e.open'))
                        self.assertIn('preference, not a proven competitive window',card.inner_text())
                        if root:
                            page.screenshot(path=str(root/f'my-team-expanded-{width}.png'),full_page=True)
                        page.goto('https://dtos.test/')
                        page.wait_for_load_state('networkidle')
                        shared=page.locator('[aria-label="Franchise outlook"]')
                        self.assertEqual(shared.count(),1)
                        shared.locator('summary').focus()
                        shared.locator('summary').press('Enter')
                        self.assertIn('Future flexibility:',shared.inner_text())
                        self.assertNotIn('1 owned future first-round pick',page.locator('#home-opportunity-cards').inner_text())
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                        if root:
                            page.screenshot(path=str(root/f'home-{width}.png'),full_page=True)
                        shared.get_by_role('link',name='Review My Team').click()
                        page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('#my-team-outlook').count(),1)
                        self.assertFalse(any(method=='POST' and any(p in url for p in ('generate','evaluate','sync','franchise-goal')) for method,url in requests))
                    finally:
                        page.close()
            finally:
                browser.close()
