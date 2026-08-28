from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.accounts import create_accounts_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware
from tools.validation.smoke_http import validate_product_contract


class AccountOnboardingPresentationTests(unittest.TestCase):
    routes = {
        "/account": ("open-front-office", 'href="/"'),
        "/account/create": ("create-account", 'action="/account/create"'),
        "/account/leagues": ("import-league", 'action="/account/leagues/import"'),
        "/account/recover": ("recover-account", 'action="/account/recover"'),
        "/account/sign-in": ("sign-in", 'action="/account/sign-in"'),
        "/account/sleeper": ("connect-sleeper", 'action="/account/sleeper"'),
    }

    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")
        service = AccountService(store)
        runtime = type("Runtime", (), {"get": AsyncMock(return_value=object())})()
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=service, required=True)
        app.include_router(create_accounts_router(service=service, runtime_manager=runtime))
        self.client = TestClient(app)
        self.fixture = {
            "DTOS_INSPECTION_AUTH_TOKEN": "presentation-secret",
            "DTOS_INSPECTION_LEAGUE_ID": "inspection-league",
            "DTOS_INSPECTION_ROSTER_ID": "9",
            "DTOS_INSPECTION_LEAGUE_NAME": "Inspection League",
            "DTOS_INSPECTION_FRANCHISE_NAME": "Inspection Franchise",
        }
        self.headers = {
            "X-DTOS-Inspection": "deterministic",
            "X-DTOS-Inspection-Auth": "presentation-secret",
        }

    def tearDown(self) -> None:
        self.client.close()
        self.folder.cleanup()

    def test_six_inspection_states_share_header_and_real_primary_action(self) -> None:
        with patch.dict("os.environ", self.fixture, clear=False):
            for route, (action_id, behavior) in self.routes.items():
                with self.subTest(route=route):
                    response = self.client.get(route, headers=self.headers)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('data-dtos-component="page-header"', response.text)
                    self.assertIn('data-dtos-shell="account-onboarding"', response.text)
                    self.assertIn('data-dtos-action="primary"', response.text)
                    self.assertIn(f'data-action-id="{action_id}"', response.text)
                    self.assertIn(behavior, response.text)
                    match = re.search(
                        r'<(?:a|button)[^>]+data-dtos-action="primary"[^>]*>([^<]+)</(?:a|button)>',
                        response.text,
                    )
                    self.assertIsNotNone(match)
                    self.assertTrue(match.group(1).strip())

    def test_desktop_tablet_and_mobile_use_one_semantic_contract(self) -> None:
        user_agents = {
            "desktop": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "tablet": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)",
            "mobile": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
        }
        with patch.dict("os.environ", self.fixture, clear=False):
            for viewport, user_agent in user_agents.items():
                for route, (action_id, _) in self.routes.items():
                    with self.subTest(viewport=viewport, route=route):
                        response = self.client.get(
                            route,
                            headers={**self.headers, "User-Agent": user_agent},
                        )
                        self.assertIn('data-dtos-component="page-header"', response.text)
                        self.assertIn(f'data-action-id="{action_id}"', response.text)
                        self.assertIn("@media(max-width:760px)", response.text)
                        self.assertIn("overflow-x:auto", response.text)

    def test_normal_and_inspection_routes_use_the_same_account_shell(self) -> None:
        for route in ("/account/create", "/account/recover", "/account/sign-in"):
            ordinary = self.client.get(route)
            with patch.dict("os.environ", self.fixture, clear=False):
                inspected = self.client.get(route, headers=self.headers)
            for response in (ordinary, inspected):
                self.assertEqual(response.status_code, 200)
                self.assertIn('data-dtos-component="page-header"', response.text)
                self.assertIn('data-dtos-shell="account-onboarding"', response.text)
                self.assertIn('data-dtos-action="primary"', response.text)

    def test_signed_out_root_redirect_finishes_on_canonical_sign_in_action(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.url.path, "/account/sign-in")
        self.assertEqual(response.history[0].status_code, 303)
        self.assertEqual(response.history[0].headers["location"], "/account/sign-in?next=/")
        validate_product_contract(response.content, "/")

    def test_inspection_fixture_contains_no_secret_or_private_account_value(self) -> None:
        with patch.dict("os.environ", self.fixture, clear=False):
            response = self.client.get("/account/leagues", headers=self.headers)
        self.assertNotIn("presentation-secret", response.text)
        self.assertNotIn("dtos_session", response.text)
        self.assertIn("Inspection League", response.text)
        self.assertIn("Inspection Franchise", response.text)


if __name__ == "__main__":
    unittest.main()
