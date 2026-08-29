"""v1.10.65 authenticated production-smoke contract regressions."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.platform.validation.progress import ValidationProgress, read_progress
from tools.validation import smoke_http


class _Response:
    status = 200
    headers = {"Content-Type": "text/plain"}

    def __init__(self, body: bytes = b"ok") -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class AuthenticatedSmokeContractTests(unittest.TestCase):
    fixture = {
        "DTOS_AUTH_REQUIRED": "true",
        "DTOS_INSPECTION_AUTH_TOKEN": "opaque-inspection-secret",
        "DTOS_INSPECTION_LEAGUE_ID": "league-a",
        "DTOS_INSPECTION_ROSTER_ID": "7",
    }

    def test_route_authentication_is_scoped_to_private_products_and_account(self) -> None:
        with patch.dict(os.environ, self.fixture, clear=True):
            for path in ("/", "/market", "/trades", "/api/trades", "/account"):
                with self.subTest(path=path):
                    self.assertTrue(smoke_http.route_uses_inspection_context(path))
            for path in (
                "/health/live", "/health/ready", "/api/status",
                "/api/market/health", "/api/inspect/health", "/openapi.json",
            ):
                with self.subTest(path=path):
                    self.assertFalse(smoke_http.route_uses_inspection_context(path))

    def test_incomplete_fixture_cannot_authenticate_smoke(self) -> None:
        with patch.dict(os.environ, {
            "DTOS_AUTH_REQUIRED": "true",
            "DTOS_INSPECTION_AUTH_TOKEN": "opaque",
            "DTOS_INSPECTION_LEAGUE_ID": "league-a",
            "DTOS_INSPECTION_ROSTER_ID": "",
        }, clear=True):
            self.assertIsNone(smoke_http.inspection_fixture())
            self.assertFalse(smoke_http.route_uses_inspection_context("/market"))
            with self.assertRaisesRegex(AssertionError, "complete inspection fixture"):
                smoke_http._request("https://example.test", "/market", authenticated=True)

    def test_private_request_uses_header_but_public_and_anonymous_do_not(self) -> None:
        observed: list[tuple[str, str | None]] = []

        def open_request(request, timeout):  # noqa: ANN001, ANN202
            observed.append((request.full_url, request.get_header("X-dtos-inspection-auth")))
            self.assertEqual(timeout, 60)
            return _Response()

        with (
            patch.dict(os.environ, self.fixture, clear=True),
            patch.object(smoke_http, "urlopen", side_effect=open_request),
        ):
            smoke_http._request("https://example.test", "/market")
            smoke_http._request("https://example.test", "/health/live")
            smoke_http._request(
                "https://example.test", "/api/trades", authenticated=False,
            )
        self.assertEqual(observed, [
            ("https://example.test/market", "opaque-inspection-secret"),
            ("https://example.test/health/live", None),
            ("https://example.test/api/trades", None),
        ])

    def test_anonymous_contract_requires_redirect_and_json_auth_boundary(self) -> None:
        calls: list[tuple[str, bool | None, bool]] = []

        def request(_base, path, **kwargs):  # noqa: ANN001, ANN202
            calls.append((path, kwargs.get("authenticated"), kwargs.get("follow_redirects", True)))
            if path == "/market":
                return 303, b"", {"Location": "/account/sign-in?next=/market"}, .01
            return 401, json.dumps({"status": "authentication_required"}).encode(), {}, .01

        with patch.object(smoke_http, "_request", side_effect=request):
            smoke_http.validate_anonymous_auth_contract("https://example.test")
        self.assertEqual(calls, [
            ("/market", False, False),
            ("/api/trades", False, True),
        ])

    def test_anonymous_contract_rejects_product_access_or_wrong_api_state(self) -> None:
        with patch.object(
            smoke_http, "_request",
            return_value=(200, b"private market", {}, .01),
        ):
            with self.assertRaisesRegex(AssertionError, "anonymous private HTML"):
                smoke_http.validate_anonymous_auth_contract("https://example.test")

    def test_inspection_identity_is_stateless_and_requires_no_real_password(self) -> None:
        with patch.dict(os.environ, self.fixture, clear=True):
            token, league, roster = smoke_http.inspection_fixture() or (None, None, None)
        self.assertEqual((league, roster), ("league-a", 7))
        self.assertEqual(token, "opaque-inspection-secret")
        self.assertNotIn("PASSWORD", self.fixture)
        self.assertNotIn("SESSION", self.fixture)

    def test_auth_setup_evidence_contains_no_sensitive_field_names(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "progress.json"
            ValidationProgress(path, "run").record(
                "smoke_phase", phase="auth_setup", status="completed",
                mechanism="inspection_header_context",
                authentication_required=True,
                auth_material_recorded=False,
                durable_session_created=False,
            )
            event = read_progress(path)["last_event"]
        self.assertFalse(event["auth_material_recorded"])
        self.assertFalse(event["durable_session_created"])


if __name__ == "__main__":
    unittest.main()
