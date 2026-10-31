"""Prepared producer -> authenticated HTTP -> actual primary recommendation cards."""
import json
import os
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright
from tests import test_trade_workflow_experience as workflow
from tools.validation.browser_runtime import launch_chromium


class ConditionalSummaryBrowserTests(unittest.TestCase):
    def test_visible_two_sided_conditions_at_four_sizes(self):
        helper = workflow.TradeWorkflowExperienceTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        reports = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320,432),(375,667),(390,844),(1280,900)]:
                    page, records, _, errors, _ = helper.page(browser, f, width, height)
                    try:
                        helper.ready(page)
                        page.select_option('#trade-strategy', 'RETOOL')
                        page.locator('#trade-find').press('Enter')
                        helper.complete(page)
                        card = page.locator('.tw-offer').first
                        self.assertGreater(page.locator('.tw-offer').count(), 0)
                        text = card.inner_text()
                        for phrase in ['Your team:', 'Their team:', 'Market fairness and receiving a pick', 'per week']:
                            self.assertIn(phrase, text)
                        self.assertTrue(card.locator('h3').first.is_visible())
                        disclosure = card.locator('details').first
                        summary = disclosure.locator('summary').first
                        summary.evaluate('(e)=>e.scrollIntoView({block:"center"})')
                        if width < 500:
                            box = summary.bounding_box()
                            touch = page.context.new_cdp_session(page)
                            touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                            touch.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}]})
                            touch.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
                        else:
                            summary.press('Enter')
                        self.assertTrue(disclosure.evaluate('e=>e.open'))
                        self.assertFalse(errors, errors)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                        root = os.environ.get('DTOS_CONDITIONAL_EVIDENCE')
                        if root:
                            Path(root).mkdir(parents=True,exist_ok=True)
                            card.scroll_into_view_if_needed()
                            page.screenshot(path=str(Path(root)/f'conditional-{width}.png'))
                        reports.append(dict(width=width,height=height,no_overflow=True,keyboard=True,post_status=records[-1]['status'],primary_summary=text))
                    finally:
                        page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_CONDITIONAL_EVIDENCE'):
            (Path(os.environ['DTOS_CONDITIONAL_EVIDENCE'])/'browser.json').write_text(json.dumps(reports,indent=2))
