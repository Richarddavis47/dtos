"""Exercise Market against the real indexed read model and signed-in browser routes."""

import os
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests.test_market_roster_relevance import MarketNeedFixture


class MarketDirectoryBrowserTests(unittest.TestCase):
    def test_neutral_pages_match_the_canonical_full_order_and_sort_override(self):
        fixture = MarketNeedFixture(self)
        canonical = fixture.market.directory(limit=100)["assets"]

        def ids(rows):
            return [row["asset_id"] for row in rows]

        def market_assets(path):
            html = fixture.client.get(path).text
            return re.findall(r'class="market-result" data-asset-id="([^"]+)"', html)

        def value(row):
            return (row.get("values") or {}).get("market_value")

        values = [value(row) for row in canonical]
        self.assertIn(None, values)
        self.assertEqual(values, sorted(values, key=lambda price: (price is not None, price or 0), reverse=True))
        self.assertGreater(len(canonical), 10)
        self.assertEqual(ids(canonical[:20]), market_assets("/market") + market_assets("/market?offset=10"))
        self.assertEqual(len(ids(canonical)), len(set(ids(canonical))))
        ties = {}
        for row in canonical:
            ties.setdefault(value(row), []).append(row["asset_id"])
        self.assertTrue(any(len(group) > 1 for group in ties.values()))
        self.assertTrue(all(group == sorted(group, reverse=True) for group in ties.values()))
        matching = fixture.market.directory(position="RB", q="RB", direction="asc", limit=100)["assets"]
        self.assertTrue(matching)
        self.assertEqual(ids(matching[:10]), market_assets("/market?q=RB&position=RB&sort=market&direction=asc"))
        ranked = [value(row) for row in matching if value(row) is not None]
        self.assertEqual(ranked, sorted(ranked))
        self.assertEqual([value(row) for row in matching[:len(ranked)]], ranked)

    def test_phone_and_desktop_market_evidence_trade_and_return(self):
        fixture = MarketNeedFixture(self, old_raw=3600)
        editor = fixture.f.editor
        initial = editor.state()
        moved = editor.post("reorder", state=initial, asset_id=initial["rows"][1]["asset_id"], to_position=1)
        self.assertEqual(moved.status_code, 200)
        original_preferences = editor.state()
        self.assertNotEqual(initial["rows"][0]["asset_id"], original_preferences["rows"][0]["asset_id"])
        screenshots = os.environ.get("DTOS_MARKET_DIRECTORY_EVIDENCE")
        if screenshots:
            Path(screenshots).mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            for width, height in [(320, 432), (390, 844), (1280, 900)]:
                with self.subTest(width=width):
                    browser = launch_chromium(pw, headless=True)
                    try:
                        self._check_viewport(browser, fixture, width, height, screenshots, original_preferences["rows"])
                    finally:
                        browser.close()
        final_preferences = fixture.f.editor.state()
        for field in ("revision", "mode", "method"):
            self.assertEqual(original_preferences[field], final_preferences[field])
        self.assertEqual([row["asset_id"] for row in original_preferences["rows"]],
                         [row["asset_id"] for row in final_preferences["rows"]])

    def _check_viewport(self, browser, fixture, width, height, screenshots, saved_rows):
        touch = width < 760
        device = SimpleNamespace(new_page=lambda **kwargs: browser.new_page(has_touch=touch, **kwargs))
        page, requests, _, _, errors = fixture.helper.page(device, fixture.f, width, height)
        page.goto(fixture.helper.origin + "/market?position=RB&availability=rostered&sort=market&direction=asc&limit=100")
        self.assertEqual(page.locator('.market-position-tabs [aria-current="true"]').inner_text(), "RB")
        brand = page.locator(".market-top .brand-mark").bounding_box()
        switcher = page.locator(".market-top .account-context summary").bounding_box()
        self.assertLessEqual(brand["x"] + brand["width"], switcher["x"])
        self.assertLessEqual(switcher["x"] + switcher["width"], width)
        other = page.locator(".market-result:not([data-asset-id='" + fixture.asset_id + "']) .market-row-change").first
        self.assertIn("No change data", other.inner_text())
        row = page.locator(f'[data-asset-id="{fixture.asset_id}"] > a')
        self.assertEqual(row.locator(".market-row-change b").inner_text(), "0")
        self.assertRegex(row.locator(".market-row-change small").inner_text(), r"[A-Z][a-z]{2} \d+–[A-Z][a-z]{2} \d+")
        rows = page.locator(".market-result")
        self.assertGreater(rows.count(), 1)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
        if screenshots:
            page.screenshot(path=str(Path(screenshots) / f"market-{width}.png"))
        row.focus()
        row.press("Enter")
        panel = page.locator("#market-row-detail")
        self.assertIn("weekly lineup gain", panel.inner_text())
        self.assertIn("0 Market points", panel.inner_text())
        sources = panel.locator("summary")
        sources.focus()
        sources.press("Enter")
        self.assertIn("FantasyCalc", panel.inner_text())
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
        if screenshots:
            page.screenshot(path=str(Path(screenshots) / f"market-expanded-{width}.png"))

        before = parse_qs(urlsplit(page.url).query)
        self.assertEqual(before["selected"], [fixture.asset_id])
        trade = panel.get_by_role("link", name=re.compile("^Trade For "))
        if touch:
            trade.tap()
        else:
            trade.focus()
            trade.press("Enter")
        page.wait_for_url("**/trades/trade-for?*")
        self.assertEqual(page.locator("#trade-builder").get_attribute("data-preload-asset"), fixture.player_id)
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        self.assertTrue(page.locator("#trade-strategy").is_enabled())
        self.assertFalse(any(method == "POST" for method, _, _ in requests))
        fixture.helper.back(page, "/market?*")
        self.assertEqual(parse_qs(urlsplit(page.url).query), before)
        panel.wait_for(state="visible")
        page.get_by_role("link", name="My DTOS", exact=True).click()
        page.wait_for_url("**/account/my-dtos?*")
        self.assertEqual(page.locator("#my-dtos-heading").inner_text(), "My DTOS")
        list_rows = page.locator(".personal-row")
        list_rows.first.wait_for()
        actual_order = list_rows.evaluate_all("(rows) => rows.map(row => row.dataset.assetId)")
        self.assertEqual(actual_order, [row["asset_id"] for row in saved_rows[:len(actual_order)]])
        self.assertEqual(page.locator(".manager-nav [aria-current='page']").inner_text().strip(), "Market")
        page.get_by_text("Ranking settings & explanation", exact=True).click()
        page.locator("#personal-settings").get_by_role("link", name="Market", exact=True).click()
        self.assertEqual(parse_qs(urlsplit(page.url).query), before)
        panel.wait_for(state="visible")
        self.assertEqual(errors, [])
