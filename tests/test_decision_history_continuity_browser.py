"""Actual disposable private HTTP → client; responsive Chromium, not Safari."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tests.test_decision_history_continuity import DecisionHistoryFixture, HistoricalContinuityFixture
from tests import test_personal_trade_browser as trade_browser
from tools.validation.browser_runtime import launch_chromium


class DecisionHistoryBrowserTests(unittest.TestCase):
    def setUp(self):
        # Use the application's complete CSS, including its base text color and
        # box sizing; the isolated HTTP helper supplies only its page shell.
        import dtos_app
        style = patch.object(trade_browser, 'DESIGN_SYSTEM_CSS', dtos_app.CSS)
        style.start()
        self.addCleanup(style.stop)

    def test_retained_market_dates_reach_existing_trade_disclosure_at_all_widths(self):
        helper = trade_browser.PersonalTradeBrowserTests()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in helper.viewports:
                    with self.subTest(width=width):
                        fixture = DecisionHistoryFixture()
                        try:
                            fixture.f.editor.initialize()
                            revision = fixture.f.editor.state()['revision']
                            page, records, errors = helper.page(browser, fixture.f, width, height)
                            helper.choose_package(page)
                            page.locator('#trade-run').click()
                            page.wait_for_function("document.querySelector('#trade-result').dataset.assessment==='true'")
                            outer = page.locator('details.tw-evaluation-detail > summary')
                            outer.focus()
                            outer.press('Enter')
                            reason = page.get_by_text('a: recorded neutral Market change', exact=False)
                            self.assertEqual(reason.count(), 1)
                            detail = reason.locator('xpath=ancestor::details[1]')
                            summary = detail.locator(':scope > summary')
                            page.keyboard.press('Tab')
                            summary.focus()
                            self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            summary.press('Enter')
                            self.assertTrue(reason.is_visible())
                            self.assertIn('+150.00 points from 2026-07-01 to 2026-08-31', reason.inner_text())
                            self.assertIn('compatible current publication', reason.inner_text())
                            summary.click()
                            self.assertFalse(reason.is_visible())
                            # Emulated touch is additional to keyboard/pointer controls.
                            touch = page.context.new_cdp_session(page)
                            touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                            summary.scroll_into_view_if_needed()
                            box = summary.bounding_box()
                            touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
                                {'x': box['x'] + box['width'] / 2, 'y': box['y'] + box['height'] / 2}]})
                            touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                            reason.wait_for(state='visible')
                            self.assertTrue(reason.is_visible())
                            custom = records[-1]['response']['evaluation']
                            page.locator('#trade-valuation-mode').select_option('neutral')
                            page.locator('#trade-run').click()
                            page.wait_for_function("document.querySelector('#trade-result').dataset.assessment==='true'")
                            neutral = records[-1]['response']['evaluation']
                            for key in ('market_evidence', 'lineup_impact'):
                                self.assertEqual(custom[key], neutral[key])
                            self.assertEqual(custom['dimensions']['historical_counterparty_evidence']['trend_signals'],
                                             neutral['dimensions']['historical_counterparty_evidence']['trend_signals'])
                            reason = page.get_by_text('a: recorded neutral Market change', exact=False)
                            page.locator('details.tw-evaluation-detail > summary').click()
                            reason.locator('xpath=ancestor::details[1]').locator(':scope > summary').click()
                            reason.scroll_into_view_if_needed()
                            self.assertFalse(errors, errors)
                            self.assertEqual(page.locator('body').evaluate('e=>getComputedStyle(e).color'), 'rgb(242, 246, 248)')
                            overflow = page.evaluate('document.documentElement.scrollWidth-innerWidth')
                            self.assertLessEqual(overflow, 0)
                            self.assertEqual(fixture.f.editor.state()['revision'], revision)
                            self.save(page, 'trade', width, height, {'overflow': overflow, 'errors': errors,
                                'reason': reason.inner_text(), 'custom': custom, 'neutral': neutral,
                                'revision_before': revision, 'revision_after': fixture.f.editor.state()['revision']})
                            page.close()
                        finally:
                            fixture.close()
            finally:
                browser.close()

    def test_acquired_week_and_exact_pick_reach_archive_and_dossier_at_all_widths(self):
        helper = trade_browser.PersonalTradeBrowserTests()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in helper.viewports:
                    with self.subTest(width=width):
                        fixture = HistoricalContinuityFixture()
                        try:
                            page, _, errors = helper.page(browser, fixture, width, height)
                            page.goto('http://testserver/transactions?scope=current_season&week=0')
                            self.assertIn('2026 Week 0', page.locator('body').inner_text())
                            link = page.locator('a[href="/trades/history/now-trade"]').first
                            self.assertTrue(link.is_visible())
                            page.keyboard.press('Tab')
                            link.focus()
                            self.assertNotEqual(link.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            link.press('Enter')
                            page.get_by_text('2028 Round 1', exact=False).first.wait_for()
                            self.assertIn('now-trade', page.url)
                            self.assertFalse(errors, errors)
                            overflow = page.evaluate('document.documentElement.scrollWidth-innerWidth')
                            self.assertLessEqual(overflow, 0)
                            self.save(page, 'history', width, height, {'overflow': overflow, 'errors': errors,
                                'text': page.locator('body').inner_text(), 'source_week': 0,
                                'exact_pick': fixture.now_trade['draft_picks']})
                            page.go_back()
                            self.assertIn('2026 Week 0', page.locator('body').inner_text())
                            page.close()
                        finally:
                            fixture.close()
            finally:
                browser.close()

    @staticmethod
    def save(page, kind, width, height, data):
        if output := os.getenv('DTOS_DECISION_HISTORY_EVIDENCE'):
            root = Path(output) / 'browser'
            root.mkdir(parents=True, exist_ok=True)
            data.update(width=width, height=height, environment='Controlled Chromium; disposable authenticated HTTP')
            (root / f'{kind}-{width}.json').write_text(json.dumps(data, indent=2, default=str))
            page.screenshot(path=str(root / f'{kind}-{width}.png'))
