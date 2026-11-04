"""Actual released history routers and shared page chrome in Chromium fixtures."""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium

from routes.historical_assets import create_historical_assets_router
from routes.history import create_history_router
from tests import test_trade_timeline as source_fixtures

DAY, ARK = source_fixtures.DAY, source_fixtures.ARK


class TradeTimelineBrowserTests(unittest.TestCase):
    def setUp(self):
        import dtos_app

        self.application = dtos_app
        self.fixture = source_fixtures.TradeTimelineTests()
        self.fixture.setUp()
        self.fixture.load()
        self.fixture.load(1)
        from tests.test_historical_faab_conflicts import publish_faab
        publish_faab(self.fixture)

    def tearDown(self):
        self.fixture.tearDown()

    def run_routes(self, league, widths):
        app = FastAPI()
        data = self.fixture.data[league]
        app.include_router(
            create_historical_assets_router(
                league_id=league, require_data=lambda: data, page=self.application.page
            )
        )
        app.include_router(
            create_history_router(league_id=league, page=self.application.page)
        )
        with (
            patch("routes.historical_assets.historical_store", self.fixture.store),
            patch("services.history.historical_store", self.fixture.store),
            patch("services.history.canonical_history_store", self.fixture.store),
            patch.dict(self.application.STATE, {"data": data}),
            TestClient(app) as client,
            sync_playwright() as pw,
        ):
            browser = launch_chromium(pw, headless=True, args=["--no-sandbox"])
            for width, height in widths:
                page = browser.new_page(viewport={"width": width, "height": height})

                def respond(route):
                    response = client.get(
                        route.request.url.replace("http://fixture", "")
                    )
                    route.fulfill(
                        status=response.status_code,
                        content_type=response.headers.get("content-type", "text/html"),
                        body=response.content,
                    )

                page.route("http://fixture/**", respond)
                for url in (
                    [
                        "/trades/history/1333655835015942144",
                        "/trades/history/965057520920260608",
                        "/picks/PICK-2026-R1-ORIG4?from_trade=1333655835015942144",
                        "/history",
                        "/history/team/" + DAY + ":franchise:3",
                    ]
                    if league == DAY
                    else ["/history"]
                ):
                    response = page.goto("http://fixture" + url)
                    self.assertEqual(
                        response.status,
                        200,
                        (url, page.locator("body").inner_text()[:200]),
                    )
                    page.locator("details").evaluate_all(
                        "(rows)=>rows.forEach(row=>row.open=true)"
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"),
                        width,
                        (league, url, width),
                    )
                    if url.startswith("/trades/history"):
                        text = page.locator(".trade-timeline").inner_text()
                        if url.endswith("965057520920260608"):
                            faab = page.locator('.timeline-faab')
                            self.assertEqual(faab.count(), 1)
                            self.assertIn('100 FAAB', faab.inner_text())
                            self.assertIn('Nasty Navel Lasers → zkobes', faab.inner_text())
                            self.assertEqual(page.locator('.timeline-asset').count(), 8)
                            source = faab.locator('summary')
                            source.focus()
                            self.assertNotEqual(source.evaluate('(el)=>getComputedStyle(el).outlineStyle'), 'none')
                            page.keyboard.press('Enter')
                            self.assertFalse(faab.locator('details').evaluate('(el)=>el.open'))
                            source.click()
                            self.assertTrue(faab.locator('details').evaluate('(el)=>el.open'))
                        else:
                            self.assertIn("Denzel Boston", text)
                            self.assertIn("exact selection time unavailable", text)
                        self.assertIn("No trade winner", text)
                        self.assertIn("NOT REVALIDATED", text)
                        control = page.locator(".timeline-asset summary").first
                        control.focus()
                        self.assertEqual(
                            page.evaluate("document.activeElement.tagName"), "SUMMARY"
                        )
                        self.assertNotEqual(
                            control.evaluate("(el)=>getComputedStyle(el).outlineStyle"),
                            "none",
                        )
                        was = control.evaluate("(el)=>el.parentElement.open")
                        page.keyboard.press("Enter")
                        self.assertNotEqual(
                            was, control.evaluate("(el)=>el.parentElement.open")
                        )
                    if url.startswith("/picks"):
                        self.assertIn(
                            "Back to original trade timeline",
                            page.locator("body").inner_text(),
                        )
                        self.assertNotIn(
                            "Not exercised", page.locator("body").inner_text()
                        )
                        self.assertIn('Consumed by verified draft conversion', page.locator('body').inner_text())
                    if url.startswith('/history/team/'):
                        self.assertIn('not a roster for every historical week', page.locator('body').inner_text())
                page.close()
            browser.close()

    def test_day_timeline_pick_and_history_phone_and_desktop(self):
        self.run_routes(
            DAY, [(320, 568), (375, 667), (390, 844), (390, 432), (1165, 800)]
        )

    def test_arkham_history_overflow_regression(self):
        self.run_routes(ARK, [(320, 568), (375, 667), (390, 844), (1165, 800)])
