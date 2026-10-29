"""Resident source -> account HTTP -> bounded Market preparation UI controls.

No private/live source data. Controlled Chromium is not physical Safari.
"""

import copy
from contextlib import ExitStack
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.background import BackgroundTask
from starlette.responses import HTMLResponse
from playwright.sync_api import sync_playwright

from routes.market_preparation import create_market_preparation_router
from routes.navigation import create_navigation_router
from services.contextual_navigation import navigation_markup, with_back
from services.market_preparation import observe_resident_market, presentation
from src.core.asset_market import AssetMarketCache
from src.core.league_runtime.manager import LeagueRuntime, RuntimeState
from src.platform.account_context import AccountContextMiddleware
from src.platform.league_context import LeagueContextMiddleware
from src.platform.market_warming import warming_page
from tests import test_personal_rankings as personal
from tests import test_contextual_back as back
from tools.validation.browser_runtime import launch_chromium


class MarketPreparationTests(unittest.TestCase):
    def fixture(self):
        e = personal.PersonalRankingsHTTPTests(
            "test_full_seed_matches_market_and_reads_create_no_rows"
        )
        e.setUp()
        self.addCleanup(e.doCleanups)
        e.initialize()
        saved = e.state()
        original_client = e.client
        data = e.data
        data["asset_market_semantic_revision"] = "fixture-A"
        store = object()
        cache = AssetMarketCache()
        runtime = LeagueRuntime(
            "league-1", state={"data": data}, status=RuntimeState.WARM
        )
        runtime.market_context = cache
        manager = SimpleNamespace(
            resident=lambda league: runtime if league == runtime.league_id else None,
            acquire_request=AsyncMock(return_value=runtime),
            release_request=AsyncMock(),
        )
        app = FastAPI()
        app.add_middleware(
            LeagueContextMiddleware,
            manager=manager,
            default_league_id="league-1",
            import_enabled=True,
        )
        app.add_middleware(AccountContextMiddleware, service=e.service, required=True)
        app.include_router(create_navigation_router())
        app.include_router(
            create_market_preparation_router(
                observer=lambda: observe_resident_market(manager, store)
            )
        )
        gate = threading.Event()

        def finish():
            gate.set()
            worker = cache._build_thread
            if worker:
                worker.join(3)
                self.assertFalse(worker.is_alive())

        self.addCleanup(finish)
        starts = []
        fixture = SimpleNamespace(
            editor=e,
            static=None,
            cache=cache,
            data=data,
            store=store,
            runtime=runtime,
            manager=manager,
            gate=gate,
            starts=starts,
            saved=saved,
            original_client=original_client,
        )

        def publish(*args, **kw):
            starts.append(1)
            gate.wait(8)
            with cache._lock:
                cache._market = SimpleNamespace(
                    store=store,
                    assets=[{"asset_id": "player:1"}],
                    semantic_generation="fixture-A",
                    generated_at="2026-10-01T12:00:00+00:00",
                )
                cache._request_marker = cache.request_marker(
                    data, runtime.state, store, runtime.league_id
                )
                cache._requested_generation = "fixture-A"
                cache._refresh_state = "ready"
                cache._build_phase = "ready"
            return cache._market

        cache._prepare_generation = publish

        # Same production cache/guard/single-flight. Only the expensive provider
        # factory is replaced by a delayed frozen compatible publication.
        @app.get("/market")
        async def market(request: Request):
            snap = cache.preparation_status(
                data, runtime.state, store, runtime.league_id
            )
            if snap["state"] not in {"ready", "stale"}:
                # The early guard passes failures through to the existing
                # router get(): an explicit new entry can retry a failed build.
                if snap["state"] == "failed":
                    from src.core.asset_market import MarketWarmingError

                    try:
                        cache.get(
                            data,
                            runtime.state,
                            store,
                            runtime.league_id,
                            background=True,
                        )
                    except MarketWarmingError:
                        pass
                    snap = cache.preparation_status(
                        data, runtime.state, store, runtime.league_id
                    )
                response = warming_page(request.url.query, snapshot=snap)
                response.background = BackgroundTask(
                    cache.reconcile, data, runtime.state, store, runtime.league_id
                )
                return response
            back, head = navigation_markup()
            return HTMLResponse(
                '<html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1">'
                + head
                + "</head><body><main>"
                + with_back("<h1>Prepared fixture Market</h1>", back)
                + '<input id="market-search" value="frozen"><p>QB · Supported fixture · Market 500</p></main></body></html>'
            )

        client = TestClient(app)
        self.addCleanup(client.close)
        client.cookies.set("dtos_session", e.tokens["account-a"][0])
        # Loopback browser adapter uses this authenticated disposable client.
        e.client = client
        fixture.static = client
        fixture.app = app
        return fixture

    def ready(self, f):
        f.gate.set()
        f.cache._prepare_generation()

    def test_safe_observation_never_builds_or_hydrates_or_writes_preferences(self):
        f = self.fixture()
        before = {"build_count": f.cache.build_count}
        guarded_names = [
            "src.core.data_platform.provider_activation.refresh_public_market",
            "src.core.data_platform.platform.DataPlatform.refresh",
            "src.core.projection_intelligence.service.ProjectionService.generate",
            "src.core.projection_intelligence.service.ProjectionService.publish_horizon",
            "services.global_evidence.retained_global_evidence",
            "services.sleeper.sleeper_get",
            "services.trade_intelligence.generate_trade_workflow",
            "src.core.fois.service.FOISService._generate_sync",
            "src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct",
            "src.core.trade_intelligence.lineup_memo.optimal_legal_lineup",
            "src.core.intelligence.roster_evidence.optimal_legal_lineup",
            "src.core.roster_intelligence.engine.optimal_legal_lineup",
            "src.core.intelligence.team_strength.optimal_legal_lineup",
        ]
        durations = []
        import psutil

        process = psutil.Process()
        rss_before = process.memory_info().rss
        # Do not copy synchronization primitives; compare counters/publication.
        with (
            ExitStack() as stack,
            patch.object(f.cache, "reconcile", side_effect=AssertionError("prepare")),
            patch.object(f.cache, "get", side_effect=AssertionError("get")),
            patch.object(
                f.cache, "_start_background", side_effect=AssertionError("build")
            ),
        ):
            guarded = {
                name: stack.enter_context(patch(name, side_effect=AssertionError(name)))
                for name in guarded_names
            }
            for _ in range(20):
                started = time.perf_counter()
                r = f.editor.client.get("/api/account/market-preparation")
                durations.append((time.perf_counter() - started) * 1000)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["state"], "waiting")
                self.assertIn("no-store", r.headers["cache-control"])
                self.assertIn("private", r.headers["cache-control"])
            self.assertTrue(all(mock.call_count == 0 for mock in guarded.values()))
        f.manager.acquire_request.assert_not_called()
        self.assertEqual(f.cache.build_count, before["build_count"])
        self.assertEqual(f.cache.semantic_child_count, 0)
        f.editor.client = f.original_client
        self.assertEqual(f.editor.state(), f.saved)
        if os.getenv("DTOS_MARKET_PREPARATION_EVIDENCE"):
            root = Path(os.environ["DTOS_MARKET_PREPARATION_EVIDENCE"])
            root.mkdir(parents=True, exist_ok=True)
            (root / "read-costs.json").write_text(
                json.dumps(
                    dict(
                        checks=20,
                        guarded_calls={
                            name: mock.call_count for name, mock in guarded.items()
                        },
                        runtime_acquisitions=f.manager.acquire_request.call_count,
                        market_builds=f.cache.build_count - before["build_count"],
                        semantic_children=f.cache.semantic_child_count,
                        saved_preferences_unchanged=True,
                        response_bytes=len(r.content),
                        request_ms=durations,
                        rss_before=rss_before,
                        rss_after=process.memory_info().rss,
                        qualification="Disposable in-process HTTP measurements; not isolated production headroom or a capacity claim.",
                    ),
                    indent=2,
                )
            )

    def test_ready_stale_failed_empty_and_incompatible_are_distinct(self):
        f = self.fixture()
        self.ready(f)

        def status():
            return f.editor.client.get("/api/account/market-preparation").json()

        self.assertEqual(status()["state"], "ready")
        f.runtime.state["last_error"] = "FAKE_CREDENTIAL /private/source/222 sentinel"
        s = status()
        self.assertEqual(s["state"], "stale")
        self.assertEqual(s["updated_at"], "2026-10-01T12:00:00Z")
        self.assertNotIn("FAKE_CREDENTIAL", json.dumps(s))
        f.cache._market.assets = []
        self.assertEqual(status()["state"], "empty")
        f.data["asset_market_semantic_revision"] = "fixture-B"
        self.assertEqual(status()["state"], "incompatible")
        f.cache._refresh_state = "failed"
        f.cache.last_error = "FAKE_CREDENTIAL /private/source/222 sentinel"
        self.assertEqual(status()["state"], "failed")
        self.assertNotIn("FAKE_CREDENTIAL", json.dumps(status()))
        f.cache._refresh_state = "idle"
        f.cache._build_phase = "idle"
        f.cache._market = None
        self.assertEqual(status()["state"], "source_failed")
        self.assertFalse(status()["can_check"])
        self.assertIn("last league update did not finish", status()["message"])
        f.runtime.state["data"] = {}
        self.assertEqual(status()["state"], "source_failed")
        self.assertNotIn("FAKE_CREDENTIAL", json.dumps(status()))

    def test_only_actual_build_phases_are_reported(self):
        f = self.fixture()
        for phase in [
            "preparing_generation",
            "building",
            "loading_artifact",
            "publishing",
            "private/path secret",
        ]:
            f.cache._building = True
            f.cache._build_phase = phase
            s = f.editor.client.get("/api/account/market-preparation").json()
            self.assertEqual(s["state"], "preparing")
            self.assertNotIn("private/path", json.dumps(s))
            self.assertNotIn("%", s["stage"])
        f.cache._building = False

    def test_current_store_source_and_empty_population_are_not_ready(self):
        f = self.fixture()
        self.ready(f)
        for change in ["store", "source", "generation", "empty"]:
            with self.subTest(change=change):
                market = f.cache._market
                original = (
                    market.store,
                    f.data["asset_market_semantic_revision"],
                    f.cache._requested_generation,
                    market.assets,
                )
                if change == "store":
                    market.store = object()
                if change == "source":
                    f.data["asset_market_semantic_revision"] = "changed"
                if change == "generation":
                    f.cache._requested_generation = "changed"
                if change == "empty":
                    market.assets = []
                self.assertNotIn(
                    f.editor.client.get("/api/account/market-preparation").json()[
                        "state"
                    ],
                    {"ready", "stale"},
                )
                (
                    market.store,
                    f.data["asset_market_semantic_revision"],
                    f.cache._requested_generation,
                    market.assets,
                ) = original

    def test_account_league_revocation_and_missing_runtime_scope(self):
        f = self.fixture()
        self.ready(f)
        client = f.editor.client
        first = client.get("/api/account/market-preparation").json()
        client.cookies.set("dtos_session", f.editor.tokens["account-b"][0])
        other = client.get("/api/account/market-preparation?league=foreign").json()
        self.assertNotEqual(first["scope"], other["scope"])
        self.assertEqual(
            other["state"], "ready"
        )  # shared neutral publication, separate account binding
        f.editor.store.upsert_membership(
            "account-b", {"league_id": "league-2"}, "account-b", 2, "Other", "active"
        )
        f.editor.store.activate("account-b", "league-2")
        switched = client.get("/api/account/market-preparation").json()
        self.assertNotEqual(other["scope"], switched["scope"])
        self.assertEqual(switched["state"], "waiting")
        self.assertFalse(switched["can_check"])
        self.assertNotIn("fixture-A", json.dumps(switched))
        f.editor.store.revoke_session(f.editor.tokens["account-b"][0])
        revoked = client.get("/api/account/market-preparation", follow_redirects=False)
        self.assertIn(revoked.status_code, [401, 303])
        self.assertNotIn(first["scope"], revoked.text)
        client.cookies.clear()
        anonymous = client.get(
            "/api/account/market-preparation", follow_redirects=False
        )
        self.assertIn(anonymous.status_code, [401, 303])
        self.assertNotIn(first["scope"], anonymous.text)

    def test_public_allowlist_withholds_raw_error_details(self):
        secret = "FAKE_CREDENTIAL /private/file source-222"
        result = presentation(
            {"state": "failed", "stage": secret, "last_error": secret, "counts": secret}
        )
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn("last_error", result)

    def test_two_views_share_existing_single_flight_and_retry_after_failure(self):
        f = self.fixture()
        for _ in range(6):
            f.cache.reconcile(f.data, f.runtime.state, f.store, "league-1")
        limit = time.monotonic() + 2
        while not f.starts and time.monotonic() < limit:
            time.sleep(0.01)
        self.assertEqual(len(f.starts), 1)
        for _ in range(5):
            self.assertEqual(
                f.editor.client.get("/api/account/market-preparation").json()["state"],
                "preparing",
            )
        f.gate.set()
        f.cache._build_thread.join(3)
        self.assertEqual(
            f.editor.client.get("/api/account/market-preparation").json()["state"],
            "ready",
        )
        self.assertIsNone(f.cache._build_thread)
        self.assertFalse(f.cache._building)

    def test_failed_worker_retains_model_and_explicit_retry_recovers(self):
        f = self.fixture()
        self.ready(f)
        previous = f.cache._market
        f.data["asset_market_semantic_revision"] = "fixture-B"
        publish = f.cache._prepare_generation
        f.cache._prepare_generation = Mock(
            side_effect=RuntimeError("FAKE_CREDENTIAL /private/source/222")
        )
        f.cache._start_background(
            f.data,
            f.runtime.state,
            f.store,
            "league-1",
            f.cache.request_marker(f.data, f.runtime.state, f.store, "league-1"),
        )
        worker = f.cache._build_thread
        if worker:
            worker.join(3)
        failed = f.editor.client.get("/api/account/market-preparation")
        self.assertEqual(failed.json()["state"], "failed")
        self.assertNotIn("FAKE_CREDENTIAL", failed.text)
        self.assertIs(f.cache.current(), previous)
        self.assertFalse(f.cache._building)
        self.assertIsNone(f.cache._build_thread)
        # The existing explicit-entry get() starts a retry; status reads don't.
        f.cache._prepare_generation = publish
        from src.core.asset_market import MarketWarmingError

        try:
            f.cache.get(f.data, f.runtime.state, f.store, "league-1", background=True)
        except MarketWarmingError:
            pass
        worker = f.cache._build_thread
        if worker:
            worker.join(3)
        self.assertEqual(
            f.editor.client.get("/api/account/market-preparation").json()["state"],
            "ready",
        )

    def test_eviction_and_replaced_publication_cannot_publish_ready(self):
        f = self.fixture()
        self.ready(f)
        cache = f.cache
        snapshot = cache.preparation_status

        def replaced(*args):
            result = snapshot(*args)
            f.runtime.state["data"] = copy.deepcopy(f.data)
            return result

        with patch.object(cache, "preparation_status", side_effect=replaced):
            s = f.editor.client.get("/api/account/market-preparation").json()
        self.assertEqual(s["state"], "waiting")
        f.manager.resident = lambda league: None
        self.assertFalse(
            f.editor.client.get("/api/account/market-preparation").json()["can_check"]
        )

    def browser(self):
        helper = back.ContextualBackTests(
            "test_scope_is_opaque_private_live_and_provider_free"
        )
        self.addCleanup(helper.doCleanups)
        return helper

    def warming_html(self, f, snapshot=None):
        from src.platform.account_context import _CURRENT_ACCOUNT

        token = _CURRENT_ACCOUNT.set(
            f.editor.store.context_for_session(f.editor.tokens["account-a"][0])
        )
        try:
            return warming_page(snapshot=snapshot).body.decode()
        finally:
            _CURRENT_ACCOUNT.reset(token)

    def test_bounded_checks_hidden_page_network_failure_and_scope_change(self):
        f = self.fixture()
        helper = self.browser()
        html = self.warming_html(f)
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                for scenario in ["bounded", "hidden", "network", "scope", "session"]:
                    with self.subTest(scenario=scenario):
                        f.editor.client.cookies.set(
                            "dtos_session", f.editor.tokens["account-a"][0]
                        )
                        p, requests, _, _, errors = helper.page(b, f)
                        p.clock.install()
                        p.route(
                            "**/market?*",
                            lambda route: route.fulfill(
                                status=503, content_type="text/html", body=html
                            ),
                        )
                        if scenario == "network":
                            p.route(
                                "**/api/account/market-preparation",
                                lambda route: route.abort(),
                            )
                        if scenario == "scope":
                            f.editor.client.cookies.set(
                                "dtos_session", f.editor.tokens["account-b"][0]
                            )
                        if scenario == "session":
                            p.route(
                                "**/api/account/market-preparation",
                                lambda route: route.fulfill(
                                    status=401,
                                    content_type="application/json",
                                    body="{}",
                                ),
                            )
                        p.goto(helper.origin + "/market?q=kept")
                        p.wait_for_timeout(150)
                        if scenario == "hidden":
                            count = len(
                                [
                                    r
                                    for r in requests
                                    if r[1] == "/api/account/market-preparation"
                                ]
                            )
                            p.evaluate(
                                "Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))"
                            )
                            p.clock.fast_forward(60001)
                            p.wait_for_timeout(100)
                            self.assertEqual(
                                len(
                                    [
                                        r
                                        for r in requests
                                        if r[1] == "/api/account/market-preparation"
                                    ]
                                ),
                                count,
                            )
                        elif scenario in ["bounded", "network"]:
                            for _ in range(13):
                                p.clock.fast_forward(5001)
                                p.wait_for_timeout(50)
                            text = p.locator(
                                "#market-preparation-recovery"
                            ).inner_text()
                            self.assertIn(
                                "checks have paused"
                                if scenario == "bounded"
                                else "could not connect",
                                text,
                            )
                            count = len(
                                [
                                    r
                                    for r in requests
                                    if r[1] == "/api/account/market-preparation"
                                ]
                            )
                            self.assertLessEqual(count, 12)
                            p.clock.fast_forward(60001)
                            p.wait_for_timeout(100)
                            self.assertEqual(
                                len(
                                    [
                                        r
                                        for r in requests
                                        if r[1] == "/api/account/market-preparation"
                                    ]
                                ),
                                count,
                            )
                        elif scenario == "scope":
                            self.assertIn(
                                "selected league changed",
                                p.locator("#market-preparation-recovery").inner_text(),
                            )
                            self.assertEqual(
                                p.locator("#market-preparation-retry").get_attribute(
                                    "href"
                                ),
                                "/market",
                            )
                        else:
                            self.assertEqual(
                                p.locator("#market-preparation-retry").get_attribute(
                                    "href"
                                ),
                                "/account/sign-in",
                            )
                        self.assertFalse(errors)
                        self.assertEqual(len(f.starts), 0)
                        p.close()
            finally:
                b.close()

    def test_phone_contrast_focus_status_and_automatic_ready_transition(self):
        f = self.fixture()
        helper = self.browser()
        evidence = (
            Path(os.environ["DTOS_MARKET_PREPARATION_EVIDENCE"])
            if os.getenv("DTOS_MARKET_PREPARATION_EVIDENCE")
            else None
        )
        if evidence:
            evidence.mkdir(parents=True, exist_ok=True)
        measurements = []
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    p, requests, _, _, errors = helper.page(b, f, width, height)
                    # Hold only the expensive factory. Initial HTML and cheap
                    # checks still return immediately through actual HTTP.
                    f.gate.clear()
                    f.cache._market = None
                    p.goto(helper.origin + "/market?q=quarterback&position=QB")
                    p.locator("#market-preparation-stage").wait_for()
                    p.wait_for_function(
                        "document.querySelector('#market-preparation-stage').textContent.includes('Preparing')"
                    )
                    self.assertEqual(p.locator("[role=status]").count(), 1)
                    dimensions = p.evaluate("""() => {
                      const p=document.querySelector('#market-preparation-message'),a=document.querySelector('#market-preparation-retry');
                      return {width:innerWidth, overflow:document.documentElement.scrollWidth>innerWidth,
                        foreground:getComputedStyle(p).color,background:getComputedStyle(document.body).backgroundColor,
                        retry:a.getBoundingClientRect().toJSON(), heading:document.querySelector('h1').getBoundingClientRect().toJSON()};
                    }""")
                    self.assertFalse(dimensions["overflow"])
                    self.assertEqual(dimensions["foreground"], "rgb(242, 246, 248)")
                    self.assertEqual(dimensions["background"], "rgb(20, 22, 23)")
                    self.assertGreaterEqual(dimensions["retry"]["height"], 44)
                    p.keyboard.press("Tab")
                    p.locator("#market-preparation-retry").focus()
                    self.assertTrue(
                        p.locator("#market-preparation-retry").evaluate(
                            "e=>e.matches(':focus-visible')"
                        )
                    )
                    self.assertEqual(
                        p.locator("#market-preparation-retry").evaluate(
                            "e=>getComputedStyle(e).outlineStyle"
                        ),
                        "solid",
                    )
                    p.locator("summary").focus()
                    p.keyboard.press("Enter")
                    self.assertTrue(p.locator("details").evaluate("e=>e.open"))
                    if evidence:
                        p.screenshot(
                            path=str(evidence / f"preparing-{width}.png"),
                            full_page=True,
                        )
                    f.gate.set()
                    p.locator("#market-search").wait_for(timeout=12000)
                    self.assertIn("q=quarterback", p.url)
                    self.assertIn("position=QB", p.url)
                    self.assertEqual(p.locator("#dtos-back").count(), 1)
                    self.assertFalse(errors)
                    self.assertEqual(len([r for r in requests if r[1] == "/market"]), 2)
                    measurements.append(dimensions)
                    if evidence:
                        p.screenshot(
                            path=str(evidence / f"ready-{width}.png"), full_page=True
                        )
                    p.close()
            finally:
                b.close()
        if evidence:
            (evidence / "measurements.json").write_text(
                json.dumps(measurements, indent=2)
            )

    def test_failed_and_incompatible_stop_checks_without_automatic_retries(self):
        f = self.fixture()
        helper = self.browser()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = helper.page(b, f)
                # Render the existing warming UI but make the status observer
                # see a failure. No delayed factory is started by status reads.
                p.route(
                    "**/market?*",
                    lambda route: route.fulfill(
                        status=503,
                        content_type="text/html",
                        body=f.editor.client.get(
                            "/market", headers={"Accept": "text/html"}
                        ).text,
                    ),
                )
                f.gate.set()
                f.cache._refresh_state = "failed"
                f.cache._build_phase = "failed"
                # Capture warming HTML once without starting background work.
                from src.platform.account_context import _CURRENT_ACCOUNT

                token = _CURRENT_ACCOUNT.set(
                    f.editor.store.context_for_session(f.editor.tokens["account-a"][0])
                )
                try:
                    html = warming_page(
                        snapshot={"state": "failed", "can_check": False}
                    ).body.decode()
                finally:
                    _CURRENT_ACCOUNT.reset(token)
                p.unroute("**/market?*")
                p.route(
                    "**/market?*",
                    lambda route: route.fulfill(
                        status=503, content_type="text/html", body=html
                    ),
                )
                p.goto(helper.origin + "/market?q=x")
                p.wait_for_function(
                    "document.querySelector('#market-preparation-title').textContent.includes('another try')"
                )
                p.wait_for_timeout(5500)
                self.assertEqual(
                    len(
                        [
                            r
                            for r in requests
                            if r[1] == "/api/account/market-preparation"
                        ]
                    ),
                    1,
                )
                self.assertEqual(len(f.starts), 0)
                self.assertFalse(errors)
                p.close()
            finally:
                b.close()

    def test_keyboard_retry_after_failed_worker_opens_ready_market(self):
        f = self.fixture()
        helper = self.browser()
        publish = f.cache._prepare_generation
        failed = Mock(side_effect=RuntimeError("SYNTHETIC_PRIVATE /private/source"))
        f.cache._prepare_generation = failed
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = helper.page(b, f)
                p.goto(helper.origin + "/market?q=quarterback")
                p.wait_for_function(
                    "document.querySelector('#market-preparation-title').textContent.includes('another try')"
                )
                self.assertEqual(failed.call_count, 1)
                self.assertNotIn("SYNTHETIC_PRIVATE", p.locator("body").inner_text())
                f.cache._prepare_generation = publish
                f.gate.set()
                p.locator("#market-preparation-retry").focus()
                p.keyboard.press("Enter")
                p.locator("#market-search").wait_for(timeout=12000)
                self.assertIn("q=quarterback", p.url)
                self.assertEqual(len(f.starts), 1)
                self.assertFalse(errors)
                p.close()
            finally:
                b.close()

    def test_contextual_back_chain_survives_preparing_to_ready_replacement(self):
        # Complete real Trade workspace -> waiting Market -> ready Market -> Back.
        helper = self.browser()
        f = helper.fixture()
        cache = AssetMarketCache()
        runtime = LeagueRuntime(
            "league-1", state={"data": f.editor.data}, status=RuntimeState.WARM
        )
        runtime.market_context = cache
        store = object()
        f.editor.app.include_router(
            create_market_preparation_router(
                observer=lambda: cache.preparation_status(
                    f.editor.data, runtime.state, store, "league-1"
                )
            )
        )
        original = f.editor.state()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = helper.page(b, f)
                helper.ready(p)
                helper.choose(p)
                p.select_option("#trade-valuation-mode", "custom")
                draft = helper.draft(p)
                seen = []

                def waiting(route):
                    if not seen:
                        seen.append(True)
                        from src.platform.account_context import _CURRENT_ACCOUNT

                        token = _CURRENT_ACCOUNT.set(
                            f.editor.store.context_for_session(
                                f.editor.tokens["account-a"][0]
                            )
                        )
                        try:
                            html = warming_page().body.decode()
                        finally:
                            _CURRENT_ACCOUNT.reset(token)
                        route.fulfill(status=503, content_type="text/html", body=html)
                    else:
                        route.continue_()

                p.route(re.compile(r".*/market(?:\?.*)?$"), waiting)
                p.locator('a[href="/market"]').first.click()
                p.locator("#market-preparation").wait_for()
                with cache._lock:
                    cache._market = SimpleNamespace(
                        store=store,
                        assets=[{}],
                        semantic_generation="A",
                        generated_at="2026-10-01T00:00:00+00:00",
                    )
                    cache._request_marker = cache.request_marker(
                        f.editor.data, runtime.state, store, "league-1"
                    )
                p.locator("#market-search").wait_for(timeout=12000)
                p.locator("#dtos-back").click()
                p.wait_for_url("**/trades/create")
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(
                    helper.draft(p)["currentProposal"], draft["currentProposal"]
                )
                self.assertEqual(helper.draft(p)["valuationMode"], "custom")
                self.assertFalse(errors)
                self.assertEqual(f.editor.state(), original)
                p.close()
            finally:
                b.close()
