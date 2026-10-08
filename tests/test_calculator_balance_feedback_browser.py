"""Pending calculator interaction and cleanup in responsive Chromium."""
import unittest

from tests import test_trade_calculator_browser as calculator


class CalculatorBalanceFeedbackBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = calculator.CalculatorBrowserTests()
        self.fixture.setUp()

    def test_phone_immediate_feedback_selective_disabled_duplicate_and_success(self):
        for width in (320, 375, 390):
            pending = []
            with self.subTest(width=width), self.fixture.fixture.page(width, workspace=self.fixture.data, api=lambda route, payload: pending.append((route, payload))) as (page, requests):
                self.fixture.build(page)
                original = self.fixture.state(page)['currentProposal']
                page.click('#trade-balance-offer')
                status = page.locator('#calculator-balance-status')
                status.get_by_text('Finding balancing options…', exact=False).wait_for()
                self.assertTrue(page.locator('#trade-balance-offer').is_disabled())
                self.assertEqual(page.locator('#trade-balance-offer').get_attribute('aria-busy'), 'true')
                self.assertEqual(page.locator('#trade-builder').get_attribute('aria-busy'), 'false')
                remove = page.get_by_role('button', name='Remove A from calculator', exact=True)
                self.assertTrue(remove.is_disabled())
                self.assertEqual(remove.evaluate('(e) => getComputedStyle(e).cursor'), 'not-allowed')
                self.assertTrue(page.get_by_role('button', name='Keep incoming target', exact=True).is_disabled())
                self.assertTrue(page.locator('#trade-received-board button[data-asset-id="player:x"]').is_disabled())
                self.assertTrue(page.get_by_role('searchbox', name='Search their assets').is_enabled())
                page.get_by_role('searchbox', name='Search their assets').fill('X')
                self.assertTrue(page.get_by_role('link', name='Open X player dossier').is_enabled())
                page.click('#calculator-protect')
                self.assertTrue(page.locator('#calculator-lock').is_disabled())
                self.assertTrue(page.locator('#trade-release-lock').is_disabled())
                page.locator('#trade-balance-offer').dispatch_event('click')
                page.wait_for_timeout(30)
                self.assertEqual(len(requests), 1)
                self.assertEqual(self.fixture.state(page)['currentProposal'], original)
                button = page.locator('#trade-balance-offer').bounding_box()
                box = status.bounding_box()
                self.assertLess(box['y'] - button['y'] - button['height'], 16)
                page.locator('#trade-balance-offer').scroll_into_view_if_needed()
                self.assertLess(status.bounding_box()['y'] + box['height'], 844)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
                self.fixture.balancing(*pending[0])
                page.get_by_role('button', name='Preview adjustment', exact=True).wait_for()
                self.assertTrue(remove.is_enabled())
                self.assertTrue(page.locator('#calculator-lock').is_enabled())
                self.assertEqual(self.fixture.state(page)['currentProposal'], original)
                page.get_by_role('button', name='Preview adjustment', exact=True).click()
                page.get_by_role('button', name='Keep original', exact=True).click()
                self.assertEqual(self.fixture.state(page)['currentProposal'], original)

    def test_empty_error_network_failure_and_timeout_restore_controls_and_original(self):
        for outcome in ('empty', 'error', 'network', 'timeout'):
            pending = []
            with self.subTest(outcome=outcome), self.fixture.fixture.page(workspace=self.fixture.data, api=lambda route, payload: pending.append(route)) as (page, _):
                self.fixture.build(page)
                original = self.fixture.state(page)['currentProposal']
                if outcome == 'timeout':
                    page.clock.install()
                page.click('#trade-balance-offer')
                page.wait_for_timeout(30)
                if outcome == 'empty':
                    pending[0].fulfill(json={'results': [], 'count': 0})
                elif outcome == 'error':
                    pending[0].fulfill(status=503, json={'detail': {'message': 'Balancing temporarily unavailable. Try again.'}})
                elif outcome == 'network':
                    pending[0].abort('failed')
                else:
                    page.clock.run_for(45001)
                    pending[0].fulfill(json={'results': [], 'count': 0})
                page.wait_for_function('!document.querySelector("#trade-balance-offer").disabled')
                self.assertTrue(page.get_by_role('button', name='Remove A from calculator', exact=True).is_enabled())
                self.assertEqual(page.locator('#trade-balance-offer').get_attribute('aria-busy'), 'false')
                self.assertEqual(self.fixture.state(page)['currentProposal'], original)
                text = page.locator('#calculator-balance-status').inner_text()
                self.assertNotIn('Finding balancing options', text)
                self.assertIn('timed out' if outcome == 'timeout' else 'No balancing' if outcome == 'empty' else 'unavailable' if outcome == 'error' else 'could not connect', text)

    def test_changed_intent_cancels_pending_balance_and_old_response_cannot_restore_it(self):
        for intent in ('partner', 'strategy', 'navigate'):
            pending = []
            with self.subTest(intent=intent), self.fixture.fixture.page(workspace=self.fixture.data, api=lambda route, payload: pending.append(route)) as (page, _):
                self.fixture.build(page)
                page.click('#trade-balance-offer')
                page.wait_for_timeout(30)
                if intent == 'partner':
                    page.select_option('#trade-partner', '')
                elif intent == 'strategy':
                    page.locator('summary').filter(has_text='Strategy for advanced').click()
                    page.select_option('#trade-strategy', 'REBUILD')
                else:
                    self.fixture.fixture.ready(page, '/trades/trade-for?front_office=1&asset_id=player:y')
                if intent == 'strategy':
                    page.click('#trade-balance-offer')
                    page.wait_for_timeout(30)
                    pending[1].fulfill(json={'results': [], 'count': 0})
                    page.wait_for_function('!document.querySelector("#trade-balance-offer").disabled')
                state = self.fixture.state(page)['currentProposal']
                pending[0].fulfill(json={'results': [self.fixture.fixture.offer(['player:a'], ['player:x'])], 'count': 1})
                page.wait_for_timeout(50)
                self.assertEqual(self.fixture.state(page)['currentProposal'], state)
                self.assertNotIn('Alternative preview', page.locator('#trade-result').inner_text())
                if intent != 'navigate':
                    self.assertFalse(page.locator('#trade-balance-offer').get_attribute('aria-busy') == 'true')
                    self.assertTrue(page.get_by_role('button', name='Remove A from calculator', exact=True).is_enabled())

    def test_pending_history_cleanup_restores_interactive_controls(self):
        pending = []
        with self.fixture.fixture.page(workspace=self.fixture.data, api=lambda route, payload: pending.append(route)) as (page, _):
            self.fixture.build(page)
            original = self.fixture.state(page)['currentProposal']
            page.click('#trade-balance-offer')
            page.wait_for_timeout(30)
            page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true})); dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}));")
            pending[0].fulfill(json={'results': [], 'count': 0})
            self.assertTrue(page.get_by_role('button', name='Remove A from calculator', exact=True).is_enabled())
            self.assertTrue(page.locator('#trade-balance-offer').is_enabled())
            self.assertEqual(self.fixture.state(page)['currentProposal'], original)
            self.assertEqual(page.locator('#trade-balance-offer').get_attribute('aria-busy'), 'false')
