"""Responsive Custom-blocker review and recovery into the real Trade client.

These are authenticated disposable HTTP fixtures in Chromium, not physical
iPhone/Safari or an unfamiliar-human acceptance study.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright

from tests import test_personal_trade_browser as existing
from tools.validation.browser_runtime import launch_chromium


class PersonalRankingsRecoveryTradeBrowserTests(unittest.TestCase):
    def test_trade_review_link_confirmed_recovery_and_neutral_custom_navigation(self):
        measurements = []
        helper = existing.PersonalTradeBrowserTests()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in helper.viewports:
                    with self.subTest(width=width):
                        fixture = helper.fixture()
                        page = None
                        try:
                            fixture.editor.initialize()
                            fixture.editor.post('reorder', asset_id='player:a', to_position=1)
                            for row in fixture.editor.market.rows:
                                if row['asset_id'] == 'player:b':
                                    row['values']['market_value'] = None
                            fixture.editor.market.generation = 'missing-b'
                            before = fixture.editor.state()
                            order_before = [row['asset_id'] for row in before['rows'] if row['custom_ranked']]
                            page, records, errors = helper.page(browser, fixture, width, height)
                            page.goto('http://testserver/trades/create')
                            page.locator('#trade-valuation-mode').wait_for()
                            self.assertEqual(page.locator('#trade-valuation-mode').input_value(), 'neutral')
                            self.assertTrue(page.locator('#trade-valuation-mode option[value="custom"]').is_disabled())
                            self.assertFalse(page.locator('#trade-valuation-mode option[value="neutral"]').is_disabled())
                            review = page.get_by_role('link', name='Review affected Custom Rankings assets', exact=True)
                            self.assertEqual(review.get_attribute('href'), '/account/my-dtos#personal-compatibility')
                            self.assertIn('b', page.locator('.tw-valuation-mode').inner_text())
                            self.assertFalse(records, records)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                            output = os.getenv('DTOS_PERSONAL_RECOVERY_EVIDENCE')
                            if output:
                                Path(output).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(output) / f'trade-blocked-{width}.png'))
                            review.focus()
                            page.keyboard.press('Tab')
                            page.keyboard.press('Shift+Tab')
                            self.assertEqual(page.evaluate('document.activeElement.textContent'), 'Review affected Custom Rankings assets')
                            self.assertNotEqual(review.evaluate('element=>getComputedStyle(element).outlineStyle'), 'none')
                            page.keyboard.press('Enter')
                            page.wait_for_url('**/account/my-dtos#personal-compatibility')
                            issue = page.locator('#personal-compatibility-issues [data-remove-asset="player:b"]')
                            issue.wait_for()
                            self.assertTrue(page.locator('#personal-compatibility').evaluate('element=>element.open'))
                            issue.click()
                            page.locator('#personal-remove-dialog').wait_for(state='visible')
                            page.locator('#personal-remove-confirm').focus()
                            page.keyboard.press('Enter')
                            page.wait_for_function("!document.querySelector('#personal-custom').disabled")
                            after = fixture.editor.state()
                            self.assertTrue(after['personal_available'])
                            self.assertEqual([row['asset_id'] for row in after['rows'] if row['custom_ranked']],
                                             [key for key in order_before if key != 'player:b'])
                            # The earlier temporary Trade draft correctly keeps
                            # its Neutral mode. Recovery enables Custom; it must
                            # not silently switch an existing user's draft.
                            page.goto('http://testserver/trades/create')
                            page.locator('#trade-valuation-mode').wait_for()
                            self.assertEqual(page.locator('#trade-valuation-mode').input_value(), 'neutral')
                            self.assertFalse(page.locator('#trade-valuation-mode option[value="custom"]').is_disabled())
                            page.locator('#trade-valuation-mode').select_option('custom')
                            helper.choose_package(page)
                            page.locator('#trade-run').click()
                            page.get_by_text('Custom DTOS · your personal assessment', exact=True).wait_for()
                            custom = next(record['response']['evaluation'] for record in records
                                          if record['endpoint'].endswith('/evaluate'))
                            page.locator('#trade-valuation-mode').select_option('neutral')
                            page.locator('#trade-run').click()
                            page.wait_for_function("document.querySelector('#trade-result')?.textContent.includes('WORTH PURSUING')")
                            neutral = next(record['response']['evaluation'] for record in reversed(records)
                                           if record['endpoint'].endswith('/evaluate'))
                            self.assertEqual(custom['market_evidence'], neutral['market_evidence'])
                            self.assertEqual(custom['lineup_impact'], neutral['lineup_impact'])
                            self.assertNotIn('personal_value_evidence', neutral)
                            self.assertFalse(errors, errors)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                            measurements.append({'width': width, 'height': height,
                                'overflow': 0, 'blocked_custom_neutral_available': True,
                                'keyboard_review_link_visible_focus': True,
                                'explicit_single_asset_confirmation': True,
                                'remaining_order_preserved': True,
                                'custom_then_neutral_market_lineup_equivalent': True,
                                'custom_recommendation': custom['recommendation'],
                                'neutral_recommendation': neutral['recommendation'],
                                'automatic_trade_calls_before_review': 0,
                                'browser_errors': errors})
                            if output:
                                page.screenshot(path=str(Path(output) / f'trade-recovered-neutral-{width}.png'))
                        finally:
                            if page:
                                page.close()
                            fixture.doCleanups()
            finally:
                browser.close()
        if os.getenv('DTOS_PERSONAL_RECOVERY_EVIDENCE'):
            (Path(os.environ['DTOS_PERSONAL_RECOVERY_EVIDENCE']) / 'trade-browser-measurements.json').write_text(
                json.dumps({'environment': 'Responsive Chromium; prepared transport; disposable authenticated accounts',
                            'measurements': measurements}, indent=2))
