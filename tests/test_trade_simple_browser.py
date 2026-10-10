"""Actual authenticated routes/APIs and current page chrome; canonical fixture sources only.

Responsive Chromium, not physical Safari. Discovery/evaluation/balance engines
execute without mocking recommendations. External provider access is forbidden.
"""

import json
import os
import unittest
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from playwright.sync_api import sync_playwright
from routes.trades import create_trades_router
from tests import test_trade_workspace_batch1 as boundary
from tests import test_trade_discovery_repair as discovery
from tools.validation.browser_runtime import launch_chromium


class SimpleTradeJourneyBrowserTests(unittest.TestCase):
    def test_actual_build_shop_trade_for_recommended_journeys(self):
        import dtos_app

        source = discovery.DiscoveryRepairTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        auth = boundary.AuthenticatedTradeBoundaryTests()
        auth.setUp()
        self.addCleanup(auth.doCleanups)
        auth.data = source.data
        auth.client.app.router.routes.clear()
        auth.client.app.include_router(
            create_trades_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: auth.data,
                page=dtos_app.page,
            )
        )
        self.addCleanup(auth.client.close)
        records = []
        with (
            patch.object(dtos_app, "account_store", auth.store),
            patch(
                "src.core.projection_intelligence.projection_service",
                source.fixture.reader,
            ),
            sync_playwright() as engine,
        ):
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in (
                    (320, 483),
                    (320, 568),
                    (375, 483),
                    (375, 667),
                    (390, 483),
                    (390, 844),
                    (1280, 900),
                ):
                    with self.subTest(width=width, height=height):
                        page = browser.new_page(
                            viewport={"width": width, "height": height}
                        )
                        page.set_default_timeout(10000)
                        page.add_init_script(
                            'window.__tradeAuditScrolls={page:0,regions:0}; document.addEventListener("scroll",e=>{window.__tradeAuditScrolls[e.target===document?"page":"regions"]++},true)'
                        )
                        requests = []
                        errors = []
                        page.on("pageerror", lambda e: errors.append(str(e)))

                        def transport(route):
                            r = route.request
                            u = urlsplit(r.url)
                            if u.netloc != "dtos.test":
                                return route.abort()
                            if u.path.startswith("/api/trades/") and r.method == "POST":
                                requests.append((u.path, r.post_data_json))
                            response = auth.client.request(
                                r.method,
                                u.path + ("?" + u.query if u.query else ""),
                                content=r.post_data,
                                headers={
                                    k: v
                                    for k, v in r.headers.items()
                                    if k in ("content-type", "x-csrf-token")
                                },
                            )
                            route.fulfill(
                                status=response.status_code,
                                content_type=response.headers.get(
                                    "content-type", "text/html"
                                ),
                                body=response.content,
                            )

                        page.route("**/*", transport)

                        def click(selector):
                            locator = page.locator(selector)
                            locator.scroll_into_view_if_needed()
                            hit = locator.evaluate(
                                "e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}"
                            )
                            self.assertTrue(hit, selector)
                            locator.click()

                        def done():
                            page.wait_for_function(
                                '!document.querySelector("#trade-run").disabled'
                            )

                        start = perf_counter()
                        page.goto("https://dtos.test/trades")
                        self.assertEqual(page.locator(".ti-workflows > a").count(), 4)
                        build_link = page.get_by_role(
                            "link", name="Build a Trade", exact=False
                        ).first
                        build_link.focus()
                        build_link.press("Enter")
                        page.select_option("#trade-partner", "2")
                        readiness = perf_counter() - start
                        click('#trade-sent-board button[data-asset-id="1qb"]')
                        self.assertIn(
                            "You send:", page.locator("#trade-balance").inner_text()
                        )
                        if width < 760:
                            click("[data-side=received]")
                        start = perf_counter()
                        click('#trade-received-board button[data-asset-id="2w"]')
                        edit = perf_counter() - start
                        self.assertTrue(
                            page.locator("#calculator-verdict").is_visible()
                        )
                        self.assertIn(
                            "you receive more",
                            page.locator("#calculator-verdict").inner_text(),
                        )
                        self.assertEqual(requests, [])
                        market_before_pick = page.locator("#trade-balance").inner_text()
                        if width < 760:
                            click("[data-side=sent]")
                        pick = '#trade-sent-board button[data-asset-id="2028-R1-21"]'
                        click(pick)
                        selected_pick = page.locator("#calculator-sent").inner_text()
                        self.assertIn("2028", selected_pick)
                        self.assertIn("Round 1", selected_pick)
                        self.assertNotEqual(
                            page.locator("#trade-balance").inner_text(),
                            market_before_pick,
                        )
                        click(pick)
                        self.assertEqual(
                            page.locator("#trade-balance").inner_text(),
                            market_before_pick,
                        )
                        self.assertEqual(requests, [])
                        self.assertIn(
                            "Not an acceptance probability",
                            page.locator(".tw-market-bar").get_attribute("aria-label"),
                        )
                        self.assertEqual(
                            page.get_by_role(
                                "button", name="Evaluate Trade", exact=True
                            ).count(),
                            1,
                        )
                        if os.environ.get("DTOS_TRADE_JOURNEY_EVIDENCE"):
                            page.screenshot(
                                path=str(
                                    Path(
                                        os.environ["DTOS_TRADE_JOURNEY_EVIDENCE"]
                                    ).parent
                                    / f"build-after-{width}-{height}.png"
                                ),
                                full_page=True,
                            )
                        market = page.locator("#trade-balance").inner_text()
                        page.select_option("#trade-strategy", "REBUILD")
                        self.assertEqual(
                            page.locator("#trade-balance").inner_text(), market
                        )
                        page.select_option("#trade-strategy", "RETOOL")
                        start = perf_counter()
                        click("#trade-run")
                        page.locator("#trade-result .dtos-explanation").wait_for()
                        done()
                        evaluate = perf_counter() - start
                        verdict = page.locator(
                            "#trade-result .dtos-explanation > p"
                        ).first.bounding_box()
                        nav = page.locator(".manager-nav").bounding_box()
                        self.assertGreaterEqual(verdict["y"], 0)
                        self.assertLessEqual(
                            verdict["y"] + verdict["height"],
                            nav["y"] if width < 760 else height,
                        )
                        self.assertEqual(
                            page.locator("#trade-balancing").evaluate(
                                "e=>e.previousElementSibling.id"
                            ),
                            "trade-result",
                        )
                        start = perf_counter()
                        click("#trade-balance-offer")
                        page.get_by_role(
                            "button", name="Preview adjustment", exact=True
                        ).first.wait_for()
                        done()
                        balance = perf_counter() - start
                        original = page.evaluate(
                            'JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith("dtos-trade-workspace:")))).currentProposal'
                        )
                        start = perf_counter()
                        page.get_by_role(
                            "button", name="Preview adjustment", exact=True
                        ).first.click()
                        preview_time = perf_counter() - start
                        self.assertEqual(
                            page.evaluate(
                                'JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith("dtos-trade-workspace:")))).currentProposal'
                            ),
                            original,
                        )
                        click('#trade-result button:text-is("Keep original")')
                        page.get_by_role(
                            "button", name="Preview adjustment", exact=True
                        ).first.click()
                        start = perf_counter()
                        click('#trade-result button:text-is("Adopt alternative")')
                        adoption_time = perf_counter() - start
                        adopted = page.evaluate(
                            'JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith("dtos-trade-workspace:")))).currentProposal'
                        )
                        self.assertNotEqual(adopted, original)
                        build_scrolls = page.evaluate("window.__tradeAuditScrolls")
                        page.reload()
                        page.locator("#calculator-verdict").wait_for()
                        self.assertEqual(
                            page.evaluate(
                                'JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith("dtos-trade-workspace:")))).currentProposal'
                            ),
                            adopted,
                        )
                        # Actual target entries auto-search, no mandatory setup.
                        n = len(requests)
                        start = perf_counter()
                        page.goto("https://dtos.test/trades/shop?asset_id=1q")
                        page.locator(".tw-offer").first.wait_for()
                        shop_time = perf_counter() - start
                        self.assertEqual(len(requests), n + 1)
                        self.assertEqual(requests[-1][1]["partner_roster_id"], 0)
                        self.assertEqual(
                            requests[-1][1]["shop_preference"], "best_overall"
                        )
                        self.assertEqual(requests[-1][1]["asset_id"], "1q")
                        page.locator("#shop-refinements > summary").click()
                        start = perf_counter()
                        page.select_option("#shop-preference", "draft_capital")
                        page.wait_for_function(
                            '!document.querySelector("#shop-preference").disabled'
                        )
                        refine_time = perf_counter() - start
                        self.assertEqual(
                            requests[-1][1]["shop_preference"], "draft_capital"
                        )
                        self.assertEqual(requests[-1][1]["asset_id"], "1q")
                        n = len(requests)
                        page.goto("https://dtos.test/trades/shop?asset_id=2028-R1-21")
                        page.wait_for_function(
                            '!document.querySelector("#trade-find").disabled'
                        )
                        self.assertEqual(len(requests), n + 1)
                        self.assertEqual(requests[-1][1]["asset_id"], "2028-R1-21")
                        self.assertEqual(requests[-1][1]["partner_roster_id"], 0)
                        self.assertIn(
                            "2028", page.locator("#trade-sent-chips").inner_text()
                        )
                        n = len(requests)
                        start = perf_counter()
                        page.goto("https://dtos.test/trades/trade-for?asset_id=2w")
                        page.locator(".tw-offer").first.wait_for()
                        trade_for_time = perf_counter() - start
                        self.assertEqual(len(requests), n + 1)
                        self.assertEqual(requests[-1][1]["partner_roster_id"], 2)
                        self.assertEqual(requests[-1][1]["assets_received"], ["2w"])
                        page.goto("https://dtos.test/trades/recommended")
                        start = perf_counter()
                        click("#trade-find")
                        page.locator(".tw-offer").first.wait_for()
                        page.wait_for_function(
                            '!document.querySelector("#trade-find").disabled'
                        )
                        recommended_time = perf_counter() - start
                        self.assertIn(
                            "Trade options ready",
                            page.locator("#recommendation-status").inner_text(),
                        )
                        first = page.locator(
                            "#trade-result .tw-offer > p"
                        ).all_text_contents()
                        start = perf_counter()
                        click("#recommendation-refresh")
                        page.wait_for_function(
                            '!document.querySelector("#trade-find").disabled'
                        )
                        next_time = perf_counter() - start
                        self.assertTrue(
                            requests[-1][1]["excluded_recommendation_families"]
                        )
                        self.assertNotEqual(
                            first,
                            page.locator(
                                "#trade-result .tw-offer > p"
                            ).all_text_contents(),
                        )
                        page.set_viewport_size({"width": width, "height": height + 100})
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"),
                            width + 1,
                        )
                        self.assertEqual(errors, [])
                        records.append(
                            {
                                "width": width,
                                "height": height,
                                "readiness_seconds": readiness,
                                "edit_seconds": edit,
                                "evaluation_seconds": evaluate,
                                "balance_seconds": balance,
                                "preview_seconds": preview_time,
                                "adoption_seconds": adoption_time,
                                "shop_route_to_first_offer_seconds": shop_time,
                                "shop_refinement_seconds": refine_time,
                                "trade_for_route_to_first_offer_seconds": trade_for_time,
                                "recommended_seconds": recommended_time,
                                "next_five_seconds": next_time,
                                "build_logical_actions": 13 if width < 760 else 12,
                                "action_count_scope": "Core opening through adopt/reload; excludes diagnostic strategy and pick edits.",
                                "automated_build_scroll_events": build_scrolls,
                                "scroll_count_scope": "Includes diagnostic edits and automatic focus/scroll events; not human touch gestures.",
                                "pointer_checks": True,
                            }
                        )
                        evidence = os.environ.get("DTOS_TRADE_JOURNEY_EVIDENCE")
                        if evidence:
                            page.screenshot(
                                path=str(
                                    Path(evidence).parent
                                    / f"journey-after-{width}-{height}.png"
                                ),
                                full_page=True,
                            )
                        page.close()
            finally:
                browser.close()
        if os.environ.get("DTOS_TRADE_JOURNEY_EVIDENCE"):
            Path(os.environ["DTOS_TRADE_JOURNEY_EVIDENCE"]).write_text(
                json.dumps(records, indent=2)
            )
