"""Disposable actual producer, secured HTTP and shared-header browser controls."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tests.test_personal_rankings_browser import PersonalEditorFixture
from tests import test_intelligence_platform as intelligence_fixture
from tools.validation.browser_runtime import launch_chromium


class OperatorContextIntegrityTests(unittest.TestCase):
    def test_actual_exception_producer_does_not_serialize_secret(self):
        f = intelligence_fixture.IntelligencePlatformTests()
        f.setUp()
        marker = "FAKE_PASSWORD /private/db.sqlite source-private-222"
        with patch.object(
            f.orchestrator.cache, "get_or_create", side_effect=RuntimeError(marker)
        ):
            with self.assertRaises(RuntimeError):
                f.orchestrator.analyze(f.data, 1)
        self.assertEqual(
            f.orchestrator.last_error, marker
        )  # Internal diagnostic retained.
        body = json.dumps(f.orchestrator.health())
        for part in marker.split():
            self.assertNotIn(part, body)
        self.assertIn("orchestration_failed", body)

    def test_selected_membership_not_default_runtime_and_switch(self):
        import dtos_app

        f = PersonalEditorFixture(page_renderer=dtos_app.page)
        self.addCleanup(f.close)
        with (
            patch.object(dtos_app, "account_store", f.store),
            patch.object(
                dtos_app,
                "STATE",
                {"data": {"league": {"name": "WRONG DEFAULT", "league_id": "999"}}},
            ),
        ):
            initial = f.client.get("/api/my-dtos").json()
            saved = f.client.post(
                "/api/my-dtos",
                json={
                    "command": "initialize",
                    "expected_revision": 0,
                    "market_generation": initial["generation"],
                    "context": initial["context"],
                },
                headers={"x-csrf-token": f.csrf},
            )
            self.assertEqual(saved.status_code, 200, saved.text)
            saved_state = saved.json()
            before = f.store.path.read_bytes()
            for _ in range(2):
                r = f.client.get("/account/my-dtos")
                self.assertEqual(r.status_code, 200)
                self.assertIn("Fixture Front Office", r.text)
                self.assertIn("Your franchise", r.text)
                self.assertNotIn("WRONG DEFAULT", r.text)
                self.assertIn('data-league-id="100"', r.text)
                self.assertEqual(f.client.get("/api/my-dtos").json(), saved_state)
            self.assertEqual(f.store.path.read_bytes(), before)
            f.store.upsert_membership(
                f.account_id,
                {"league_id": "200", "name": "Second League", "season": "2026"},
                "fixture-user",
                2,
                "Second Franchise",
                "active",
            )
            f.store.activate(f.account_id, "200")
            r = f.client.get("/account/my-dtos")
            self.assertIn("Second League Front Office", r.text)
            self.assertIn("Second Franchise", r.text)
            self.assertIn('data-league-id="200"', r.text)
            # Old prepared data is not allowed to impersonate selected league 200.
            self.assertNotEqual(f.client.get("/api/my-dtos").status_code, 200)

    def test_four_viewports_and_stale_first_response(self):
        import dtos_app

        f = PersonalEditorFixture(page_renderer=dtos_app.page)
        self.addCleanup(f.close)
        output = os.getenv("DTOS_OPERATOR_CONTEXT_EVIDENCE")
        with patch.object(dtos_app, "account_store", f.store), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    page = f.browser_page(browser, width, height, touch=width < 760)
                    page.goto("https://dtos.test/account/my-dtos")
                    page.wait_for_function(
                        "document.querySelector('#personal-status').textContent.includes('Market rankings loaded')"
                    )
                    self.assertIn(
                        "Fixture", page.locator(".account-context summary").inner_text()
                    )
                    self.assertFalse(
                        page.evaluate("document.documentElement.scrollWidth>innerWidth")
                    )
                    for _ in range(30):
                        page.keyboard.press("Tab")
                        if page.locator(".account-context summary").evaluate(
                            "e=>e===document.activeElement"
                        ):
                            break
                    self.assertTrue(
                        page.locator(".account-context summary").evaluate(
                            "e=>e===document.activeElement"
                        )
                    )
                    page.keyboard.press("Enter")
                    self.assertTrue(
                        page.locator(".account-context").evaluate("e=>e.open")
                    )
                    if output:
                        p = Path(output)
                        p.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(p / f"identity-{width}.png"))
                    # A later session switch cannot replace rankings under the old header.
                    page.route(
                        "**/api/my-dtos",
                        lambda route: route.fulfill(
                            status=200,
                            json={
                                "account_scope": {"league_id": "200", "roster_id": 2},
                                "csrf_token": f.csrf,
                                "rows": [],
                            },
                        ),
                    )
                    page.locator("#personal-settings > summary").click()
                    page.locator("#personal-reload").click()
                    page.wait_for_function(
                        "document.querySelector('#personal-error').textContent.includes('Reload this page')"
                    )
                    self.assertTrue(page.locator("#personal-custom").is_disabled())
                    page.close()
            finally:
                browser.close()

    def test_peer_scope_and_incompatible_runtime_are_not_substituted(self):
        import dtos_app
        from types import SimpleNamespace

        f = PersonalEditorFixture(page_renderer=dtos_app.page)
        self.addCleanup(f.close)
        peer, _ = f.service.create_account(
            "other-manager", "Other Manager", "disposable password"
        )
        f.store.upsert_membership(
            peer,
            {"league_id": "100", "name": "Fixture", "season": "2026"},
            "peer-user",
            2,
            "Peer franchise",
            "active",
        )
        f.store.activate(peer, "100")
        peer_token, _ = f.service.new_session(peer)
        with patch.object(dtos_app, "account_store", f.store):
            f.client.cookies.set("dtos_session", peer_token)
            body = f.client.get("/account/my-dtos").text
            self.assertIn("Peer franchise", body)
            self.assertIn('data-roster-id="2"', body)
            self.assertNotIn("Your franchise", body)
            self.assertEqual(
                f.client.get("/api/my-dtos").json()["account_scope"],
                {"league_id": "100", "roster_id": 2},
            )
            with patch.object(
                dtos_app,
                "current_league_context",
                return_value=SimpleNamespace(
                    league_id="999",
                    state={"data": {"league": {"league_id": "999", "name": "FOREIGN"}}},
                ),
            ):
                r = f.client.get("/account/my-dtos")
                self.assertEqual(r.status_code, 409)
                self.assertNotIn("FOREIGN", r.text)

    def test_nested_provider_exception_is_safe_in_operator_http(self):
        from tests import test_public_welcome_security as secure
        from tests.test_data_platform import FixtureProvider
        from src.core.data_platform import DataPlatform

        f = secure.PublicWelcomeSecurityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        marker = "FAKE_PROVIDER_CREDENTIAL /private/provider.sqlite source-SECRET-222"
        platform = DataPlatform()
        platform.register(FixtureProvider(failure=marker))
        platform.fetch("Fixture", "p1", {}, allow_cached=False)
        self.assertEqual(platform._health["Fixture"].failure_reason, marker)
        f.client.cookies.set("dtos_session", f.f.sessions["bob"])
        with patch("routes.api.data_platform", platform):
            r = f.client.get(
                "/api/platform/health",
                headers={"X-DTOS-Inspection-Auth": "fixture-only-token"},
            )
            self.assertEqual(r.status_code, 200)
            for private in marker.split():
                self.assertNotIn(private, r.text)
            self.assertEqual(
                r.json()["data_platform"]["providers"]["Fixture"]["status"], "degraded"
            )
