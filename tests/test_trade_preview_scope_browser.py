"""Rendered workspace contracts. Controlled API evidence, responsive Chromium.

Numerical intelligence is covered separately by the actual authenticated engine
journeys; these fixtures isolate persistence, freshness and asynchronous UI state.
"""
import json
import unittest

from tests import test_trade_scout_state_browser as scout


class PreviewScopeBrowserTests(unittest.TestCase):
    def setUp(self):
        self.harness = scout.ScoutWorkspaceStateBrowserTests()
        self.workspace = self.harness.workspace()
        self.workspace['calculator_generation'] = 'market-one'
        own = self.workspace['teams'][0]['assets']
        own[0].update(label='Omarion Hampton', position='RB', trade_value=492)
        own[3].update(asset_id='2028-R4-1', original_roster_id=1, label='2028 Round 4 — Original Chase Bank', round=4, trade_value=180)
        self.workspace['teams'][1]['assets'][0].update(label='Joe Burrow', position='QB', trade_value=658)
        self.row = self.harness.offer(['player:a', '2028-R4-1'], ['player:x'])
        self.row.update(exploration=True, search_result_type='SUPPORTED COSTLY ALTERNATIVE', workflow='trade_for')
        self.row['evaluation'].update(recommendation='NOT WORTH IT', major_drawback='Sacrifices rebuild capital for a costly veteran.',
            major_limitations=['LIMITED_MANAGER_HISTORY'], major_risks=['REBUILD_CAPITAL_COST'],
            dimensions={'confidence': {'assessment': 'MEDIUM', 'explanation': 'Complete prices; limited manager history.'}},
            provenance={'evaluation_id': 'fixture-evaluation', 'inputs': {'market_generation': 'market-one'}})

    @staticmethod
    def click(page, selector):
        control = page.locator(selector)
        control.scroll_into_view_if_needed()
        assert control.evaluate('e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
        control.click()

    def respond(self, route, payload):
        if route.request.url.endswith('/evaluate'):
            return route.fulfill(json={'evaluation': self.row['evaluation']})
        route.fulfill(json={'results': [self.row], 'count': 1})

    def preview(self, page):
        self.harness.ready(page, '/trades/trade-for?asset_id=player:x')
        page.select_option('#trade-strategy', 'REBUILD')
        self.click(page, '#trade-find')
        self.click(page, '.tw-offer button.tw-next-action')

    def test_exploratory_reload_adopt_balance_and_keep_at_phone_sizes(self):
        for width, height in ((320, 483), (320, 568), (375, 483), (375, 667), (390, 483), (390, 844), (1280, 900)):
            pending = []

            def api(route, payload):
                if route.request.url.endswith('/balance'):
                    pending.append(route)
                else:
                    self.respond(route, payload)

            with self.subTest(width=width, height=height), self.harness.page(width, workspace=self.workspace, api=api) as (page, requests):
                page.set_viewport_size({'width': width, 'height': height})
                self.preview(page)
                original = self.harness.proposal(page)
                page.reload()
                page.get_by_role('button', name='Adopt alternative', exact=True).wait_for()
                preview = page.locator('#trade-result').inner_text()
                self.assertIn('Exploratory only', preview)
                self.assertIn(self.row['evaluation']['major_drawback'], preview)
                self.assertIn('not revalidated', preview.lower())
                self.assertIn('MEDIUM', preview)
                self.assertEqual(self.harness.proposal(page), original)
                self.click(page, '#trade-result button:text-is("Adopt alternative")')
                self.assertEqual(self.harness.proposal(page)['sent'], self.row['proposal']['assets_sent'])
                self.assertEqual(page.input_value('#trade-strategy'), 'REBUILD')
                assessment = page.locator('#trade-result').inner_text()
                self.assertIn('NOT WORTH IT', assessment)
                self.assertIn('Exploratory only', assessment)
                self.assertIn(self.row['evaluation']['major_drawback'], assessment)
                self.click(page, '#trade-balance-offer')
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                self.assertIn(self.row['evaluation']['major_drawback'], page.locator('#trade-evaluation-retained').inner_text())
                self.assertIn('Finding balancing', page.locator('#calculator-balance-status').inner_text())
                pending.pop().fulfill(json={'results': [self.row], 'count': 1})
                page.wait_for_function('!document.querySelector("#trade-balance-offer").disabled')
                self.assertIn('NOT WORTH IT', page.locator('#trade-evaluation-retained').inner_text())
                self.click(page, '#trade-result .tw-offer button.tw-next-action')
                self.click(page, '#trade-result button:text-is("Keep original")')
                self.assertIn(self.row['evaluation']['major_drawback'], page.locator('#trade-evaluation-retained').inner_text())
                self.assertEqual(self.harness.proposal(page)['sent'], self.row['proposal']['assets_sent'])
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
                page.locator('#trade-balance-offer').focus()
                self.assertEqual(page.evaluate('document.activeElement.id'), 'trade-balance-offer')
                self.assertNotIn('explanation_html', page.evaluate("sessionStorage.getItem('dtos-trade-workspace:scout-session')"))

    def test_recommended_restoration_source_strategy_and_balance_error(self):
        self.row['exploration'] = False
        self.row['evaluation']['recommendation'] = 'WORTH PURSUING'
        with self.harness.page(workspace=self.workspace, api=self.respond) as (page, requests):
            self.preview(page)
            self.workspace['calculator_generation'] = 'market-two'
            page.reload()
            page.get_by_role('button', name='Adopt alternative', exact=True).wait_for()
            self.assertIn('Market', page.locator('#trade-result').inner_text())
            self.assertIn('not revalidated', page.locator('#trade-result').inner_text().lower())
            self.click(page, '#trade-result button:text-is("Adopt alternative")')
            page.route('**/api/trades/balance', lambda r: r.fulfill(status=503, json={'detail': {'message': 'Controlled failure'}}))
            self.click(page, '#trade-balance-offer')
            page.locator('#calculator-balance-status').get_by_text('Controlled failure').wait_for()
            self.assertIn('WORTH PURSUING', page.locator('#trade-evaluation-retained').inner_text())
            page.select_option('#trade-strategy', 'WIN NOW')
            self.assertEqual(page.locator('#trade-evaluation-retained').count(), 0)
            self.assertFalse(page.locator('#trade-result').is_visible())

    def test_new_shop_asset_resets_scope_same_asset_reload_preserves_it(self):
        def empty(route, payload):
            route.fulfill(json={'results': [], 'count': 0, 'quiet_state': 'No supported fixture offers.'})

        with self.harness.page(api=empty, workspace=self.workspace) as (page, requests):
            self.harness.ready(page, '/trades/shop?asset_id=player:a')
            page.locator('#shop-refinements > summary').click()
            page.select_option('#trade-partner', '2')
            page.select_option('#shop-preference', 'draft_capital')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            count = len(requests)
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(page.input_value('#trade-partner'), '2')
            self.assertEqual(page.input_value('#shop-preference'), 'draft_capital')
            self.assertEqual(len(requests), count)
            self.click(page, '#trade-build-own')
            page.wait_for_url('**/trades/create?*')
            self.harness.ready(page, '/trades/shop?asset_id=2028-R4-1')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            self.assertEqual(page.input_value('#trade-partner'), '')
            self.assertEqual(page.input_value('#shop-preference'), 'best_overall')
            self.assertEqual(requests[-1][1]['partner_roster_id'], 0)
            self.assertEqual(requests[-1][1]['asset_id'], '2028-R4-1')
            self.assertEqual(requests[-1][1]['shop_preference'], 'best_overall')
            count = len(requests)
            page.go_back()
            page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
            page.go_back()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(page.input_value('#trade-partner'), '2')
            self.assertEqual(page.input_value('#shop-preference'), 'draft_capital')
            self.assertEqual(len(requests), count)

    def test_explicit_shop_choices_win_but_reload_does_not_reapply_old_url(self):
        def empty(route, payload):
            route.fulfill(json={'results': [], 'count': 0})

        with self.harness.page(api=empty, workspace=self.workspace) as (page, requests):
            self.harness.ready(page, '/trades/shop?asset_id=player:a&partner_roster_id=2&shop_preference=draft_capital')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            self.assertEqual(page.input_value('#trade-partner'), '2')
            self.assertEqual(page.input_value('#shop-preference'), 'draft_capital')
            page.select_option('#trade-partner', '')
            page.locator('#shop-refinements > summary').click()
            page.select_option('#shop-preference', 'win_now')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            count = len(requests)
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(page.input_value('#trade-partner'), '')
            self.assertEqual(page.input_value('#shop-preference'), 'win_now')
            self.assertEqual(len(requests), count)

    def test_balance_network_timeout_and_stale_source_keep_completed_assessment(self):
        for failure in ('network', 'timeout', 'source', 'success_source'):
            pending = []

            def api(route, payload):
                if route.request.url.endswith('/balance'):
                    if failure == 'network':
                        route.abort('failed')
                    elif failure == 'source':
                        route.fulfill(status=422, json={'detail': {'code': 'canonical_evidence_changed'}})
                    elif failure == 'success_source':
                        row = json.loads(json.dumps(self.row))
                        row['evaluation']['provenance']['inputs']['market_generation'] = 'market-two'
                        route.fulfill(json={'results': [row], 'count': 1})
                    else:
                        pending.append(route)
                else:
                    self.respond(route, payload)

            with self.subTest(failure=failure), self.harness.page(workspace=self.workspace, api=api) as (page, requests):
                self.preview(page)
                self.click(page, '#trade-result button:text-is("Adopt alternative")')
                if failure == 'timeout':
                    page.clock.install()
                self.click(page, '#trade-balance-offer')
                if failure == 'timeout':
                    page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                    page.clock.fast_forward(45001)
                    pending.pop().fulfill(json={'results': [self.row], 'count': 1})
                page.wait_for_function('!document.querySelector("#trade-balance-offer").disabled')
                self.assertIn(self.row['evaluation']['major_drawback'], page.locator('#trade-evaluation-retained').inner_text())
                feedback = page.locator('#calculator-balance-status').inner_text()
                self.assertIn({'network': 'could not connect', 'timeout': 'timed out', 'source': 'evidence refreshed', 'success_source': 'Balancing options ready'}[failure].lower(), feedback.lower())
                if failure in ('source', 'success_source'):
                    self.assertIn('not revalidated', page.locator('#trade-evaluation-retained').inner_text().lower())

    def test_changed_ownership_blocks_restored_adoption(self):
        with self.harness.page(workspace=self.workspace, api=self.respond) as (page, requests):
            self.preview(page)
            self.workspace['teams'][0]['assets'] = [a for a in self.workspace['teams'][0]['assets'] if a['asset_id'] != 'player:a']
            self.workspace['workspace_context']['ownership_generation'] = 'ownership-two'
            page.reload()
            page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
            self.assertIn('Ownership changed', page.locator('#trade-result').inner_text())
            self.assertEqual(self.harness.proposal(page)['sent'], [])

    def test_same_shop_asset_resume_and_history_keep_intent_without_extra_search(self):
        def empty(route, payload):
            route.fulfill(json={'results': [], 'count': 0})

        with self.harness.page(workspace=self.workspace, api=empty) as (page, requests):
            self.harness.ready(page, '/trades/shop?asset_id=player:a')
            page.locator('#shop-refinements > summary').click()
            page.select_option('#shop-preference', 'draft_capital')
            page.select_option('#trade-partner', '2')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            count = len(requests)
            self.harness.ready(page, '/trades/shop?asset_id=player:a')
            self.assertEqual(page.input_value('#shop-preference'), 'draft_capital')
            self.assertEqual(page.input_value('#trade-partner'), '2')
            self.assertEqual(len(requests), count)

            self.harness.ready(page, '/trades/shop?asset_id=2028-R4-1')
            self.assertEqual(page.input_value('#trade-partner'), '')
            self.assertEqual(page.input_value('#shop-preference'), 'best_overall')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            count = len(requests)
            page.go_back()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(page.input_value('#trade-partner'), '2')
            self.assertEqual(page.input_value('#shop-preference'), 'draft_capital')
            self.assertEqual(len(requests), count)
            page.go_forward()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(page.input_value('#trade-partner'), '')
            self.assertEqual(len(requests), count)

    def test_cached_page_return_keeps_shop_anchor_scope_and_preview_context(self):
        with self.harness.page(workspace=self.workspace, api=self.respond) as (page, requests):
            self.preview(page)
            page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted:true})); dispatchEvent(new PageTransitionEvent("pageshow", {persisted:true}))')
            self.assertIn('Exploratory only', page.locator('#trade-result').inner_text())
            self.assertIn('not revalidated', page.locator('#trade-result').inner_text().lower())
            self.assertIn(self.row['evaluation']['major_drawback'], page.locator('#trade-result').inner_text())
            self.harness.ready(page, '/trades/shop?asset_id=player:a')
            page.locator('#shop-refinements > summary').click()
            page.select_option('#shop-preference', 'draft_capital')
            page.select_option('#trade-partner', '2')
            page.wait_for_function('!document.querySelector("#trade-find").disabled')
            count = len(requests)
            # Interception disables actual BF-cache. Abort a real navigation
            # without discarding this document, then exercise its native
            # persisted pagehide/pageshow handlers on the rendered workspace.
            page.route('**/trades/create?*', lambda route: route.abort('aborted'))
            with page.expect_request('**/trades/create?*'):
                page.locator('#trade-build-own').click(no_wait_after=True)
            page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted:true})); dispatchEvent(new PageTransitionEvent("pageshow", {persisted:true}))')
            self.assertEqual(self.harness.proposal(page)['sent'], ['player:a'])
            self.assertEqual(page.input_value('#trade-partner'), '2')
            self.assertEqual(page.input_value('#shop-preference'), 'draft_capital')
            self.assertEqual(len(requests), count)



if __name__ == '__main__':
    unittest.main()
