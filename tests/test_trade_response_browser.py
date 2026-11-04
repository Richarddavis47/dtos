"""Actual producer/HTTP/client timeout and explicit recovery, disposable accounts."""
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests import test_trade_workflow_experience as workflow
from tools.validation.browser_runtime import launch_chromium


class TradeResponseBrowserTests(unittest.TestCase):
    def test_bounded_timeout_late_response_and_explicit_retry_at_four_sizes(self):
        helper = workflow.TradeWorkflowExperienceTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        self.addCleanup(f.static.close)
        with f.f.store.connect() as connection:
            goals = list(connection.execute('SELECT * FROM account_franchise_goals'))
            rankings = list(connection.execute('SELECT * FROM account_personal_rankings'))
        output = Path(os.environ['DTOS_TRADE_RESPONSE_EVIDENCE']) if os.getenv('DTOS_TRADE_RESPONSE_EVIDENCE') else None
        observations = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page, records, held, errors, control = helper.page(browser, f, width, height)
                    try:
                        page.add_init_script('''(() => {
                          const original = window.setTimeout.bind(window);
                          window.setTimeout = (fn, ms, ...args) => original(fn,
                            window.__tradeTimeoutControl && ms === 120000 ? 50 : ms, ...args);
                          document.addEventListener('DOMContentLoaded', () => {
                            const status = document.querySelector('#recommendation-status');
                            new MutationObserver(() => {
                              if(status.dataset.state==='complete') window.__tradeCompleteAt=performance.now();
                            }).observe(status,{attributes:true,childList:true,subtree:true});
                          });
                        })();''')
                        helper.ready(page)
                        page.select_option('#trade-strategy', 'REBUILD')
                        page.evaluate('window.__tradeTimeoutControl=true')
                        control['hold'] = True
                        page.locator('#trade-find').press('Enter')
                        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='error'")
                        self.assertIn('timed out', page.locator('#recommendation-status').inner_text())
                        self.assertTrue(page.locator('#trade-find').is_enabled())
                        self.assertEqual(len(records), 1)
                        if output:
                            output.mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(output / f'timeout-{width}.png'))
                        route, response = held.pop()
                        route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                        page.wait_for_timeout(150)
                        self.assertEqual(len(records), 1)
                        self.assertEqual(page.locator('.tw-offer').count(), 0)
                        self.assertEqual(page.input_value('#trade-strategy'), 'REBUILD')
                        control['hold'] = False
                        page.evaluate('window.__tradeTimeoutControl=false')
                        button = page.locator('#trade-find')
                        button.scroll_into_view_if_needed()
                        if width < 500:
                            box = button.bounding_box()
                            touch = page.context.new_cdp_session(page)
                            touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                            touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x']+box['width']/2, 'y': box['y']+box['height']/2}]})
                            touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                        else:
                            button.press('Enter')
                        helper.complete(page)
                        page.wait_for_function('window.__tradeCompleteAt>0')
                        self.assertEqual(len(records), 2)
                        self.assertEqual(records[1]['payload'], records[0]['payload'])
                        self.assertEqual(records[1]['status'], 200)
                        self.assertGreater(records[1]['body']['count'], 0)
                        self.assertFalse(errors, errors)
                        overflow = page.evaluate('document.documentElement.scrollWidth-innerWidth')
                        self.assertLessEqual(overflow, 0)
                        rendering = page.evaluate('''() => {
                          const entries=performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/trades/generate'));
                          const last=entries.at(-1);
                          return {response_end_ms:last.responseEnd,complete_ms:window.__tradeCompleteAt,
                            response_to_complete_ms:window.__tradeCompleteAt-last.responseEnd};
                        }''')
                        self.assertGreaterEqual(rendering['response_to_complete_ms'], 0)
                        with f.f.store.connect() as connection:
                            self.assertEqual(list(connection.execute('SELECT * FROM account_franchise_goals')), goals)
                            self.assertEqual(list(connection.execute('SELECT * FROM account_personal_rankings')), rankings)
                        observations.append(dict(width=width, height=height, overflow=overflow,
                            keyboard=True, controlled_touch=width < 500, accelerated_existing_timeout_ms=50,
                            real_declared_timeout_ms=120000, automatic_retry_requests=0,
                            explicit_retry_succeeded=True, exact_request_preserved=True, saved_intent_unchanged=True,
                            browser_rendering=rendering))
                        if output:
                            page.screenshot(path=str(output / f'retry-ready-{width}.png'))
                    finally:
                        page.close()
            finally:
                browser.close()
        if output:
            (output / 'timeout-browser.json').write_text(json.dumps(observations, indent=2))
