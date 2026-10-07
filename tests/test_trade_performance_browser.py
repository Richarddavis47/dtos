"""Phone loading and revision guard while a real browser request is pending."""
import unittest
from tests import test_trade_scout_state_browser as scout


class TradePerformanceBrowserTests(unittest.TestCase):
    def test_pending_search_progress_and_old_strategy_result_ignored(self):
        for width in (375, 390):
            fixture = scout.ScoutWorkspaceStateBrowserTests()
            pending = []
            def hold(route, payload):
                pending.append((route, payload))
            with self.subTest(width=width), fixture.page(width, api=hold) as (page, _):
                fixture.ready(page, '/trades/recommended')
                page.click('#trade-find')
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                self.assertIn('Searching supported bilateral options', page.locator('#trade-result').inner_text())
                self.assertTrue(page.locator('#trade-find').is_disabled())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                page.locator('#trade-strategy').select_option('WIN NOW')
                old_offer = fixture.offer(['player:a'], ['player:x'])
                pending[0][0].fulfill(json={'results': [old_offer], 'count': 1})
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="false"')
                self.assertTrue(page.locator('#trade-result').is_hidden())
                page.click('#trade-find')
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                self.assertEqual(pending[1][1]['strategy'], 'WIN NOW')
                pending[1][0].fulfill(json={'results': [old_offer], 'count': 1})
                page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
