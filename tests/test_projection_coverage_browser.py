"""Private fixture publication -> actual My Team/weekly HTML -> Chromium.

Synthetic rosters only. These are controlled desktop/phone viewports, not
physical Safari testing or a live Day Traders publication.
"""
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests.projection_coverage_fixture import prepared
from tools.validation.browser_runtime import launch_chromium


class ProjectionCoverageBrowserTests(unittest.TestCase):
    def test_coverage_exclusions_weekly_context_and_navigation(self):
        f, data, service = prepared(self)
        reports = []
        output = os.environ.get('DTOS_PROJECTION_COVERAGE_EVIDENCE')
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    with self.subTest(width=width):
                        page = f.f.browser_page(browser, width, height)
                        try:
                            errors = []
                            page.on('pageerror', lambda error: errors.append(str(error)))
                            self.assertEqual(page.goto('https://dtos.test/teams/1').status, 200)
                            root = page.locator('#my-team-outlook')
                            self.assertIn('/7 supported', root.inner_text())
                            self.assertIn('10 total', root.inner_text())
                            detail = page.locator('#my-team-outlook-evidence')
                            summary = detail.locator('summary')
                            # Enter keyboard modality before testing visible focus.
                            page.keyboard.press('Tab')
                            summary.focus()
                            self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            summary.press('Enter')
                            self.assertTrue(detail.evaluate('e=>e.open'))
                            self.assertIn('among 7 supported', detail.inner_text())
                            self.assertIn('7/10 franchises can fill', detail.inner_text())
                            self.assertIn('Franchise 8: excluded', detail.inner_text())
                            self.assertIn('1 QB slot', detail.inner_text())
                            self.assertEqual(summary.evaluate('e=>document.activeElement===e'), True)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            row = dict(width=width, height=height, outlook=root.bounding_box(),
                                       expanded_text=root.inner_text(), keyboard_focus=True)
                            if output:
                                Path(output).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(output, f'coverage-{width}.png')), full_page=True)
                            summary.press('Enter')
                            # Emulated touch activates the same native disclosure.
                            cdp = page.context.new_cdp_session(page)
                            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                            summary.scroll_into_view_if_needed()
                            box = summary.bounding_box()
                            point = {'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}
                            cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [point]})
                            cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                            self.assertTrue(detail.evaluate('e=>e.open'))
                            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
                            for label, target in (('Depth', '#positional-depth'),
                                                  ('Draft capital', '#draft-capital'),
                                                  ('View full roster', '#full-roster')):
                                link = page.get_by_role('navigation', name='Roster sections').get_by_role('link', name=label, exact=True)
                                self.assertEqual(link.get_attribute('href'), target)
                                link.click()
                                self.assertTrue(page.locator(target).is_visible())
                            self.assertEqual(page.goto('https://dtos.test/teams/8').status, 200)
                            page.locator('#my-team-outlook-evidence summary').click()
                            self.assertIn('1 QB slot', page.locator('#my-team-outlook').inner_text())
                            self.assertEqual(page.locator('#my-team-outlook a[href^="/trades"]').count(), 0)
                            # Actual weekly endpoint is an embeddable fragment,
                            # not a standalone full player-dossier acceptance.
                            contexts = []
                            for pid, expected in [('1-u', 'no usable scoring statistics'),
                                                  ('1-bye', 'NFL bye in Week 8'),
                                                  ('1-out', 'Listed OUT at preparation'),
                                                  ('10-w', 'DB / WR')]:
                                self.assertEqual(page.goto(f'https://dtos.test/players/{pid}/projections?week=8').status, 200)
                                panel = page.locator('#player-weekly-projections')
                                self.assertIn(expected, panel.inner_text())
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                contexts.append(dict(player=pid, text=panel.inner_text(), panel=panel.bounding_box()))
                            row['weekly_fragments'] = contexts
                            reports.append(row)
                            self.assertEqual(errors, [])
                        finally:
                            page.close()
            finally:
                browser.close()
        self.assertEqual(service.snapshot()['players']['1-bye']['canonical_projection'], 40)
        self.assertEqual(len(data['teams']), 10)
        if output:
            Path(output, 'measurements.json').write_text(json.dumps(reports, indent=2))
