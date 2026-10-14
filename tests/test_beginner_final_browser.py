"""Released routers/scripts with authenticated disposable state and real Chromium."""

import json
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient

from routes.trades import create_trades_router
from routes.home import create_home_router
from routes.teams import create_teams_router
from routes.transactions import create_transactions_router
from tools.validation.browser_runtime import launch_chromium
from tests import test_trade_workspace_batch1 as boundary


class FinalResetBrowserTests(unittest.TestCase):
    def setUp(self):
        Path(".validation/beginner-final").mkdir(parents=True, exist_ok=True)

    def test_visible_roster_picker_full_reset_and_two_league_intent(self):
        import dtos_app

        f = boundary.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        app = f.client.app
        app.router.routes.clear()
        acquired = f.data["teams"][1]["picks_owned"].pop(0)
        acquired["current_owner_id"] = 1
        from datetime import datetime, timezone
        from src.core.valuation.config import NORMALIZATION_VERSION

        now = datetime.now(timezone.utc).isoformat()
        f.data["market_data"]["pick_quotes"] = {
            "FantasyCalc": [
                {
                    "provider": "FantasyCalc",
                    "market_format": "fc:12:2qb:ppr",
                    "year": 2027,
                    "round": r,
                    "pick_type": "generic_round",
                    "availability": "current",
                    "retrieved_at": now,
                    "value": value * 12,
                    "confidence": 80,
                    "normalization_reference": {
                        "provider": "FantasyCalc",
                        "raw_value": value * 12,
                        "normalized_value": value,
                        "version": NORMALIZATION_VERSION,
                        "generation": "reset-browser-fixture",
                        "method": "provider_range_linear",
                    },
                }
                for r, value in ((1, 200), (2, 100), (3, 75), (4, 50))
            ]
        }
        f.data["teams"][0]["picks_owned"].append(acquired)
        f.data["market_data"]["providers"]["FantasyCalc"]["2-QB-0"]["value"] = 18000
        app.include_router(
            create_trades_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: f.data,
                page=dtos_app.page,
            )
        )
        common = dict(
            ensure_fresh=AsyncMock(), require_data=lambda: f.data, page=dtos_app.page
        )
        app.include_router(create_home_router(**common))
        app.include_router(create_teams_router(**common, state={"data": f.data}))
        app.include_router(
            create_transactions_router(
                **common, refresh_transactions=AsyncMock(), state={"data": f.data}
            )
        )
        static = TestClient(dtos_app.app)
        measurements = []
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
                    page.set_default_timeout(8000)
                    errors = []
                    pending = []
                    hold = [False]
                    requests = []
                    page.on("pageerror", lambda e: errors.append(str(e)))

                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.netloc != "dtos.test":
                            route.abort()
                            return
                        path = url.path + ("?" + url.query if url.query else "")
                        client = (
                            static
                            if url.path.startswith("/static/")
                            and not url.path.endswith(
                                (
                                    "trade_workspace.js",
                                    "trade_workspace.css",
                                    "strategy_session.js",
                                )
                            )
                            else f.client
                        )
                        response = client.request(
                            route.request.method,
                            path,
                            content=route.request.post_data,
                            headers={
                                k: v
                                for k, v in route.request.headers.items()
                                if k in ("content-type", "x-csrf-token")
                            },
                        )
                        if route.request.method == "POST":
                            requests.append(path)
                            self.assertEqual(response.status_code, 200, response.text)
                            if hold[0]:
                                pending.append((route, response))
                                return
                        route.fulfill(
                            status=response.status_code,
                            content_type=response.headers.get(
                                "content-type", "text/html"
                            ),
                            body=response.content,
                        )

                    page.route("**/*", transport)
                    start = time.perf_counter()
                    self.assertEqual(page.goto("https://dtos.test/").status, 200)
                    home_link = page.locator('.ux-action[href$="#full-roster"]')
                    self.assertEqual(
                        home_link.get_attribute("href"), "/teams/1#full-roster"
                    )
                    home_link.click()
                    self.assertTrue(
                        page.locator("#my-team-roster").evaluate("e=>e.open")
                    )
                    page.goto("https://dtos.test/teams/1")
                    first = page.locator("#full-roster .thq-player").first
                    self.assertTrue(first.is_visible())
                    roster_y = first.evaluate(
                        "e=>e.getBoundingClientRect().top + scrollY"
                    )
                    Path(".validation/beginner-final/roster-debug.json").write_text(
                        json.dumps(
                            page.locator(
                                "main > *, .thq-header, .thq-actions, #full-roster, .thq-roster, .thq-room-head, .thq-player"
                            ).evaluate_all(
                                "es=>es.slice(0,30).map(e=>({cls:e.className,id:e.id,text:e.textContent.slice(0,100),y:e.getBoundingClientRect().top,height:e.getBoundingClientRect().height}))"
                            ),
                            indent=2,
                        )
                    )
                    page.screenshot(path=".validation/beginner-final/roster-debug.png")
                    self.assertLess(roster_y, 600, (width, roster_y))
                    if height >= 667:
                        self.assertLess(
                            first.bounding_box()["y"] + first.bounding_box()["height"],
                            height,
                            (width, first.bounding_box()),
                        )
                    self.assertEqual(
                        page.locator("#full-roster .thq-player").count(), 10
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    player = page.locator('#full-roster a[href^="/players/"]').first
                    player.click()
                    page.get_by_role("link", name="← Back to My Team roster").click()
                    self.assertTrue(
                        page.locator("#my-team-roster").evaluate("e=>e.open")
                    )
                    page.goto("https://dtos.test/trades/create")
                    own = page.locator("#trade-sent-board")
                    own.get_by_role("searchbox").wait_for()
                    picker_y = own.locator("button[data-asset-id]").first.evaluate(
                        "e=>e.getBoundingClientRect().top+scrollY"
                    )
                    self.assertLess(picker_y, 900, (width, picker_y))
                    self.assertNotIn("Market evidence", own.inner_text())
                    page.locator("#trade-strategy").select_option("REBUILD")
                    page.get_by_label("Counterparty", exact=True).select_option("2")
                    own.get_by_role(
                        "button", name="Add Player 1-QB-0 — you send", exact=True
                    ).click()
                    own.get_by_role(
                        "button", name="Add Player 1-RB-2 — you send", exact=True
                    ).click()
                    if width < 760:
                        page.locator("[data-side=received]").click()
                    page.locator("#trade-received-board").get_by_role(
                        "button", name="Add Player 2-QB-0 — you receive", exact=True
                    ).click()
                    if width < 760:
                        page.locator("[data-side=sent]").click()
                    own.get_by_role("button", name="PICKS", exact=True).click()
                    own.get_by_role(
                        "button",
                        name="Add 2027 Round 1 (Team 2) — you send",
                        exact=True,
                    ).click()
                    page.locator("#calculator-protect").click()
                    page.locator("#trade-constraint-asset").select_option("1-QB-1")
                    page.locator("#calculator-lock").click()
                    binding = page.evaluate(
                        "Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'))"
                    )
                    before = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", binding
                    )
                    self.assertEqual(len(before["currentProposal"]["sent"]), 3)
                    self.assertIn("2027-R1-2", before["currentProposal"]["sent"])
                    page.locator("#trade-run").click()
                    page.wait_for_function(
                        'Object.entries(sessionStorage).some(([k,v])=>k.startsWith("dtos-trade-workspace:") && JSON.parse(v).currentAssessment)'
                    )
                    page.locator("#trade-balance-offer").click()
                    page.get_by_role(
                        "button", name="Preview adjustment", exact=True
                    ).first.click()
                    previewed = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", binding
                    )
                    self.assertIsNotNone(previewed["previewProposal"])
                    self.assertIsNotNone(previewed["originalProposal"])
                    page.get_by_role("button", name="Keep original", exact=True).click()
                    hold[0] = True
                    page.locator("#trade-run").click()
                    page.wait_for_function(
                        'document.querySelector("#trade-result").textContent.includes("Evaluating")'
                    )
                    self.assertEqual(len(pending), 1)
                    self.assertEqual(pending[0][1].status_code, 200)

                    self.assertIn("1-QB-1", before["protectedAssets"])
                    # Another supported league draft remains independent during cleanup.
                    page.evaluate(
                        "sessionStorage.setItem('dtos-trade-workspace:other-league', JSON.stringify({schema:2,currentProposal:{sent:['foreign-pick'],received:[],partner:3},savedAt:Date.now()}))"
                    )
                    page.on("dialog", lambda dialog: dialog.accept())
                    page.locator("#trade-start-new").click()
                    own = page.locator("#trade-sent-board")
                    own.get_by_role("searchbox").wait_for()
                    for delayed, response in pending:
                        try:
                            delayed.fulfill(
                                status=response.status_code,
                                content_type="application/json",
                                body=response.content,
                            )
                        except Exception as exc:
                            self.assertTrue(
                                any(
                                    word in str(exc).lower()
                                    for word in (
                                        "closed",
                                        "handled",
                                        "cancel",
                                        "invalid",
                                    )
                                ),
                                str(exc),
                            )
                    hold[0] = False
                    page.reload()
                    own.get_by_role("searchbox").wait_for()
                    after = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", binding
                    )
                    self.assertEqual(
                        after["currentProposal"],
                        {"sent": [], "received": [], "partner": 0},
                    )
                    for key in (
                        "requiredOutgoingAsset",
                        "requiredIncomingAsset",
                        "currentAssessment",
                        "previewProposal",
                        "originalProposal",
                        "adoptedProposal",
                    ):
                        self.assertIsNone(after[key])
                    self.assertEqual(after["protectedAssets"], [])
                    self.assertEqual(after["adjustmentConstraints"], {})
                    self.assertEqual(
                        page.locator("#trade-strategy").input_value(), "REBUILD"
                    )
                    other = page.evaluate(
                        "JSON.parse(sessionStorage.getItem('dtos-trade-workspace:other-league'))"
                    )
                    self.assertEqual(other["currentProposal"]["sent"], ["foreign-pick"])
                    page.goto("https://dtos.test/teams/1")
                    page.go_back()
                    own.get_by_role("searchbox").wait_for()
                    self.assertEqual(page.locator("#trade-partner").input_value(), "")
                    page.goto("https://dtos.test/trades/trade-for")
                    page.get_by_label("Counterparty", exact=True).select_option("2")
                    if width < 760:
                        self.assertTrue(
                            page.locator("#trade-received-board").is_visible()
                        )
                    if width < 760:
                        page.locator("[data-side=received]").click()
                    page.locator("#trade-received-board").get_by_role(
                        "button", name="Add Player 2-QB-0 — you receive", exact=True
                    ).click()
                    if width < 760:
                        page.locator("[data-side=sent]").click()
                    page.locator("#trade-sent-board").get_by_role(
                        "button", name="Add Player 1-RB-2 — you send", exact=True
                    ).click()
                    page.locator("#trade-clear-package").click()
                    cleared = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", binding
                    )
                    self.assertEqual(cleared["requiredIncomingAsset"], "2-QB-0")
                    self.assertEqual(cleared["currentProposal"]["sent"], [])
                    self.assertEqual(cleared["currentProposal"]["received"], ["2-QB-0"])
                    self.assertEqual(
                        page.locator("#trade-strategy").input_value(), "REBUILD"
                    )
                    page.reload()
                    # Wait for the actual workspace publication, not the static
                    # tab shell: reload initialization restores the retained
                    # incoming objective and selects the outgoing board. A click
                    # before that publication would be superseded by initialization.
                    page.locator(
                        "#trade-sent-board button[data-asset-id]"
                    ).first.wait_for(state="attached")
                    if width < 760:
                        page.locator("[data-side=received]").click()
                    page.locator("#trade-received-board input[type=search]").wait_for()
                    self.assertEqual(
                        page.evaluate(
                            "key=>JSON.parse(sessionStorage.getItem(key)).requiredIncomingAsset",
                            binding,
                        ),
                        "2-QB-0",
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    first_draft_after_navigation = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", binding
                    )
                    source_scoring = dict(f.data.get("scoring_settings") or {})
                    f.store.upsert_membership(
                        f.account_id,
                        {
                            "league_id": "league-2",
                            "season": "2026",
                            "name": "Second league",
                        },
                        "fixture-user",
                        2,
                        "Team 2",
                        "active",
                    )
                    f.store.activate(f.account_id, "league-2")
                    f.data["league"]["league_id"] = "league-2"
                    f.data["scoring_settings"] = {
                        **source_scoring,
                        "rec": 0.5,
                        "bonus_rec_te": 0.5,
                    }
                    page.goto("https://dtos.test/")
                    second_home = page.locator('.ux-action[href$="#full-roster"]')
                    self.assertEqual(
                        second_home.get_attribute("href"), "/teams/2#full-roster"
                    )
                    second_home.click()
                    self.assertTrue(
                        page.locator("#my-team-roster").evaluate("e=>e.open")
                    )
                    page.goto("https://dtos.test/trades/create?front_office=2")
                    page.locator("#trade-sent-board input[type=search]").wait_for()
                    page.locator("#trade-strategy").select_option("WIN NOW")
                    page.get_by_label("Counterparty", exact=True).select_option("1")
                    page.locator("#trade-sent-board").get_by_role(
                        "button", name="Add Player 2-QB-0 — you send", exact=True
                    ).click()
                    keys = page.evaluate(
                        "Object.keys(sessionStorage).filter(k=>k.startsWith('dtos-trade-workspace:') && k!=='dtos-trade-workspace:other-league')"
                    )
                    second_binding = next(k for k in keys if k != binding)
                    second_draft = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", second_binding
                    )
                    f.store.activate(f.account_id, "league-1")
                    f.data["league"]["league_id"] = "league-1"
                    f.data["scoring_settings"] = source_scoring
                    page.goto("https://dtos.test/trades/create")
                    page.locator("#trade-sent-board input[type=search]").wait_for()
                    self.assertEqual(
                        page.locator("#trade-strategy").input_value(), "REBUILD"
                    )
                    current = page.evaluate(
                        "key=>JSON.parse(sessionStorage.getItem(key))", binding
                    )
                    self.assertEqual(
                        current["currentProposal"],
                        first_draft_after_navigation["currentProposal"],
                    )
                    self.assertEqual(current["protectedAssets"], [])
                    self.assertEqual(
                        page.evaluate(
                            "key=>JSON.parse(sessionStorage.getItem(key)).currentProposal",
                            second_binding,
                        ),
                        second_draft["currentProposal"],
                    )
                    self.assertTrue(requests)
                    self.assertTrue(
                        all(path.startswith("/api/trades/") for path in requests)
                    )
                    self.assertEqual(errors, [])
                    measurements.append(
                        {
                            "width": width,
                            "height": height,
                            "roster_first_y": roster_y,
                            "picker_first_y": picker_y,
                            "journey_ms": round(
                                (time.perf_counter() - start) * 1000, 2
                            ),
                        }
                    )
                    page.close()
            finally:
                browser.close()
        target = Path(".validation/beginner-final")
        target.mkdir(parents=True, exist_ok=True)
        (target / "browser-geometry.json").write_text(
            json.dumps(measurements, indent=2)
        )


class FinalNavigationBrowserTests(unittest.TestCase):
    def test_pick_market_origin_and_read_only_franchise_routes(self):
        import dtos_app
        from routes.historical_assets import create_historical_assets_router
        from routes.hq import create_hq_router
        from tests import test_beginner_market as market_base

        f = market_base.BeginnerMarketTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.fixture.data
        data.update(
            week=1,
            scoring_settings={"rec": 1},
            league_settings={},
            matchups={},
            transactions=[],
            roster_positions=["QB", "RB", "WR", "TE"],
        )
        data["league"]["season"] = "2026"
        from routes.market import create_market_router
        from types import SimpleNamespace

        f.client.app.router.routes.clear()
        f.client.app.include_router(
            create_market_router(
                require_data=lambda: data,
                page=dtos_app.page,
                state=f.fixture.state,
                league_id=f.fixture.league_id,
                context_resolver=lambda: SimpleNamespace(
                    state=f.fixture.state,
                    league_id=f.fixture.league_id,
                    market=f.fixture.cache,
                ),
            )
        )
        f.client.app.include_router(
            create_historical_assets_router(
                league_id="league-1", require_data=lambda: data, page=dtos_app.page
            )
        )
        f.client.app.include_router(
            create_transactions_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: data,
                refresh_transactions=AsyncMock(),
                state=f.fixture.state,
                page=dtos_app.page,
            )
        )
        owner = boundary.AuthenticatedTradeBoundaryTests()
        owner.setUp()
        self.addCleanup(owner.doCleanups)
        owner.data["teams"][1]["team_name"] = "Runaway McBride"
        from src.core.accounts import AccountService
        from src.platform.account_context import AccountContextMiddleware

        f.client.app.add_middleware(
            AccountContextMiddleware, service=AccountService(owner.store), required=True
        )
        f.client.cookies.update(owner.client.cookies)
        common = dict(
            ensure_fresh=AsyncMock(),
            require_data=lambda: owner.data,
            page=dtos_app.page,
        )
        owner.client.app.include_router(create_home_router(**common))
        owner.client.app.include_router(
            create_teams_router(**common, state={"data": owner.data})
        )
        owner.client.app.include_router(
            create_hq_router(**common, state={"data": owner.data}, league_id="league-1")
        )
        static = TestClient(dtos_app.app)
        with (
            patch("routes.historical_assets.historical_store", f.fixture.store),
            patch.object(dtos_app, "account_store", owner.store),
            sync_playwright() as pw,
        ):
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
                    page.set_default_timeout(10000)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))

                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.netloc != "dtos.test":
                            return route.abort()
                        path = url.path + ("?" + url.query if url.query else "")
                        if url.path.startswith("/static/"):
                            response = static.get(path)
                        elif url.path.startswith(
                            ("/market", "/api/market", "/picks/", "/players/")
                        ):
                            response = f.get(path)
                        else:
                            response = owner.client.request(
                                route.request.method,
                                path,
                                content=route.request.post_data,
                            )
                        route.fulfill(
                            status=response.status_code,
                            content_type=response.headers.get(
                                "content-type", "text/html"
                            ),
                            body=response.content,
                        )

                    page.route("**/*", transport)
                    page.goto(
                        "https://dtos.test/market?q=2029+Round+2&position=PICK&availability=owned_pick&sort=confidence&direction=asc&limit=10&front_office=1"
                    )
                    self.assertEqual(page.locator(".market-asset").count(), 3)
                    page.locator(".market-asset").first.click()
                    selected = page.url.split("#")[0]
                    page.get_by_role("link", name="Open canonical dossier").click()
                    self.assertIn("/picks/", page.url)
                    page.reload()
                    back = page.get_by_role("link", name="← Back to Market results")
                    back.click()
                    self.assertEqual(page.url, selected)
                    self.assertEqual(page.locator(".market-asset").count(), 3)
                    page.go_back()
                    self.assertIn("/picks/", page.url)
                    page.go_forward()
                    self.assertEqual(page.url, selected)
                    page.goto(
                        "https://dtos.test/market?position=PICK&sort=confidence&direction=asc&offset=10&limit=10&front_office=1"
                    )
                    self.assertGreater(page.locator(".market-asset").count(), 0)
                    page.locator(".market-asset").first.click()
                    offset_selected = page.url.split("#")[0]
                    page.get_by_role("link", name="Open canonical dossier").click()
                    # A newer explicit Market origin wins over stale team context.
                    page.goto(page.url + "&from_team=1")
                    page.get_by_role("link", name="← Back to Market results").click()
                    self.assertEqual(page.url, offset_selected)
                    self.assertIn("offset=10", page.url)
                    page.goto(
                        "https://dtos.test/market?q=free+agents+Boston&availability=taxi"
                    )
                    self.assertEqual(page.locator(".market-asset").count(), 0)
                    page.goto("https://dtos.test/")
                    page.get_by_text("View another franchise", exact=True).click()
                    page.locator("#front-office").select_option("2")
                    page.get_by_role(
                        "button", name="View franchise", exact=True
                    ).click()
                    self.assertIn("/teams/2", page.url)
                    self.assertIn(
                        "Runaway McBride", page.locator(".thq-title").inner_text()
                    )
                    self.assertEqual(page.locator("#my-team-strategy").count(), 0)
                    self.assertEqual(page.locator('a[href^="/trades/shop"]').count(), 0)
                    self.assertIn(
                        "Read-only",
                        page.get_by_role(
                            "navigation", name="Read-only franchise navigation"
                        ).inner_text(),
                    )
                    page.reload()
                    page.get_by_role("link", name="Back to Home", exact=True).click()
                    self.assertIn("Team 1", page.locator("main").inner_text())
                    page.go_back()
                    self.assertIn("/teams/2", page.url)
                    page.go_forward()
                    owner.store.upsert_membership(
                        owner.account_id,
                        {"league_id": "league-2", "season": "2026", "name": "Other"},
                        "fixture-user",
                        2,
                        "Second controlled franchise",
                        "active",
                    )
                    owner.store.activate(owner.account_id, "league-2")
                    owner.data["league"]["league_id"] = "league-2"
                    page.goto("https://dtos.test/")
                    page.get_by_text("View another franchise", exact=True).click()
                    page.locator("#front-office").select_option("1")
                    page.get_by_role(
                        "button", name="View franchise", exact=True
                    ).click()
                    self.assertIn("Team 1", page.locator(".thq-title").inner_text())
                    self.assertEqual(page.locator("#my-team-strategy").count(), 0)
                    self.assertEqual(page.locator('a[href^="/trades/shop"]').count(), 0)
                    owner.store.activate(owner.account_id, "league-1")
                    owner.data["league"]["league_id"] = "league-1"
                    page.goto("https://dtos.test/commissioner")
                    self.assertEqual(
                        page.locator(".cd-intelligence").last.locator("b").count(), 17
                    )
                    for text in (
                        page.locator(".cd-intelligence")
                        .last.locator("b")
                        .all_text_contents()
                    ):
                        self.assertNotIn(text, ("None", "null", "NaN", "nan"))
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertEqual(errors, [])
                    page.screenshot(
                        path=f".validation/beginner-final/navigation-{width}-{height}.png"
                    )
                    page.close()
            finally:
                browser.close()
