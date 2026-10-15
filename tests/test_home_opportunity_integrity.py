"""Real publication/evaluator/HTTP and released-client adoption integrity.

All ownership changes are isolated canonical fixtures, never Sleeper writes.
"""

import base64
import copy
import json
import unittest
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from routes.home import create_home_router
from routes.trades import create_trades_router
from services import home_trade_opportunities as ideas
from src.ui.home_trade_opportunities import cards
from tests import test_capital_strategy_reconciliation as capital
from tests import test_trade_workspace_batch1 as boundary
from tools.validation.browser_runtime import launch_chromium


class OpportunityIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.f = boundary.AuthenticatedTradeBoundaryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.source = capital.CapitalStrategyTests()
        self.source.setUp()
        self.addCleanup(self.source.doCleanups)
        self.f.data.clear()
        self.f.data.update(self.source.data)
        self.source.data = self.f.data
        self.enterContext(
            patch(
                "services.trade_intelligence._trade_projection_service",
                return_value=self.source.reader,
            )
        )
        import dtos_app

        self.enterContext(patch.object(dtos_app, "account_store", self.f.store))
        app = self.f.client.app
        app.router.routes.clear()
        kwargs = dict(
            ensure_fresh=AsyncMock(),
            require_data=lambda: self.f.data,
            page=dtos_app.page,
        )
        app.include_router(create_trades_router(**kwargs))
        app.include_router(create_home_router(**kwargs))
        self.static = TestClient(dtos_app.app)
        self.workspace = self.f.client.get(
            "/api/trades/workspace?front_office=1"
        ).json()
        ctx = self.workspace["workspace_context"]
        self.cookie = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "scope": ctx["strategy_scope"],
                        "rows": [["league-1:1", "REBUILD"]],
                    }
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
        self.f.client.cookies.set("dtos_strategy", self.cookie)
        self.payload = dict(
            workflow="recommended",
            active_roster_id=1,
            partner_roster_id=2,
            strategy="REBUILD",
            assets_sent=["a"],
            assets_received=["2028-R1-4"],
            workspace_context=ctx,
        )
        self.row = self.evaluate().json()
        self.assertEqual(self.row["evaluation"]["recommendation"], "WORTH PURSUING")
        self.assertTrue(self.row["evaluation"]["generated_trade_eligible"])
        self.assertEqual(
            self.row["evaluation"]["legality"]["execution_status"],
            "NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER",
        )
        with ideas._lock:
            ideas._entries.clear()
        self.addCleanup(ideas._entries.clear)
        self.seed()

    def evaluate(self):
        return self.f.client.post(
            "/api/trades/evaluate",
            json=self.payload,
            headers={"X-CSRF-Token": self.f.csrf},
        )

    def seed(self):
        meta = self.f.client.get("/api/trades/home-opportunities?front_office=1").json()
        key = (
            meta["workspace_context"]["binding"],
            meta["source_identity"],
            "REBUILD",
            (),
            (),
        )
        ideas.publish(key, {"results": [self.row]}, self.payload)
        self.meta = self.f.client.get(
            "/api/trades/home-opportunities?front_office=1"
        ).json()
        self.assertEqual(self.meta["count"], 1)
        self.token = ideas.read(key)["rows"][0]["home_offer"]

    def move(self):
        player = self.f.data["teams"][0]["players"].pop(0)
        self.f.data["teams"][1]["players"].append(player)
        return player

    def test_real_qualifying_offer_token_and_evaluation_reject_changed_ownership(self):
        self.move()
        r = self.f.client.get(
            "/api/trades/home-opportunities",
            params={"front_office": 1, "offer": self.token},
        )
        self.assertEqual(r.status_code, 410)
        r = self.evaluate()
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "ownership_changed")

    def test_semantic_assessment_identity_tracks_publications_not_offer_or_retrieval_clock(
        self,
    ):
        old = self.row["assessment_source_identity"]
        self.assertEqual(self.evaluate().json()["assessment_source_identity"], old)
        self.f.data["last_sync"] = "2099-01-01"
        self.assertEqual(self.evaluate().json()["assessment_source_identity"], old)
        self.source.points["c"] = 20
        self.source.publish()
        self.assertNotEqual(self.evaluate().json()["assessment_source_identity"], old)
        projection = self.evaluate().json()["assessment_source_identity"]
        self.source.prices(a=300)
        self.f.data["market_data"] = self.source.data["market_data"]
        self.f.client.get("/api/trades/workspace")
        self.assertNotEqual(
            self.evaluate().json()["assessment_source_identity"], projection
        )
        self.payload["assets_sent"] = ["b"]
        source = self.evaluate().json()["assessment_source_identity"]
        self.payload["assets_sent"] = ["e"]
        self.assertEqual(self.evaluate().json()["assessment_source_identity"], source)

    def test_source_change_during_http_evaluation_fails_closed(self):
        from services import trade_intelligence

        original = trade_intelligence.evaluate_trade_request

        def interrupted(*args, **kwargs):
            value = original(*args, **kwargs)
            self.source.points["c"] += 1
            self.source.publish()
            return value

        with patch("routes.trades.evaluate_trade_request", side_effect=interrupted):
            result = self.evaluate()
        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.json()["detail"]["code"], "canonical_evidence_changed")

    def test_home_package_reason_drawback_and_unfavorable_honesty(self):
        row = copy.deepcopy(self.row)
        row["home_offer"] = "opaque"
        row["evaluation"]["dominant_reason"] = "Generic methodology"
        for label in ("WORTH PURSUING", "NOT WORTH IT", "REJECT", None):
            row["evaluation"]["recommendation"] = label
            row["exploration"] = label != "WORTH PURSUING"
            html = cards([row], 1)
            primary = html.split("<b>Why consider:</b>", 1)[1].split("</p>", 1)[0]
            self.assertNotIn("Generic methodology", primary)
            self.assertIn(row["evaluation"]["why_you_would_do_it"], primary)
            if label in ("REJECT", "NOT WORTH IT"):
                self.assertIn("Not endorsed.", primary)
            self.assertIn(row["evaluation"]["major_drawback"], html)
        row["evaluation"].pop("why_you_would_do_it")
        self.assertIn("No supported positive strategic case", cards([row], 1))
        self.assertEqual(cards([], 1), "")

    def transport(self, route):
        u = urlsplit(route.request.url)
        if u.netloc != "dtos.test":
            return route.abort()
        cookie = next(
            (
                x.split("=", 1)[1]
                for x in route.request.headers.get("cookie", "").split("; ")
                if x.startswith("dtos_strategy=")
            ),
            None,
        )
        if cookie:
            self.f.client.cookies.set("dtos_strategy", cookie)
        target = (
            self.static
            if u.path.startswith("/static/")
            and not u.path.endswith(
                (
                    "trade_workspace.js",
                    "trade_workspace.css",
                    "strategy_session.js",
                    "home-opportunities.js",
                )
            )
            else self.f.client
        )
        r = target.request(
            route.request.method,
            u.path + ("?" + u.query if u.query else ""),
            content=route.request.post_data,
            headers={
                k: v
                for k, v in route.request.headers.items()
                if k in ("content-type", "x-csrf-token")
            },
        )
        route.fulfill(
            status=r.status_code,
            content_type=r.headers.get("content-type"),
            body=r.content,
        )

    def browser_page(self, browser, width=390, height=844):
        page = browser.new_page(viewport=dict(width=width, height=height))
        page.set_default_timeout(15000)
        page.context.add_cookies(
            [dict(name="dtos_strategy", value=self.cookie, url="https://dtos.test/")]
        )
        page.route("**/*", self.transport)
        return page

    def test_released_browser_stale_adoption_retains_package_and_reevaluates(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in (
                    (320, 568),
                    (375, 667),
                    (390, 682),
                    (390, 844),
                    (1280, 900),
                ):
                    page = self.browser_page(browser, width, height)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").wait_for()
                    self.assertIn(
                        self.row["evaluation"]["why_you_would_do_it"],
                        page.locator(".home-opportunity").inner_text(),
                    )
                    page.get_by_role("link", name="Explore / Edit").click()
                    page.get_by_text("Alternative preview", exact=True).wait_for()
                    moved = self.move()
                    page.get_by_role(
                        "button", name="Adopt alternative", exact=True
                    ).click()
                    result = page.locator("#trade-result")
                    self.assertIn("NOT REVALIDATED", result.inner_text())
                    self.assertEqual(
                        result.get_attribute("data-assessment-freshness"), "retained"
                    )
                    conclusion = result.locator("[data-retained-conclusion]")
                    self.assertIn(
                        "NOT REVALIDATED",
                        conclusion.evaluate(
                            "e => getComputedStyle(e,'::after').content"
                        ),
                    )
                    self.assertIn(
                        "not revalidated", conclusion.get_attribute("aria-label")
                    )
                    self.assertNotIn(
                        "NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER",
                        result.inner_text(),
                    )
                    self.assertIn(
                        "Previous execution assessment (not current)",
                        result.text_content(),
                    )
                    state = page.evaluate(
                        "() => JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'))))"
                    )
                    self.assertEqual(state["currentProposal"]["sent"], ["a"])
                    self.assertEqual(
                        state["currentProposal"]["received"], ["2028-R1-4"]
                    )
                    self.assertEqual(state["strategy"], "REBUILD")
                    self.assertTrue(state["currentAssessment"]["identity"]["source"])
                    page.get_by_role("button", name="Reevaluate Trade").click()
                    page.get_by_text(
                        "Current ownership blocker:", exact=False
                    ).wait_for()
                    self.assertEqual(
                        result.get_attribute("data-assessment-freshness"), "retained"
                    )
                    self.f.data["teams"][1]["players"].remove(moved)
                    self.f.data["teams"][0]["players"].insert(0, moved)
                    page.reload()
                    page.get_by_role("button", name="Reevaluate Trade").wait_for()
                    self.assertIn("NOT REVALIDATED", result.inner_text())
                    page.get_by_role("button", name="Reevaluate Trade").focus()
                    self.assertEqual(
                        page.evaluate("document.activeElement.dataset.reevaluate"),
                        "true",
                    )
                    page.keyboard.press("Enter")
                    page.wait_for_function(
                        "document.querySelector('#trade-result').dataset.assessmentFreshness==='current'"
                    )
                    self.assertIn("WORTH PURSUING", result.inner_text())
                    self.assertEqual(
                        page.locator("#trade-strategy").input_value(), "REBUILD"
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertEqual(errors, [])
                    page.close()
                    self.seed()
            finally:
                browser.close()

    def test_repeated_focus_visibility_pageshow_context_change_reload(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = self.browser_page(browser)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto("https://dtos.test/")
                page.locator(".home-opportunity").wait_for()
                self.f.store.upsert_membership(
                    self.f.account_id,
                    {"league_id": "league-2", "season": "2026", "name": "Other"},
                    "fixture-user",
                    1,
                    "Other",
                    "active",
                )
                self.f.store.activate(self.f.account_id, "league-2")
                self.f.data["league"]["league_id"] = "league-2"
                page.evaluate("dispatchEvent(new Event('focus'))")
                page.wait_for_function(
                    "document.querySelector('#home-opportunities').dataset.state==='context_changed'"
                )
                page.evaluate("for(let i=0;i<6;i++)dispatchEvent(new Event('focus'))")
                self.assertEqual(errors, [])
                page.evaluate(
                    "for(let i=0;i<6;i++){dispatchEvent(new Event('focus'));document.dispatchEvent(new Event('visibilitychange'));dispatchEvent(new Event('pageshow'));}"
                )
                self.assertEqual(page.locator(".home-opportunity").count(), 0)
                self.assertTrue(page.locator("#home-find-ideas").is_disabled())
                page.get_by_role("button", name="Reload Home").focus()
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "document.querySelector('#home-opportunities').dataset.state==='NOT SEARCHED'"
                )
                self.assertEqual(page.locator(".home-opportunity").count(), 0)
                self.f.store.activate(self.f.account_id, "league-1")
                self.f.data["league"]["league_id"] = "league-1"
                page.reload()
                page.locator(".home-opportunity").wait_for()
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_released_browser_market_projection_strategy_and_incomplete_reevaluation(
        self,
    ):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for change in ("market", "projection", "strategy", "unchanged"):
                    page = self.browser_page(browser)
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").wait_for()
                    page.get_by_role("link", name="Explore / Edit").click()
                    page.get_by_text("Alternative preview", exact=True).wait_for()
                    if change == "market":
                        self.source.prices(a=300)
                        self.f.data["market_data"] = self.source.data["market_data"]
                    elif change == "projection":
                        self.source.points["f"] += 1
                        self.source.publish()
                    elif change == "strategy":
                        page.locator("#trade-strategy").select_option("WIN NOW")
                        # A deliberate strategy edit closes the old preview.
                        # Reload retains its exact package only after adoption;
                        # no old response may turn the prior strategy current.
                        self.assertFalse(
                            page.get_by_role(
                                "button", name="Adopt alternative", exact=True
                            ).is_visible()
                        )
                        page.close()
                        self.f.client.cookies.set("dtos_strategy", self.cookie)
                        self.seed()
                        continue
                    page.get_by_role(
                        "button", name="Adopt alternative", exact=True
                    ).click()
                    self.assertEqual(
                        page.locator("#trade-result").get_attribute(
                            "data-assessment-freshness"
                        ),
                        "retained",
                    )
                    self.assertIn(
                        "NOT REVALIDATED", page.locator("#trade-result").inner_text()
                    )
                    page.get_by_role("button", name="Reevaluate Trade").click()
                    try:
                        page.wait_for_function(
                            "document.querySelector('#trade-result').dataset.assessmentFreshness==='current'"
                        )
                    except Exception as error:
                        raise AssertionError(
                            (change, page.locator("#trade-result").inner_text())
                        ) from error
                    fresh = page.evaluate(
                        "JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:')))).currentAssessment.identity.source"
                    )
                    if change == "unchanged":
                        self.assertEqual(fresh, self.meta["source_identity"])
                    else:
                        self.assertNotEqual(fresh, self.meta["source_identity"])
                    # Actual incomplete canonical pricing cannot make the old
                    # qualifying assessment current again.
                    previous = page.evaluate(
                        "JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:')))).currentAssessment"
                    )
                    saved = self.f.data["market_data"]
                    self.f.data["market_data"] = {}
                    page.locator("#trade-run").click()
                    page.wait_for_function(
                        "document.querySelector('#trade-result').dataset.assessmentFreshness==='retained'"
                    )
                    self.assertIn(
                        "not revalidated", page.locator("#trade-result").inner_text()
                    )
                    retained = page.evaluate(
                        "JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:')))).currentAssessment"
                    )
                    self.assertEqual(
                        retained["identity"]["source"], previous["identity"]["source"]
                    )
                    self.assertEqual(
                        retained["identity"]["strategy"],
                        previous["identity"]["strategy"],
                    )
                    for key in (
                        "recommendation",
                        "why_you_would_do_it",
                        "major_drawback",
                        "major_limitations",
                    ):
                        self.assertEqual(
                            retained["evaluation"].get(key),
                            previous["evaluation"].get(key),
                        )
                    self.assertIn(
                        "Latest incomplete evaluation",
                        page.locator("#trade-result").inner_text(),
                    )
                    self.f.data["market_data"] = saved
                    page.close()
                    self.f.client.cookies.set("dtos_strategy", self.cookie)
                    self.f.client.get("/api/trades/workspace")
                    self.seed()
            finally:
                browser.close()

    def test_released_browser_new_strategy_rejects_delayed_actual_evaluation(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = self.browser_page(browser)
                page.goto("https://dtos.test/")
                page.locator(".home-opportunity").wait_for()
                page.get_by_role("link", name="Explore / Edit").click()
                page.get_by_role("button", name="Adopt alternative", exact=True).click()
                pending = []
                page.route(
                    "**/api/trades/evaluate", lambda route: pending.append(route)
                )
                page.get_by_role("button", name="Reevaluate Trade").click()
                page.wait_for_function("document.querySelector('#trade-run').disabled")
                page.locator("#trade-strategy").select_option("WIN NOW")
                self.assertEqual(len(pending), 1)
                # The old response is a real successful current-server evaluation
                # of its frozen REBUILD request, not a JavaScript assessment stub.
                response = self.f.client.post(
                    "/api/trades/evaluate",
                    json=json.loads(pending[0].request.post_data),
                    headers={"X-CSRF-Token": self.f.csrf},
                )
                self.assertEqual(response.status_code, 200)
                pending[0].fulfill(
                    status=200, content_type="application/json", body=response.content
                )
                page.wait_for_function("!document.querySelector('#trade-run').disabled")
                self.assertEqual(
                    page.locator("#trade-strategy").input_value(), "WIN NOW"
                )
                self.assertFalse(page.locator("#trade-result").is_visible())
                state = page.evaluate(
                    "JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'))))"
                )
                self.assertEqual(state["currentProposal"]["sent"], ["a"])
                self.assertIsNone(state["currentAssessment"])
                self.assertEqual(state["strategy"], "WIN NOW")
            finally:
                browser.close()
