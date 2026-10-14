"""Settled authenticated Home -> actual completed-trade routes in Chromium."""

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from routes.home import create_home_router
from routes.historical_assets import create_historical_assets_router
from tests import test_trade_workspace_batch1 as auth
from tests import test_home_trade_news as fixtures
from tests import test_trade_timeline as sources
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_runtime import launch_chromium


class TradeNewsBrowserTests(unittest.TestCase):
    def test_authenticated_source_direction_portraits_evaluation_return_and_leagues(
        self,
    ):
        import dtos_app

        f = auth.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        h = sources.TradeTimelineTests()
        h.setUp()
        self.addCleanup(h.tearDown)
        h.load()
        h.load(1)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        data = h.data[sources.DAY]
        raw = next(
            t
            for b in h.sources[0]["transactions"].values()
            for t in b
            if t["transaction_id"] == "1414718106177122304"
        )
        # Real source identities/directions. Source clock remains unmodified.
        source_clock = datetime.fromtimestamp(
            raw["status_updated"] / 1000, timezone.utc
        )
        now = source_clock + timedelta(hours=1)
        data["transactions"] = [copy.deepcopy(raw)]
        data["season_transactions"] = {"6": data["transactions"]}
        data["market_data"] = fixtures.fixture(now)["market_data"]
        data["players"]["13417"] = {
            "full_name": "De’Zhaun Stribling",
            "position": "WR",
            "team": "HOU",
        }
        data["market_data"]["providers"]["FantasyCalc"]["13417"] = data["market_data"][
            "providers"
        ]["FantasyCalc"].pop("13406")
        data["teams"][3]["picks_owned"] = [
            {"year": 2029, "round": 2, "original_roster_id": 1, "current_owner_id": 4}
        ]
        data["week"] = 6
        h.store.update_current(sources.DAY, data)
        f.store.upsert_membership(
            f.account_id, data["league"], "fixture-user", 1, "Chase Bank", "active"
        )
        f.store.activate(f.account_id, sources.DAY)
        active = [data]
        app = f.client.app
        app.router.routes.clear()
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: active[0],
                page=dtos_app.page,
            )
        )
        app.include_router(
            create_historical_assets_router(
                league_id=sources.DAY,
                require_data=lambda: active[0],
                page=dtos_app.page,
                league_resolver=lambda: active[0]["league"]["league_id"],
            )
        )
        static = TestClient(dtos_app.app)
        metrics = []
        with (
            patch.object(dtos_app, "account_store", f.store),
            patch("routes.historical_assets.historical_store", h.store),
            patch(
                "src.core.intelligence_memory.intelligence_checkpoint_store", h.memory
            ),
            patch("routes.home.datetime") as clock,
            sync_playwright() as pw,
        ):
            clock.now.return_value = now
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [
                    (320, 432),
                    (375, 667),
                    (390, 844),
                    (390, 432),
                    (1280, 900),
                ]:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_default_timeout(8000)
                    errors = []
                    requests = []
                    page.on("pageerror", lambda e: errors.append(str(e)))

                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.hostname == "sleepercdn.com":
                            route.fulfill(
                                status=200,
                                content_type="image/jpeg",
                                body=image_bytes("image/jpeg"),
                            )
                            return
                        if url.hostname != "dtos.test":
                            route.abort()
                            return
                        path = url.path + ("?" + url.query if url.query else "")
                        requests.append((route.request.method, path))
                        response = (
                            static if url.path.startswith("/static/") else f.client
                        ).request(
                            route.request.method, path, content=route.request.post_data
                        )
                        route.fulfill(
                            status=response.status_code,
                            content_type=response.headers.get(
                                "content-type", "text/html"
                            ),
                            body=response.content,
                        )

                    page.route("**/*", transport)
                    page.goto("http://dtos.test/", wait_until="networkidle")
                    card = page.locator('[data-news-trade="1414718106177122304"]')
                    self.assertTrue(card.is_visible())
                    self.assertIn(
                        "Denzel Boston", card.locator(".news-side").nth(0).inner_text()
                    )
                    self.assertIn(
                        "Chase Bank", card.locator(".news-side").nth(0).inner_text()
                    )
                    self.assertIn(
                        "De’Zhaun Stribling",
                        card.locator(".news-side").nth(1).inner_text(),
                    )
                    self.assertIn(
                        "originally Chase Bank",
                        card.locator(".news-side").nth(1).inner_text(),
                    )
                    self.assertTrue(card.locator("img.player-headshot").count() == 2)
                    card.locator(
                        "img.player-headshot"
                    ).first.scroll_into_view_if_needed()
                    self.assertTrue(
                        card.locator("img.player-headshot").first.evaluate(
                            "e=>e.complete && e.naturalWidth>0"
                        )
                    )
                    self.assertFalse(
                        card.locator(".news-evaluation").evaluate("e=>e.open")
                    )
                    collapsed_height = card.bounding_box()["height"]
                    card.screenshot(
                        path=f".validation/home-trade-news/card-{width}-{height}.png"
                    )
                    summary = card.locator(".news-evaluation summary")
                    summary.scroll_into_view_if_needed()
                    summary.focus()
                    self.assertNotEqual(
                        summary.evaluate("e=>getComputedStyle(e).outlineStyle"), "none"
                    )
                    summary.press("Enter")
                    self.assertTrue(
                        card.locator(".news-evaluation").evaluate("e=>e.open")
                    )
                    self.assertIn("Decision-time strategy", card.inner_text())
                    self.assertIn("Cost:", card.inner_text())
                    self.assertNotIn("manager intentionally", card.inner_text())
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    metrics.append(
                        {
                            "width": width,
                            "height": height,
                            "cardHeight": card.bounding_box()["height"],
                            "collapsedCardHeight": collapsed_height,
                            "newsTop": page.locator(
                                ".league-trade-news"
                            ).bounding_box()["y"]
                            + page.evaluate("scrollY"),
                            "documentWidth": page.evaluate(
                                "document.documentElement.scrollWidth"
                            ),
                        }
                    )
                    page.screenshot(
                        path=f".validation/home-trade-news/home-{width}-{height}.png",
                        full_page=True,
                    )
                    link = card.get_by_role(
                        "link", name="Open original completed trade →"
                    )
                    link.scroll_into_view_if_needed()
                    link.click()
                    self.assertIn("Historical Trade Timeline", page.title())
                    page.get_by_role("link", name="← Back to Home", exact=True).click()
                    self.assertTrue(page.locator("[data-news-trade]").count() == 1)
                    page.reload(wait_until="networkidle")
                    self.assertTrue(page.locator("[data-news-trade]").count() == 1)
                    page.go_back(wait_until="networkidle")
                    page.go_forward(wait_until="networkidle")
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    # Selected league source is independent; same local roster IDs.
                    other = h.data[sources.ARK]
                    other["transactions"] = []
                    other["season_transactions"] = {}
                    other["week"] = 6
                    active[0] = other
                    f.store.upsert_membership(
                        f.account_id,
                        other["league"],
                        "fixture-user",
                        1,
                        "Arkham franchise",
                        "active",
                    )
                    f.store.activate(f.account_id, sources.ARK)
                    page.reload(wait_until="networkidle")
                    self.assertEqual(page.locator("[data-news-trade]").count(), 0)
                    self.assertIn(
                        "No completed league trades",
                        page.locator(".league-trade-news").inner_text(),
                    )
                    active[0] = data
                    f.store.activate(f.account_id, sources.DAY)
                    page.reload(wait_until="networkidle")
                    self.assertTrue(page.locator("[data-news-trade]").count() == 1)
                    self.assertFalse(any(m != "GET" for m, _ in requests))
                    self.assertFalse(errors, errors)
                    page.close()
            finally:
                browser.close()
        Path(".validation/home-trade-news/browser-metrics.json").write_text(
            json.dumps(metrics, indent=2)
        )

    def test_busy_partial_multi_party_faab_and_photo_fallback_all_widths(self):
        import dtos_app

        f = auth.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        now = datetime.now(timezone.utc)
        data = fixtures.fixture(now)
        data["transactions"] = [
            fixtures.trade(now, str(n), hours=n + 1) for n in range(8)
        ]
        data["transactions"][0].update(
            roster_ids=[1, 2, 3],
            waiver_budget=[{"sender": 2, "receiver": 3, "amount": 100}],
        )
        data["transactions"].append(
            fixtures.trade(
                now,
                "unknown",
                adds={"unpriced": 1},
                drops={"unpriced": 2},
                draft_picks=[],
            )
        )
        f.store.upsert_membership(
            f.account_id, data["league"], "fixture-user", 1, "Chase Bank", "active"
        )
        f.store.activate(f.account_id, sources.DAY)
        app = f.client.app
        app.router.routes.clear()
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(), require_data=lambda: data, page=dtos_app.page
            )
        )
        static = TestClient(dtos_app.app)
        with patch.object(dtos_app, "account_store", f.store), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [
                    (320, 432),
                    (375, 667),
                    (390, 844),
                    (390, 432),
                    (1280, 900),
                ]:
                    page = browser.new_page(viewport={"width": width, "height": height})

                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.hostname == "sleepercdn.com":
                            route.abort("failed")
                            return
                        if url.hostname != "dtos.test":
                            route.abort()
                            return
                        response = (
                            static if url.path.startswith("/static/") else f.client
                        ).get(url.path + ("?" + url.query if url.query else ""))
                        route.fulfill(
                            status=response.status_code,
                            content_type=response.headers.get(
                                "content-type", "text/html"
                            ),
                            body=response.content,
                        )

                    page.route("**/*", transport)
                    page.goto("http://dtos.test/", wait_until="networkidle")
                    self.assertEqual(page.locator(".news-card").count(), 6)
                    self.assertEqual(page.locator(".news-card:visible").count(), 2)
                    first = page.locator(".news-card").first
                    self.assertEqual(first.locator(".news-side").count(), 3)
                    self.assertIn("100 FAAB", first.inner_text())
                    self.assertEqual(first.locator(".news-bar").count(), 0)
                    self.assertTrue(
                        first.locator(".player-headshot").first.evaluate("e=>e.hidden")
                    )
                    self.assertTrue(
                        first.locator(".player-headshot-fallback").first.is_visible()
                    )
                    more = page.locator(".news-more>summary")
                    more.scroll_into_view_if_needed()
                    more.click()
                    self.assertEqual(page.locator(".news-card:visible").count(), 6)
                    last = page.locator('[data-news-trade="unknown"]')
                    self.assertIn("Market unavailable", last.inner_text())
                    self.assertIn("Market advantage unavailable", last.inner_text())
                    self.assertEqual(last.locator(".news-bar").count(), 0)
                    self.assertEqual(page.locator(".news-evaluation[open]").count(), 0)
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertTrue(
                        page.locator(".news-evaluation>summary").evaluate_all(
                            "es=>es.every(e=>e.getBoundingClientRect().height>=44)"
                        )
                    )
                    page.close()
            finally:
                browser.close()
