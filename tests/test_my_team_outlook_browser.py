"""Authenticated rendered Chromium controls, not physical Safari or human testing."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests.test_roster_diagnostic_http import DiagnosticHTTPTests
from tools.validation.browser_runtime import launch_chromium


class MyTeamOutlookBrowserTests(unittest.TestCase):
    def test_primary_summary_disclosure_shortcuts_and_trade_return(self):
        f = DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        def explicit_save(page):
            values=page.locator('#my-team-goal-form').evaluate('e=>Object.fromEntries(new FormData(e))')
            response=f.f.f.client.post('/account/franchise-goal',data=values,follow_redirects=False)
            self.assertEqual(response.status_code,303,response.text)
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320,432), (375,667), (390,844), (1280,900)):
                    page = f.f.browser_page(browser, width, height)
                    try:
                        response = page.goto('https://dtos.test/teams/1')
                        self.assertEqual(response.status, 200)
                        page.wait_for_load_state('networkidle')
                        page.locator('#my-team-strategy').select_option('')
                        explicit_save(page)
                        page.reload(wait_until='networkidle')
                        root = page.locator('#my-team-outlook')
                        self.assertEqual(root.count(), 1)
                        self.assertLess(root.bounding_box()['y'], page.locator('#full-roster').bounding_box()['y'])
                        self.assertIn('lineup', root.inner_text())
                        self.assertIn('Choose your goal', root.inner_text())
                        self.assertNotIn('Unavailable · Fresh · Unavailable', root.inner_text())
                        detail = page.locator('#my-team-outlook-evidence')
                        self.assertFalse(detail.evaluate('e => e.open'))
                        summary = detail.locator('summary')
                        summary.focus()
                        self.assertNotEqual(summary.evaluate('e => getComputedStyle(e).outlineStyle'), 'none')
                        summary.press('Enter')
                        self.assertTrue(detail.evaluate('e => e.open'))
                        self.assertIn('Standing', detail.inner_text())
                        self.assertIn('Select a goal', detail.inner_text())
                        self.assertIn('not championship probability', detail.inner_text())
                        summary.press('Enter')
                        page.evaluate('scrollTo(0,0)')
                        row = page.evaluate('''() => {
                          const rect = s => { const r=document.querySelector(s).getBoundingClientRect();return {y:r.y,height:r.height,width:r.width};};
                          return {header:rect('.thq-header'),outlook:rect('#my-team-outlook'),
                            firstFinding:rect('#my-team-outlook p'),roster:rect('#full-roster'),
                            shortcuts:rect('[aria-label="Roster sections"]'),
                            overflow:document.documentElement.scrollWidth-innerWidth,
                            summaryText:document.querySelector('#my-team-outlook').innerText,
                            action:rect('#my-team-outlook-action'),font:getComputedStyle(document.querySelector('#my-team-outlook p')).fontSize};}''')
                        self.assertLessEqual(row['overflow'], 0)
                        self.assertGreaterEqual(row['action']['height'], 44)
                        row.update(width=width, height=height)
                        measurements.append(row)
                        out = os.environ.get('DTOS_OUTLOOK_EVIDENCE')
                        if out:
                            Path(out).mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(Path(out) / f'my-team-{width}.png'), full_page=True)
                            (Path(out) / 'phone-measurements.json').write_text(json.dumps(measurements, indent=2))
                        self.assertLess(row['outlook']['y'], height if height > 432 else 432)
                        for label, target in (('Depth','#positional-depth'), ('Draft capital','#draft-capital'), ('View full roster','#full-roster')):
                            link = page.get_by_role('navigation', name='Roster sections').get_by_role('link', name=label, exact=True)
                            self.assertEqual(link.get_attribute('href'), target)
                            link.click()
                            self.assertTrue(page.locator(target).is_visible())
                        page.locator('#my-team-strategy').select_option('WIN NOW')
                        explicit_save(page)
                        page.reload(wait_until='networkidle')
                        self.assertIn('WIN NOW:', page.locator('#my-team-outlook-goal').text_content())
                        self.assertEqual(page.locator('#my-team-outlook-action').get_attribute('href'), '/trades/trade-for?front_office=1')
                        page.locator('#my-team-outlook-action').click()
                        page.wait_for_function("document.querySelector('#trade-strategy')?.value === 'WIN NOW'")
                        self.assertEqual(page.locator('#trade-strategy').input_value(), 'WIN NOW')
                        page.go_back(wait_until='domcontentloaded')
                        self.assertIn('WIN NOW:', page.locator('#my-team-outlook-goal').text_content())
                        page.locator('#my-team-strategy').select_option('REBUILD')
                        self.assertEqual(page.locator('#my-team-outlook-action').get_attribute('href'), '#draft-capital')
                        page.goto('https://dtos.test/teams/2')
                        self.assertEqual(page.locator('#my-team-outlook-action').count(), 0)
                        self.assertEqual(page.locator('#my-team-outlook a[href^="/trades"]').count(), 0)
                        self.assertIn('Read-only', page.locator('.thq-content').inner_text())
                    finally:
                        page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_OUTLOOK_EVIDENCE'):
            (Path(os.environ['DTOS_OUTLOOK_EVIDENCE']) / 'phone-measurements.json').write_text(json.dumps(measurements, indent=2))
