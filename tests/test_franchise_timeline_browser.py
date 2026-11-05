"""Actual history route, retained-source fixtures and phone interaction checks."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_franchise_timeline_coverage as fixtures
from tests.test_historical_tracker_phase2 import DAY, ARK


class FranchiseTimelineBrowserTests(unittest.TestCase):
    def test_two_league_coverage_at_four_sizes_keyboard_touch_and_no_read_work(self):
        import dtos_app
        helper = fixtures.FranchiseTimelineCoverageTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        helper.past()
        f = helper.f
        f.page_renderer = dtos_app.page
        root = os.environ.get('DTOS_FRANCHISE_HISTORY_EVIDENCE')
        if not root and os.environ.get('DTOS_PHASE2_EVIDENCE'):
            root = str(Path(os.environ['DTOS_PHASE2_EVIDENCE']) / 'franchise-history')
        records = []
        with patch.object(f.fixture.store, 'season_chain', side_effect=lambda league: {'seasons': [
                {'season': 2022, 'league_id': '9000000000000002022', 'cache_status': 'unavailable'}]} if league == DAY else {}), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for league, roster in ((DAY, '3'), (ARK, '1')):
                    f.data = f.fixture.data[league]
                    for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                        with self.subTest(league=league, width=width), patch.dict(dtos_app.STATE, {'data': f.data}):
                            page = browser.new_page(viewport={'width': width, 'height': height})
                            requests = []
                            def respond(route):
                                path = route.request.url.replace('http://fixture', '')
                                requests.append(path)
                                response = helper.client.get(path)
                                route.fulfill(status=response.status_code, content_type=response.headers.get('content-type', 'text/html'), body=response.content)
                            page.route('http://fixture/**', respond)
                            try:
                                response = page.goto('http://fixture/history/team/' + league + ':franchise:' + roster)
                                self.assertEqual(response.status, 200)
                                page.wait_for_load_state('networkidle')
                                timeline = page.locator('.franchise-timeline')
                                body = timeline.inner_text()
                                self.assertIn('Partial transaction coverage', body)
                                self.assertIn('RETAINED / NOT REVALIDATED', body)
                                if league == DAY:
                                    self.assertIn('2024 · Complete transaction coverage', body)
                                    self.assertIn('2022 · Unknown transaction coverage', body)
                                count = len(requests)
                                details = timeline.locator('details').first
                                summary = details.locator('summary')
                                summary.scroll_into_view_if_needed()
                                summary.focus()
                                self.assertEqual(summary.evaluate('el=>el===document.activeElement'), True)
                                self.assertNotEqual(summary.evaluate('el=>getComputedStyle(el).outlineStyle'), 'none')
                                summary.press('Enter')
                                self.assertTrue(details.evaluate('el=>el.open'))
                                box = summary.bounding_box()
                                self.assertGreaterEqual(box['height'], 44)
                                if width < 500:
                                    touch = page.context.new_cdp_session(page)
                                    touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                                    touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
                                    touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                                    self.assertFalse(details.evaluate('el=>el.open'))
                                self.assertEqual(len(requests), count)
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                                record = {'league_control': 'Day Traders retained replay' if league == DAY else 'Arkham retained replay', 'width': width, 'height': height, 'keyboard': True,
                                    'touch_emulated': width < 500, 'overflow': False, 'extra_disclosure_requests': len(requests)-count}
                                records.append(record)
                                if root:
                                    directory = Path(root)
                                    directory.mkdir(parents=True, exist_ok=True)
                                    timeline.scroll_into_view_if_needed()
                                    page.screenshot(path=str(directory / f'{league}-{width}.png'))
                            finally:
                                page.close()
            finally:
                browser.close()
        if root:
            (Path(root) / 'browser.json').write_text(json.dumps(records, indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
