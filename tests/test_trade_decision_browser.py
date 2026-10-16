"""Released shared client behavior in Chromium; actual HTTP is tested separately."""

import json
import unittest

from tests import test_trade_scout_state_browser as scout


class TradeDecisionBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = scout.ScoutWorkspaceStateBrowserTests()

    def home(self, page):
        body = (
            '<div id="trade-home-boundary" data-workspace-context=\''
            + json.dumps(self.fixture.workspace()["workspace_context"])
            + '\'></div><a href="/trades/create?front_office=1">Build trade</a><script src="/static/js/trade_workspace.js" defer></script>'
        )
        page.context.route(
            "https://dtos.test/",
            lambda route: route.fulfill(content_type="text/html", body=body),
        )

    def populated(self, page):
        self.fixture.ready(page, "/trades/create?front_office=1")
        page.select_option("#trade-partner", "2")
        page.select_option("#trade-strategy", "RETOOL")
        page.locator('#trade-sent-board button[data-asset-id="player:a"]').click()
        return self.fixture.proposal(page)

    def test_internal_calculator_reload_and_supporting_return_preserve_work(self):
        with self.fixture.page() as (page, _):
            original = self.populated(page)
            self.fixture.ready(page, "/trades/calculator?front_office=1")
            self.assertEqual(self.fixture.proposal(page), original)
            for path in ("/market", "/players/a"):
                page.route(
                    "https://dtos.test" + path,
                    lambda route: route.fulfill(
                        content_type="text/html",
                        body='<a href="/trades/calculator?front_office=1">Return to Trade</a>',
                    ),
                )
                page.goto("https://dtos.test" + path)
                page.get_by_role("link", name="Return to Trade").click()
                page.locator("#trade-context").get_by_text(
                    "Active league", exact=False
                ).wait_for()
                self.assertEqual(self.fixture.proposal(page), original)
            page.reload()
            page.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(self.fixture.proposal(page), original)

    def test_home_back_forward_and_other_league_draft_cannot_resurrect_old_package(
        self,
    ):
        with self.fixture.page() as (page, _):
            self.home(page)
            self.populated(page)
            other = {
                "currentProposal": {"sent": ["foreign"], "received": [], "partner": 4},
                "strategy": "REBUILD",
            }
            page.evaluate(
                '(v)=>sessionStorage.setItem("dtos-trade-workspace:other-league",JSON.stringify(v))',
                other,
            )
            page.goto("https://dtos.test/")
            page.go_back()
            page.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                self.fixture.proposal(page), {"sent": [], "received": [], "partner": 0}
            )
            self.assertEqual(page.locator("#trade-strategy").input_value(), "RETOOL")
            page.go_forward()
            page.get_by_role("link", name="Build trade").wait_for()
            page.get_by_role("link", name="Build trade").click()
            page.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                self.fixture.proposal(page), {"sent": [], "received": [], "partner": 0}
            )
            self.assertEqual(
                page.evaluate(
                    'JSON.parse(sessionStorage.getItem("dtos-trade-workspace:other-league"))'
                ),
                other,
            )

    def test_home_in_separate_opener_tab_does_not_clear_active_tab(self):
        with self.fixture.page() as (page, _):
            self.home(page)
            original = self.populated(page)
            with page.expect_popup() as opened:
                page.evaluate('window.open("/", "_blank")')
            second = opened.value
            second.get_by_role("link", name="Build trade").wait_for()
            second.get_by_role("link", name="Build trade").click()
            second.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                self.fixture.proposal(second),
                {"sent": [], "received": [], "partner": 0},
            )
            page.bring_to_front()
            self.assertEqual(self.fixture.proposal(page), original)
            second.close()

    def test_opener_cloned_session_storage_does_not_inherit_editable_package(self):
        with self.fixture.page() as (page, _):
            original = self.populated(page)
            with page.expect_popup() as opened:
                page.evaluate('window.open("/trades/create?front_office=1", "_blank")')
            second = opened.value
            second.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                self.fixture.proposal(second),
                {"sent": [], "received": [], "partner": 0},
            )
            self.assertEqual(second.locator("#trade-strategy").input_value(), "RETOOL")
            self.assertEqual(self.fixture.proposal(page), original)
            second.close()

    def test_shop_reload_requires_visible_action_and_error_empty_states_are_honest(
        self,
    ):
        calls = []

        def answer(route, payload):
            calls.append(payload)
            if len(calls) == 1:
                return route.fulfill(
                    json={
                        "results": [],
                        "markets": [],
                        "count": 0,
                        "quiet_state": "Projection coverage is incomplete.",
                    }
                )
            return route.fulfill(
                status=503, json={"detail": "Search unavailable; try again."}
            )

        with self.fixture.page(320, api=answer) as (page, _):
            self.fixture.ready(page, "/trades/shop?asset_id=player:a")
            page.locator(
                "#recommendation-status[data-search-state=complete]"
            ).wait_for()
            self.assertIn(
                "No credible", page.locator("#recommendation-status").inner_text()
            )
            self.assertIn(
                "Projection coverage is incomplete",
                page.locator("#trade-result").inner_text(),
            )
            self.assertEqual(len(calls), 1)
            page.reload()
            page.locator(
                "#recommendation-status[data-search-state=not_started]"
            ).wait_for()
            self.assertEqual(len(calls), 1)
            self.assertTrue(page.locator("#trade-find").is_enabled())
            self.assertIn("Find Shop returns", page.locator("#trade-find").inner_text())
            page.click("#trade-find")
            page.locator("#recommendation-status[data-search-state=error]").wait_for()
            self.assertTrue(page.locator("#trade-find").is_enabled())
            self.assertFalse(page.locator("#trade-result").is_hidden())
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth"), 320
            )

    def test_shop_search_action_precedes_manual_asset_inventory(self):
        with self.fixture.page(390) as (page, _):
            self.fixture.ready(page, "/trades/shop?asset_id=player:a")
            page.locator("#trade-result .tw-offer").first.wait_for()
            self.assertTrue(
                page.locator("#trade-find").evaluate(
                    '(e)=>Boolean(e.compareDocumentPosition(document.querySelector("#trade-board")) & Node.DOCUMENT_POSITION_FOLLOWING)'
                )
            )
            self.assertTrue(
                page.locator("#recommendation-status").evaluate(
                    '(e)=>Boolean(e.compareDocumentPosition(document.querySelector("#trade-board")) & Node.DOCUMENT_POSITION_FOLLOWING)'
                )
            )

    def test_home_boundary_invalidates_proposal_but_not_strategy(self):
        with self.fixture.page(390) as (page, _):
            home = (
                '<div id="trade-home-boundary" data-workspace-context=\''
                + json.dumps(self.fixture.workspace()["workspace_context"])
                + '\'></div><a href="/trades/create?front_office=1">Build trade</a><script src="/static/js/trade_workspace.js" defer></script>'
            )
            page.route(
                "https://dtos.test/",
                lambda route: route.fulfill(content_type="text/html", body=home),
            )
            self.fixture.ready(page, "/trades/create?front_office=1")
            page.select_option("#trade-strategy", "REBUILD")
            page.select_option("#trade-partner", "2")
            page.locator('#trade-sent-board button[data-asset-id="player:a"]').click()
            page.goto("https://dtos.test/")
            page.get_by_role("link", name="Build trade").click()
            page.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                self.fixture.proposal(page), {"sent": [], "received": [], "partner": 0}
            )
            self.assertEqual(page.locator("#trade-strategy").input_value(), "REBUILD")
