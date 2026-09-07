"""Authenticated Trade Center mechanics; no provider or production mutations."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.trades import create_trades_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware
from tests.test_trade_intelligence import fixture_data


class AuthenticatedTradeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")
        service = AccountService(store)
        account_id, _ = service.create_account("manager", "Manager", "fixture password only")
        store.link_sleeper(account_id, sleeper_user_id="fixture-user", username="manager", display_name="Manager")
        store.upsert_membership(account_id, {"league_id": "league-1", "season": "2026", "name": "Fixture"}, "fixture-user", 1, "Team 1", "active")
        store.activate(account_id, "league-1")
        token, self.csrf = service.new_session(account_id)
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=service, required=True)
        data = fixture_data()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: data, page=lambda title, body: body))
        self.client = TestClient(app)
        self.client.cookies.set("dtos_session", token)
        self.data, self.store, self.account_id = data, store, account_id
        self.payload = {"active_roster_id": 1, "partner_roster_id": 2, "assets_sent": ["1-QB-0"], "assets_received": ["2-QB-0"]}

    def test_missing_csrf_reproduces_both_failures_before_engine_entry(self):
        for path, engine in (("evaluate", "evaluate_trade_request"), ("assist", "assist_trade_request")):
            with self.subTest(path=path), patch("routes.trades." + engine) as call:
                response = self.client.post("/api/trades/" + path, json=self.payload)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"status": "csrf_rejected"})
                call.assert_not_called()

    def test_valid_session_csrf_reaches_actual_evaluator(self):
        workspace = self.client.get("/api/trades/workspace").json()
        response = self.client.post("/api/trades/evaluate", json={**self.payload, "workspace_context": workspace["workspace_context"]}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("recommendation", response.json()["evaluation"])
        self.assertEqual(response.json()["proposal"]["assets_sent"], self.payload["assets_sent"])

    def test_workspace_resources_are_served_by_actual_router(self):
        for path, media in (("js/trade_workspace.js", "text/javascript"), ("css/trade_workspace.css", "text/css")):
            response = self.client.get("/static/" + path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(media, response.headers["content-type"])
            self.assertGreater(len(response.content), 100)

    def _post(self, payload=None, path="evaluate"):
        context = self.client.get("/api/trades/workspace").json()["workspace_context"]
        return self.client.post("/api/trades/" + path, json={**self.payload, "workspace_context": context, **(payload or {})}, headers={"X-CSRF-Token": self.csrf})

    def test_wrong_active_franchise_is_rejected_server_side(self):
        response = self._post({"active_roster_id": 2})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "unauthorized_franchise")

    def test_workspace_from_another_session_cannot_be_reused(self):
        context = self.client.get("/api/trades/workspace").json()["workspace_context"]
        context["binding"] = "other-account-session"
        response = self._post({"workspace_context": context})
        self.assertEqual(response.json()["detail"]["code"], "workspace_context_changed")

    def test_switching_leagues_does_not_reinterpret_an_old_proposal(self):
        old = self.client.get("/api/trades/workspace").json()["workspace_context"]
        self.store.upsert_membership(self.account_id, {"league_id": "league-2", "season": "2026", "name": "Separate"}, "fixture-user", 1, "Separate Franchise", "active")
        self.store.activate(self.account_id, "league-2")
        self.data["league"]["league_id"] = "league-2"
        new = self.client.get("/api/trades/workspace").json()["workspace_context"]
        self.assertNotEqual(old["binding"], new["binding"])
        response = self._post({"workspace_context": old})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "workspace_context_changed")
        self.assertEqual(self._post().status_code, 200)
        self.store.activate(self.account_id, "league-1")
        self.data["league"]["league_id"] = "league-1"
        restored = self.client.get("/api/trades/workspace").json()["workspace_context"]
        self.assertEqual(restored, old)

    def test_compare_cannot_bypass_controlled_franchise(self):
        response = self._post({"proposals": [{**self.payload, "active_roster_id": 2}, self.payload]}, path="compare")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "unauthorized_franchise")

    def test_ownership_changed_names_asset_without_engine_entry(self):
        player = self.data["teams"][0]["players"].pop(0)
        self.data["teams"][1]["players"].append(player)
        for endpoint in ("evaluate", "assist"):
            response = self._post(path=endpoint)
            self.assertEqual(response.status_code, 422)
            detail = response.json()["detail"]
            self.assertEqual(detail["code"], "ownership_changed")
            self.assertIn(player["name"], detail["message"])

    def test_engine_failure_does_not_claim_ownership_change_or_leak_exception(self):
        with patch("routes.trades.evaluate_trade_request", side_effect=RuntimeError("sensitive fixture exception")):
            response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "evaluation_unavailable")
        self.assertNotIn("sensitive", response.text)
        self.assertIn("proposal is still intact", response.text)

    def test_evaluator_value_error_is_not_misreported_as_user_input(self):
        with patch("services.trade_intelligence.evaluate_bilateral", side_effect=ValueError("private evaluator detail")):
            response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "evaluation_unavailable")
        self.assertNotIn("private evaluator", response.text)

    def test_duplicate_asset_rejected(self):
        response = self._post({"assets_sent": ["1-QB-0", "1-QB-0"]})
        self.assertEqual(response.json()["detail"]["code"], "duplicate_asset")

    def test_traded_pick_retains_identity_and_follows_current_owner(self):
        before = self.client.get("/api/trades/workspace").json()["workspace_context"]
        pick = self.data["teams"][0]["picks_owned"].pop(0)
        pick["current_owner_id"] = 2
        self.data["teams"][1]["picks_owned"].append(pick)
        result = self.client.get("/api/trades/workspace").json()
        self.assertNotEqual(before["ownership_generation"], result["workspace_context"]["ownership_generation"])
        rows = [a for t in result["teams"] for a in t["assets"] if a["asset_id"] == f'{pick["season"]}-R{pick["round"]}-1']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_roster_id"], 2)
        self.assertIn("Team 1", rows[0]["raw_label"])
        response = self._post({"assets_sent": [rows[0]["asset_id"]], "workspace_context": before})
        self.assertEqual(response.json()["detail"]["code"], "ownership_changed")

    def test_malformed_asset_collections_fail_as_input_not_engine_failure(self):
        for values in ("1-QB-0", [{"id": "1-QB-0"}], [None]):
            with self.subTest(values=values):
                response = self._post({"assets_sent": values})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"]["code"], "invalid_proposal")

    def test_no_credible_adjustment_is_not_engine_error(self):
        response = self._post({"protected_assets": [p["id"] for p in self.data["teams"][0]["players"]], "instruction": "make it cheaper"}, path="assist")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertTrue(response.json()["search_completed"])

    def test_unrecognized_protected_name_is_not_silently_ignored(self):
        response = self._post({"instruction": "Do not trade nonexistent fixture player"}, path="assist")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["interpretation_error"], "specific_asset_required")
        self.assertFalse(response.json()["search_completed"])

    def test_generation_respects_explicit_counterparty(self):
        response = self._post({"workflow": "recommended"}, path="generate")
        self.assertEqual(response.status_code, 200)
        for row in response.json()["results"]:
            self.assertEqual(row["proposal"]["partner_roster_id"], 2)
        response = self._post({"workflow": "trade_for", "asset_id": "2-QB-0", "partner_roster_id": 1}, path="generate")
        self.assertEqual(response.json()["detail"]["code"], "legality_rejected")
