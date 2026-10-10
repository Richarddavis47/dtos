"""Responsive Chromium: actual authenticated cheaper API, preview and adoption."""
import copy
import unittest
from urllib.parse import urlsplit

from services import trade_intelligence as trade
from tests import test_make_it_cheaper_completeness as cheaper_fixtures
from tests import test_trade_scout_state_browser as scout_browser
from tests import test_trade_workspace_batch1 as account_fixtures


class CheaperRepairBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = cheaper_fixtures.CheaperRepairCompletenessTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.account = account_fixtures.AuthenticatedTradeBoundaryTests()
        self.account.setUp()
        self.addCleanup(self.account.doCleanups)
        self.account.data.clear()
        self.account.data.update(copy.deepcopy(self.fixture.data))
        response = self.account.client.get('/api/trades/workspace?front_office=1')
        self.assertEqual(response.status_code, 200)
        self.workspace = response.json()
        self.harness = scout_browser.ScoutWorkspaceStateBrowserTests()
        self.responses = []

    def proposal(self, page):
        key = 'dtos-trade-workspace:' + self.workspace['workspace_context']['binding']
        return page.evaluate('key => JSON.parse(sessionStorage.getItem(key)).currentProposal', key)

    def handler(self, initial_sent):
        original = trade.evaluate_trade_request(self.account.data,
            {**self.fixture.payload, 'assets_sent': initial_sent, 'workflow': 'shop'},
            projection_reader=self.fixture.fixture.reader)
        def api(route, payload):
            path = urlsplit(route.request.url).path
            if path.endswith('/generate'):
                return route.fulfill(json={'markets': [{'counterparty_roster_id': 2, 'returns': [original]}],
                                          'count': 1, 'results': [original]})
            response = self.account.client.post(path, json=payload, headers={'X-CSRF-Token': self.account.csrf})
            self.assertEqual(response.status_code, 200, response.text)
            self.responses.append(response.json())
            route.fulfill(json=response.json())
        return api

    def start_offer(self, page):
        self.harness.ready(page, '/trades/shop?asset_id=daniels')
        page.get_by_label('Your strategy', exact=True).select_option('WIN NOW')
        page.locator('#shop-refinements > summary').click()
        page.locator('#shop-protected').select_option(['bijan', '2027-R4-3'])
        page.click('#trade-find')
        self.harness.adopt(page)

    def cheaper(self, page):
        page.click('#trade-adjust')
        page.fill('#trade-instruction', 'make it cheaper')
        page.click('#trade-apply-adjust')

    def test_763_to_751_preview_keep_adopt_locks_diagnostics_and_reload_at_phone_widths(self):
        for width in (375, 390):
            with self.subTest(width=width), self.harness.page(width, workspace=self.workspace,
                    api=self.handler(['daniels', '2029-R3-1'])) as (page, requests):
                self.start_offer(page)
                original = self.proposal(page)
                self.cheaper(page)
                card = page.locator('.tw-offer').filter(has_text='Outgoing Market cost: 763 → 751 (12 lower).')
                card.wait_for()
                self.assertEqual(self.proposal(page), original)
                self.assertEqual(self.responses[-1]['search_evidence']['evaluated'], 2)
                card.get_by_role('button', name='Open editable offer:', exact=False).click()
                self.assertEqual(self.proposal(page), original)
                self.assertIn('Original: Jayden Daniels', page.locator('#trade-result').inner_text())
                page.get_by_role('button', name='Keep original', exact=True).click()
                self.assertEqual(self.proposal(page), original)
                page.locator('.tw-offer').filter(has_text='Outgoing Market cost: 763 → 751 (12 lower).').get_by_role(
                    'button', name='Open editable offer:', exact=False).click()
                page.get_by_role('button', name='Adopt alternative', exact=True).click()
                self.assertEqual(set(self.proposal(page)['sent']), {'daniels', '2027-R4-1'})
                page.reload()
                page.locator('#trade-target:not([hidden])').wait_for()
                self.assertEqual(set(self.proposal(page)['sent']), {'daniels', '2027-R4-1'})
                self.assertEqual(self.proposal(page)['received'], ['mcbride'])
                locks = page.locator('#shop-protected').evaluate('n => [...n.selectedOptions].map(o => o.value)')
                self.assertEqual(set(locks), {'bijan', '2027-R4-3'})
                assist = next(payload for path, payload in requests if path == 'assist')
                self.assertEqual(assist['origin_asset_id'], 'daniels')
                self.assertEqual(set(assist['protected_assets']), {'bijan', '2027-R4-3'})
                self.assertLessEqual(page.locator('body').evaluate('n => n.scrollWidth'), width)

    def test_no_cheaper_explanation_uses_actual_funnel_and_preserves_offer(self):
        with self.harness.page(375, workspace=self.workspace, api=self.handler(['daniels'])) as (page, requests):
            self.start_offer(page)
            original = self.proposal(page)
            self.cheaper(page)
            page.get_by_text('No lower-cost construction', exact=False).wait_for()
            self.assertIn('Shop anchor', page.locator('#trade-result').inner_text())
            self.assertEqual(self.proposal(page), original)
            page.get_by_text('Technical search details', exact=True).click()
            self.assertIn('prune_reason_counts', page.locator('#trade-result').inner_text())
            self.assertIn('CONSTRUCTIONS_EXHAUSTED', page.locator('#trade-result').inner_text())
            self.assertEqual(self.responses[-1]['count'], 0)
            self.assertEqual(self.responses[-1]['search_evidence']['full_evaluations'], 0)
            self.assertEqual(requests[-1][1]['origin_asset_id'], 'daniels')
            self.assertLessEqual(page.locator('body').evaluate('n => n.scrollWidth'), 375)
