"""Shipped UI handoffs using one actual evaluator output, not search acceptance."""

from tools.validation.browser_runtime import launch_chromium
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
            browser = launch_chromium(engine, headless=True)
            try:
                for width in (390, 1280):
                    for flow in ('trade-for', 'shop', 'recommended', 'create'):
                        with self.subTest(width=width, workflow=flow):
                            page = browser.new_page(viewport={'width': width, 'height': 900})
                            page.set_default_timeout(8000)
                            pending, errors, operations = [], [], []
                            page.on('pageerror', lambda error: errors.append(str(error)))

                            def route(request):
                                parsed = urlsplit(request.request.url)
                                if parsed.netloc != 'dtos.test':
                                    return request.abort()
                                if request.request.method == 'POST' and parsed.path.startswith('/api/trades/'):
                                    operations.append(parsed.path)
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
                            if flow == 'recommended':
                                page.locator('#trade-asset-options > summary').click()
                            page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').wait_for()
                            if flow == 'create':
                                page.get_by_label('Trade partner', exact=True).select_option('2')
                                page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').click()
                                if width < 760:
                                    page.get_by_role('button', name='Their assets', exact=True).click()
                                page.locator('#trade-received-board button[data-asset-id="2-QB-0"]').click()
                                page.locator('#trade-adjust').click()
                                page.locator('#trade-apply-adjust').click()
                            elif flow == 'recommended':
                                page.locator('#trade-find').click()
                            page.locator('#trade-apply-adjust:disabled').wait_for(state='attached')
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
                            focus_before = page.evaluate('document.activeElement.id')
                            scroll_before = page.evaluate('scrollY')
                            pending.pop().fulfill(json=body)
                            # A separate live announcement delivers immediate feedback.
                            # Preserve visible completion and workspace busy semantics. Wait for actual completion, not root busy.
                            page.locator('#recommendation-status[data-state="complete"]').wait_for()
                            self.assertEqual(page.locator('#trade-builder').get_attribute('aria-busy'), 'false')
                            if flow == 'shop':  # Initial targeted entry retains its context.
                                self.assertEqual(page.evaluate('document.activeElement.id'), focus_before)
                                self.assertEqual(page.evaluate('scrollY'), scroll_before)
                            else:
                                self.assertEqual(page.evaluate('document.activeElement.id'), 'trade-result')
                            card = page.locator('.tw-offer')
                            self.assertEqual(card.locator('h3').first.inner_text(), offer['evaluation']['recommendation'] or 'Recommendation unavailable')
                            self.assertEqual(card.locator(':scope > .tw-lineup-details').count(), 0)
                            self.assertEqual(card.locator('.tw-draft-capital').count(), 0)
                            original_count = page.locator('#trade-sent-chips .tw-asset').count()
                            before_review_operations = list(operations)
                            review_action = card.get_by_role('button', name='Review trade', exact=True)
                            self.assertGreaterEqual(review_action.bounding_box()['height'], 44)
                            review_action.focus()
                            page.keyboard.press('Enter')
                            review = page.locator('#trade-result .tw-offer-review')
                            self.assertEqual(page.locator('#trade-sent-chips .tw-asset').count(), original_count)
                            self.assertEqual(operations, before_review_operations)
                            # The compact card deliberately omits deep evidence.
                            # Read the same already-prepared explanation through
                            # the real organized review before checking parity.
                            for selector in ('.tw-depth-details', '.tw-lineup-details', '.tw-offer-sources'):
                                details = review.locator(':scope > ' + selector)
                                summary = details.locator(':scope > summary')
                                self.assertGreaterEqual(summary.bounding_box()['height'], 44)
                                summary.focus()
                                page.keyboard.press('Enter')
                                self.assertTrue(details.evaluate('e=>e.open'))
                            prepared_text = review.locator('.tw-offer-sources .dtos-explanation').text_content()
                            prepared_slots = review.locator(':scope > .tw-lineup-details').text_content()
                            prepared_risks = review.locator(':scope > .tw-depth-details .tw-lineup-warning').all_text_contents()
                            self.assertEqual(operations, before_review_operations)
                            page.get_by_role('button', name='Use this offer in my draft', exact=True).click()
                            self.assertEqual(operations, before_review_operations)
                            adopted = page.evaluate('history.state.dtosTrade.draft.currentProposal')
                            self.assertEqual(adopted['sent'], list(offer['proposal']['assets_sent']))
                            self.assertEqual(adopted['received'], list(offer['proposal']['assets_received']))
                            self.assertEqual(adopted['partner'], offer['proposal']['partner_roster_id'])
                            # All evaluator evidence remains identical. Review
                            # groups slots and risks separately from calculations;
                            # compare each exact family with adopted Evaluate.
                            assessment = page.locator('#trade-result .dtos-explanation')
                            balance = assessment.locator(':scope > a[href="#trade-balancing"]')
                            self.assertEqual(balance.count(), 1)
                            self.assertTrue(balance.is_visible())
                            self.assertEqual(assessment.locator(':scope > .tw-lineup-details').text_content(), prepared_slots)
                            self.assertEqual(assessment.locator(':scope > .tw-lineup-warning').all_text_contents(), prepared_risks)
                            complete_text = assessment.evaluate("e=>{const copy=e.cloneNode(true);copy.querySelectorAll(':scope > a[href=\"#trade-balancing\"], :scope > .tw-lineup-details, :scope > .tw-lineup-warning').forEach(n=>n.remove());return copy.textContent;}")
                            self.assertEqual(complete_text, prepared_text)
                            self.assertEqual(page.locator('#trade-review button[data-asset-id="1-QB-0"]').count(), 1)
                            self.assertEqual(page.locator('#trade-review button[data-asset-id="2-QB-0"]').count(), 1)
                            self.assertEqual(page.evaluate('document.activeElement.id'), 'trade-result')
                            weekly = page.locator('#trade-result summary').filter(has_text='Weekly optimal-lineup detail')
                            if weekly.count():
                                full = assessment.get_by_text('Full team, weekly and evaluator evidence', exact=True)
                                self.assertFalse(full.evaluate('(e) => e.parentElement.open'))
                                self.assertGreaterEqual(full.bounding_box()['height'], 44)
                                full.focus()
                                page.keyboard.press('Enter')
                                self.assertTrue(full.evaluate('(e) => e.parentElement.open'))
                                support = page.locator('#trade-result summary').filter(has_text='Supporting evidence and limitations')
                                support.focus()
                                page.keyboard.press('Enter')
                                self.assertGreaterEqual(weekly.bounding_box()['height'], 44)
                                weekly.focus()
                                page.keyboard.press('Enter')
                                self.assertTrue(weekly.evaluate('(e) => e.parentElement.open'))
                            if flow == 'create':
                                self.assertTrue(page.locator('#trade-balance').is_visible())
                            else:
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
            browser = launch_chromium(engine, headless=True)
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
                        self.assertIn('No qualified recommendations', page.locator('#trade-result').inner_text())
                        self.assertIn('No credible opportunity in this bounded search.', page.locator('#trade-result').inner_text())
                        self.assertNotIn('tw-error', page.locator('#trade-result').get_attribute('class') or '')
                        self.assertEqual(page.locator('.tw-offer').count(), 0)
                        page.locator('#trade-find').click()
                        page.locator('#trade-builder[aria-busy="true"]').wait_for()
                        page.locator('#trade-search-options > summary').click()
                        page.locator('#recommendation-filter').select_option('future')
                        pending.pop().fulfill(status=503, json={'detail': 'Old search unavailable'})
                        page.locator('#trade-builder[aria-busy="false"]').wait_for()
                        self.assertTrue(page.locator('#trade-result').is_hidden())
                        self.assertEqual(page.locator('#recommendation-filter').input_value(), 'future')
                        self.assertFalse(page.locator('#trade-find').is_disabled())
                        page.close()
            finally:
                browser.close()
