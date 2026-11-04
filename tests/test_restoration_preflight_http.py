"""Operator-only restoration preflight routing without league preparation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
import time
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import operations_inspect
from routes.operations_inspect import create_operations_inspection_router
from src.platform import operational_inspection as evidence
from src.platform.account_context import AccountContextMiddleware
from src.platform.inspection_security import OperationalInspectionBoundary, PREFIX
from src.platform.league_context import LeagueContextMiddleware
from src.platform.market_warming import AssetMarketWarmingMiddleware
from tools.projection_reachability import InspectionLimit


GRANITE = "1314695233040052224"
TOKEN = "disposable-preflight-http-credential"
HEADERS = {"X-DTOS-Inspection-Auth": TOKEN}
ENDPOINT = PREFIX + "/restoration-preflight"


class RestorationPreflightHTTPTests(unittest.TestCase):
    def setUp(self):
        self.accounts, self.manager, self.market = Mock(), Mock(), Mock()
        self.accounts.store.context_for_session.side_effect = AssertionError("Session read")
        self.manager.get.side_effect = AssertionError("Runtime hydration")
        self.manager.acquire_request.side_effect = AssertionError("Runtime acquisition")
        self.manager.resident.side_effect = AssertionError("Unexpected runtime lookup")
        self.market.begin_warming_guard.side_effect = AssertionError("Market preparation")
        self.snapshot = {
            "advisory_only": True,
            "non_atomic": True,
            "recheck_required": True,
            "process": {"pid": os.getpid(), "coordination_scope": "serving_process"},
            "memory": {"scope": "container", "current_bytes": None},
            "verdict": "unknown",
            "reason": "memory_telemetry_unknown",
            "cache": {
                "payload_readability": "not_checked",
                "content_compatibility": "not_evaluated",
            },
        }
        self.provider = Mock(return_value=self.snapshot)
        self.env = self.enterContext(patch.dict(os.environ, {
            "DTOS_INSPECTION_AUTH_TOKEN": TOKEN,
            # Operations must not require or inherit semantic inspection scope.
            "DTOS_INSPECTION_LEAGUE_ID": "a-different-semantic-league",
            "DTOS_INSPECTION_ROSTER_ID": "7",
        }))
        self.client = self.make_client(self.provider)
        self.enterContext(patch.object(
            evidence.InspectionStores, "configured",
            side_effect=AssertionError("Preflight constructed storage services"),
        ))

    def make_client(self, provider):
        app = FastAPI()
        app.include_router(create_operations_inspection_router(restoration_preflight=provider))
        app.add_middleware(
            LeagueContextMiddleware, manager=self.manager,
            default_league_id="default", import_enabled=True,
        )
        app.add_middleware(
            AssetMarketWarmingMiddleware, cache=self.market, data_provider=Mock(),
            state={}, store=Mock(), league_id="default", build_allowed=Mock(),
        )
        app.add_middleware(AccountContextMiddleware, service=self.accounts, required=True)
        app.add_middleware(OperationalInspectionBoundary)
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def get(self, **kwargs):
        kwargs.setdefault("headers", HEADERS)
        kwargs.setdefault("params", {"league_id": GRANITE})
        return self.client.get(ENDPOINT, **kwargs)

    def assert_private(self, response):
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("private", response.headers["cache-control"])
        self.assertEqual(response.headers["vary"], "X-DTOS-Inspection-Auth")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertNotIn(TOKEN, response.text)

    def assert_no_preparation(self):
        self.accounts.store.context_for_session.assert_not_called()
        self.manager.get.assert_not_called()
        self.manager.acquire_request.assert_not_called()
        self.manager.resident.assert_not_called()
        self.market.begin_warming_guard.assert_not_called()

    def test_missing_invalid_and_duplicate_credentials_fail_before_discovery(self):
        credentials = [
            {}, {"X-DTOS-Inspection-Auth": "wrong"},
            {"X-DTOS-Inspection-Auth": "Bearer " + TOKEN},
            {"X-DTOS-Inspection-Auth": TOKEN + " "},
            {"X-DTOS-Inspection-Auth": hashlib.sha256(TOKEN.encode()).hexdigest()},
            [("X-DTOS-Inspection-Auth", TOKEN)] * 2,
        ]
        for headers in credentials:
            with self.subTest(headers_kind=type(headers).__name__):
                response = self.get(headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "Inspection authorization required"})
                self.assert_private(response)
        self.provider.assert_not_called()
        self.assert_no_preparation()

    def test_cookie_bearer_and_query_values_cannot_authorize(self):
        for kwargs in (
            {"headers": {"Cookie": "dtos_session=disposable-account-session"}},
            {"headers": {"Authorization": "Bearer " + TOKEN}},
            {"headers": {}, "params": {"league_id": GRANITE, "token": TOKEN}},
        ):
            response = self.get(**kwargs)
            self.assertEqual(response.status_code, 401)
            self.assert_private(response)
        self.provider.assert_not_called()
        self.assert_no_preparation()

    def test_exact_approved_league_is_required_before_provider_access(self):
        for league in ("1314695233040052225", "0" + GRANITE, "123"):
            with self.subTest(league=league):
                response = self.get(params={"league_id": league})
                self.assertEqual(response.status_code, 403)
                self.assert_private(response)
        # A digest identifies neither an authorized request nor an approved ID.
        response = self.get(params={"league_id": hashlib.sha256(GRANITE.encode()).hexdigest()})
        self.assertEqual(response.status_code, 400)
        self.provider.assert_not_called()
        self.assert_no_preparation()

    def test_only_one_strict_league_parameter_is_supported(self):
        cases = [
            {}, {"league_id": ""}, {"league_id": " " + GRANITE},
            {"league_id": "+" + GRANITE}, {"league_id": "1" * 33},
            {"league_id": "١٣١٤٦٩٥٢٣٣٠٤٠٠٥٢٢٢٤"},
            {"league_id": "../../private-cache.json"},
            {"league_id": GRANITE, "path": "/private/cache"},
            {"league_id": GRANITE, "limit": "1"},
            [("league_id", GRANITE), ("league_id", GRANITE)],
        ]
        for params in cases:
            with self.subTest(params_kind=type(params).__name__):
                response = self.get(params=params)
                self.assertEqual(response.status_code, 400)
                self.assert_private(response)
                self.assertNotIn("/private", response.text)
        self.provider.assert_not_called()
        self.assert_no_preparation()

    def test_authorized_read_is_scoped_private_and_bypasses_preparation(self):
        before = time.monotonic()
        response = self.get()
        after = time.monotonic()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), self.snapshot)
        self.assert_private(response)
        self.provider.assert_called_once()
        league, budget = self.provider.call_args.args
        self.assertEqual(league, GRANITE)
        self.assertIsInstance(budget, evidence.Budget)
        self.assertGreaterEqual(budget.deadline, before + 3)
        self.assertLessEqual(budget.deadline, after + 3)
        self.assertEqual(budget.decoded_bytes, 0)
        self.assertEqual(budget.rows, 0)
        self.assert_no_preparation()

    def test_snapshots_are_not_cached_and_do_not_grant_entry(self):
        next_snapshot = deepcopy(self.snapshot)
        next_snapshot.update(verdict="would_defer", reason="insufficient_headroom")
        next_snapshot["memory"]["current_bytes"] = 2 * 1024**3 - 1
        self.provider.side_effect = [deepcopy(self.snapshot), next_snapshot]
        first, second = self.get(), self.get()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["verdict"], "unknown")
        self.assertEqual(second.json()["verdict"], "would_defer")
        for response in (first, second):
            self.assertTrue(response.json()["advisory_only"])
            self.assertTrue(response.json()["non_atomic"])
            self.assertTrue(response.json()["recheck_required"])
            self.assertEqual(response.json()["process"]["coordination_scope"], "serving_process")
            self.assertEqual(response.json()["memory"]["scope"], "container")
            self.assertEqual(response.json()["cache"]["content_compatibility"], "not_evaluated")
        self.assertEqual(self.provider.call_count, 2)
        self.assertIsNot(self.provider.call_args_list[0].args[1], self.provider.call_args_list[1].args[1])
        self.assert_no_preparation()

    def test_operation_remains_get_only(self):
        for method in ("POST", "PUT", "DELETE", "OPTIONS", "HEAD"):
            response = self.client.request(method, ENDPOINT, headers=HEADERS,
                                           params={"league_id": GRANITE})
            self.assertEqual(response.status_code, 405)
            self.assert_private(response)
        self.provider.assert_not_called()
        self.assert_no_preparation()

    def test_missing_provider_fails_closed_without_initialization(self):
        client = self.make_client(None)
        response = client.get(ENDPOINT, headers=HEADERS, params={"league_id": GRANITE})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Inspection unavailable or budget exceeded"})
        self.assert_private(response)
        self.assert_no_preparation()

    def test_busy_diagnostic_does_not_queue_or_call_provider(self):
        operations_inspect._DIAGNOSTIC_LOCK.acquire()
        try:
            response = self.get()
        finally:
            operations_inspect._DIAGNOSTIC_LOCK.release()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "5")
        self.assert_private(response)
        self.provider.assert_not_called()
        self.assert_no_preparation()

    def test_preflight_does_not_consume_or_bypass_graph_cooldown(self):
        deadline = time.monotonic() + 30
        with patch.object(operations_inspect, "_NEXT_GRAPH_READ", deadline):
            response = self.get()
            self.assertEqual(operations_inspect._NEXT_GRAPH_READ, deadline)
        self.assertEqual(response.status_code, 200, response.text)
        self.provider.assert_called_once()
        self.assert_no_preparation()

    def test_provider_failures_are_sanitized_and_do_not_leak_secrets(self):
        for failure in (OSError("PRIVATE_CACHE_PATH " + TOKEN),
                        ValueError("PRIVATE_PAYLOAD " + TOKEN),
                        InspectionLimit("PRIVATE_DIAGNOSTIC " + TOKEN)):
            self.provider.side_effect = failure
            response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": "Inspection unavailable or budget exceeded"})
            self.assertNotIn("PRIVATE_", response.text)
            self.assert_private(response)
        self.assert_no_preparation()

    def test_original_summary_deadline_and_response_ceiling_still_apply(self):
        expired = evidence.Budget(time.monotonic() - 1)
        with patch.object(evidence, "Budget", return_value=expired):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assert_private(response)
        self.provider.reset_mock()
        self.provider.return_value = {"oversized": "x" * (256 * 1024)}
        with patch.object(operations_inspect, "MAX_RESPONSE_BYTES", 256 * 1024):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("oversized", response.text)
        self.assert_private(response)
        self.assert_no_preparation()

    def test_query_budget_and_catalog_are_private_without_provider_access(self):
        response = self.get(params={"league_id": GRANITE, "unknown": "x" * 128})
        self.assertEqual(response.status_code, 400)
        self.assert_private(response)
        catalog = self.client.get(PREFIX, headers=HEADERS)
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("restoration-preflight", catalog.json()["operations"])
        self.assertTrue(catalog.json()["read_only"])
        self.assert_private(catalog)
        self.provider.assert_not_called()
        self.assert_no_preparation()


if __name__ == "__main__":
    unittest.main()
