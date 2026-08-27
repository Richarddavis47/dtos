from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routes.accounts import create_accounts_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware


class _RuntimeManager:
    get = AsyncMock(return_value=object())


class AccountFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")
        self.service = AccountService(self.store)

    def tearDown(self) -> None:
        self.folder.cleanup()

    def _client(self, *, required: bool = True) -> TestClient:
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=self.service, required=required)
        app.include_router(create_accounts_router(service=self.service, runtime_manager=_RuntimeManager()))

        @app.get("/")
        async def private_home() -> dict[str, str]:
            return {"status": "private"}

        @app.get("/api/trades")
        async def private_api(request: Request) -> dict[str, str]:
            return {"status": "private", "query": request.url.query}

        @app.get("/api/fois/leagues/{league_id}")
        async def league_api(league_id: str, request: Request) -> dict[str, str]:
            return {"league_id": league_id, "query": request.url.query}

        return TestClient(app)

    def test_passwords_sessions_and_recovery_are_hashed(self) -> None:
        account_id, codes = self.service.create_account("dynasty.gm", "Dynasty GM", "a secure password")
        row = self.store.account_by_username("dynasty.gm")
        self.assertNotIn("a secure password", row["password_hash"])
        self.assertNotIn(codes[0], row["recovery_hashes"])
        token, csrf = self.service.new_session(account_id)
        self.assertIsNotNone(self.store.context_for_session(token))
        self.assertTrue(self.store.verify_csrf(token, csrf))
        recovered = self.service.recover("dynasty.gm", codes[0], "a different secure password")
        self.assertIsNotNone(recovered)
        self.assertIsNone(self.store.context_for_session(token))
        self.assertIsNone(self.service.recover("dynasty.gm", codes[0], "another secure password"))
        self.assertEqual(self.service.authenticate("dynasty.gm", "a different secure password"), account_id)

    def test_recovery_codes_never_enter_url_and_cookie_is_httponly(self) -> None:
        client = self._client()
        response = client.post(
            "/account/create",
            data={"display_name": "GM", "username": "general.manager", "password": "a secure password"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Save your recovery codes", response.text)
        self.assertNotIn("location", response.headers)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        self.assertNotIn(b"password", response.url.query)

    def test_private_html_and_api_require_authentication(self) -> None:
        client = self._client()
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)
        response = client.get("/api/trades")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["status"], "authentication_required")

        account_id, _ = self.service.create_account("unmapped", "Unmapped", "a secure password")
        token, _ = self.service.new_session(account_id)
        client.cookies.set("dtos_session", token)
        self.assertEqual(client.get("/api/trades").json()["status"], "active_league_required")

    def test_csrf_rejects_state_change_and_logout_revokes_session(self) -> None:
        account_id, _ = self.service.create_account("manager", "Manager", "a secure password")
        token, csrf = self.service.new_session(account_id)
        client = self._client()
        client.cookies.set("dtos_session", token)
        self.assertEqual(client.post("/account/logout", data={"csrf_token": "wrong"}).status_code, 403)
        response = client.post("/account/logout", data={"csrf_token": csrf}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIsNone(self.store.context_for_session(token))

    def test_duplicate_sleeper_identity_is_unique(self) -> None:
        first, _ = self.service.create_account("first", "First", "a secure password")
        second, _ = self.service.create_account("second", "Second", "a secure password")
        self.store.link_sleeper(first, sleeper_user_id="sleeper-1", username="one", display_name="One")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.link_sleeper(second, sleeper_user_id="sleeper-1", username="one", display_name="One")

    def test_auth_rate_limit_is_bounded_and_generic(self) -> None:
        client = self._client()
        for _ in range(5):
            response = client.post("/account/sign-in", data={"username": "missing", "password": "wrong"}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
        response = client.post("/account/sign-in", data={"username": "missing", "password": "wrong"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "900")

    def test_migration_is_idempotent_and_preserves_records(self) -> None:
        account_id, _ = self.service.create_account("existing", "Existing", "a secure password")
        self.store.link_sleeper(account_id, sleeper_user_id="sleeper", username="existing", display_name="Existing")
        league = {"league_id": "league", "name": "League", "season": "2026"}
        self.store.upsert_membership(account_id, league, "sleeper", 4, "Franchise", "active")
        self.store.activate(account_id, "league")
        AccountStore(self.store.path)
        AccountStore(self.store.path)
        health = self.store.health()
        self.assertEqual(health["schema_version"], 2)
        self.assertEqual(health["counts"]["accounts"], 1)
        self.assertEqual(health["counts"]["sleeper_links"], 1)
        self.assertEqual(health["counts"]["memberships"], 1)
        self.assertEqual(self.store.account_by_username("existing")["active_league_id"], "league")

    def test_session_membership_is_authoritative_and_cross_league_path_is_denied(self) -> None:
        account_id, _ = self.service.create_account("scoped", "Scoped", "a secure password")
        self.store.link_sleeper(account_id, sleeper_user_id="sleeper", username="scoped", display_name="Scoped")
        league = {"league_id": "allowed", "name": "Allowed", "season": "2026"}
        self.store.upsert_membership(account_id, league, "sleeper", 7, "Seven", "active")
        self.store.activate(account_id, "allowed")
        token, _ = self.service.new_session(account_id)
        client = self._client()
        client.cookies.set("dtos_session", token)
        allowed = client.get("/api/fois/leagues/allowed?league_id=attacker&front_office=999")
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("league_id=allowed", allowed.json()["query"])
        self.assertIn("front_office=7", allowed.json()["query"])
        self.assertNotIn("front_office=999", allowed.json()["query"])
        denied = client.get("/api/fois/leagues/other")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["status"], "unauthorized_league")

    def test_session_survives_store_restart_and_private_responses_are_not_cached(self) -> None:
        account_id, _ = self.service.create_account("durable", "Durable", "a secure password")
        league = {"league_id": "allowed", "name": "Allowed", "season": "2026"}
        self.store.upsert_membership(account_id, league, "sleeper", 7, "Seven", "active")
        self.store.activate(account_id, "allowed")
        token, _ = self.service.new_session(account_id)
        restarted = AccountStore(self.store.path)
        self.assertEqual(restarted.context_for_session(token).controlled_roster_id, 7)
        client = self._client()
        client.cookies.set("dtos_session", token)
        response = client.get("/api/trades")
        self.assertEqual(response.status_code, 200)
        self.assertIn("front_office=7", response.json()["query"])
        self.assertEqual(response.headers["cache-control"], "no-store, private")
        self.assertEqual(response.headers["vary"], "Cookie")

    def test_expired_and_invalid_sessions_are_denied(self) -> None:
        account_id, _ = self.service.create_account("expired", "Expired", "a secure password")
        self.store.create_session(account_id=account_id, token="expired-token", session_id="expired", csrf_token="csrf", ttl_hours=-1)
        self.assertIsNone(self.store.context_for_session("expired-token"))
        client = self._client()
        client.cookies.set("dtos_session", "invalid-token")
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)

    def test_inspection_auth_requires_complete_fixture_and_establishes_context(self) -> None:
        client = self._client()
        incomplete = {
            "DTOS_INSPECTION_AUTH_TOKEN": "inspection-secret",
            "DTOS_INSPECTION_LEAGUE_ID": "",
            "DTOS_INSPECTION_ROSTER_ID": "",
        }
        with patch.dict("os.environ", incomplete, clear=False):
            self.assertEqual(
                client.get("/api/trades", headers={"X-DTOS-Inspection-Auth": "inspection-secret"}).status_code,
                401,
            )
        fixture = {
            "DTOS_INSPECTION_AUTH_TOKEN": "inspection-secret",
            "DTOS_INSPECTION_LEAGUE_ID": "inspection-league",
            "DTOS_INSPECTION_ROSTER_ID": "9",
        }
        with patch.dict("os.environ", fixture, clear=False):
            response = client.get("/api/trades", headers={"X-DTOS-Inspection-Auth": "inspection-secret"})
            leagues = client.get("/account/leagues", headers={"X-DTOS-Inspection-Auth": "inspection-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("league=inspection-league", response.json()["query"])
        self.assertIn("front_office=9", response.json()["query"])
        self.assertNotIn("inspection-secret", response.text)
        self.assertEqual(leagues.status_code, 200)
        self.assertIn("Inspection League", leagues.text)
        self.assertIn("Inspection Franchise", leagues.text)

    def test_two_accounts_in_one_league_keep_distinct_franchises(self) -> None:
        contexts = []
        for suffix, roster_id in (("a", 3), ("b", 8)):
            account_id, _ = self.service.create_account(f"manager-{suffix}", f"Manager {suffix}", "a secure password")
            sleeper_id = f"sleeper-{suffix}"
            self.store.link_sleeper(account_id, sleeper_user_id=sleeper_id, username=suffix, display_name=suffix)
            league = {"league_id": "shared", "name": "Shared", "season": "2026"}
            self.store.upsert_membership(account_id, league, sleeper_id, roster_id, f"Team {suffix}", "active")
            self.store.activate(account_id, "shared")
            token, _ = self.service.new_session(account_id)
            contexts.append(self.store.context_for_session(token))
        self.assertEqual([context.controlled_roster_id for context in contexts], [3, 8])
        self.assertNotEqual(contexts[0].account_id, contexts[1].account_id)

    def test_session_and_membership_resolution_is_bounded_local_work(self) -> None:
        account_id, _ = self.service.create_account("timed", "Timed", "a secure password")
        league = {"league_id": "timed-league", "name": "Timed", "season": "2026"}
        self.store.upsert_membership(account_id, league, "sleeper", 4, "Four", "active")
        self.store.activate(account_id, "timed-league")
        token, _ = self.service.new_session(account_id)
        started = time.perf_counter()
        contexts = [self.store.context_for_session(token) for _ in range(100)]
        duration = time.perf_counter() - started
        self.assertTrue(all(context and context.controlled_roster_id == 4 for context in contexts))
        self.assertLess(duration, 1.0)


class SleeperOnboardingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")

    async def asyncTearDown(self) -> None:
        self.folder.cleanup()

    def _service(self, responses: dict[str, object]) -> AccountService:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = responses.get(request.url.path)
            if payload is None:
                return httpx.Response(404, json=None)
            return httpx.Response(200, json=payload)

        transport = httpx.MockTransport(handler)
        return AccountService(self.store, client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs))

    async def test_resolves_identity_and_discovers_unique_leagues(self) -> None:
        service = self._service({
            "/v1/user/tester": {"user_id": "u1", "username": "tester", "display_name": "Tester"},
            "/v1/user/u1/leagues/nfl/2026": [{"league_id": "l1", "name": "Current", "season": "2026"}],
            "/v1/user/u1/leagues/nfl/2025": [{"league_id": "l1", "name": "Current", "season": "2026"}, {"league_id": "l0", "name": "Prior", "season": "2025"}],
        })
        user = await service.resolve_sleeper("tester")
        leagues = await service.discover(user["user_id"], seasons=(2026, 2025))
        self.assertEqual(user["user_id"], "u1")
        self.assertEqual([row["league_id"] for row in leagues], ["l1", "l0"])

    async def test_membership_requires_exactly_one_roster_association(self) -> None:
        service = self._service({
            "/v1/league/l1/rosters": [{"roster_id": 7, "owner_id": "owner", "co_owners": ["u1"], "metadata": {"team_name": "Seven"}}],
            "/v1/league/l1/users": [{"user_id": "owner", "display_name": "Owner"}],
        })
        roster_id, name, status = await service.resolve_membership({"league_id": "l1"}, "u1")
        self.assertEqual((roster_id, name, status), (7, "Seven", "active"))

        ambiguous = self._service({
            "/v1/league/l1/rosters": [{"roster_id": 1, "owner_id": "u1"}, {"roster_id": 2, "owner_id": "u1"}],
            "/v1/league/l1/users": [],
        })
        self.assertEqual(await ambiguous.resolve_membership({"league_id": "l1"}, "u1"), (None, None, "ambiguous"))

    async def test_missing_sleeper_identity_is_honest(self) -> None:
        service = self._service({})
        with self.assertRaises(ValueError):
            await service.resolve_sleeper("missing")


if __name__ == "__main__":
    unittest.main()
