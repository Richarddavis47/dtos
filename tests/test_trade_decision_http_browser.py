"""Actual authenticated routes, publishers and engines in responsive Chromium.

No production drafts or provider writes. Historical example amounts are controlled
fixtures, not an assertion that these values/projections are current live facts.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
from time import perf_counter
import unittest
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from playwright.sync_api import sync_playwright
from routes.home import create_home_router
from routes.trades import create_trades_router
from tests import test_capital_strategy_reconciliation as capital
from tests import test_trade_workspace_batch1 as boundary
from tools.validation.browser_runtime import launch_chromium


class DecisionHTTPBrowserTests(unittest.TestCase):
    def setUp(self):
        import dtos_app

        self.f = capital.CapitalStrategyTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data = self.f.data
        self.f.points.update(a=20, c=27.7)
        for team in self.data["teams"]:
            team.pop("strategy", None)
            for player in team["players"]:
                player["status"] = "Active"
                player["team"] = "BUF"
                self.data["players"][player["id"]].update(status="Active", team="BUF")
        for pid, name in [("a", "Jayden Daniels"), ("c", "Josh Allen")]:
            self.data["players"][pid]["full_name"] = name
            next(p for t in self.data["teams"] for p in t["players"] if p["id"] == pid)[
                "name"
            ] = name
        self.f.prices(a=611, c=929, b=80, d=150, e=100, f=100)
        self.data["teams"][0]["picks_owned"].append(
            {"year": 2029, "round": 1, "original_roster_id": 1, "current_owner_id": 1}
        )
        quote = dict(
            self.data["market_data"]["pick_quotes"]["FantasyCalc"][0],
            year=2029,
            value=334 * 12,
        )
        quote["normalization_reference"] = {
            **quote["normalization_reference"],
            "raw_value": 334 * 12,
            "normalized_value": 334,
        }
        self.data["market_data"]["pick_quotes"]["FantasyCalc"].append(quote)
        self.f.publish()
        self.auth = boundary.AuthenticatedTradeBoundaryTests()
        self.auth.setUp()
        self.addCleanup(self.auth.doCleanups)
        self.auth.data = self.data
        app = self.auth.client.app
        app.router.routes.clear()
        app.include_router(
            create_trades_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=dtos_app.page,
            )
        )
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=dtos_app.page,
            )
        )
        self.addCleanup(self.auth.client.close)
        self.enterContext(patch.object(dtos_app, "account_store", self.auth.store))
        self.enterContext(
            patch(
                "services.trade_intelligence._trade_projection_service",
                return_value=self.f.reader,
            )
        )
        self.enterContext(
            patch("src.core.projection_intelligence.projection_service", self.f.reader)
        )
        self.measurements = []
        self.requests = []
        self.responses = []

    @contextmanager
    def browser(self, width=390, height=682):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            errors = []
            context = browser.new_context(viewport={"width": width, "height": height})
            context.on(
                "page",
                lambda page: page.on("pageerror", lambda e: errors.append(str(e))),
            )

            def transport(route):
                request = route.request
                url = urlsplit(request.url)
                if url.hostname != "dtos.test":
                    return route.abort()
                start = perf_counter()
                response = self.auth.client.request(
                    request.method,
                    url.path + ("?" + url.query if url.query else ""),
                    content=request.post_data,
                    headers={
                        k: v
                        for k, v in request.headers.items()
                        if k in ("content-type", "x-csrf-token")
                    },
                )
                if request.method == "POST":
                    self.requests.append((url.path, request.post_data_json))
                    self.responses.append(response.json())
                self.measurements.append(
                    {
                        "path": url.path,
                        "method": request.method,
                        "status": response.status_code,
                        "http_ms": round((perf_counter() - start) * 1000, 3),
                    }
                )
                route.fulfill(
                    status=response.status_code,
                    content_type=response.headers.get("content-type", "text/html"),
                    body=response.content,
                )

            context.route("**/*", transport)
            page = context.new_page()
            page.set_default_timeout(15000)
            try:
                yield page
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def ready(self, page, path="/trades/create?front_office=1"):
        page.goto("https://dtos.test" + path)
        page.locator("#trade-context").get_by_text(
            "Active league", exact=False
        ).wait_for()

    def select(self, page, which, pid):
        button = page.locator(f"[data-side={which}]")
        if button.is_visible():
            button.click()
        page.locator(f'#trade-{which}-board button[data-asset-id="{pid}"]').click()

    def state(self, page):
        return page.evaluate(
            "Object.fromEntries(Object.keys(sessionStorage).filter(k=>k.startsWith('dtos-trade-workspace:')).map(k=>[k,JSON.parse(sessionStorage.getItem(k))]))"
        )

    def test_daniels_allen_exact_first_strategy_market_facts_and_phone_decision(self):
        geometry = []
        for width, height in [
            (320, 432),
            (320, 844),
            (375, 667),
            (390, 682),
            (390, 844),
            (1280, 900),
        ]:
            with (
                self.subTest(width=width, height=height),
                self.browser(width, height) as page,
            ):
                self.ready(page)
                page.select_option("#trade-partner", "2")
                self.select(page, "sent", "a")
                self.select(page, "sent", "2029-R1-1")
                self.select(page, "received", "c")
                page.get_by_role("button", name="Evaluate Trade", exact=True).click()
                choose = page.get_by_role(
                    "button", name="Choose analysis strategy", exact=True
                )
                choose.wait_for()
                self.assertIn(
                    "Current evaluation completed · incomplete evidence",
                    page.locator("#trade-result").inner_text(),
                )
                self.assertEqual(page.locator("#trade-result").get_attribute("data-assessment-state"), "fresh_incomplete")
                self.assertNotIn("Previous assessment", page.locator("#trade-result").inner_text())
                report = self.responses[-1]["evaluation"]
                self.assertIsNone(report["recommendation"])
                self.assertEqual(report["market_evidence"]["sent"]["total"], 945)
                self.assertEqual(report["market_evidence"]["received"]["total"], 929)
                self.assertAlmostEqual(
                    report["decision_context"]["lineup"]["delta"], 7.7
                )
                self.assertIn("Choose", page.locator(".tw-decision").inner_text())
                self.assertIn("16", page.locator(".tw-decision-market").inner_text())
                self.assertEqual(
                    page.locator(".tw-evaluation-detail").get_attribute("open"), None
                )
                choose.click()
                self.assertEqual(
                    page.locator("#trade-strategy").evaluate(
                        "e=>e===document.activeElement"
                    ),
                    True,
                )
                page.select_option("#trade-strategy", "WIN NOW")
                page.get_by_role("button", name="Evaluate Trade", exact=True).click()
                page.locator(".dtos-explanation").wait_for()
                updated = self.responses[-1]["evaluation"]
                self.assertIsNotNone(updated["recommendation"])
                self.assertEqual(updated["market_evidence"], report["market_evidence"])
                self.assertEqual(
                    updated["decision_context"]["strategy"]["resolved"], "WIN NOW"
                )
                facts = page.locator(".tw-player-facts > summary")
                facts.focus()
                facts.press("Enter")
                self.assertIn(
                    "Jayden Daniels", page.locator(".tw-player-facts").inner_text()
                )
                self.assertIn(
                    "Market positional rank",
                    page.locator(".tw-player-facts").inner_text(),
                )
                self.assertIn("Week 2", page.locator(".tw-player-facts").inner_text())
                facts.press("Enter")
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"), width
                )
                choose_rect = page.locator(".tw-decision").bounding_box()
                geometry.append(
                    {
                        "width": width,
                        "height": height,
                        "decision_height": round(choose_rect["height"], 2),
                        "market_height": round(
                            page.locator(".tw-decision-market").bounding_box()[
                                "height"
                            ],
                            2,
                        ),
                        "official_verdict": updated["recommendation"],
                        "overflow": False,
                    }
                )
        target = os.environ.get("DTOS_DECISION_BROWSER_EVIDENCE")
        if target:
            Path(target).write_text(
                json.dumps({"geometry": geometry, "http": self.measurements}, indent=2)
            )

    def test_actual_balance_preview_keep_adopt_reload_then_home_fresh_entry(self):
        with self.browser() as page:
            self.ready(page)
            page.select_option("#trade-partner", "2")
            page.select_option("#trade-strategy", "WIN NOW")
            self.select(page, "sent", "a")
            self.select(page, "received", "c")
            original = next(iter(self.state(page).values()))["currentProposal"]
            page.click("#trade-balance-offer")
            page.get_by_role(
                "button", name="Preview adjustment", exact=True
            ).first.wait_for()
            balanced = self.responses[-1]
            self.assertTrue(
                all(
                    "c" in row["proposal"]["assets_received"]
                    for row in balanced["results"]
                )
            )
            self.assertLessEqual(balanced["search_evidence"]["evaluated"], 8)
            page.get_by_role(
                "button", name="Preview adjustment", exact=True
            ).first.click()
            self.assertEqual(
                next(iter(self.state(page).values()))["currentProposal"], original
            )
            page.get_by_role("button", name="Keep original", exact=False).click()
            self.assertEqual(
                next(iter(self.state(page).values()))["currentProposal"], original
            )
            page.get_by_role(
                "button", name="Preview adjustment", exact=True
            ).first.click()
            page.get_by_role("button", name="Adopt alternative", exact=True).click()
            adopted = next(iter(self.state(page).values()))["currentProposal"]
            self.assertIn("c", adopted["received"])
            page.reload()
            page.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                next(iter(self.state(page).values()))["currentProposal"], adopted
            )
            page.goto("https://dtos.test/")
            page.get_by_role(
                "link", name="Build a trade", exact=True
            ).click()
            page.get_by_role("link", name="Build a Trade", exact=False).first.click()
            page.locator("#trade-context").get_by_text(
                "Active league", exact=False
            ).wait_for()
            self.assertEqual(
                next(iter(self.state(page).values()))["currentProposal"],
                {"sent": [], "received": [], "partner": 0},
            )
            self.assertEqual(page.locator("#trade-strategy").input_value(), "WIN NOW")
            self.assertTrue(
                all(path.startswith("/api/trades/") for path, _ in self.requests)
            )

    def test_shop_target_action_status_and_results_precede_optional_controls(self):
        geometry = []
        for width, height in [
            (320, 432),
            (375, 667),
            (390, 682),
            (390, 844),
            (1280, 900),
        ]:
            with self.subTest(width=width), self.browser(width, height) as page:
                self.ready(page, "/trades/shop?front_office=1&asset_id=a")
                page.locator(
                    "#recommendation-status[data-search-state=complete]"
                ).wait_for()
                self.assertEqual(page.evaluate("scrollY"), 0)
                row = {"width": width, "height": height}
                for key, selector in [
                    ("target_y", "#trade-target"),
                    ("find_y", "#trade-find"),
                    ("status_y", "#recommendation-status"),
                    ("results_y", "#trade-result"),
                    ("partner_y", "#trade-partner"),
                    ("board_y", "#trade-board"),
                ]:
                    row[key] = round(page.locator(selector).bounding_box()["y"], 2)
                self.assertLess(row["target_y"], row["find_y"])
                self.assertLess(row["find_y"], row["status_y"])
                self.assertLess(row["results_y"], row["partner_y"])
                self.assertLess(row["partner_y"], row["board_y"])
                find = page.locator("#trade-find")
                find.scroll_into_view_if_needed()
                self.assertTrue(
                    find.evaluate(
                        "e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}"
                    )
                )
                find.focus()
                self.assertTrue(find.evaluate("e=>e===document.activeElement"))
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"), width
                )
                geometry.append(row)
                before = len(self.requests)
                page.select_option("#trade-strategy", "REBUILD")
                self.assertIn(
                    "Not started for this strategy",
                    page.locator("#recommendation-status").inner_text(),
                )
                self.assertTrue(page.locator("#trade-result").is_hidden())
                self.assertEqual(len(self.requests), before)
        target = os.environ.get("DTOS_DECISION_BROWSER_EVIDENCE")
        if target:
            Path(target).with_name("shop-priority-after-geometry.json").write_text(
                json.dumps(geometry, indent=2)
            )

    def test_trade_and_canonical_player_route_share_source_display_precision(self):
        import dtos_app
        from routes.transactions import create_transactions_router

        self.f.points.update(a=20.125, c=24.335)
        self.f.publish()
        from fastapi.staticfiles import StaticFiles

        self.auth.client.app.mount(
            "/static",
            StaticFiles(directory=str(Path(__file__).resolve().parents[1] / "static")),
            name="projection-parity-static",
        )
        self.auth.client.app.include_router(
            create_transactions_router(
                ensure_fresh=AsyncMock(),
                refresh_transactions=AsyncMock(),
                require_data=lambda: self.data,
                state={},
                page=dtos_app.page,
            )
        )
        with (
            patch("routes.transactions.projection_service", self.f.reader),
            self.browser() as page,
        ):
            response = page.goto(
                "https://dtos.test/players/a/projections?front_office=1&week=2"
            )
            self.assertEqual(response.status, 200)
            canonical = page.locator(
                '#player-weekly-projections [data-projection-week="2"]'
            )
            source_display = canonical.inner_text()
            self.assertEqual(
                canonical.get_attribute("data-projection-availability"), "available"
            )
            self.ready(page)
            page.select_option("#trade-partner", "2")
            self.select(page, "sent", "a")
            self.select(page, "received", "c")
            page.get_by_role("button", name="Evaluate Trade", exact=True).click()
            page.locator(".tw-player-facts > summary").click()
            self.assertIn(
                "Sleeper projection: " + source_display + " ·",
                page.locator(".tw-player-facts").inner_text(),
            )
            facts = self.responses[-1]["evaluation"]["player_facts"]["a"]["projection"]
            self.assertEqual(facts["value"], 20.125)
            self.assertEqual(facts["display"], source_display)
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth"), 390
            )
