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
                        "2029 R2 · Chase Bank",
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
                    link = card.get_by_role("link", name="Open original trade →")
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
                    self.assertIn("Unpriced", last.inner_text())
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

    def test_real_eleven_asset_compact_geometry_complete_expansion_and_hit_targets(
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
        data = h.data[sources.DAY]
        capture = json.loads(
            (
                Path(__file__).parent / "fixtures/home_news_recent_trades.json"
            ).read_text()
        )
        data["transactions"] = capture["transactions"]
        data["season_transactions"] = {"5": data["transactions"]}
        now = datetime.fromtimestamp(
            max(r["status_updated"] for r in data["transactions"]) / 1000, timezone.utc
        ) + timedelta(hours=1)
        data["market_data"] = fixtures.fixture(now)["market_data"]
        data["market_data"]["providers"]["FantasyCalc"]["13417"] = data["market_data"][
            "providers"
        ]["FantasyCalc"].pop("13406")
        data["market_data"]["provider_status"] = {
            "FantasyCalc": {"refresh_result": "cached_fallback"}
        }
        data["players"]["13417"] = {"full_name": "De’Zhaun Stribling", "position": "WR"}
        data["week"] = 6
        f.store.upsert_membership(
            f.account_id, data["league"], "fixture-user", 1, "Chase Bank", "active"
        )
        f.store.activate(f.account_id, sources.DAY)
        f.client.app.router.routes.clear()
        f.client.app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(), require_data=lambda: data, page=dtos_app.page
            )
        )
        static = TestClient(dtos_app.app)
        metrics = []
        with (
            patch.object(dtos_app, "account_store", f.store),
            patch("routes.home.datetime") as clock,
            sync_playwright() as pw,
        ):
            clock.now.return_value = now
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [
                    (320, 568),
                    (375, 667),
                    (390, 682),
                    (390, 844),
                    (390, 432),
                    (1280, 900),
                ]:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_default_timeout(8000)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))

                    def transport(route):
                        u = urlsplit(route.request.url)
                        if u.netloc == "sleepercdn.com":
                            return route.fulfill(
                                status=200,
                                content_type="image/jpeg",
                                body=image_bytes("image/jpeg"),
                            )
                        if u.netloc != "dtos.test":
                            return route.abort()
                        r = (static if u.path.startswith("/static/") else f.client).get(
                            u.path + ("?" + u.query if u.query else "")
                        )
                        route.fulfill(
                            status=r.status_code,
                            content_type=r.headers.get("content-type", "text/html"),
                            body=r.content,
                        )

                    page.route("**/*", transport)
                    page.goto("http://dtos.test/", wait_until="networkidle")
                    header = page.locator(".ux-feature")
                    news = page.locator(".league-trade-news")
                    self.assertIn("Chase Bank", header.inner_text())
                    self.assertLess(
                        header.bounding_box()["y"], news.bounding_box()["y"]
                    )
                    actions = header.locator(".ux-feature-actions")
                    self.assertLess(
                        actions.bounding_box()["y"], 550 if width < 700 else 720
                    )

                    # Actual pointer geometry, including sticky-navigation overlap.
                    def hit(locator):
                        locator.scroll_into_view_if_needed()
                        self.assertTrue(
                            locator.evaluate(
                                """e=>{const r=e.getBoundingClientRect();const h=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return h===e||e.contains(h)}"""
                            )
                        )

                    hit(header.get_by_role("link", name="Open My Team", exact=True))
                    large = page.locator('[data-news-trade="1415021723840966656"]')
                    boston = page.locator('[data-news-trade="1414718106177122304"]')
                    complete = large.locator(".news-complete-assets")
                    self.assertFalse(complete.evaluate("e=>e.open"))
                    self.assertFalse(
                        large.locator(".news-evaluation").evaluate("e=>e.open")
                    )
                    self.assertLess(
                        large.bounding_box()["height"], 650 if width == 320 else 600
                    )
                    self.assertLess(boston.bounding_box()["height"], 600)
                    metrics.append(
                        {
                            "width": width,
                            "height": height,
                            "large_collapsed_height": large.bounding_box()["height"],
                            "boston_height": boston.bounding_box()["height"],
                            "actions_top": actions.bounding_box()["y"]
                            + page.evaluate("scrollY"),
                            "document_width": page.evaluate(
                                "document.documentElement.scrollWidth"
                            ),
                        }
                    )
                    summary = complete.locator("summary")
                    self.assertIn("11 items", summary.inner_text())
                    hit(summary)
                    summary.click()
                    self.assertTrue(complete.evaluate("e=>e.open"))
                    self.assertEqual(complete.locator("[data-news-asset]").count(), 11)
                    self.assertEqual(
                        len(
                            set(
                                complete.locator("[data-news-asset]").evaluate_all(
                                    "es=>es.map(e=>e.dataset.newsAsset)"
                                )
                            )
                        ),
                        11,
                    )
                    self.assertEqual(complete.locator('a[href^="/picks/"]').count(), 6)
                    self.assertEqual(complete.locator(".news-player").count(), 5)
                    self.assertFalse(
                        large.locator(".news-evaluation").evaluate("e=>e.open")
                    )
                    summary.focus()
                    summary.press("Enter")
                    self.assertFalse(complete.evaluate("e=>e.open"))
                    evaluation = large.locator(".news-evaluation>summary")
                    hit(evaluation)
                    evaluation.click()
                    self.assertTrue(
                        large.locator(".news-evaluation").evaluate("e=>e.open")
                    )
                    self.assertFalse(complete.evaluate("e=>e.open"))
                    evaluation.click()
                    pricing = boston.locator(".news-evidence>summary")
                    hit(pricing)
                    pricing.click()
                    self.assertIn(
                        "cached_fallback", boston.locator(".news-evidence").inner_text()
                    )
                    self.assertIn(
                        "Source observation:",
                        boston.locator(".news-evidence").inner_text(),
                    )
                    pricing.click()
                    self.assertFalse(
                        boston.locator(".news-evaluation").evaluate("e=>e.open")
                    )
                    self.assertTrue(boston.locator(".news-bar").is_visible())
                    self.assertIn("received 125 more", boston.inner_text())
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertFalse(errors, errors)
                    page.screenshot(
                        path=f".validation/home-news-corrections/accepted-{width}-{height}.png",
                        full_page=True,
                    )
                    # Actual historical three-party source at its own supported
                    # source time; never move its timestamp into the current feed.
                    cash_source = json.loads(
                        (
                            Path(__file__).parent / "fixtures/trade_faab_source.json"
                        ).read_text()
                    )
                    cash_raw = next(
                        r
                        for b in cash_source["transactions"].values()
                        for r in b
                        if r["transaction_id"] == "965057520920260608"
                    )
                    original = {
                        k: data.get(k)
                        for k in (
                            "league",
                            "teams",
                            "players",
                            "transactions",
                            "season_transactions",
                            "market_data",
                        )
                    }
                    data["league"] = cash_source["league"]
                    users = {u["user_id"]: u for u in cash_source["users"]}
                    data["teams"] = [
                        {
                            "roster_id": r["roster_id"],
                            "team_name": (
                                users.get(r["owner_id"], {}).get("metadata") or {}
                            ).get("team_name")
                            or users.get(r["owner_id"], {}).get("display_name"),
                            "players": [],
                            "picks_owned": [],
                        }
                        for r in cash_source["rosters"]
                    ]
                    data["players"] = cash_source["player_identities"]
                    data["market_data"] = {}
                    f.store.upsert_membership(
                        f.account_id,
                        data["league"],
                        "fixture-user",
                        1,
                        "Historical fixture",
                        "active",
                    )
                    f.store.activate(f.account_id, data["league"]["league_id"])
                    data["transactions"] = [cash_raw]
                    data["season_transactions"] = {"0": [cash_raw]}
                    clock.now.return_value = datetime.fromtimestamp(
                        cash_raw["status_updated"] / 1000, timezone.utc
                    ) + timedelta(hours=1)
                    page.reload(wait_until="networkidle")
                    cash_card = page.locator('[data-news-trade="965057520920260608"]')
                    self.assertEqual(cash_card.locator(".news-side").count(), 3)
                    self.assertEqual(cash_card.locator(".news-bar").count(), 0)
                    cash_summary = cash_card.locator(".news-complete-assets>summary")
                    hit(cash_summary)
                    cash_summary.click()
                    self.assertEqual(
                        cash_card.locator(
                            ".news-complete-assets [data-news-asset]"
                        ).count(),
                        9,
                    )
                    self.assertEqual(
                        cash_card.locator(
                            '.news-complete-assets [data-news-asset="faab:3:6:100.0"]'
                        ).count(),
                        1,
                    )
                    self.assertIn(
                        "100 FAAB",
                        cash_card.locator(".news-complete-assets").inner_text(),
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    data.update(original)
                    f.store.activate(f.account_id, sources.DAY)
                    # Rolling expiry still defeats the warmed Home model.
                    clock.now.return_value = now + timedelta(days=8)
                    page.reload(wait_until="networkidle")
                    self.assertEqual(page.locator(".news-card").count(), 0)
                    self.assertIn(
                        "No completed league trades",
                        page.locator(".news-quiet").inner_text(),
                    )
                    self.assertIn(
                        "Chase Bank", page.locator(".ux-feature").inner_text()
                    )
                    clock.now.return_value = now
                    page.close()
            finally:
                browser.close()
        Path(
            ".validation/home-news-corrections/accepted-browser-metrics.json"
        ).write_text(json.dumps(metrics, indent=2))
