"""Disposable provider -> evaluator -> authenticated HTTP -> released client.

Chromium/CDP touch controls are not physical iPhone/Safari acceptance.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tests import test_rebuild_discovery_integrity as controls
from tests import test_trade_workflow_experience as workflow
from tools.validation.browser_runtime import launch_chromium


class RebuildDiscoveryBrowserTests(unittest.TestCase):
    def test_real_unseeded_generation_and_zero_results_at_four_viewports(self):
        case = controls.RebuildDiscoveryIntegrityTests()
        self.addCleanup(case.doCleanups)
        source = case.fixture()
        helper = workflow.TradeWorkflowExperienceTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        self.addCleanup(f.static.close)
        f.f.data.clear()
        f.f.data.update(deepcopy(source.data))
        source.data = f.f.data
        source.publish()
        reports = []
        with patch('services.trade_intelligence._trade_projection_service', return_value=source.reader), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page, records, _, errors, _ = helper.page(browser, f, width, height)
                    helper.ready(page)
                    self.assertEqual(records, [])
                    for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
                        page.select_option('#trade-strategy', strategy)
                        button = page.locator('#trade-find')
                        button.focus()
                        self.assertNotEqual(button.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                        button.press('Enter')
                        helper.complete(page)
                        payload, response = records[-1]['payload'], records[-1]['body']
                        self.assertIsNone(payload['asset_id'])
                        self.assertEqual(payload['partner_roster_id'], 0)
                        self.assertEqual(payload['assets_sent'], [])
                        self.assertEqual(payload['assets_received'], [])
                        self.assertEqual(payload['strategy'], strategy)
                        self.assertLessEqual(response['search_evidence']['full_evaluations'], 180)
                        for row in response['results']:
                            self.assertTrue(row['workflow_eligibility']['eligible'])
                        reports.append(dict(width=width, strategy=strategy, count=response['count'],
                                            search=response['search_evidence']))
                    self.assertGreater(response['count'], 0)
                    result = page.locator('#trade-result')
                    self.assertIn('Qualified recommendations', result.inner_text())
                    self.assertTrue(result.evaluate('e=>e===document.activeElement'))
                    output = os.environ.get('DTOS_REBUILD_DISCOVERY_EVIDENCE')
                    if output:
                        Path(output).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(output, f'rebuild-qualified-{width}.png')), full_page=True)
                    # Change ONLY the disposable browser's existing optional
                    # exact exclusions, not saved account preferences or the
                    # evaluator. Retain one severely overpriced exchange.
                    workspace = f.f.client.get('/api/trades/workspace?front_office=1').json()
                    ids = {a['asset_id'] for t in workspace['teams'] for a in t['assets']}
                    excluded = sorted(ids - {'z-veteran', '2028-R4-4'})
                    page.evaluate('''excluded => {
                        const key=Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'));
                        const draft=JSON.parse(sessionStorage.getItem(key));
                        draft.excludedAssets=excluded;
                        sessionStorage.setItem(key,JSON.stringify(draft));
                        history.replaceState({...history.state,dtosTrade:{...history.state.dtosTrade,draft}},'');
                    }''', excluded)
                    page.reload()
                    page.wait_for_function("!document.querySelector('#trade-find').disabled")
                    button = page.locator('#trade-find')
                    button.scroll_into_view_if_needed()
                    box = button.bounding_box()
                    self.assertGreaterEqual(box['height'], 44)
                    if width < 500:
                        touch = page.context.new_cdp_session(page)
                        touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                        touch.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[dict(x=box['x']+box['width']/2, y=box['y']+box['height']/2)]))
                        touch.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                        touch.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
                    else:
                        button.click()
                    helper.complete(page)
                    zero = records[-1]['body']
                    self.assertEqual(set(records[-1]['payload']['excluded_assets']), set(excluded))
                    self.assertEqual(zero['count'], 0)
                    self.assertFalse(zero['zero_result_guidance']['recommendation'])
                    text = page.locator('#trade-result').inner_text()
                    self.assertIn('No qualified recommendations', text)
                    self.assertIn('No bilateral recommendation', text)
                    self.assertIn('not qualified offers', text)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    bad = page.locator('main *').evaluate_all('es=>es.filter(e=>e.getBoundingClientRect().width>innerWidth+1).map(e=>e.tagName+"."+e.className)')
                    self.assertEqual(bad, [])
                    self.assertEqual(errors, [])
                    reports.append(dict(width=width, zero=zero, keyboard=True,
                                        chromium_touch=width < 500, overflowing_components=bad))
                    if output:
                        page.screenshot(path=str(Path(output, f'rebuild-zero-{width}.png')), full_page=True)
                    page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_REBUILD_DISCOVERY_EVIDENCE'):
            Path(os.environ['DTOS_REBUILD_DISCOVERY_EVIDENCE'], 'browser.json').write_text(json.dumps(reports, indent=2))
