"""Cold selected-league recovery through actual sync, middleware and HTTP.

Only external Sleeper responses and unrelated post-sync intelligence work are
controlled. Accounts, source failure retention, runtime admission and routes are
real. No production account, provider or history writes.
"""
from contextlib import asynccontextmanager
from copy import deepcopy
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.accounts import create_accounts_router
from routes.api import create_api_router
from routes.home import create_home_router
from routes.trades import create_trades_router
from src.core.accounts import AccountService, AccountStore
from src.core.league_runtime import LeagueRuntime, LeagueRuntimeManager, LeagueRuntimeNotFound
from src.core.projection_intelligence.service import ProjectionService
from src.platform.account_context import AccountContextMiddleware
from src.platform.league_context import LeagueContextMiddleware, current_league_context
from tests.test_import_commissioner_integrity import snapshot
from tests import test_public_readiness as onboarding
from tests.test_trade_intelligence import fixture_data


class ColdLeagueRecoveryTests(unittest.TestCase):
    def setUp(self):
        import dtos_app

        self.dtos = dtos_app
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")
        original_client = httpx.AsyncClient
        self.service = AccountService(self.store, client_factory=lambda **options: original_client(transport=httpx.MockTransport(self.upstream), **options))
        self.account, _ = self.service.create_account("cold-manager", "Cold manager", "disposable test password")
        self.store.link_sleeper(self.account, sleeper_user_id="cold-user", username="cold-manager", display_name="Cold manager")
        for league in ("100", "200"):
            self.store.upsert_membership(self.account, {"league_id": league, "name": "Fixture " + league, "season": "2026"}, "cold-user", 1, "Franchise " + league, "active")
        self.store.activate(self.account, "200")
        self.token, self.csrf = self.service.new_session(self.account)
        self.mode = "404"
        self.discovery_failed = False
        self.source_requests = []
        self.manager = LeagueRuntimeManager(max_warm=3, hydrator=dtos_app._hydrate_league_runtime)
        data = fixture_data()
        data["league"].update(league_id="100", name="Fixture 100", season="2026")
        runtime = self.manager.attach_default("100", {"data": data}, warm=True)
        dtos_app._publish_runtime_context(runtime, ProjectionService(league_id="100"))

        @asynccontextmanager
        async def lifespan(_app):
            yield
            await self.manager.shutdown()

        self.app = FastAPI(lifespan=lifespan)
        self.app.add_middleware(LeagueContextMiddleware, manager=self.manager, default_league_id="100", import_enabled=True)
        self.app.add_middleware(AccountContextMiddleware, service=self.service, required=True)
        self.app.include_router(create_accounts_router(service=self.service, runtime_manager=self.manager))
        common = dict(ensure_fresh=AsyncMock(), require_data=lambda: current_league_context().data, page=dtos_app.page)
        self.app.include_router(create_home_router(**common))
        self.app.include_router(create_trades_router(**common))
        self.app.include_router(create_api_router(ensure_fresh=common["ensure_fresh"], require_data=common["require_data"], sync_sleeper=AsyncMock(), state={}, league_id="100"))

        @self.app.get("/api/recovery-context")
        async def context():
            selected = current_league_context()
            return {"league_id": selected.league_id, "name": selected.data["league"]["name"]}

        original = httpx.AsyncClient

        def client(**options):
            return original(transport=httpx.MockTransport(self.upstream), **options)

        self.enterContext(patch("services.sleeper.httpx.AsyncClient", side_effect=client))
        self.enterContext(patch.object(dtos_app, "account_store", self.store))
        self.client = self.enterContext(TestClient(self.app, raise_server_exceptions=False))
        self.client.cookies.set("dtos_session", self.token)

    def upstream(self, request):
        path = request.url.path
        self.source_requests.append(path)
        if "/user/" in path and "/leagues/nfl/" in path:
            if self.discovery_failed:
                raise httpx.ReadTimeout("private discovery diagnostic", request=request)
            return httpx.Response(200, json=[{"league_id": "100", "name": "Fixture 100", "season": "2026", "sport": "nfl"}] if path.endswith("/2026") else [])
        if path.endswith("/league/200"):
            if self.mode == "timeout":
                raise httpx.ReadTimeout("private upstream diagnostic", request=request)
            if self.mode == "404":
                return httpx.Response(404, json={"error": "private upstream diagnostic"})
            if self.mode == "null":
                return httpx.Response(200, json=None)
            return httpx.Response(200, json={"league_id": "200", "name": "Recovered league", "season": "2026", "status": "in_season", "roster_positions": ["QB", "BN"], "scoring_settings": {"pass_td": 4}, "settings": {"leg": 1, "draft_rounds": 3}})
        if path.endswith("/state/nfl"):
            return httpx.Response(200, json={"season": "2026", "week": 1, "season_type": "regular"})
        if path.endswith("/players/nfl"):
            return httpx.Response(200, json={})
        if path.endswith("/league/200/users"):
            return httpx.Response(200, json=[{"user_id": "cold-user", "display_name": "Cold manager"}])
        if path.endswith("/league/200/rosters"):
            return httpx.Response(200, json=[{"roster_id": 1, "owner_id": "cold-user", "players": [], "starters": [], "settings": {"wins": 0, "losses": 0, "ties": 0, "fpts": 0, "fpts_against": 0}}])
        return httpx.Response(200, json=[])

    def test_actual_sync_failure_withholds_empty_intelligence_and_account_writes(self):
        for mode in ("404", "timeout", "null"):
            with self.subTest(mode=mode):
                self.mode = mode
                before = snapshot(self.store)
                with patch.object(self.dtos, "_generate_fois_coordinated", wraps=self.dtos._generate_fois_coordinated) as fois:
                    response = self.client.get("/api/recovery-context")
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.json()["status"], "failed")
                self.assertIn("unavailable", response.json()["reason"].lower())
                self.assertNotIn("private upstream", response.text)
                fois.assert_not_called()
                self.assertEqual(snapshot(self.store), before)

    def test_html_failure_preserves_context_and_exposes_safe_recovery(self):
        before = snapshot(self.store)
        response = self.client.get("/?q=%3Cscript%3E", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("League data is temporarily unavailable", response.text)
        self.assertIn("Fixture 200", response.text)
        self.assertIn('href="/account/leagues"', response.text)
        self.assertIn("Your account and saved leagues are unchanged", response.text)
        self.assertNotIn("<script>", response.text)
        self.assertNotIn("FOIS canonical", response.text)
        self.assertEqual(snapshot(self.store), before)

    def test_browser_retry_keeps_decoded_path_on_the_same_origin(self):
        response = self.client.get("/%5Cforeign.example", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 503)
        self.assertIn('href="/%5Cforeign.example?', response.text)
        self.assertNotIn('href="/\\foreign.example"', response.text)
        with onboarding.PublicOnboardingTests.browser(self, 390, 844) as page:
            foreign = []

            def only_local(route):
                if route.request.url.startswith(self.origin + "/"):
                    route.continue_()
                else:
                    foreign.append(route.request.url)
                    route.abort()

            page.route("**/*", only_local)
            self.assertEqual(page.goto(self.origin + "/%5Cforeign.example", wait_until="networkidle").status, 503)
            with page.expect_navigation(wait_until="networkidle"):
                page.get_by_role("link", name="Try this page again", exact=True).click()
            self.assertTrue(page.url.startswith(self.origin + "/%5Cforeign.example"))
            self.assertEqual(foreign, [])

    def test_account_health_static_and_unauthorized_requests_need_no_hydration(self):
        for path in ("/account", "/api/account", "/account/sign-in", "/health/live", "/static/js/trade_workspace.js"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.source_requests, [])
        before = snapshot(self.store)
        response = self.client.post("/api/account/active-league", json={"league_id": "100"}, headers={"X-CSRF-Token": "foreign"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(snapshot(self.store), before)
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/", follow_redirects=False).status_code, 303)
        self.assertEqual(self.source_requests, [])

    def test_explicit_later_selection_recovers_without_retrying_failed_league(self):
        self.assertEqual(self.client.get("/").status_code, 503)
        calls = len(self.source_requests)
        response = self.client.post("/api/account/active-league", json={"league_id": "100"}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.store.context_for_session(self.token).active_league_id, "100")
        self.assertEqual(len(self.source_requests), calls)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(len(self.store.memberships(self.account)), 2)

    def test_source_recovery_can_prepare_same_selected_league(self):
        with patch.object(self.dtos, "_generate_fois_coordinated", new_callable=AsyncMock, return_value=()) as fois, patch.object(self.dtos.AssetMarketCache, "reconcile"), patch.object(self.dtos, "start_background_backfill", new_callable=AsyncMock, return_value={"status": "unavailable"}), patch.object(self.dtos, "history_progress_contracts"), patch.object(self.dtos, "resolve_historical_trade_market", new_callable=AsyncMock), patch("services.league_maintenance.ensure_periodic_refresh"):
            before = snapshot(self.store)
            self.assertEqual(self.client.get("/api/recovery-context").status_code, 503)
            fois.assert_not_called()
            self.mode = "valid"
            response = self.client.get("/api/recovery-context")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {"league_id": "200", "name": "Recovered league"})
            async def finish():
                runtime = self.manager.resident("200")
                while runtime.background_tasks:
                    await asyncio.gather(*tuple(runtime.background_tasks))
            self.client.portal.call(finish)
            self.assertGreaterEqual(fois.await_count, 1)
            self.assertEqual(snapshot(self.store), before)

    def test_failed_refresh_keeps_existing_supported_facts_eligible(self):
        data = fixture_data()
        data["league"].update(league_id="200", season="2026")
        original = deepcopy(data["teams"])
        state = LeagueRuntime("200").state
        state["data"] = data
        runtime = self.manager.attach_default("200", state, warm=False)
        with patch.object(self.dtos, "_generate_fois_coordinated", new_callable=AsyncMock, side_effect=RuntimeError("supported downstream reached")) as fois:
            async def hydrate_and_finish():
                result = await self.dtos._hydrate_league_runtime(runtime, prepare_history=False)
                while runtime.background_tasks:
                    await asyncio.gather(*tuple(runtime.background_tasks))
                return result
            with patch("services.league_maintenance.ensure_periodic_refresh"), patch.object(self.dtos.AssetMarketCache, "reconcile"), patch.object(self.dtos, "start_background_backfill", new_callable=AsyncMock, return_value={"status": "unavailable"}), patch.object(self.dtos, "history_progress_contracts"), patch.object(self.dtos, "resolve_historical_trade_market", new_callable=AsyncMock):
                self.assertTrue(asyncio.run(hydrate_and_finish()))
            fois.assert_awaited_once()
            self.assertEqual(runtime.lifecycle["fois_generation"], "failed")
            self.assertEqual(runtime.canonical_context.fois_state, "unavailable")
        self.assertEqual(runtime.state["data"]["teams"], original)

    def test_unrelated_programming_errors_are_not_reclassified(self):
        async def broken(_runtime):
            raise ValueError("unrelated programming error")
        self.manager._hydrator = broken
        response = self.client.get("/api/recovery-context")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("League data is temporarily unavailable", response.text)

    def test_discovery_outage_preserves_saved_connections_for_recovery(self):
        self.discovery_failed = True
        before = snapshot(self.store)
        response = self.client.get("/account/leagues", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("Saved connected leagues", response.text)
        self.assertIn("Fixture 100", response.text)
        self.assertNotIn("private discovery", response.text)
        self.assertEqual(snapshot(self.store), before)
        self.assertFalse(any(path.endswith("/league/200") for path in self.source_requests))
        response = self.client.post("/account/leagues/100/activate", data={"csrf_token": self.csrf}, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text)
        self.assertEqual(self.store.context_for_session(self.token).active_league_id, "100")

    def test_discovery_fallback_cannot_expose_another_accounts_connections(self):
        self.discovery_failed = True
        other, _ = self.service.create_account("other-cold-manager", "Other manager", "disposable other password")
        self.store.link_sleeper(other, sleeper_user_id="other-user", username="other", display_name="Other manager")
        token, _ = self.service.new_session(other)
        self.client.cookies.set("dtos_session", token)
        before = snapshot(self.store)
        response = self.client.get("/account/leagues")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Fixture 100", response.text)
        self.assertNotIn("Franchise 200", response.text)
        self.assertEqual(snapshot(self.store), before)

    def test_default_api_and_head_keep_structured_failure_contract(self):
        for path, headers in (("/", {}), ("/api/recovery-context", {"Accept": "text/html"})):
            response = self.client.get(path, headers=headers)
            self.assertEqual(response.status_code, 503)
            self.assertIn("application/json", response.headers["content-type"])
            self.assertEqual(response.json()["status"], "failed")
            self.assertEqual(response.headers["cache-control"].split(",")[0], "no-store")
        response = self.client.head("/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"")

    def test_known_invalid_runtime_keeps_invalid_status_and_clear_heading(self):
        async def missing(_runtime):
            raise LeagueRuntimeNotFound("Requested league could not be found")
        self.manager._hydrator = missing
        response = self.client.get("/", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("League could not be opened", response.text)
        self.assertNotIn("temporarily unavailable", response.text)
        response = self.client.get("/api/recovery-context")
        self.assertEqual(response.json()["status"], "invalid")

    def test_settled_account_reads_have_no_growth_or_provider_work(self):
        before = snapshot(self.store)
        def files():
            return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(self.folder.name).iterdir() if p.is_file()}
        physical = files()
        for _ in range(20):
            self.assertEqual(self.client.get("/api/account").status_code, 200)
        self.assertEqual(snapshot(self.store), before)
        self.assertEqual(files(), physical)
        self.assertEqual(self.source_requests, [])

    def test_rendered_phone_recovery_keeps_account_controls_reachable(self):
        rows = []
        before = snapshot(self.store)
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            with self.subTest(width=width), onboarding.PublicOnboardingTests.browser(self, width, height) as page:
                response = page.goto(self.origin + "/", wait_until="networkidle")
                self.assertEqual(response.status, 503)
                self.assertTrue(page.get_by_role("heading", name="League data is temporarily unavailable", exact=True).is_visible())
                retry = page.get_by_role("link", name="Try this page again", exact=True)
                self.assertGreaterEqual(retry.bounding_box()["height"], 44)
                choose = page.get_by_role("link", name="Choose a connected league", exact=True)
                choose.focus()
                self.assertNotEqual(choose.evaluate("e=>getComputedStyle(e).outlineStyle"), "none")
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                rows.append({"viewport": [width, height], "retry": retry.bounding_box(), "recovery_height": page.locator("main").bounding_box()["height"]})
                page.keyboard.press("Enter")
                page.wait_for_url(self.origin + "/account/leagues")
                self.assertIn("Fixture 100", page.locator("body").inner_text())
        self.assertEqual(snapshot(self.store), before)
        target = os.environ.get("DTOS_COLD_RECOVERY_EVIDENCE")
        if target:
            Path(target).write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    unittest.main()
