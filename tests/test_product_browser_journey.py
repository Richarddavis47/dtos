"""Small real-router/browser journey; no capture archives or publication.

Only canonical input is synthetic. Account middleware, form activation, product
routers and page chrome execute normally. Browser HTTP is transported through
a loopback-only test server; external traffic is denied except fixture images.
"""
from __future__ import annotations

import tempfile
import socket
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import patch

from fastapi import FastAPI
import uvicorn
from playwright.sync_api import sync_playwright

from routes.accounts import create_accounts_router
from routes.fois import create_fois_router
from routes.home import create_home_router
from routes.market import create_market_router
from routes.teams import create_teams_router
from routes.trades import create_trades_router
from src.core.accounts import AccountService, AccountStore
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.league_runtime import LeagueRuntimeManager
from src.core.projection_intelligence.service import ProjectionService
from src.platform.account_context import AccountContextMiddleware
from src.platform.league_context import (
    LeagueContextMiddleware, RuntimeStateProxy, current_league_context,
)
from tests.test_market_render_cache import _Cache, _Market
from tests.test_trade_intelligence import fixture_data
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_contract import A11Y_SCRIPT


class ProductBrowserJourneyTests(unittest.TestCase):
    def test_authenticated_product_navigation_and_league_switching(self):
        import dtos_app

        with tempfile.TemporaryDirectory() as folder:
            store = AccountStore(Path(folder) / "accounts.sqlite3")
            service = AccountService(store)
            tokens = {}
            for account, leagues in (("alpha", ("100", "200")), ("beta", ("300",))):
                identity, _ = service.create_account(account, account, "fixture-only secure password")
                for league in leagues:
                    store.upsert_membership(identity, {
                        "league_id": league, "name": f"League {league}", "season": "2026",
                    }, account, 1, f"Franchise {league}", "active")
                store.activate(identity, leagues[0])
                tokens[account], _ = service.new_session(identity)

            manager = LeagueRuntimeManager(max_warm=3, hydrator=None)
            image_urls = {"https://sleepercdn.com/content/nfl/players/4984.jpg"}
            fixture_image = image_bytes("browser-journey")
            for league in ("100", "200", "300"):
                data = fixture_data()
                image_urls.update(f"https://sleepercdn.com/content/nfl/players/{identity}.jpg" for identity in data["players"])
                data["league"].update(league_id=league, name=f"League {league}", season="2026")
                for team in data["teams"]:
                    team["team_name"] = f"Franchise {league}" if team["roster_id"] == 1 else f"Partner {league}-{team['roster_id']}"
                state = {"data": data, "last_sync": "fixture-boundary"}
                runtime = manager.attach_default(league, state, warm=True)
                market = _Market(f"generation-{league}")
                market.assets = [{
                    "asset_id": "player:4984", "display_name": f"Asset {league}",
                    "asset_type": "player", "position": "QB", "nfl_team": "BUF",
                    "rank": 1, "values": {}, "owner": {"team_name": f"Franchise {league}"},
                }]
                runtime.canonical_context = SimpleNamespace(
                    runtime=runtime, league_id=league, data=data, state=state, market=_Cache(market),
                    projection=ProjectionService(Path(folder) / f"projection-{league}.sqlite3", league_id=league),
                )

            async def fresh():
                pass  # Published fixture state; provider access is forbidden below.

            def data():
                return current_league_context().data

            app = FastAPI()
            app.add_middleware(LeagueContextMiddleware, manager=manager, default_league_id="100", import_enabled=False)
            app.add_middleware(AccountContextMiddleware, service=service, required=True)
            app.include_router(create_accounts_router(service=service, runtime_manager=manager))
            common = dict(ensure_fresh=fresh, require_data=data, page=dtos_app.page)
            app.include_router(create_home_router(**common))
            app.include_router(create_teams_router(**common, state=RuntimeStateProxy({})))
            app.include_router(create_trades_router(**common))
            app.include_router(create_market_router(require_data=data, page=dtos_app.page,
                state={}, league_id="100", context_resolver=current_league_context))
            app.include_router(create_fois_router(require_data=data, page=dtos_app.page,
                service=FOISService(repository=FOISRepository(Path(folder) / "fois.sqlite3"))))

            with patch.object(dtos_app, "account_store", store), patch(
                "services.sleeper.sleeper_get", side_effect=AssertionError("request-time provider call"),
            ), sync_playwright() as playwright, socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
                server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
                thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
                thread.start()
                deadline = time.monotonic() + 10
                while not server.started and time.monotonic() < deadline:
                    time.sleep(0.01)
                browser = None
                try:
                    self.assertTrue(server.started)
                    browser = playwright.chromium.launch(headless=True)
                    for viewport in ({"width": 1280, "height": 900}, {"width": 390, "height": 844}):
                        for account, sequence in (("alpha", ("100", "200", "100")), ("beta", ("300",))):
                            with browser.new_context(viewport=viewport) as context:
                                context.add_cookies([{"name": "dtos_session", "value": tokens[account], "url": origin}])
                                page = context.new_page()
                                errors = []
                                page.on("pageerror", lambda error: errors.append(str(error)))

                                def transport(route):
                                    request = route.request
                                    url = urlsplit(request.url)
                                    if request.method == "GET" and request.url in image_urls:
                                        route.fulfill(status=200, content_type="image/png", body=fixture_image)
                                        return
                                    if url.netloc != urlsplit(origin).netloc:
                                        raise AssertionError(f"Unexpected external fixture request: {url.hostname}")
                                    route.continue_()

                                context.route("**/*", transport)
                                for league in sequence:
                                    initial = page.goto(origin + "/", wait_until="domcontentloaded")
                                    self.assertEqual(initial.status, 200, "Account home must render before league activation")
                                    with page.expect_navigation(wait_until="domcontentloaded"):
                                        page.get_by_role("button", name=f"League {league}", exact=True).click()
                                    for path in ("/", "/league", "/teams/1", "/fois", "/market", "/trades", "/trades/create", "/trades/trade-for", "/trades/shop", "/trades/recommended"):
                                        with self.subTest(viewport=viewport, account=account, league=league, route=path):
                                            response = page.goto(origin + path, wait_until="domcontentloaded")
                                            self.assertEqual(response.status, 200)
                                            chrome = page.get_by_role("complementary", name="Account and league context").inner_text()
                                            self.assertIn(f"Franchise {league}", chrome)
                                            for other in {"100", "200", "300"} - {league}:
                                                self.assertNotIn(f"Franchise {other}", page.locator("body").inner_text())
                                            self.assertGreater(page.get_by_role("main").count(), 0)
                                            if path.startswith("/trades/"):
                                                page.locator(".ti-roster-browser").wait_for(state="visible")
                                            accessibility = page.evaluate(A11Y_SCRIPT)
                                            for key in ("buttons_without_names", "links_without_names", "images_without_alt", "inputs_without_labels"):
                                                self.assertEqual(accessibility[key], 0, (path, key))
                                    self.assertEqual(errors, [])
                                # Forging the other account's membership must remain forbidden.
                                denied = page.evaluate("""async () => {
                                    const token = document.querySelector('input[name="csrf_token"]').value;
                                    const response = await fetch('/account/leagues/999/activate', {
                                        method: 'POST', body: new URLSearchParams({csrf_token: token})
                                    });
                                    return response.status;
                                }""")
                                self.assertEqual(denied, 403)
                finally:
                    try:
                        if browser is not None:
                            browser.close()
                    finally:
                        server.should_exit = True
                        thread.join(timeout=10)
                        self.assertFalse(thread.is_alive(), "test server did not stop")
            self.assertEqual(manager.hydrations, 0)


if __name__ == "__main__":
    unittest.main()
