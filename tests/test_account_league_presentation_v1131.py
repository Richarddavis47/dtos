"""Request-local presentation dependencies must not use default-league state."""
from __future__ import annotations

import inspect
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from src.core.accounts import AccountService, AccountStore
from src.core.league_runtime import LeagueRuntimeManager
from src.platform.account_context import AccountContextMiddleware, current_account
from src.platform.league_context import LeagueContextMiddleware, current_league_context
from src.ui.render_cache import GenerationRenderCache
from tests.test_market_render_cache import _Market, _Cache

from src.platform.league_context import _CURRENT_CONTEXT, RuntimeStateProxy
from src.core.valuation.universe import ValuationUniverse
from validation.routes import _children, discover_http_endpoints, HttpEndpoint


class ValuationContextTests(unittest.TestCase):
    def test_registered_valuation_route_uses_active_runtime_state(self) -> None:
        import dtos_app

        self.assertIn(HttpEndpoint("GET", "/api/valuation/status"),
                      discover_http_endpoints(dtos_app.app.routes))
        def endpoints(routes):
            for route in routes:
                if hasattr(route, "endpoint"):
                    yield route.endpoint
                yield from endpoints(_children(route))

        endpoint = next(endpoint for endpoint in endpoints(dtos_app.app.routes)
                        if endpoint.__name__ == "valuation_status")
        universe = inspect.getclosurevars(endpoint).nonlocals["universe"]
        state = inspect.getclosurevars(universe).nonlocals["state"]
        self.assertIsInstance(state, RuntimeStateProxy)
        for league_id, timestamp in (
            ("100", "2026-09-01T00:00:00+00:00"),
            ("200", "2026-09-02T00:00:00+00:00"),
            ("100", "2026-09-03T00:00:00+00:00"),
        ):
            data = {"league": {"league_id": league_id}, "players": {}}
            marker = _CURRENT_CONTEXT.set(SimpleNamespace(
                league_id=league_id, data=data,
                state={"data": data, "last_sync": timestamp},
            ))
            try:
                result = ValuationUniverse(data, state)
                self.assertEqual(result.freshness["sleeper_sync_timestamp"], timestamp)
            finally:
                _CURRENT_CONTEXT.reset(marker)


class MultiAccountMarketTests(unittest.TestCase):
    def test_real_middleware_switching_concurrency_and_colliding_ids(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = AccountStore(Path(folder) / "accounts.sqlite3")
            service = AccountService(store)
            accounts = {}
            tokens = {}
            for name, leagues in (("account-a", ("100", "200")), ("account-b", ("300",))):
                account_id, _ = service.create_account(name, "Same display name", "test-only secure password")
                accounts[name] = account_id
                for league in leagues:
                    store.upsert_membership(account_id, {"league_id": league, "name": "Same league name", "season": "2026"},
                                            name, 1, "Same franchise name", "active")
                store.activate(account_id, leagues[0])
                tokens[name], _ = service.new_session(account_id)

            contexts = {}
            markets = {}
            manager = LeagueRuntimeManager(max_warm=3, hydrator=None)
            for league in ("100", "200", "300"):
                data = {"league": {"league_id": league, "name": "Same league name"}}
                state = {"data": data, "last_sync": "same-sync"}
                runtime = manager.attach_default(league, state, warm=True)
                market = _Market("same-generation")
                market.assets = [{"asset_id": "player:4984", "display_name": "Same Player", "asset_type": "player",
                                  "position": "QB", "nfl_team": "BUF", "rank": 1, "values": {},
                                  "owner": {"team_name": f"private-owner-{league}"}}]
                markets[league] = market
                runtime.canonical_context = SimpleNamespace(league_id=league, state=state, data=data, market=_Cache(market))
                contexts[league] = runtime.canonical_context

            def page(title, body):
                account = current_account()
                context = current_league_context()
                return HTMLResponse(f"{account.account_id}|{account.csrf_token}|{context.league_id}|{body}")

            app = FastAPI()
            app.add_middleware(LeagueContextMiddleware, manager=manager, default_league_id="100", import_enabled=False)
            app.add_middleware(AccountContextMiddleware, service=service, required=True)
            app.include_router(create_market_router(
                require_data=lambda: current_league_context().data,
                state=contexts["100"].state, league_id="100", page=page,
                context_resolver=current_league_context,
            ))
            with patch("routes.market.market_render_cache", GenerationRenderCache("market")), patch(
                "routes.market.market_body_render_cache", GenerationRenderCache("market_body")
            ), TestClient(app) as client:
                def read(name):
                    response = client.get("/market?league=999&front_office=99", headers={"Cookie": f"dtos_session={tokens[name]}"})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["cache-control"], "no-store, private")
                    return response.text

                baseline = {}
                for league in ("200", "100", "200", "100"):
                    store.activate(accounts["account-a"], league)
                    content = read("account-a")
                    self.assertTrue(content.startswith(accounts["account-a"] + "|"))
                    self.assertIn(f"private-owner-{league}", content)
                    for other in {"100", "200", "300"} - {league}:
                        self.assertNotIn(f"private-owner-{other}", content)
                    if league in baseline:
                        self.assertEqual(content, baseline[league])
                    baseline[league] = content
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(read, ["account-a", "account-b"] * 8))
                for index, content in enumerate(results):
                    name, league = ("account-a", "100") if index % 2 == 0 else ("account-b", "300")
                    self.assertTrue(content.startswith(accounts[name] + "|"))
                    self.assertIn(f"private-owner-{league}", content)
                    self.assertNotIn("private-owner-200", content)
                self.assertEqual(manager.hydrations, 0)
                self.assertTrue(all(market.directory_calls == 1 for market in markets.values()))


if __name__ == "__main__":
    unittest.main()
