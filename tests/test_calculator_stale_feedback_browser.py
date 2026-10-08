"""Balancing feedback belongs to the exact offer/request, not a page lifetime."""
import unittest

from tests import test_trade_calculator_browser as calculator


class CalculatorStaleFeedbackBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = calculator.CalculatorBrowserTests()
        self.fixture.setUp()
        self.data = self.fixture.data
        next(a for a in self.data['teams'][0]['assets'] if a['asset_id'] == 'pick:2028:2:3')['trade_value'] = 180
        self.data['teams'][1]['assets'].append({'asset_id': 'pick:2029:4:1', 'kind': 'pick', 'label': '2029 fourth originally Active',
            'raw_label': '2029 fourth originally Active', 'trade_value': 180, 'season': 2029, 'round': 4, 'original_roster_id': 1, 'current_owner_id': 2})

    def respond(self, route, payload):
        values = {a['asset_id']: a['trade_value'] for t in self.data['teams'] for a in t['assets']}
        sent = payload['assets_sent']
        received = payload['assets_received']
        row = self.fixture.fixture.offer(sent + ['pick:2028:1:3'], received)
        old = sum(values[a] for a in sent)
        incoming = sum(values[a] for a in received)
        new = old + values['pick:2028:1:3']
        row['balance_adjustment'] = {'change': 'ADD_PICK', 'market_generation': 'canonical-fixture',
            'original': {'sent': {'total': old}, 'received': {'total': incoming}, 'absolute_gap': abs(incoming - old)},
            'suggested': {'sent': {'total': new}, 'received': {'total': incoming}, 'absolute_gap': abs(incoming - new)},
            'reason': 'Owned exact pick narrows the gap.', 'meaning': 'Market comparison, not a guaranteed better trade.', 'strategic_caution': True}
        route.fulfill(json={'results': [row], 'count': 1})

    def success(self, page):
        page.click('#trade-balance-offer')
        page.get_by_role('button', name='Preview adjustment', exact=True).wait_for()
        self.assertIn('Balancing options ready', page.locator('#calculator-balance-status').inner_text())

    def no_old_feedback(self, page):
        self.assertEqual(page.locator('#calculator-balance-status').inner_text(), '')
        self.assertFalse(page.get_by_role('button', name='Preview adjustment', exact=True).is_visible())
        self.assertIsNone(self.fixture.state(page)['previewProposal'])

    def add(self, page, which, asset_id):
        if page.locator(f'[data-side={which}]').is_visible():
            page.click(f'[data-side={which}]')
        page.locator(f'#trade-{which}-board button[data-asset-id="{asset_id}"]').click()

    def test_phone_success_edit_and_equal_180_exact_pick_swap_clear_feedback(self):
        for width in (320, 375, 390):
            with self.subTest(width=width), self.fixture.fixture.page(width, workspace=self.data, api=self.respond) as (page, _):
                self.fixture.build(page)
                self.success(page)
                status = page.locator('#calculator-balance-status')
                height = status.bounding_box()['height']
                page.get_by_role('button', name='Remove A from calculator', exact=True).click()
                self.no_old_feedback(page)
                self.assertAlmostEqual(status.bounding_box()['height'], height, delta=2)
                page.get_by_role('button', name='Remove X from calculator', exact=True).click()
                self.add(page, 'sent', 'pick:2028:2:3')
                self.add(page, 'received', 'pick:2029:4:1')
                self.assertIn('Approximately balanced', page.locator('#calculator-verdict').inner_text())
                self.assertIn('You send: 180', page.locator('#trade-balance').inner_text())
                self.assertIn('You receive: 180', page.locator('#trade-balance').inner_text())
                self.assertTrue(page.locator('#trade-balance-offer').is_disabled())
                self.no_old_feedback(page)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
                button = page.locator('#trade-balance-offer').bounding_box()
                self.assertLess(status.bounding_box()['y'] - button['y'] - button['height'], 16)
                state = self.fixture.state(page)['currentProposal']
                self.assertEqual(state['sent'], ['pick:2028:2:3'])
                self.assertEqual(state['received'], ['pick:2029:4:1'])

    def test_rebalance_preview_keep_adopt_and_exact_protections(self):
        with self.fixture.fixture.page(workspace=self.data, api=self.respond) as (page, requests):
            self.fixture.build(page)
            page.click('#calculator-protect')
            for asset_id in ('player:d', 'pick:2028:2:3'):
                page.select_option('#trade-constraint-asset', asset_id)
                page.click('#calculator-lock')
            original = self.fixture.state(page)['currentProposal']
            self.success(page)
            page.get_by_role('button', name='Preview adjustment', exact=True).click()
            self.assertEqual(self.fixture.state(page)['currentProposal'], original)
            page.get_by_role('button', name='Keep original', exact=True).click()
            self.assertIn('Balancing options ready', page.locator('#calculator-balance-status').inner_text())
            page.get_by_role('button', name='Preview adjustment', exact=True).click()
            page.get_by_role('button', name='Remove A from calculator', exact=True).click()
            self.no_old_feedback(page)
            self.add(page, 'sent', 'player:b')
            edited = self.fixture.state(page)['currentProposal']
            self.success(page)
            self.assertEqual(requests[-1][1]['assets_sent'], ['player:b'])
            page.get_by_role('button', name='Preview adjustment', exact=True).click()
            self.assertEqual(self.fixture.state(page)['currentProposal'], edited)
            page.get_by_role('button', name='Adopt alternative', exact=True).click()
            state = self.fixture.state(page)
            self.assertEqual(state['currentProposal']['sent'], ['player:b', 'pick:2028:1:3'])
            self.assertEqual(state['protectedAssets'], ['player:d', 'pick:2028:2:3'])
            self.assertEqual(page.locator('#calculator-balance-status').inner_text(), '')
            page.reload()
            page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
            self.assertEqual(self.fixture.state(page)['currentProposal'], state['currentProposal'])
            self.assertEqual(self.fixture.state(page)['protectedAssets'], state['protectedAssets'])
            self.assertEqual(page.locator('#calculator-balance-status').inner_text(), '')

    def test_constraints_strategy_and_partner_invalidate_balancing_preview(self):
        for change in ('protect', 'release', 'strategy', 'partner'):
            with self.subTest(change=change), self.fixture.fixture.page(workspace=self.data, api=self.respond) as (page, _):
                self.fixture.build(page)
                if change == 'release':
                    page.click('#calculator-protect')
                    page.select_option('#trade-constraint-asset', 'player:d')
                    page.click('#calculator-lock')
                self.success(page)
                page.get_by_role('button', name='Preview adjustment', exact=True).click()
                if change in ('protect', 'release'):
                    page.click('#calculator-protect')
                    page.select_option('#trade-constraint-asset', 'player:d')
                    page.click('#calculator-lock' if change == 'protect' else '#trade-release-lock')
                    message = page.locator('#trade-result').inner_text()
                    self.assertIn('protection added' if change == 'protect' else 'lock removed', message)
                    page.click('[data-side=sent]')
                    self.assertEqual(page.locator('#trade-result').inner_text(), message)
                elif change == 'strategy':
                    page.locator('summary').filter(has_text='Strategy for advanced').click()
                    page.select_option('#trade-strategy', 'REBUILD')
                else:
                    page.select_option('#trade-partner', '')
                self.no_old_feedback(page)

    def test_old_response_after_cancel_and_player_or_exact_pick_edit_is_ignored(self):
        for asset_id in ('player:b', 'pick:2028:2:3'):
            pending = []
            with self.subTest(asset_id=asset_id), self.fixture.fixture.page(workspace=self.data, api=lambda route, payload: pending.append((route, payload))) as (page, _):
                self.fixture.build(page)
                page.click('#trade-balance-offer')
                page.wait_for_timeout(30)
                self.assertTrue(page.get_by_role('button', name='Remove A from calculator', exact=True).is_disabled())
                page.locator('summary').filter(has_text='Strategy for advanced').click()
                page.select_option('#trade-strategy', 'REBUILD')
                page.get_by_role('button', name='Remove A from calculator', exact=True).click()
                self.add(page, 'sent', asset_id)
                edited = self.fixture.state(page)['currentProposal']
                self.respond(*pending[0])
                page.wait_for_timeout(50)
                self.no_old_feedback(page)
                self.assertEqual(self.fixture.state(page)['currentProposal'], edited)

    def test_error_and_empty_feedback_own_current_revision_and_clear_after_edit(self):
        for outcome in ('error', 'empty'):
            def respond(route, payload):
                route.fulfill(status=503 if outcome == 'error' else 200, json={'detail': {'message': 'Balancing unavailable'}} if outcome == 'error' else {'results': [], 'count': 0})
            with self.subTest(outcome=outcome), self.fixture.fixture.page(workspace=self.data, api=respond) as (page, _):
                self.fixture.build(page)
                original = self.fixture.state(page)['currentProposal']
                page.click('#trade-balance-offer')
                page.wait_for_function('document.querySelector("#trade-balance-offer").getAttribute("aria-busy") === "false"')
                self.assertIn('unavailable' if outcome == 'error' else 'No balancing', page.locator('#calculator-balance-status').inner_text())
                self.assertEqual(self.fixture.state(page)['currentProposal'], original)
                page.get_by_role('button', name='Remove A from calculator', exact=True).click()
                self.no_old_feedback(page)

    def test_reload_and_new_target_do_not_resurrect_obsolete_feedback(self):
        with self.fixture.fixture.page(workspace=self.data, api=self.respond) as (page, _):
            self.fixture.build(page)
            self.success(page)
            page.get_by_role('button', name='Preview adjustment', exact=True).click()
            page.get_by_role('button', name='Remove A from calculator', exact=True).click()
            edited = self.fixture.state(page)['currentProposal']
            page.reload()
            page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
            self.no_old_feedback(page)
            self.assertEqual(self.fixture.state(page)['currentProposal'], edited)
            self.fixture.fixture.ready(page, '/trades/trade-for?front_office=1&asset_id=player:y')
            self.fixture.fixture.ready(page, '/trades/calculator?front_office=1')
            self.no_old_feedback(page)
            self.assertEqual(self.fixture.state(page)['requiredIncomingAsset'], 'player:y')
            page.go_back()
            page.go_back()
            page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
            self.no_old_feedback(page)
