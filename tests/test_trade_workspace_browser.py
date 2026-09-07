"""Focused real Chromium journeys through authenticated local Trade APIs."""
import base64
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import tests.test_trade_workspace_batch1 as boundary


class TradeWorkspaceBrowserTests(unittest.TestCase):
    def test_mobile_and_desktop_authenticated_build_review_evaluate_edit(self):
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for width in (390, 1280):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={"width": width, "height": 900})
                        page.set_default_timeout(8000)
                        errors = []
                        page.on("pageerror", lambda e: errors.append(str(e)))

                        def route(request):
                            parsed = urlsplit(request.request.url)
                            if parsed.netloc == "sleepercdn.com":
                                request.fulfill(content_type="image/png", body=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2ioAAAAASUVORK5CYII="))
                            elif parsed.netloc == "dtos.test":
                                response = fixture.client.request(request.request.method, parsed.path + ("?" + parsed.query if parsed.query else ""), content=request.request.post_data, headers={key: value for key, value in request.request.headers.items() if key in ("content-type", "x-csrf-token")})
                                request.fulfill(status=response.status_code, content_type=response.headers.get("content-type", "text/html"), body=response.content)
                            else:
                                request.abort()

                        page.route("**/*", route)
                        page.goto("https://dtos.test/trades/create", wait_until="domcontentloaded")
                        page.get_by_label("Counterparty", exact=True).select_option("2")
                        own = page.locator("#trade-sent-board")
                        own.get_by_role("button", name="Add Player 1-QB-0 — you send", exact=True).click()
                        own.get_by_role("button", name="PICKS", exact=True).click()
                        own.get_by_role("button", name="Add 2027 Round 1 (Team 1) — you send", exact=True).click()
                        own.get_by_role("button", name="ALL", exact=True).click()
                        self.assertEqual(own.get_by_role("button", name="Remove Player 1-QB-0 — you send", exact=True).get_attribute("aria-pressed"), "true")
                        if width < 760:
                            page.get_by_role("button", name="Their assets", exact=True).click()
                        other = page.locator("#trade-received-board")
                        other.get_by_role("searchbox").fill("2-QB-0")
                        other.get_by_role("button", name="Add Player 2-QB-0 — you receive", exact=True).click()
                        other.get_by_role("searchbox").fill("")
                        other.get_by_role("button", name="Add Player 2-QB-1 — you receive", exact=True).click()
                        self.assertIn("4 assets", page.locator("#trade-tray-text").inner_text())
                        page.locator("#trade-tray-view").click()
                        self.assertTrue(page.locator("#trade-review").is_visible())
                        page.get_by_role("button", name="Evaluate Trade", exact=True).click()
                        page.locator("#trade-result h3").wait_for()
                        self.assertNotIn("failed", page.locator("#trade-result").inner_text().lower())
                        page.get_by_role("button", name="Edit Trade", exact=True).click()
                        self.assertIn("4 assets", page.locator("#trade-tray-text").inner_text())
                        page.reload()
                        page.locator("#trade-tray:not([hidden])").wait_for()
                        self.assertIn("4 assets", page.locator("#trade-tray-text").inner_text())
                        # Canonical ownership may advance while a proposal is open.
                        # The error must name that boundary and retain the proposal.
                        player = fixture.data["teams"][1]["players"].pop(0)
                        fixture.data["teams"][0]["players"].append(player)
                        page.get_by_role("button", name="Evaluate Trade", exact=True).click()
                        page.get_by_text("Trade needs refreshing:", exact=False).wait_for()
                        self.assertIn("4 assets", page.locator("#trade-tray-text").inner_text())
                        self.assertIn(player["name"], page.locator("#trade-result").inner_text())
                        page.reload()
                        page.locator('#trade-tray:not([hidden])').wait_for()
                        self.assertIn("4 assets", page.locator("#trade-tray-text").inner_text())
                        self.assertIn("retained for review", page.locator("#trade-result").inner_text())
                        fixture.data["teams"][0]["players"].remove(player)
                        fixture.data["teams"][1]["players"].insert(0, player)
                        self.assertFalse(errors, errors)
                        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                        if width == 390:
                            for workflow, target, expected_side in (("trade-for", "2-QB-0", "received"), ("shop", "1-QB-0", "sent")):
                                page.evaluate("sessionStorage.clear()")
                                page.goto(f"https://dtos.test/trades/{workflow}?asset_id={target}&owner_roster_id=1")
                                page.locator(f'#trade-{expected_side}-chips button[data-asset-id="{target}"]').wait_for(state="attached")
                                if workflow == "trade-for":
                                    self.assertEqual(page.get_by_label("Counterparty", exact=True).input_value(), "2")
                                self.assertTrue(page.get_by_role('region', name='Selected trade target').is_visible())
                                self.assertTrue(page.get_by_role("button", name="Find Bilateral Options").is_visible())
                            page.goto("https://dtos.test/trades/recommended")
                            page.get_by_label("Counterparty", exact=True).select_option("2")
                            self.assertEqual(page.locator('#trade-builder').get_attribute('data-trade-workflow'), 'recommended')
                        page.close()
            finally:
                browser.close()
