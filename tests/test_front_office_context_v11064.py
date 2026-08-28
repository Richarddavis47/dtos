"""v1.10.64 authenticated Front Office context-contract regressions."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.accounts import AccountContext, LeagueMembership
from src.platform.account_context import AccountContextMiddleware, current_account
from tools.validation.smoke_http import (
    expected_front_office_context,
    validate_front_office_manager_context,
)


def _context(account: str, league: str, roster: int) -> AccountContext:
    membership = LeagueMembership(
        account_id=account,
        league_id=league,
        sleeper_user_id=f"sleeper-{account}",
        roster_id=roster,
        status="active",
        mapping_source="test",
    )
    return AccountContext(
        account_id=account,
        username=account,
        display_name=account,
        sleeper_user_id=membership.sleeper_user_id,
        sleeper_username=account,
        sleeper_link_state="linked",
        active_league_id=league,
        membership=membership,
        csrf_token="csrf",
        session_id=f"session-{account}-{league}",
    )


class _Store:
    contexts = {
        "token-a": _context("account-a", "league-a", 1),
        "token-a-b": _context("account-a", "league-b", 9),
        "token-b": _context("account-b", "league-a", 2),
    }

    def context_for_session(self, token: str) -> AccountContext | None:
        return self.contexts.get(token)


class FrontOfficeContextContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        service = SimpleNamespace(store=_Store())
        app.add_middleware(AccountContextMiddleware, service=service, required=True)

        @app.get("/front-offices")
        async def page(front_office: int | None = None) -> dict[str, object]:
            context = current_account()
            return {
                "account": context.account_id if context else None,
                "true_franchise": context.controlled_roster_id if context else None,
                "active_front_office": front_office,
            }

        @app.get("/api/front-offices")
        async def api(front_office: int | None = None) -> dict[str, object]:
            context = current_account()
            return {
                "account": context.account_id if context else None,
                "true_franchise": context.controlled_roster_id if context else None,
                "active_front_office": front_office,
            }

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def _cookie(self, token: str | None) -> None:
        self.client.cookies.clear()
        if token:
            self.client.cookies.set("dtos_session", token)

    def test_authenticated_html_and_api_preserve_true_franchise(self) -> None:
        self._cookie("token-a")
        for path in ("/front-offices?front_office=2", "/api/front-offices?front_office=2"):
            payload = self.client.get(path).json()
            self.assertEqual(payload["account"], "account-a")
            self.assertEqual(payload["true_franchise"], 1)
            self.assertEqual(payload["active_front_office"], 1)

    def test_explicit_query_does_not_mutate_membership_or_session(self) -> None:
        self._cookie("token-a")
        self.client.get("/front-offices?front_office=2")
        repeated = self.client.get("/api/front-offices").json()
        self.assertEqual(repeated["active_front_office"], 1)
        self.assertEqual(_Store.contexts["token-a"].controlled_roster_id, 1)

    def test_league_switch_resolves_new_membership_without_leakage(self) -> None:
        self._cookie("token-a")
        self.assertEqual(self.client.get("/api/front-offices?front_office=2").json()["active_front_office"], 1)
        self._cookie("token-a-b")
        switched = self.client.get("/api/front-offices?front_office=2").json()
        self.assertEqual(switched["account"], "account-a")
        self.assertEqual(switched["active_front_office"], 9)

    def test_accounts_in_same_league_remain_isolated(self) -> None:
        self._cookie("token-a")
        first = self.client.get("/api/front-offices?front_office=2").json()
        self._cookie("token-b")
        second = self.client.get("/api/front-offices?front_office=1").json()
        self.assertEqual((first["account"], first["active_front_office"]), ("account-a", 1))
        self.assertEqual((second["account"], second["active_front_office"]), ("account-b", 2))

    def test_logout_removes_authenticated_context(self) -> None:
        self._cookie("token-a")
        self.assertEqual(self.client.get("/api/front-offices").status_code, 200)
        self._cookie(None)
        self.assertEqual(self.client.get("/api/front-offices").status_code, 401)

    def test_smoke_expectation_uses_inspection_membership(self) -> None:
        fixture = {
            "DTOS_INSPECTION_AUTH_TOKEN": "secret",
            "DTOS_INSPECTION_LEAGUE_ID": "league-a",
            "DTOS_INSPECTION_ROSTER_ID": "1",
        }
        with patch.dict("os.environ", fixture, clear=False):
            self.assertEqual(expected_front_office_context(2), 1)
            validate_front_office_manager_context({"active_front_office": 1}, 2)
            with self.assertRaisesRegex(AssertionError, "authenticated membership"):
                validate_front_office_manager_context({"active_front_office": 2}, 2)

    def test_unscoped_smoke_keeps_explicit_request_local_context(self) -> None:
        with patch.dict("os.environ", {
            "DTOS_INSPECTION_AUTH_TOKEN": "",
            "DTOS_INSPECTION_LEAGUE_ID": "",
            "DTOS_INSPECTION_ROSTER_ID": "",
        }, clear=False):
            self.assertEqual(expected_front_office_context(2), 2)
            validate_front_office_manager_context({"active_front_office": 2}, 2)


if __name__ == "__main__":
    unittest.main()
