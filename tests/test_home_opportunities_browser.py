"""Rendered authenticated routes and canonical client preview lifecycle.

Positive assessment fixtures are controlled, not real Day/Ark recommendations.
"""

import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from routes.home import create_home_router
from services import home_trade_opportunities as ideas
from tests import test_trade_workspace_batch1 as boundary
from tests import test_home_opportunities as fixtures


class HomeOpportunityBrowserTests(unittest.TestCase):
    def test_cached_home_preview_keep_adopt_reload_scope_and_pending_intent(self):
        import dtos_app

        f = boundary.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        app = f.client.app
        # Keep authenticated middleware + actual registered Trade router/static assets.
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: f.data,
                page=dtos_app.page,
            )
        )
        from routes.trades import create_trades_router

        app.router.routes.clear()
        app.include_router(
            create_trades_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: f.data,
                page=dtos_app.page,
            )
        )
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: f.data,
                page=dtos_app.page,
            )
        )
        static = TestClient(dtos_app.app)
        row = fixtures.supported_row(f.data)
        bad = fixtures.supported_row(f.data, "1-RB-2", "3-RB-2", "NOT WORTH IT", 3)
        result = {
            "workflow": "recommended",
            "results": [row],
            "exploratory_results": [bad],
            "result_state": "COMPLETE",
        }
        with ideas._lock:
            ideas._entries.clear()
        measurements = []
        with (
            patch("routes.trades.generate_trade_workflow", return_value=result),
            patch.object(dtos_app, "account_store", f.store),
            sync_playwright() as pw,
        ):
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in (
                    (320, 568),
                    (375, 667),
                    (390, 844),
                    (390, 432),
                    (1280, 900),
                ):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_default_timeout(10000)
                    errors = []
                    requests = []
                    pending = []
                    hold = [False]
                    page.on("pageerror", lambda e: errors.append(str(e)))

                    def transport(route):
                        u = urlsplit(route.request.url)
                        if u.netloc != "dtos.test":
                            return route.abort()
                        requests.append(u.path)
                        if hold[0] and u.path == "/api/trades/generate":
                            pending.append(route)
                            return
                        cookies = route.request.headers.get("cookie", "")
                        raw = next(
                            (
                                x.split("=", 1)[1]
                                for x in cookies.split("; ")
                                if x.startswith("dtos_strategy=")
                            ),
                            None,
                        )
                        if raw:
                            f.client.cookies.set("dtos_strategy", raw)
                        else:
                            f.client.cookies.delete("dtos_strategy")
                        target = (
                            static
                            if u.path.startswith("/static/")
                            and not u.path.endswith(
                                (
                                    "trade_workspace.js",
                                    "trade_workspace.css",
                                    "strategy_session.js",
                                    "home-opportunities.js",
                                )
                            )
                            else f.client
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

                    page.route("**/*", transport)
                    page.goto("https://dtos.test/")
                    page.wait_for_function(
                        "document.querySelector('#home-opportunities').dataset.state"
                    )
                    before = requests.count("/api/trades/generate")
                    self.assertEqual(before, 0)
                    page.locator("#home-find-ideas").click()
                    page.locator(".home-opportunity").first.wait_for()
                    self.assertEqual(page.locator(".home-opportunity").count(), 2)
                    self.assertIn(
                        "RECOMMENDED",
                        page.locator(".home-opportunity").first.inner_text(),
                    )
                    self.assertIn(
                        "NOT WORTH IT",
                        page.locator(".home-opportunity").nth(1).inner_text(),
                    )
                    self.assertEqual(
                        page.evaluate(
                            "document.documentElement.scrollWidth<=innerWidth"
                        ),
                        True,
                    )
                    dimensions = page.evaluate("""() => ({width:innerWidth,identity:document.querySelector('.ux-feature').getBoundingClientRect().top+scrollY,
                      actions:document.querySelector('.ux-feature-actions').getBoundingClientRect().top+scrollY,
                      cards:[...document.querySelectorAll('.home-opportunity')].map(x=>x.getBoundingClientRect().height)})""")
                    measurements.append(dimensions)
                    # Genuinely populated original draft, scoped to current authenticated binding.
                    meta = f.client.get(
                        "/api/trades/home-opportunities?front_office=1"
                    ).json()
                    page.evaluate(
                        """meta => sessionStorage.setItem('dtos-trade-workspace:'+meta.workspace_context.binding,JSON.stringify({schema:2,
                      currentProposal:{sent:['1-RB-2'],received:['2-RB-2'],partner:2},protectedAssets:[],excludedAssets:[],strategy:'',
                      ownership:meta.workspace_context.ownership_generation}))""",
                        meta,
                    )
                    page.locator(".home-opportunity").first.get_by_role(
                        "link", name="Explore / Edit"
                    ).click()
                    page.get_by_text("Alternative preview", exact=True).wait_for()
                    page.get_by_role("button", name="Keep original", exact=True).click()
                    self.assertIn(
                        "1-RB-2", page.locator("#trade-sent-chips").inner_text()
                    )
                    page.reload()
                    page.locator(
                        "#trade-sent-board button[data-asset-id]"
                    ).first.wait_for(state="attached")
                    self.assertEqual(
                        page.get_by_text("Alternative preview", exact=True).count(), 0
                    )
                    self.assertIn(
                        "1-RB-2", page.locator("#trade-sent-chips").inner_text()
                    )
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").first.wait_for()
                    page.locator(".home-opportunity").first.get_by_role(
                        "link", name="Explore / Edit"
                    ).click()
                    page.get_by_role(
                        "button", name="Adopt alternative", exact=True
                    ).click()
                    page.locator(
                        '#trade-sent-board button[data-asset-id="1-QB-0"]'
                    ).wait_for(state="attached")
                    self.assertIn(
                        "1-QB-0", page.locator("#trade-sent-chips").inner_text()
                    )
                    page.reload()
                    page.locator(
                        '#trade-sent-board button[data-asset-id="1-QB-0"]'
                    ).wait_for(state="attached")
                    self.assertNotIn(
                        "1-RB-2", page.locator("#trade-sent-chips").inner_text()
                    )
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").first.wait_for()
                    page.reload()
                    page.locator(".home-opportunity").first.wait_for()
                    # Actual authenticated A -> B -> A HTTP/browser isolation, same local roster IDs.
                    original_name = f.data["teams"][0]["team_name"]
                    f.store.upsert_membership(
                        f.account_id,
                        {"league_id": "league-2", "season": "2026", "name": "Separate"},
                        "fixture-user",
                        1,
                        "Separate Franchise",
                        "active",
                    )
                    f.store.activate(f.account_id, "league-2")
                    f.data["league"]["league_id"] = "league-2"
                    f.data["teams"][0]["team_name"] = "Separate Franchise"
                    page.goto("https://dtos.test/")
                    page.wait_for_function(
                        "document.querySelector('#home-opportunities').dataset.state"
                    )
                    self.assertEqual(page.locator(".home-opportunity").count(), 0)
                    self.assertIn(
                        "Separate Franchise", page.locator(".ux-feature").inner_text()
                    )
                    f.store.activate(f.account_id, "league-1")
                    f.data["league"]["league_id"] = "league-1"
                    f.data["teams"][0]["team_name"] = original_name
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").first.wait_for()
                    self.assertEqual(page.locator(".home-opportunity").count(), 2)
                    # Different explicit strategy invalidates cached assessments and pending result.
                    page.evaluate(
                        """async () => {const m=await (await fetch('/api/trades/home-opportunities?front_office=1')).json();window.dtosStrategy.set(m.workspace_context,'REBUILD');window.dispatchEvent(new Event('focus'));}"""
                    )
                    page.wait_for_function(
                        "document.querySelectorAll('.home-opportunity').length===0"
                    )
                    hold[0] = True
                    page.locator("#home-find-ideas").click()
                    page.wait_for_function(
                        "document.querySelector('#home-opportunities').dataset.state==='loading'"
                    )
                    page.evaluate(
                        """async () => {const m=await (await fetch('/api/trades/home-opportunities?front_office=1')).json();window.dtosStrategy.set(m.workspace_context,'WIN NOW');window.dispatchEvent(new Event('focus'));}"""
                    )
                    page.wait_for_function(
                        "document.querySelector('#home-opportunities').dataset.state!=='loading'"
                    )
                    for r in pending:
                        r.abort()
                    pending.clear()
                    hold[0] = False
                    self.assertEqual(page.locator(".home-opportunity").count(), 0)
                    page.get_by_role("link", name="Explore more trades").click()
                    page.wait_for_url("**/trades/recommended?front_office=1")
                    page.locator(
                        "#trade-sent-board button[data-asset-id]"
                    ).first.wait_for()
                    self.assertEqual(
                        page.locator("#trade-strategy").input_value(), "WIN NOW"
                    )
                    self.assertEqual(
                        page.evaluate(
                            "document.documentElement.scrollWidth<=innerWidth"
                        ),
                        True,
                    )
                    self.assertEqual(errors, [])
                    page.close()
            finally:
                browser.close()
        folder = Path(".validation/home-opportunities")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "browser-geometry.json").write_text(
            json.dumps(measurements, indent=2)
        )


if __name__ == "__main__":
    unittest.main()
