"""Disposable authenticated HTTP → released client; Chromium, not human/Safari acceptance."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests import test_personal_trade_browser as personal_fixtures
from tests import test_roster_diagnostic_http as team_fixtures
from tests import test_trade_decision_http_browser as trade_fixtures
from tools.validation.browser_runtime import launch_chromium


class PlainEnglishBrowserTests(unittest.TestCase):
    viewports = ((320, 432), (375, 667), (390, 844), (1280, 900))

    def capture(self, page, name, width, height, selector):
        measurement = page.locator(selector).evaluate('''e => ({
            y:e.getBoundingClientRect().top, text:e.innerText,
            overflow:document.documentElement.scrollWidth-innerWidth})''')
        self.assertLessEqual(measurement['overflow'], 0)
        output = os.getenv('DTOS_PLAIN_ENGLISH_EVIDENCE')
        if output:
            root = Path(output)
            root.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(root / f'{name}-{width}.png'), full_page=True)
            (root / f'{name}-{width}.json').write_text(json.dumps({
                **measurement, 'width':width, 'height':height,
                'environment':'Responsive Chromium; disposable authenticated HTTP fixture'}, indent=2))

    def test_uninitialized_rankings_and_custom_trade_prerequisite(self):
        helper = personal_fixtures.PersonalTradeBrowserTests()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in self.viewports:
                    with self.subTest(width=width):
                        fixture = helper.fixture()
                        try:
                            page, records, errors = helper.page(browser, fixture, width, height)
                            page.goto('http://testserver/account/my-dtos')
                            page.locator('.personal-row').first.wait_for()
                            self.assertIn('Create rankings to personalize', page.locator('.personal-row').first.inner_text())
                            self.assertNotIn('Personal Unavailable', page.locator('#my-dtos').inner_text())
                            self.capture(page, 'rankings-setup', width, height, '#my-dtos')
                            summary = page.locator('#personal-settings > summary')
                            page.keyboard.press('Tab')
                            summary.focus()
                            self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            summary.press('Enter')
                            self.assertTrue(page.locator('#personal-settings').evaluate('e=>e.open'))
                            page.goto('http://testserver/trades/create?front_office=1')
                            page.locator('#trade-valuation-mode').wait_for()
                            self.assertTrue(page.locator('#trade-valuation-mode option[value=custom]').is_disabled())
                            self.assertIn('Create Custom Rankings in My DTOS', page.locator('.tw-valuation-mode').inner_text())
                            self.assertEqual(page.locator('.tw-valuation-mode a').get_attribute('href'), '/account/my-dtos')
                            self.capture(page, 'trade-setup', width, height, '.tw-valuation-mode')
                            self.assertEqual(records, [])
                            self.assertEqual(errors, [])
                            page.close()
                        finally:
                            fixture.doCleanups()
            finally:
                browser.close()

    def test_my_team_depth_and_partial_weekly_trade_explanation(self):
        team = team_fixtures.DiagnosticHTTPTests()
        team.setUp()
        self.addCleanup(team.doCleanups)
        team.publish(datetime.now(timezone.utc).isoformat())
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in self.viewports:
                    with self.subTest(width=width):
                        page = team.f.browser_page(browser, width, height)
                        page.goto('https://dtos.test/teams/1')
                        page.wait_for_load_state('networkidle')
                        self.assertNotIn('Biggest depth risk', page.locator('#my-team-outlook').inner_text())
                        self.assertNotIn('Unavailable · Fresh · Unavailable', page.locator('#positional-depth').inner_text())
                        self.capture(page, 'my-team', width, height, '#my-team-outlook')
                        page.locator('#my-team-outlook-evidence > summary').click()
                        self.assertIn('Depth and uncertainty', page.locator('#my-team-outlook').inner_text())
                        self.capture(page, 'depth', width, height, '#positional-depth')
                        page.close()
            finally:
                browser.close()
        trade = trade_fixtures.DecisionHTTPBrowserTests()
        trade.setUp()
        self.addCleanup(trade.doCleanups)
        for width, height in self.viewports:
            with self.subTest(width=width), trade.browser(width, height) as page:
                trade.ready(page)
                page.select_option('#trade-partner', '2')
                trade.select(page, 'sent', 'a')
                trade.select(page, 'sent', '2029-R1-1')
                trade.select(page, 'received', 'c')
                page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                page.locator('.tw-decision').wait_for()
                result = trade.responses[-1]['evaluation']
                self.assertIsNone(result['recommendation'])
                self.assertAlmostEqual(result['decision_context']['lineup']['delta'], 7.7)
                self.assertIn("This week's lineup comparison", page.locator('.tw-decision').inner_text())
                self.assertIn('not a complete trade recommendation', page.locator('.tw-decision').inner_text())
                self.assertIn('Other team:', page.locator('.tw-decision').inner_text())
                self.assertIn('Their cost and uncertainty:', page.locator('.tw-decision').inner_text())
                self.assertEqual(page.locator('.tw-evaluation-detail').get_attribute('open'), None)
                self.capture(page, 'trade-partial', width, height, '.tw-decision')
