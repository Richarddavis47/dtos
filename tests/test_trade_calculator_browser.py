"""Responsive Chromium calculator editing, preview/adoption and navigation."""
import copy
import unittest

from tests import test_trade_scout_state_browser as scout


class CalculatorBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = scout.ScoutWorkspaceStateBrowserTests()
        self.data = self.fixture.workspace()
        self.data['calculator_generation'] = 'canonical-fixture'

    @staticmethod
    def state(page):
        return page.evaluate('JSON.parse(sessionStorage.getItem("dtos-trade-workspace:scout-session"))')

    def build(self, page):
        self.fixture.ready(page, '/trades/calculator?front_office=1')
        page.select_option('#trade-partner', '2')
        page.locator('#trade-sent-board button[data-asset-id="player:a"]').click()
        if page.locator('[data-side=received]').is_visible():
            page.click('[data-side=received]')
        page.locator('#trade-received-board button[data-asset-id="player:x"]').click()

    def balancing(self, route, payload):
        if route.request.url.endswith('/balance'):
            self.assertEqual(payload['assets_sent'], ['player:a'])
        offered = self.fixture.offer(['player:a', 'pick:2028:1:3'], ['player:x'])
        offered['balance_adjustment'] = {'change': 'ADD_PICK', 'original': {'sent': {'total': 400}, 'received': {'total': 600}, 'absolute_gap': 200},
            'suggested': {'sent': {'total': 600}, 'received': {'total': 600}, 'absolute_gap': 0},
            'reason': 'Narrower owned exact-pick gap.', 'meaning': 'Market adjustment, not a guaranteed better trade.', 'strategic_caution': True}
        if route.request.url.endswith('/evaluate'):
            return route.fulfill(json={'evaluation': offered['evaluation']})
        route.fulfill(json={'results': [offered], 'count': 1})

    def test_phone_verdict_controls_owned_selection_and_no_provider_requests(self):
        for width in (320, 375, 390):
            with self.subTest(width=width), self.fixture.page(width, workspace=self.data) as (page, requests):
                self.build(page)
                self.assertIn('Side A favored', page.locator('#calculator-verdict').inner_text())
                self.assertIn('Value gap: 200', page.locator('#trade-balance').inner_text())
                self.assertTrue(page.locator('#trade-balance-offer').is_enabled())
                self.assertLessEqual(page.locator('#trade-balance-offer').bounding_box()['y'], 650)
                self.assertEqual(requests, [])
                page.get_by_role('button', name='Remove A from calculator', exact=True).click()
                self.assertIn('Choose assets', page.locator('#calculator-verdict').inner_text())
                self.assertTrue(page.locator('#trade-balance-offer').is_disabled())
                page.click('[data-side=sent]')
                page.locator('#trade-sent-board button[data-asset-id="pick:2028:1:3"]').click()
                self.assertIn('Extremely Long Franchise', page.locator('#calculator-sent').inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)

    def test_exact_decimal_equal_and_partial_total_not_zero(self):
        data = copy.deepcopy(self.data)
        data['teams'][0]['assets'][0]['trade_value'] = 0.1
        data['teams'][0]['assets'][1]['trade_value'] = 0.2
        data['teams'][1]['assets'][0]['trade_value'] = 0.3
        with self.fixture.page(workspace=data) as (page, _):
            self.build(page)
            page.click('[data-side=sent]')
            page.locator('#trade-sent-board button[data-asset-id="player:b"]').click()
            self.assertIn('Approximately balanced', page.locator('#calculator-verdict').inner_text())
        data['teams'][0]['assets'][1]['trade_value'] = None
        with self.fixture.page(workspace=data) as (page, requests):
            self.build(page)
            page.click('[data-side=sent]')
            page.locator('#trade-sent-board button[data-asset-id="player:b"]').click()
            self.assertIn('Cannot determine reliably', page.locator('#calculator-verdict').inner_text())
            self.assertIn('Partial · known subtotal 0.1', page.locator('#trade-balance').inner_text())
            self.assertTrue(page.locator('#trade-balance-offer').is_disabled())
            self.assertEqual(requests, [])

    def test_preview_keep_adopt_reload_exact_pick_and_advanced_preserve_package(self):
        with self.fixture.page(workspace=self.data, api=self.balancing) as (page, requests):
            self.build(page)
            original = self.state(page)['currentProposal']
            page.click('#trade-balance-offer')
            page.get_by_role('button', name='Preview adjustment', exact=True).click()
            self.assertEqual(self.state(page)['currentProposal'], original)
            self.assertIn('Original Market: 400 sent / 600 received · Gap 200', page.locator('#trade-result').inner_text())
            self.assertIn('Major drawback', page.locator('#trade-result').inner_text())
            page.get_by_role('button', name='Keep original', exact=True).click()
            self.assertEqual(self.state(page)['currentProposal'], original)
            page.get_by_role('button', name='Preview adjustment', exact=True).click()
            page.reload()
            page.get_by_role('button', name='Adopt alternative', exact=True).wait_for()
            self.assertIn('Suggested Market: 600 sent / 600 received · Gap 0', page.locator('#trade-result').inner_text())
            page.get_by_role('button', name='Adopt alternative', exact=True).click()
            adopted = self.state(page)['currentProposal']
            self.assertEqual(adopted['sent'], ['player:a', 'pick:2028:1:3'])
            page.reload()
            page.locator('#calculator-verdict').get_by_text('Approximately balanced', exact=False).wait_for()
            self.assertEqual(self.state(page)['currentProposal'], adopted)
            page.click('#trade-run')
            page.locator('#trade-result').get_by_text('WORTH PURSUING', exact=False).wait_for()
            self.assertEqual(requests[-1][0], 'evaluate')
            self.assertEqual(requests[-1][1]['assets_sent'], adopted['sent'])
            self.assertEqual(requests[-1][1]['workflow'], 'create')

    def test_strategy_changes_arithmetic_identical_and_no_expensive_request(self):
        with self.fixture.page(workspace=self.data) as (page, requests):
            self.build(page)
            initial = page.locator('#trade-balance').inner_text()
            page.locator('summary').filter(has_text='Strategy for advanced').click()
            for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
                page.select_option('#trade-strategy', strategy)
                self.assertEqual(page.locator('#trade-balance').inner_text(), initial)
            self.assertEqual(requests, [])

    def test_protected_player_exact_acquired_pick_and_kept_incoming_sent_to_balance(self):
        held = []
        def capture(route, payload):
            held.append(payload)
            route.fulfill(json={'results': [], 'quiet_state': 'No credible option with these exact protections.'})
        with self.fixture.page(workspace=self.data, api=capture) as (page, _):
            self.build(page)
            page.click('#calculator-protect')
            for exact in ('player:b', 'pick:2028:1:3'):
                page.select_option('#trade-constraint-asset', exact)
                page.click('#calculator-lock')
            page.get_by_role('button', name='Keep incoming target', exact=True).click()
            page.click('#trade-balance-offer')
            page.locator('#trade-result').get_by_text('No credible option', exact=False).wait_for()
            self.assertEqual(held[-1]['protected_assets'], ['player:b', 'pick:2028:1:3'])
            self.assertEqual(held[-1]['required_incoming_asset'], 'player:x')
            self.assertEqual(held[-1]['market_generation'], 'canonical-fixture')
            page.reload()
            page.locator('#trade-balance').get_by_text('Exact protections', exact=False).wait_for()
            self.assertEqual(self.state(page)['protectedAssets'], held[-1]['protected_assets'])

    def test_generated_adopted_workflow_to_calculator_preserves_package_anchor_and_new_intent(self):
        with self.fixture.page(workspace=self.data) as (page, _):
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            self.fixture.adopt(page)
            original = self.state(page)['currentProposal']
            page.get_by_role('link', name='Open this workspace in Calculator', exact=True).click()
            page.locator('#calculator-verdict').wait_for()
            self.assertEqual(self.state(page)['currentProposal'], original)
            self.assertEqual(self.state(page)['requiredIncomingAsset'], 'player:x')
            self.fixture.ready(page, '/trades/shop?asset_id=player:b')
            self.assertEqual(self.state(page)['currentProposal']['sent'], ['player:b'])
            self.assertEqual(self.state(page)['currentProposal']['received'], [])
            self.assertIsNone(self.state(page)['requiredIncomingAsset'])

    def test_pending_balance_cannot_overwrite_newer_intent(self):
        pending = []
        def hold(route, payload):
            pending.append(route)
        with self.fixture.page(workspace=self.data, api=hold) as (page, _):
            self.build(page)
            page.click('#trade-balance-offer')
            page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy") === "true"')
            page.select_option('#trade-partner', '')
            pending[0].fulfill(json={'results': [self.fixture.offer(['player:a'], ['player:x'])]})
            page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy") === "false"')
            self.assertEqual(self.state(page)['currentProposal']['received'], [])
            self.assertTrue(page.locator('#trade-result').is_hidden())

    def test_desktop_readable_and_bounded(self):
        with self.fixture.page(1280, workspace=self.data) as (page, _):
            self.build(page)
            self.assertIn('Side A favored', page.locator('#calculator-verdict').inner_text())
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 1281)

    def test_changed_generation_offers_explicit_refresh_preserving_offer(self):
        def refreshed(route, payload):
            route.fulfill(status=422, json={'detail': {'code': 'canonical_evidence_changed', 'message': 'Market changed.'}})
        with self.fixture.page(workspace=self.data, api=refreshed) as (page, requests):
            self.build(page)
            original = self.state(page)['currentProposal']
            page.click('#trade-balance-offer')
            page.get_by_role('button', name='Reload Market facts', exact=True).wait_for()
            self.assertEqual(len(requests), 2)
            self.assertEqual(self.state(page)['currentProposal'], original)
            page.get_by_role('button', name='Reload Market facts', exact=True).click()
            page.locator('#calculator-verdict').get_by_text('Side A favored', exact=False).wait_for()
            self.assertEqual(self.state(page)['currentProposal'], original)
