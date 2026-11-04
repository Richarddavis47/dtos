"""Disposable authenticated source → store → HTTP → rendered partial Custom UI."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from playwright.sync_api import sync_playwright

from tests import test_personal_rankings_partial as controls
from tests import test_personal_trade_browser as existing
from tools.validation.browser_runtime import launch_chromium


class PartialCustomBrowserTests(unittest.TestCase):
    def test_partial_editor_and_supported_mixed_neutral_trade_at_all_widths(self):
        helper = existing.PersonalTradeBrowserTests()
        output = Path(os.environ['DTOS_PERSONAL_PARTIAL_EVIDENCE']) if os.getenv('DTOS_PERSONAL_PARTIAL_EVIDENCE') else None
        if output:
            output.mkdir(parents=True, exist_ok=True)
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in helper.viewports:
                    with self.subTest(width=width):
                        fixture = controls.PartialTradeHTTPTests('test_supported_package_and_all_workflows_remain_usable_without_repricing')
                        fixture.setUp()
                        page = None
                        try:
                            saved = deepcopy(fixture.f.document())
                            fixture.missing()
                            trade = fixture.f.fixture
                            touch_browser = SimpleNamespace(new_page=lambda **kw: browser.new_page(has_touch=width < 500, **kw))
                            page, records, errors = helper.page(touch_browser, trade, width, height)
                            page.goto('http://testserver/account/my-dtos')
                            page.locator('[data-asset-id="player:a"] .personal-values').wait_for()
                            self.assertIn('Personal 250', page.locator('[data-asset-id="player:a"] .personal-values').inner_text())
                            self.assertIn('depends on missing prices', page.locator('[data-asset-id="player:c"] .personal-values').inner_text())
                            self.assertIn('6 saved assets', page.locator('#personal-warnings').inner_text())
                            disclosure = page.locator('#personal-compatibility-summary')
                            disclosure.focus()
                            page.keyboard.press('Tab')
                            page.keyboard.press('Shift+Tab')
                            self.assertTrue(disclosure.evaluate('e=>e===document.activeElement'))
                            self.assertNotEqual(disclosure.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            disclosure.press('Enter')
                            self.assertTrue(page.locator('#personal-compatibility').evaluate('e=>e.open'))
                            if width < 500:
                                disclosure.scroll_into_view_if_needed()
                                box = disclosure.bounding_box()
                                page.touchscreen.tap(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                self.assertFalse(page.locator('#personal-compatibility').evaluate('e=>e.open'))
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                            if output:
                                output.mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(output / f'partial-editor-{width}.png'), full_page=True)
                            self.assertFalse(records)
                            helper.choose_package(page)
                            self.assertFalse(page.locator('#trade-valuation-mode option[value="custom"]').is_disabled())
                            page.locator('#trade-run').click()
                            page.get_by_text('Custom DTOS · your personal assessment', exact=True).wait_for()
                            custom = records[-1]['response']['evaluation']
                            self.assertEqual(custom['personal_value_evidence']['ranking_availability'], 'partial')
                            page.locator('#trade-valuation-mode').select_option('neutral')
                            page.locator('#trade-run').click()
                            page.wait_for_function("document.querySelector('#trade-result')?.textContent.includes('WORTH PURSUING')")
                            neutral = records[-1]['response']['evaluation']
                            for field in ('market_evidence', 'lineup_impact', 'multi_horizon_impact'):
                                self.assertEqual(custom[field], neutral[field])
                            page.locator('#trade-valuation-mode').select_option('custom')
                            page.locator('#trade-edit').click()
                            if not page.locator('#trade-received-board').is_visible():
                                page.locator('[data-side="received"]').click()
                            page.locator('#trade-received-board button[data-asset-id="2028-R1-4"]').click()
                            page.locator('#trade-received-board button[data-asset-id="c"]').click()
                            self.assertIn('without a verified personal value', page.locator('.tw-personal-comparison').inner_text())
                            page.locator('#trade-run').click()
                            page.wait_for_function("document.querySelector('#trade-result.tw-error')?.textContent.includes('personal value')")
                            self.assertEqual(records[-1]['response']['detail']['code'], 'personal_evidence_unavailable')
                            self.assertNotIn('evaluation', records[-1]['response'])
                            self.assertEqual(fixture.f.document(), saved)
                            self.assertFalse(errors, errors)
                            row = page.evaluate("()=>({viewport:[innerWidth,innerHeight],overflow:document.documentElement.scrollWidth-innerWidth,components:[...document.querySelectorAll('.tw-personal-comparison,.tw-valuation-mode')].map(e=>({width:e.clientWidth,overflow:e.scrollWidth-e.clientWidth}))})")
                            self.assertLessEqual(row['overflow'], 0)
                            self.assertTrue(all(x['overflow'] <= 1 for x in row['components']))
                            row.update(keyboard_focus=True, touch=width < 500, saved_document_unchanged=True,
                                       supported_custom_and_neutral_equivalent=True, dependent_package_withheld=True,
                                       uncontrolled_external_calls=0)
                            measurements.append(row)
                            if output:
                                page.screenshot(path=str(output / f'partial-mixed-package-{width}.png'), full_page=True)
                                (output / f'partial-ui-{width}.json').write_text(json.dumps(row, indent=2))
                        finally:
                            if page:
                                page.close()
                            fixture.doCleanups()
            finally:
                browser.close()
        if output:
            (output / 'browser-summary.json').write_text(json.dumps(measurements, indent=2))
