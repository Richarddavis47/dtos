"""Disposable source -> actual authorized HTTP -> rendered Trade workflow.

No production account writes. Held responses simulate transfer delays, not
fabricated recommendation results. Chromium/CDP is not physical Safari.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tests import test_home_opportunity_integrity as fixtures
from tools.validation.browser_runtime import launch_chromium


class TradeWorkflowExperienceTests(unittest.TestCase):
    def fixture(self):
        f = fixtures.OpportunityIntegrityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def page(self, browser, f, width=375, height=667):
        page = browser.new_page(viewport=dict(width=width, height=height))
        page.set_default_timeout(10000)
        records, held, errors = [], [], []
        control = dict(hold=False, fail=False, invalid=False, hold_workspace=False, fail_workspace=False)
        page.on('pageerror', lambda e: errors.append(str(e)))

        def transport(route):
            request, u = route.request, urlsplit(route.request.url)
            if u.hostname != 'dtos.test':
                return route.fulfill(status=200, body='')
            headers = {k: v for k, v in request.headers.items()
                       if k in ('content-type', 'x-csrf-token')}
            if u.path == '/api/trades/workspace' and control['fail_workspace']:
                return route.fulfill(status=503, content_type='application/json', body='{"detail":"Synthetic unavailable workspace"}')
            if u.path == '/api/trades/generate' and control['invalid']:
                records.append(dict(path=u.path, payload=request.post_data_json, status=200, body={}))
                return route.fulfill(status=200, content_type='application/json', body='{}')
            if u.path == '/api/trades/generate' and control['fail']:
                with patch('routes.trades.generate_trade_workflow', side_effect=RuntimeError('synthetic private error')):
                    response = f.f.client.request(request.method, u.path, content=request.post_data, headers=headers)
            else:
                response = f.f.client.request(request.method, u.path + ('?' + u.query if u.query else ''), content=request.post_data, headers=headers)
            if response.status_code == 404 and u.path.startswith('/static/'):
                response = f.static.get(u.path)
            if request.method == 'POST' and u.path.startswith('/api/trades/'):
                records.append(dict(path=u.path, payload=request.post_data_json,
                                    status=response.status_code, body=response.json()))
            if (u.path == '/api/trades/generate' and control['hold']) or (u.path == '/api/trades/workspace' and control['hold_workspace']):
                held.append((route, response))
                return
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)

        page.route('**/*', transport)
        return page, records, held, errors, control

    def ready(self, page, flow='recommended'):
        page.goto('https://dtos.test/trades/' + flow + '?front_office=1')
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")

    def complete(self, page):
        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='complete'")

    def test_initial_reads_never_discover_and_intent_routes_are_distinct(self):
        f = self.fixture()
        with patch('routes.trades.generate_trade_workflow') as generate:
            for path in ['/trades?front_office=1', '/trades/recommended?front_office=1', '/trades/calculator?front_office=1']:
                response = f.f.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('Generate Trades', response.text)
                self.assertIn('Evaluate Trade', response.text)
            generate.assert_not_called()
        html = f.f.client.get('/trades/recommended?front_office=1').text
        self.assertLess(html.index('id="trade-strategy"'), html.index('id="trade-board"'))
        self.assertLess(html.index('id="trade-result"'), html.index('id="trade-board"'))
        self.assertIn('id="trade-asset-options"', html)

    def test_unseeded_goals_and_exact_pick_exclusions_are_request_only(self):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, _ = self.page(browser, f)
                self.ready(page)
                workspace = f.workspace
                picks = {a['asset_id'] for t in workspace['teams'] for a in t['assets'] if a['kind'] == 'pick'}
                self.assertTrue(picks)
                for strategy in ('', 'WIN NOW', 'RETOOL', 'REBUILD'):
                    page.select_option('#trade-strategy', strategy)
                    page.locator('#trade-find').click()
                    self.complete(page)
                    p = records[-1]['payload']
                    self.assertEqual(p['strategy'], strategy or None)
                    self.assertEqual(p['partner_roster_id'], 0)
                    self.assertIsNone(p['asset_id'])
                    self.assertEqual(p['assets_sent'], [])
                    self.assertEqual(p['assets_received'], [])
                    self.assertEqual(p['recommendation_filter'], 'all')
                    self.assertEqual(p['excluded_assets'], [])
                page.locator('#trade-search-options > summary').click()
                page.locator('#trade-include-picks').uncheck()
                count = len(records)
                page.wait_for_timeout(50)
                self.assertEqual(len(records), count)
                page.locator('#trade-find').click()
                self.complete(page)
                p = records[-1]['payload']
                self.assertEqual(set(p['excluded_assets']), picks)
                body = records[-1]['body']
                for row in body.get('results', []) + body.get('exploratory_results', []):
                    self.assertFalse(picks & set(row['proposal']['assets_sent'] + row['proposal']['assets_received']))
                # Temporary exclusions must not become saved exact locks when
                # the server echoes constraints. Re-enabling restores defaults.
                page.locator('#trade-include-picks').check()
                page.locator('#trade-find').click()
                self.complete(page)
                self.assertEqual(records[-1]['payload']['excluded_assets'], [])
                page.locator('#recommendation-filter').select_option('value')
                page.locator('#trade-find').click()
                self.complete(page)
                self.assertEqual(records[-1]['payload']['recommendation_filter'], 'value')
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_progress_duplicate_cancel_strategy_and_late_response(self):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, held, errors, control = self.page(browser, f)
                self.ready(page)
                # A browser that cannot abort transfer must still reject an old
                # response by intent revision, not just trust abort delivery.
                page.evaluate('() => {window.AbortController=class {abort(){} get signal(){return undefined}}}')
                control['hold'] = True
                page.evaluate("document.querySelector('#trade-find').click();document.querySelector('#trade-find').click()")
                page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='loading'")
                self.assertTrue(page.locator('#trade-find').is_disabled())
                self.assertIsNone(page.locator('#trade-operation-announcement').evaluate("e=>e.closest('[aria-busy=true]')"))
                self.assertEqual(page.locator('#trade-operation-announcement').text_content(), page.locator('#recommendation-status').text_content())
                self.assertEqual(page.locator('#trade-builder').get_attribute('aria-busy'), 'true')
                page.wait_for_timeout(50)
                self.assertEqual(len(records), 1)
                page.locator('#trade-cancel').click()
                self.assertEqual(page.locator('#recommendation-status').get_attribute('data-state'), 'cancelled')
                self.assertTrue(page.locator('#trade-find').evaluate('e=>e===document.activeElement'))
                route, response = held.pop()
                route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                page.wait_for_timeout(100)
                self.assertEqual(page.locator('.tw-offer').count(), 0)
                page.locator('#trade-find').click()
                page.wait_for_timeout(100)
                self.assertTrue(held)
                page.select_option('#trade-strategy', 'REBUILD')
                route, response = held.pop()
                route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                page.wait_for_timeout(100)
                self.assertEqual(page.locator('.tw-offer').count(), 0)
                self.assertIn('Strategy changed', page.locator('#recommendation-status').inner_text())
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_failure_retry_is_safe_and_does_not_reset_inputs(self):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, control = self.page(browser, f)
                self.ready(page)
                page.select_option('#trade-strategy', 'RETOOL')
                control['fail'] = True
                page.locator('#trade-find').click()
                page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='error'")
                self.assertEqual(records[-1]['status'], 503)
                self.assertNotIn('synthetic private error', page.content())
                self.assertFalse(page.locator('#trade-find').is_disabled())
                control['fail'] = False
                control['invalid'] = True
                page.locator('#trade-find').click()
                page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='error'")
                self.assertIn('incomplete', page.locator('#trade-result').inner_text())
                control['invalid'] = False
                page.locator('#trade-find').click()
                self.complete(page)
                self.assertEqual(records[-1]['status'], 200)
                self.assertEqual(records[-1]['payload']['strategy'], 'RETOOL')
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_preparation_failure_retry_and_ready_controls(self):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, held, errors, control = self.page(browser, f)
                control['hold_workspace'] = True
                page.goto('https://dtos.test/trades/recommended?front_office=1')
                self.assertIn('Preparing', page.locator('#recommendation-status').inner_text())
                self.assertTrue(page.locator('#trade-find').is_disabled())
                self.assertTrue(page.locator('#trade-strategy').is_disabled())
                page.wait_for_timeout(50)
                route, response = held.pop()
                route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                page.wait_for_function("!document.querySelector('#trade-find').disabled")
                control['hold_workspace'] = False
                control['fail_workspace'] = True
                page.reload()
                retry = page.get_by_role('button', name='Retry loading workspace')
                retry.wait_for()
                self.assertTrue(page.locator('#trade-find').is_disabled())
                control['fail_workspace'] = False
                retry.click()
                page.wait_for_function("!document.querySelector('#trade-find').disabled")
                self.assertEqual(records, [])
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_custom_neutral_modes_and_saved_rankings_survive_discovery(self):
        from tests import test_personal_trade_browser as personal_browser

        helper = personal_browser.PersonalTradeBrowserTests()
        f = helper.fixture()
        self.addCleanup(f.doCleanups)
        f.editor.initialize()
        before = f.editor.state()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page, records, errors = helper.page(browser, f, width, height)
                    page.goto('http://testserver/trades/recommended')
                    page.locator('#trade-valuation-mode').wait_for()
                    for selector in ('#trade-strategy', '#trade-valuation-mode'):
                        fit = page.locator(selector).evaluate("e=>{const c=document.createElement('canvas').getContext('2d'),s=getComputedStyle(e);c.font=s.font;return {text:Math.max(...Array.from(e.options).filter(o=>!o.disabled).map(o=>c.measureText(o.textContent).width)),available:e.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-24}}")
                        self.assertLessEqual(fit['text'], fit['available'], (width, selector, fit))
                    for mode in ('custom', 'neutral'):
                        page.select_option('#trade-valuation-mode', mode)
                        page.select_option('#trade-strategy', 'RETOOL')
                        page.locator('#trade-find').click()
                        self.complete(page)
                        self.assertEqual(records[-1]['payload']['valuation_mode'], mode)
                        self.assertEqual(records[-1]['status'], 200)
                        self.assertEqual(records[-1]['payload']['assets_sent'], [])
                        self.assertEqual(records[-1]['payload']['assets_received'], [])
                    self.assertEqual(errors, [])
                    page.close()
                self.assertEqual(f.editor.state()['revision'], before['revision'])
                self.assertEqual(f.editor.state()['rows'], before['rows'])
            finally:
                browser.close()

    def test_four_viewports_controls_results_disclosures_and_focus(self):
        f = self.fixture()
        reports = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page, records, _, errors, _ = self.page(browser, f, width, height)
                    self.ready(page)
                    page.get_by_role('link', name='Evaluate Trade', exact=True).click()
                    page.locator('.tw-calculator').wait_for()
                    page.get_by_role('link', name='Generate Trades', exact=True).click()
                    page.wait_for_function("!document.querySelector('#trade-find').disabled")
                    self.assertEqual(records, [])
                    strategy = page.locator('#trade-strategy').bounding_box()
                    generate = page.locator('#trade-find').bounding_box()
                    page.keyboard.press('Tab')
                    summary = page.locator('#trade-search-options > summary')
                    summary.focus()
                    self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                    summary.press('Enter')
                    self.assertTrue(summary.evaluate('e=>e.parentElement.open'))
                    summary.click()
                    if width < 500:
                        summary.scroll_into_view_if_needed()
                        box = summary.bounding_box()
                        touch = page.context.new_cdp_session(page)
                        touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                        touch.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[dict(x=box['x']+box['width']/2, y=box['y']+box['height']/2)]))
                        touch.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                        self.assertTrue(summary.evaluate('e=>e.parentElement.open'))
                        touch.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
                        summary.click()
                    page.locator('#trade-find').click()
                    self.complete(page)
                    result = page.locator('#trade-result')
                    self.assertTrue(result.evaluate('e=>e===document.activeElement'))
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    bad = page.locator('main *').evaluate_all('es=>es.filter(e=>e.getBoundingClientRect().width>innerWidth+1).map(e=>e.tagName+"."+e.className)')
                    self.assertEqual(bad, [])
                    body = records[-1]['body']
                    qualified = [r for r in body.get('results', []) if r['evaluation'].get('generated_trade_eligible') and r['evaluation'].get('recommendation') in ('SMASH ACCEPT', 'WORTH PURSUING')]
                    self.assertIn('Qualified recommendations' if qualified else 'No qualified recommendations', result.inner_text())
                    self.assertEqual(errors, [])
                    box = result.bounding_box()
                    reports.append(dict(width=width, height=height, strategy=strategy, generate=generate, result_document_y=box['y'] + page.evaluate('scrollY'), result_viewport_y=box['y'], overflow=bad, focus=True))
                    directory = os.environ.get('DTOS_TRADE_WORKFLOW_EVIDENCE')
                    if directory:
                        Path(directory).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(directory, f'results-{width}.png')), full_page=True)
                        page.evaluate('scrollTo(0,0)')
                        page.screenshot(path=str(Path(directory, f'controls-{width}.png')), full_page=True)
                    page.locator('#trade-edit').click()
                    self.assertTrue(page.locator('#trade-asset-options').evaluate('e=>e.open'))
                    self.assertTrue(page.locator('#trade-partner').evaluate('e=>e===document.activeElement'))
                    page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_TRADE_WORKFLOW_EVIDENCE'):
            Path(os.environ['DTOS_TRADE_WORKFLOW_EVIDENCE'], 'browser-results.json').write_text(json.dumps(reports, indent=2))
