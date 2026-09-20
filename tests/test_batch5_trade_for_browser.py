"""Offer handoff fixture only; search quality is covered by separate real panels."""
import json
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from services.trade_intelligence import evaluate_trade_request
from tests import test_trade_workspace_batch1 as boundary


class TradeForHandoffTests(unittest.TestCase):
    def test_edit_adjust_and_build_own_mobile_desktop(self):
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        offer = evaluate_trade_request(fixture.data, fixture.payload)
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True)
            for width in (390, 1280):
                with self.subTest(width=width):
                    page = browser.new_page(viewport={'width': width, 'height': 900})
                    page.set_default_timeout(8000)
                    adjustments = []
                    def route(request):
                        parsed = urlsplit(request.request.url)
                        if parsed.netloc != 'dtos.test':
                            return request.abort()
                        if parsed.path == '/api/trades/generate':
                            return request.fulfill(json={'results': [offer]})
                        if parsed.path == '/api/trades/assist':
                            adjustments.append(json.loads(request.request.post_data))
                            return request.fulfill(json={'results': [], 'requested_mode': 'MAKE_THIS_TRADE_WORK',
                                                         'returned_modes': [], 'quiet_state': 'Handoff captured'})
                        response = fixture.client.request(request.request.method, parsed.path + '?' + parsed.query,
                            content=request.request.post_data, headers={k: v for k, v in request.request.headers.items()
                                                                      if k in ('content-type', 'x-csrf-token')})
                        request.fulfill(status=response.status_code, content_type=response.headers.get('content-type'), body=response.content)
                    page.route('**/*', route)
                    page.goto('https://dtos.test/trades/trade-for?asset_id=2-QB-0')
                    page.locator('#trade-target:not([hidden])').wait_for()
                    page.locator('#trade-find').click()
                    page.get_by_role('button', name='Open editable offer:', exact=False).click()
                    self.assertEqual(page.locator('#trade-review button[data-asset-id="1-QB-0"]').count(), 1)
                    self.assertEqual(page.locator('#trade-review button[data-asset-id="2-QB-0"]').count(), 1)
                    page.locator('#trade-adjust').click()
                    page.locator('#trade-instruction').fill('make this trade work')
                    page.locator('#trade-apply-adjust').click()
                    page.get_by_text('Handoff captured', exact=True).wait_for()
                    self.assertEqual(adjustments[0]['assets_sent'], ['1-QB-0'])
                    self.assertEqual(adjustments[0]['assets_received'], ['2-QB-0'])
                    page.locator('#trade-edit').click()
                    page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').click()
                    page.locator('#trade-sent-board button[data-asset-id="1-QB-1"]').click()
                    page.locator('#trade-sent-board button[data-asset-id="1-RB-2"]').click()
                    self.assertIn('3 assets', page.locator('#trade-tray-text').inner_text())
                    page.locator('#trade-build-own').click()
                    page.wait_for_url('**/trades/create?front_office=1')
                    page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').wait_for()
                    self.assertTrue(page.locator('#trade-tray').is_hidden())
                    self.assertEqual(page.locator('#trade-partner').input_value(), '')
                    page.close()
            browser.close()
