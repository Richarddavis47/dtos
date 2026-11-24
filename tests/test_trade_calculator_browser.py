"""Responsive Chromium calculator editing, preview/adoption and navigation."""
import copy
import os
from pathlib import Path
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
        offered['balance_adjustment'] = {'change': 'ADD_PICK', 'market_generation': 'canonical-fixture', 'original': {'sent': {'total': 400}, 'received': {'total': 600}, 'absolute_gap': 200},
            'suggested': {'sent': {'total': 600}, 'received': {'total': 600}, 'absolute_gap': 0},
            'reason': 'Narrower owned exact-pick gap.', 'meaning': 'Market adjustment, not a guaranteed better trade.', 'strategic_caution': True}
        if route.request.url.endswith('/evaluate'):
            # The fixture proves a prepared Market adjustment, not a bilateral
            # lineup/counterparty case. Completed does not mean fully supported.
            from services.trade_decision import decision_context, assessment_state
            from services.trade_explanation import render_trade_explanation
            evaluation = {**offered['evaluation'], 'recommendation': None,
                'generated_trade_eligible': False, 'recommendation_availability': 'unavailable',
                'provenance': {'evaluation_id': 'adjustment-fixture', 'evaluator': 'controlled-market-adjustment',
                    'inputs': {'league_id': 'fixture-league'}},
                'major_drawback': 'Lineup and counterparty evidence are missing from this adjustment fixture.'}
            evaluation['decision_context'] = decision_context(evaluation)
            evaluation['assessment_state'] = assessment_state(evaluation)
            evaluation['explanation_html'] = render_trade_explanation(evaluation, league_id='fixture-league')
            return route.fulfill(json={'evaluation': evaluation, 'assessment_source_identity': {'fixture': 'canonical-fixture'}})
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
            gauge = page.locator('#trade-balance > .tw-valuation-gauge')
            self.assertEqual(gauge.get_attribute('data-balance'), 'even')
            self.assertEqual(gauge.locator('.tw-gauge-pointer').evaluate('e=>e.style.left'), '50%')
        data['teams'][0]['assets'][1]['trade_value'] = None
        with self.fixture.page(workspace=data) as (page, requests):
            self.build(page)
            page.click('[data-side=sent]')
            page.locator('#trade-sent-board button[data-asset-id="player:b"]').click()
            self.assertIn('Cannot determine reliably', page.locator('#calculator-verdict').inner_text())
            self.assertIn('Partial · known subtotal 0.1', page.locator('#trade-balance').inner_text())
            gauge = page.locator('#trade-balance > .tw-valuation-gauge')
            self.assertEqual(gauge.get_attribute('data-balance'), 'incomplete')
            self.assertEqual(gauge.locator('.tw-gauge-pointer').count(), 0)
            self.assertTrue(page.locator('#trade-balance-offer').is_disabled())
            self.assertEqual(requests, [])

    def test_shared_value_gauge_and_selected_week_review_on_phone_and_desktop(self):
        for width, mode, expected in ((320, 'neutral', 'receive'), (390, 'custom', 'give'), (1280, 'neutral', 'receive')):
            data = copy.deepcopy(self.data)
            owned = data['teams'][0]['assets']
            owned.extend([
                {**owned[0], 'asset_id': 'player:c', 'label': 'C', 'trade_value': 400},
                {**owned[0], 'asset_id': 'player:missing', 'label': 'Missing value', 'trade_value': None},
            ])
            owned.reverse()
            data['personalization'] = {
                'mode': mode, 'revision': 1, 'available': True, 'method_label': 'Absolute Slot',
                'values': {'player:a': 800, 'player:x': 200},
            }
            def values(sent, received):
                return {'availability': 'full', 'sent': {'total': sent}, 'received': {'total': received}}
            def evaluate(route, payload):
                self.assertEqual(payload['assets_sent'], ['player:a'])
                self.assertEqual(payload['assets_received'], ['player:x'])
                self.assertEqual(payload['valuation_mode'], mode)
                evaluation = {
                    'recommendation': 'REJECT', 'personalization': {'mode': mode, 'method': 'personal-current-market-slot-curve-v1'},
                    'market_evidence': values(400, 600), 'personal_value_evidence': values(800, 200),
                    'assessment_state': {'state': 'fresh_complete', 'recommendation_supported': True},
                    'decision_context': {
                        'lineup_comparisons': {'current_week': {'weeks': [13], 'delta': 0, 'state': 'supported'}},
                        'partner_lineup_comparisons': {'current_week': {'weeks': [13], 'delta': -2, 'state': 'provisional'}},
                        'remaining_lineup_points': {'selected_week': 13, 'sides': {
                            'active': {'weeks': [14, 15], 'compared': [14, 15], 'subtotal': 4, 'calendar_complete': True},
                            'partner': {'weeks': [14, 15], 'compared': [14], 'subtotal': -3, 'calendar_complete': True},
                        }},
                    },
                }
                route.fulfill(json={'evaluation': evaluation, 'assessment_source_identity': {'fixture': True}})

            with self.subTest(width=width), self.fixture.page(width, workspace=data, api=evaluate) as (page, requests):
                self.fixture.ready(page, '/trades/calculator?front_office=1')
                page.select_option('#trade-partner', '2')
                picker = page.locator('#trade-sent-board')
                self.assertEqual(picker.locator('[data-picker-group]').all_text_contents(), ['WR', 'Draft picks'])
                self.assertEqual(picker.locator('button[data-asset-id]').evaluate_all(
                    'els=>els.map(e=>e.dataset.assetId)'), ['player:a', 'player:c', 'player:b', 'player:d', 'player:missing',
                                                          'pick:2028:1:3', 'pick:2028:2:3'])
                for side, asset in (('sent', 'player:a'), ('received', 'player:x')):
                    page.locator(f'[data-add-side="{side}"]').click()
                    self.assertEqual(page.locator(f'#trade-{side}-board input').evaluate('e=>e===document.activeElement'), True)
                    page.locator(f'#trade-{side}-board button[data-asset-id="{asset}"]').click()
                gauge = page.locator('#trade-balance > .tw-valuation-gauge')
                difference = '−600 Custom points' if mode == 'custom' else '+200 Market points'
                self.assertEqual(gauge.get_attribute('data-balance'), expected)
                self.assertIn(difference, gauge.inner_text())
                offset = float(gauge.locator('.tw-gauge-pointer').evaluate('e=>parseFloat(e.style.left)'))
                self.assertTrue(offset < 38 if expected == 'give' else offset > 62)
                target = os.environ.get('DTOS_TRADE_REDESIGN_EVIDENCE')
                if target:
                    page.locator('.tw-calculator').screenshot(path=str(Path(target, f'build-{width}.png')))
                self.assertEqual(requests, [])
                original = self.state(page)['currentProposal']
                page.locator('#trade-run').click()
                result = page.locator('#trade-result')
                result.locator('.tw-projected-points > summary').wait_for()
                self.assertIn('REJECT', result.inner_text())
                if width == 320:
                    packages = result.locator('.tw-review-packages > section')
                    sent, received = (packages.nth(index).bounding_box() for index in range(2))
                    self.assertGreaterEqual(received['y'], sent['y'] + sent['height'])
                    self.assertAlmostEqual(received['width'], sent['width'], delta=1)
                self.assertIn(difference, result.locator('.tw-valuation-gauge').inner_text())
                result.locator('.tw-projected-points > summary').press('Enter')
                table = result.locator('.tw-projected-table')
                self.assertIn('0.00', table.inner_text())
                self.assertIn('Partial · weeks 14', table.inner_text())
                self.assertIn('Missing weeks 15', table.inner_text())
                self.assertIn('Weeks 14, 15', table.inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                if target:
                    result.locator('.tw-evaluation-overview').screenshot(path=str(Path(target, f'evaluated-{width}.png')))
                page.locator('#trade-edit').click()
                self.assertEqual(self.state(page)['currentProposal'], original)
                self.assertEqual([path for path, _ in requests], ['evaluate'])

    def test_preview_keep_adopt_reload_exact_pick_and_advanced_preserve_package(self):
        with self.fixture.page(workspace=self.data, api=self.balancing) as (page, requests):
            self.build(page)
            original = self.state(page)['currentProposal']
            page.click('#trade-balance-offer')
            self.assertIn('Current Market: You send 600 / You receive 600', page.locator('#trade-result .tw-offer-summary').inner_text())
            page.get_by_role('button', name='Review trade', exact=True).click()
            self.assertEqual(self.state(page)['currentProposal'], original)
            comparison = page.get_by_text('Compare with your current draft', exact=True)
            self.assertIsNone(comparison.locator('..').get_attribute('open'))
            self.assertIn('Current Market: You send 600 / You receive 600', page.locator('.tw-balance-offer').inner_text())
            comparison.click()
            self.assertIn('Original Market: 400 sent / 600 received · Gap 200', page.locator('#trade-result').inner_text())
            self.assertIn('Major drawback', page.locator('#trade-result').inner_text())
            page.get_by_role('button', name='Back to offers', exact=True).click()
            self.assertEqual(self.state(page)['currentProposal'], original)
            page.get_by_role('button', name='Review trade', exact=True).click()
            page.reload()
            page.get_by_role('button', name='Use this offer in my draft', exact=True).wait_for()
            comparison = page.get_by_text('Compare with your current draft', exact=True)
            self.assertIsNone(comparison.locator('..').get_attribute('open'))
            comparison.click()
            self.assertIn('Suggested Market: 600 sent / 600 received · Gap 0', page.locator('#trade-result').inner_text())
            page.get_by_role('button', name='Use this offer in my draft', exact=True).click()
            adopted = self.state(page)['currentProposal']
            self.assertEqual(adopted['sent'], ['player:a', 'pick:2028:1:3'])
            page.reload()
            page.locator('#calculator-verdict').get_by_text('Approximately balanced', exact=False).wait_for()
            self.assertEqual(self.state(page)['currentProposal'], adopted)
            page.click('#trade-run')
            page.locator('#trade-result .dtos-explanation > p').filter(has_text='Recommendation unavailable').wait_for()
            self.assertNotIn('WORTH PURSUING', page.locator('#trade-result .dtos-explanation > p').first.inner_text())
            self.assertEqual(page.locator('#trade-result').get_attribute('data-assessment-state'), 'fresh_incomplete')
            self.assertEqual(self.state(page)['currentProposal'], adopted)
            self.assertEqual(requests[-1][0], 'evaluate')
            self.assertEqual(requests[-1][1]['assets_sent'], adopted['sent'])
            self.assertEqual(requests[-1][1]['workflow'], 'create')

    def test_strategy_changes_arithmetic_identical_and_no_expensive_request(self):
        with self.fixture.page(workspace=self.data) as (page, requests):
            self.build(page)
            initial = page.locator('#trade-balance').inner_text()
            self.assertTrue(page.locator('#trade-strategy').is_visible())
            page.locator('#trade-strategy').focus()
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
            page.wait_for_function('document.querySelector("#trade-balance-offer").getAttribute("aria-busy") === "true"')
            page.select_option('#trade-partner', '')
            pending[0].fulfill(json={'results': [self.fixture.offer(['player:a'], ['player:x'])]})
            page.wait_for_function('document.querySelector("#trade-balance-offer").getAttribute("aria-busy") === "false"')
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

    def test_price_refresh_invalidates_only_restored_preview_not_current_offer_or_locks(self):
        with self.fixture.page(workspace=self.data, api=self.balancing) as (page, _):
            self.build(page)
            page.click('#calculator-protect')
            page.select_option('#trade-constraint-asset', 'player:b')
            page.click('#calculator-lock')
            original = self.state(page)['currentProposal']
            page.click('#trade-balance-offer')
            page.get_by_role('button', name='Review trade', exact=True).click()
            fresh = copy.deepcopy(self.data)
            fresh['calculator_generation'] = 'new-generation'
            fresh['teams'][0]['assets'][0]['trade_value'] = 450
            page.route('**/api/trades/workspace?*', lambda route: route.fulfill(json=fresh))
            page.reload()
            page.locator('#trade-result').get_by_text('Market evidence updated.', exact=False).wait_for()
            self.assertIn('Value gap: 150', page.locator('#trade-balance').inner_text())
            self.assertIsNone(self.state(page)['previewProposal'])
            self.assertEqual(self.state(page)['currentProposal'], original)
            self.assertEqual(self.state(page)['protectedAssets'], ['player:b'])
