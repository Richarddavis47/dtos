"""Shipped UI handoffs using one actual evaluator output, not search acceptance."""
from copy import deepcopy
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from services.trade_intelligence import evaluate_trade_request
from tests import test_trade_workspace_batch1 as boundary


class TradeUXTests(unittest.TestCase):
    def test_generated_and_adjusted_offers_share_explanation_and_keep_proposal(self):
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        offer = evaluate_trade_request(fixture.data, fixture.payload)
        original = deepcopy(offer)
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True)
            try:
                for width in (390, 1280):
                    for flow in ('trade-for', 'shop', 'recommended', 'create'):
                        with self.subTest(width=width, workflow=flow):
                            page = browser.new_page(viewport={'width': width, 'height': 900})
                            page.set_default_timeout(8000)
                            pending, errors = [], []
                            page.on('pageerror', lambda error: errors.append(str(error)))

                            def route(request):
                                parsed = urlsplit(request.request.url)
                                if parsed.netloc != 'dtos.test':
                                    return request.abort()
                                if parsed.path in ('/api/trades/generate', '/api/trades/assist'):
                                    pending.append(request)
                                    return None
                                response = fixture.client.request(request.request.method, parsed.path + '?' + parsed.query,
                                    content=request.request.post_data, headers={k: v for k, v in request.request.headers.items()
                                    if k in ('content-type', 'x-csrf-token')})
                                request.fulfill(status=response.status_code,
                                    content_type=response.headers.get('content-type'), body=response.content)

                            page.route('**/*', route)
                            target = '?asset_id=1-QB-0' if flow == 'shop' else '?asset_id=2-QB-0' if flow == 'trade-for' else ''
                            page.goto('https://dtos.test/trades/' + flow + target)
                            page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').wait_for()
                            if flow == 'create':
                                page.get_by_label('Counterparty', exact=True).select_option('2')
                                page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').click()
                                if width < 760:
                                    page.get_by_role('button', name='Their assets', exact=True).click()
                                page.locator('#trade-received-board button[data-asset-id="2-QB-0"]').click()
                                page.locator('#trade-adjust').click()
                                page.locator('#trade-apply-adjust').click()
                            else:
                                page.locator('#trade-find').click()
                            page.locator('#trade-builder[aria-busy="true"]').wait_for()
                            self.assertTrue(page.locator('#trade-find').is_disabled())
                            self.assertTrue(page.locator('#trade-apply-adjust').is_disabled())
                            self.assertIn('proposal stays intact', page.locator('#trade-result').inner_text())
                            self.assertEqual(len(pending), 1)
                            body = {'results': [offer]}
                            if flow == 'shop':
                                body['markets'] = [{'counterparty_roster_id': 2, 'returns': [offer]}]
                            elif flow == 'recommended':
                                body['workflow'] = 'recommended'
                            elif flow == 'create':
                                body.update(requested_mode='MAKE_THIS_TRADE_WORK',
                                            returned_modes=['MAKE_THIS_TRADE_WORK'], target_preserved=True)
                            pending.pop().fulfill(json=body)
                            page.locator('#trade-builder[aria-busy="false"]').wait_for()
                            self.assertEqual(page.evaluate('document.activeElement.id'), 'trade-result')
                            card = page.locator('.tw-offer')
                            self.assertEqual(card.locator('h3').first.inner_text(), offer['evaluation']['recommendation'] or 'Recommendation unavailable')
                            summary = card.locator('summary').first
                            self.assertGreaterEqual(summary.bounding_box()['height'], 44)
                            summary.focus()
                            page.keyboard.press('Enter')
                            self.assertTrue(card.locator('details').first.evaluate('(e) => e.open'))
                            compact_text = card.locator('.dtos-explanation').inner_text()
                            card.get_by_role('button', name='Open editable offer:', exact=False).click()
                            self.assertEqual(page.locator('#trade-result .dtos-explanation').inner_text(), compact_text)
                            self.assertEqual(page.locator('#trade-review button[data-asset-id="1-QB-0"]').count(), 1)
                            self.assertEqual(page.locator('#trade-review button[data-asset-id="2-QB-0"]').count(), 1)
                            self.assertEqual(page.evaluate('document.activeElement.id'), 'trade-result')
                            weekly = page.locator('#trade-result summary').filter(has_text='Weekly optimal-lineup detail')
                            if weekly.count():
                                support = page.locator('#trade-result summary').filter(has_text='Supporting evidence and limitations')
                                support.focus()
                                page.keyboard.press('Enter')
                                self.assertGreaterEqual(weekly.bounding_box()['height'], 44)
                                weekly.focus()
                                page.keyboard.press('Enter')
                                self.assertTrue(weekly.evaluate('(e) => e.parentElement.open'))
                            self.assertTrue(page.locator('.tw-market-detail').evaluate('(e) => !e.open'))
                            self.assertTrue(page.evaluate("Boolean(document.querySelector('#trade-result').compareDocumentPosition(document.querySelector('.tw-market-detail')) & Node.DOCUMENT_POSITION_FOLLOWING)"))
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            self.assertFalse(errors, errors)
                            page.close()
            finally:
                browser.close()
        self.assertEqual(offer, original)

    def test_quiet_result_is_not_error_and_stale_error_cannot_replace_changed_context(self):
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True)
            try:
                for width in (390, 1280):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 900})
                        page.set_default_timeout(8000)
                        pending = []

                        def route(request):
                            parsed = urlsplit(request.request.url)
                            if parsed.netloc != 'dtos.test':
                                return request.abort()
                            if parsed.path == '/api/trades/generate':
                                pending.append(request)
                                return None
                            response = fixture.client.request(request.request.method, parsed.path + '?' + parsed.query,
                                content=request.request.post_data, headers={k: v for k, v in request.request.headers.items()
                                if k in ('content-type', 'x-csrf-token')})
                            request.fulfill(status=response.status_code,
                                content_type=response.headers.get('content-type'), body=response.content)

                        page.route('**/*', route)
                        page.goto('https://dtos.test/trades/recommended')
                        page.locator('#trade-find').click()
                        page.locator('#trade-builder[aria-busy="true"]').wait_for()
                        self.assertNotIn('%', page.locator('#trade-result').inner_text())
                        pending.pop().fulfill(json={'workflow': 'recommended', 'results': [],
                            'quiet_state': 'No credible opportunity in this bounded search.'})
                        page.locator('#trade-builder[aria-busy="false"]').wait_for()
                        self.assertEqual(page.locator('#trade-result').inner_text(), 'No credible opportunity in this bounded search.')
                        self.assertNotIn('tw-error', page.locator('#trade-result').get_attribute('class') or '')
                        self.assertEqual(page.locator('.tw-offer').count(), 0)
                        page.locator('#trade-find').click()
                        page.locator('#trade-builder[aria-busy="true"]').wait_for()
                        page.locator('#recommendation-filter').select_option('future')
                        pending.pop().fulfill(status=503, json={'detail': 'Old search unavailable'})
                        page.locator('#trade-builder[aria-busy="false"]').wait_for()
                        self.assertTrue(page.locator('#trade-result').is_hidden())
                        self.assertEqual(page.locator('#recommendation-filter').input_value(), 'future')
                        self.assertFalse(page.locator('#trade-find').is_disabled())
                        page.close()
            finally:
                browser.close()
