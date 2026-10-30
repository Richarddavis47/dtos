"""Actual authorized HTTP and unchanged client over disposable full rosters."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests import test_trade_workflow_experience as workflow
from tools.validation.browser_runtime import launch_chromium


class RebuildRosterSpaceBrowserTests(unittest.TestCase):
    def test_full_rosters_unseeded_strategies_and_qualified_zero_states_at_four_sizes(self):
        helper = workflow.TradeWorkflowExperienceTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        self.addCleanup(f.static.close)
        f.f.data['league']['roster_positions'] = ['QB', 'BN', 'BN']
        f.source.prices(a=350)
        f.source.publish()
        source = deepcopy(f.f.data)
        with f.f.store.connect() as connection:
            original_goals = list(connection.execute('SELECT * FROM account_franchise_goals'))
            original_rankings = list(connection.execute('SELECT * FROM account_personal_rankings'))
        measurements = []
        output = Path(os.environ['DTOS_REBUILD_SPACE_EVIDENCE']) if os.getenv('DTOS_REBUILD_SPACE_EVIDENCE') else None
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page, records, _, errors, _ = helper.page(browser, f, width, height)
                    try:
                        helper.ready(page)
                        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
                            page.select_option('#trade-strategy', strategy)
                            generate = page.locator('#trade-find')
                            generate.focus()
                            self.assertNotEqual(generate.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            generate.press('Enter')
                            helper.complete(page)
                            request, response = records[-1]['payload'], records[-1]['body']
                            self.assertIsNone(request['asset_id'])
                            self.assertEqual(request['assets_sent'], [])
                            self.assertEqual(request['assets_received'], [])
                            self.assertEqual(request['partner_roster_id'], 0)
                            self.assertEqual(response['search_evidence']['hard_invalid'], 0)
                            self.assertLessEqual(response['search_evidence']['full_evaluations'], 180)
                        self.assertGreater(response['count'], 0)
                        self.assertIn('Qualified recommendations', page.locator('#trade-result').inner_text())
                        if output:
                            output.mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(output / f'full-roster-qualified-{width}.png'))
                        workspace = f.f.client.get('/api/trades/workspace').json()
                        ids = {a['asset_id'] for team in workspace['teams'] for a in team['assets']}
                        excluded = sorted(ids - {'a', '2028-R1-4'})
                        page.evaluate('''excluded=>{
                          const key=Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'));
                          const draft=JSON.parse(sessionStorage.getItem(key));draft.excludedAssets=excluded;
                          sessionStorage.setItem(key,JSON.stringify(draft));
                          history.replaceState({...history.state,dtosTrade:{...history.state.dtosTrade,draft}},'');
                        }''', excluded)
                        page.reload()
                        page.wait_for_function("!document.querySelector('#trade-find').disabled")
                        button = page.locator('#trade-find')
                        button.scroll_into_view_if_needed()
                        if width < 500:
                            box = button.bounding_box()
                            touch = page.context.new_cdp_session(page)
                            touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                            touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x']+box['width']/2, 'y': box['y']+box['height']/2}]})
                            touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                        else:
                            button.click()
                        helper.complete(page)
                        zero = records[-1]['body']
                        self.assertEqual(zero['count'], 0)
                        self.assertEqual(zero['search_evidence']['full_evaluations'], 0)
                        self.assertIn('extra roster space', page.locator('#trade-result').inner_text())
                        self.assertIn('not qualified offers', page.locator('#trade-result').inner_text())
                        self.assertFalse(zero['zero_result_guidance']['recommendation'])
                        overflow = page.evaluate('document.documentElement.scrollWidth-innerWidth')
                        self.assertLessEqual(overflow, 0)
                        self.assertFalse(errors, errors)
                        self.assertEqual(f.f.data, source)
                        with f.f.store.connect() as connection:
                            self.assertEqual(list(connection.execute('SELECT * FROM account_franchise_goals')), original_goals)
                            self.assertEqual(list(connection.execute('SELECT * FROM account_personal_rankings')), original_rankings)
                        measurements.append({'width': width, 'height': height, 'overflow': overflow,
                            'keyboard': True, 'chromium_touch': width < 500, 'unseeded': True,
                            'zero_result_capacity_explained': True, 'saved_goals_rankings_unchanged': True,
                            'admission': zero['search_evidence']['construction_admission']})
                        if output:
                            page.screenshot(path=str(output / f'full-roster-zero-{width}.png'))
                    finally:
                        page.close()
            finally:
                browser.close()
        if output:
            (output / 'browser-summary.json').write_text(json.dumps(measurements, indent=2))
