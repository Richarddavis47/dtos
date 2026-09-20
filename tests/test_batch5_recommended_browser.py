"""Positive UI fixture; not a fabricated real-league recommendation."""
import json
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from services.trade_intelligence import evaluate_trade_request
from tests import test_trade_workspace_batch1 as boundary


class RecommendedHandoffTests(unittest.TestCase):
    def test_refresh_edit_adjust_fresh_manual_and_new_session(self):
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        offer = evaluate_trade_request(fixture.data, fixture.payload)
        offer.update(family_id='a' * 64, opportunity={'reason_tags': [], 'why_now': {'availability': 'unavailable', 'catalysts': []}})
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True)
            for width in (390, 1280):
                with self.subTest(width=width):
                    page = browser.new_page(viewport={'width': width, 'height': 900})
                    page.set_default_timeout(8000)
                    searches, handoffs = [], []
                    def route(request):
                        parsed = urlsplit(request.request.url)
                        if parsed.netloc != 'dtos.test':
                            return request.abort()
                        if parsed.path == '/api/trades/generate':
                            payload = json.loads(request.request.post_data)
                            searches.append(payload)
                            return request.fulfill(json={'workflow': 'recommended',
                                'results': [] if payload.get('excluded_recommendation_families') else [offer],
                                'quiet_state': 'No additional credible ideas.'})
                        if parsed.path == '/api/trades/assist':
                            handoffs.append(json.loads(request.request.post_data))
                            return request.fulfill(json={'results': [], 'requested_mode': 'MAKE_THIS_TRADE_WORK',
                                'returned_modes': [], 'quiet_state': 'Handoff captured'})
                        response = fixture.client.request(request.request.method, parsed.path + '?' + parsed.query,
                            content=request.request.post_data, headers={k: v for k, v in request.request.headers.items()
                            if k in ('content-type', 'x-csrf-token')})
                        request.fulfill(status=response.status_code, content_type=response.headers.get('content-type'), body=response.content)
                    page.route('**/*', route)
                    page.goto('https://dtos.test/trades/recommended')
                    page.get_by_role('button', name='Discover Recommended Trades').click()
                    page.get_by_role('button', name='Open editable offer:', exact=False).click()
                    self.assertEqual(searches[-1]['partner_roster_id'], 0)
                    self.assertIsNone(searches[-1]['asset_id'])
                    page.get_by_text('No supported current catalyst is available.', exact=True).wait_for()
                    page.locator('#trade-edit').click()
                    page.locator('#trade-adjust').click()
                    page.locator('#trade-apply-adjust').click()
                    page.get_by_text('Handoff captured', exact=True).wait_for()
                    self.assertEqual(handoffs[-1]['assets_sent'], ['1-QB-0'])
                    self.assertNotIn('excluded_recommendation_families', handoffs[-1])
                    page.locator('#recommendation-refresh').click()
                    page.get_by_text('No additional credible ideas.', exact=True).wait_for()
                    self.assertEqual(searches[-1]['excluded_recommendation_families'], ['a' * 64])
                    page.locator('#trade-build-own').click()
                    page.wait_for_url('**/trades/create?front_office=1')
                    page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').wait_for()
                    self.assertTrue(page.locator('#trade-tray').is_hidden())
                    page.goto('https://dtos.test/trades/recommended')
                    page.get_by_role('button', name='Discover Recommended Trades').click()
                    page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
                    self.assertEqual(searches[-1]['excluded_recommendation_families'], [])
                    page.close()
            browser.close()
