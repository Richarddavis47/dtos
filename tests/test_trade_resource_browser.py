"""Authenticated phone readiness/deferral/retry; all mutations are disposable."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from src.platform import trade_execution as execution
from tests import test_home_opportunity_integrity as fixtures
from tests import test_trade_resource_admission as memory_fixtures
from tools.validation.browser_runtime import launch_chromium


class TradeResourceBrowserTests(unittest.TestCase):
    def test_four_sizes_distinguish_capacity_source_and_completed_search_without_losing_work(self):
        f = fixtures.OpportunityIntegrityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        measurements = []
        evidence = os.environ.get('DTOS_TRADE_RESOURCE_BROWSER_EVIDENCE')
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = launch_chromium(playwright, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    control = {'pressure': False}
                    posts = []
                    context = browser.new_context(viewport={'width': width, 'height': height},
                        has_touch=True, is_mobile=width < 1000)
                    try:
                        page = context.new_page()
                        def transport(route):
                            request = route.request
                            u = urlsplit(request.url)
                            if u.hostname != 'dtos.test':
                                return route.fulfill(status=200, body='')
                            headers = {k:v for k,v in request.headers.items() if k in ('content-type', 'x-csrf-token')}
                            if u.path == '/api/trades/generate' and control['pressure']:
                                with patch.object(execution, 'observe_memory', return_value=memory_fixtures.sample(2000 * execution.MIB)):
                                    response = f.f.client.request(request.method, u.path, content=request.post_data, headers=headers)
                            else:
                                response = f.f.client.request(request.method, u.path + ('?' + u.query if u.query else ''),
                                    content=request.post_data, headers=headers)
                            if response.status_code == 404 and u.path.startswith('/static/'):
                                response = f.static.get(u.path)
                            if request.method == 'POST':
                                posts.append({'path':u.path, 'payload':request.post_data_json, 'status':response.status_code})
                            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                        page.route('**/*', transport)
                        page.goto('https://dtos.test/trades/recommended?front_office=1')
                        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
                        self.assertIn('Projections prepared.', page.locator('#trade-search-readiness').inner_text())
                        self.assertEqual(posts, [])
                        # Temporary strategy is retained through deferral and retry.
                        page.locator('#trade-strategy').select_option('REBUILD')
                        control['pressure'] = True
                        page.locator('#trade-find').focus()
                        page.keyboard.press('Enter')
                        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='deferred'")
                        self.assertIn('temporarily paused', page.locator('#trade-search-readiness').inner_text())
                        self.assertNotIn('No qualified', page.locator('#recommendation-status').inner_text())
                        self.assertEqual(len(posts), 1)
                        if evidence:
                            page.screenshot(path=str(Path(evidence) / f'{width}x{height}-deferred.png'))
                        page.wait_for_timeout(150)
                        self.assertEqual(len(posts), 1)  # No automatic expensive retry.
                        control['pressure'] = False
                        page.locator('#trade-find').tap()
                        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='complete'")
                        self.assertEqual([x['status'] for x in posts], [503, 200])
                        for key in ('strategy', 'assets_sent', 'assets_received', 'protected_assets', 'excluded_assets', 'valuation_mode', 'workspace_context'):
                            self.assertEqual(posts[0]['payload'].get(key), posts[1]['payload'].get(key))
                        self.assertEqual(page.locator('#trade-strategy').input_value(), 'REBUILD')
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        if evidence:
                            page.screenshot(path=str(Path(evidence) / f'{width}x{height}-complete.png'))
                        page.reload()
                        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
                        self.assertEqual(len(posts), 2)
                        self.assertEqual(page.locator('#trade-strategy').input_value(), 'REBUILD')
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        measurements.append(dict(width=width, height=height, keyboard=True, touch=True,
                            source_state='prepared', deferred_status=503, retry_status=200, automatic_retries=0,
                            preserved_request=True, navigation_searches=0))
                    finally:
                        context.close()
            finally:
                browser.close()
        if evidence:
            Path(evidence, 'measurements.json').write_text(json.dumps(measurements, indent=2))
        print('DTOS_TRADE_RESOURCE_BROWSER ' + json.dumps(measurements))
