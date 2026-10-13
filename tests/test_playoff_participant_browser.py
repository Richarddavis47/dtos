"""Real publisher/router HTML and released disclosure client in Chromium."""
from __future__ import annotations

import copy
import re
import unittest

from playwright.sync_api import sync_playwright
from tests import test_history_final_source_browser as browser_fixtures
from tests import test_historical_tracker_phase2 as fixtures


class PlayoffParticipantBrowserTests(unittest.TestCase):
    def setUp(self):
        self.browser_fixture = browser_fixtures.HistoryFinalSourceBrowserTests()
        self.browser_fixture.setUp()

    def tearDown(self):
        self.browser_fixture.tearDown()

    def test_actual_season_page_valid_and_conflicted_at_phone_and_desktop_widths(self):
        fixture = self.browser_fixture.fixture
        with sync_playwright() as pw:
            browser, page = self.browser_fixture.browser(pw)
            for duplicate in (False, True):
                facts = copy.deepcopy(fixture.fixture.sources[0])
                facts['winners_bracket'] = [{'m': 1, 'p': 1, 't1': 1,
                    't2': 1 if duplicate else 2, 'w': 1, 'l': 2}]
                fixture.publish(facts)
                for width, height in [(320, 568), (375, 667), (390, 432), (390, 844), (1165, 800)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    response = page.goto('http://fixture/history/2026')
                    self.assertEqual(response.status, 200)
                    champion = page.locator('.season-champion h3')
                    if duplicate:
                        self.assertEqual(champion.inner_text(), 'Pending / unavailable')
                        self.assertEqual(page.locator('.season-champion .status-trophy').count(), 0)
                    else:
                        self.assertNotEqual(champion.inner_text(), 'Pending / unavailable')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            browser.close()

    def test_production_disclosure_numeric_week_order_and_keyboard_reopen(self):
        fixture = self.browser_fixture.fixture
        facts = copy.deepcopy(fixture.fixture.sources[0])
        facts['matchups'] = {str(week): [{'roster_id': 4, 'players': ['13346'],
            'starters': ['13346'] if week == 1 else [], 'players_points': {'13346': points}}]
            for week, points in [(1, 10), (10, 0), (2, 20), (11, None)]}
        fixture.publish(facts)
        with sync_playwright() as pw:
            browser, page = self.browser_fixture.browser(pw)
            for width, height in [(320, 568), (375, 667), (390, 432), (390, 844), (1165, 800)]:
                page.set_viewport_size({'width': width, 'height': height})
                disclosure = self.browser_fixture.open(page, fixtures.ROOT)
                disclosure.get_by_text('Complete holding-period benefit: Unavailable.', exact=False).first.wait_for()
                self.assertEqual(disclosure.get_attribute('data-loaded'), 'true')
                details = disclosure.locator('details').filter(has_text='Observed weeks and independent ownership intervals').first
                details.locator(':scope > summary').focus()
                details.locator(':scope > summary').press('Enter')
                texts = disclosure.locator('li').all_text_contents()
                weeks = [int(match[1]) for text in texts if (match := re.match(r'2026 Week (\d+) ·', text))]
                self.assertEqual(weeks, [1, 2, 10, 11])
                self.assertIn('Known observed roster subtotal: 30.00', disclosure.inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                disclosure.locator(':scope > summary').press('Enter')
                disclosure.locator(':scope > summary').press('Enter')
                self.assertEqual(disclosure.get_attribute('data-loaded'), 'true')
            browser.close()


if __name__ == '__main__':
    unittest.main()
