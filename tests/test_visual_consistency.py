"""Prepared authenticated route journeys for the shared presentation."""
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest

from playwright.sync_api import expect, sync_playwright

from tests.test_contextual_back import ContextualBackTests
from tools.validation.browser_runtime import launch_chromium


class VisualConsistencyTests(unittest.TestCase):
    def test_market_return_and_transactions_controls_at_three_widths(self):
        helper = ContextualBackTests()
        fixture = helper.fixture()
        self.addCleanup(helper.doCleanups)
        output = os.environ.get("DTOS_VISUAL_CONSISTENCY_EVIDENCE")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            browser = launch_chromium(playwright, headless=True)
            try:
                for width, height in ((320, 432), (390, 844), (1280, 900)):
                    with self.subTest(width=width):
                        page, requests, _, _, errors = helper.page(browser, fixture, width, height)
                        try:
                            self.exercise(page, helper.origin, output, width)
                            self.assertFalse(errors, errors)
                            self.assertFalse(any(method == "POST" for method, _, _ in requests), requests)
                        finally:
                            page.close()
            finally:
                browser.close()

    def exercise(self, page, origin, output, width):
        def capture(name):
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
            if output:
                page.screenshot(path=str(Path(output, f"{name}-{width}.png")), full_page=True)

        status = page.goto(origin + "/market?position=QB&sort=value&direction=desc")
        self.assertEqual(status.status, 200)
        switcher = page.locator(".compact-top .account-context > summary")
        expect(switcher).to_be_visible()
        self.assertGreaterEqual(switcher.bounding_box()["height"], 44)
        first = page.locator(".market-row").first
        first.click()
        page.wait_for_url("**/market?*selected=*")
        expanded_url = urlsplit(page.url).query
        capture("market")
        link = page.locator("#market-row-detail a[href^='/players/']").first
        link.click()
        page.wait_for_url("**/players/*")
        expect(page.get_by_role("region", name="Player details")).to_be_visible()
        expect(page.locator("#player-weekly-projections")).to_be_visible()
        self.assertEqual(page.locator("a.back:visible").count(), 0)
        capture("player")
        page.locator("#dtos-back").press("Enter")
        page.wait_for_url("**/market?*selected=*")
        self.assertEqual(urlsplit(page.url).query, expanded_url)
        expect(page.locator(".market-row[aria-expanded='true']")).to_be_visible()

        page.goto(origin + "/transactions?scope=all_history&type=trade&status=complete")
        expect(page.get_by_label("Active transaction filters")).to_contain_text("Status: Completed")
        expect(page.get_by_role("heading", name="Historical Archive")).to_be_visible()
        filters = page.get_by_text("Search and filters", exact=True)
        activity = page.get_by_text("Current-week activity counts", exact=True)
        self.assertFalse(page.locator("details.tx-disclosure").nth(0).evaluate("e=>e.open"))
        self.assertFalse(page.locator("details.tx-disclosure").nth(1).evaluate("e=>e.open"))
        capture("transactions")
        filters.press("Enter")
        expect(page.get_by_label("Transaction type")).to_have_value("trade")
        expect(page.get_by_label("History scope")).to_have_value("all_history")
        page.get_by_label("Search", exact=True).fill("fixture")
        apply = page.get_by_role("button", name="Apply filters")
        apply.scroll_into_view_if_needed()
        self.assertTrue(apply.evaluate("""e => {
            const r = e.getBoundingClientRect();
            const point = document.elementFromPoint(r.x+r.width/2, r.y+r.height/2);
            return e.contains(point);
        }"""))
        apply.click()
        page.wait_for_url("**/transactions?*q=fixture*")
        expect(page.get_by_label("Active transaction filters")).to_contain_text("Search: fixture")
        activity.press("Enter")
        expect(page.get_by_role("button", name="Refresh Transactions")).to_be_visible()
        capture("transactions-activity")
