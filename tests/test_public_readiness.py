"""Isolated new-user routes with the real Sleeper client, account store and browser."""
from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path
import tempfile
import socket
import threading
import time
from time import perf_counter
import unittest
from unittest.mock import AsyncMock

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.accounts import create_accounts_router
from src.core.accounts import AccountService, AccountStore
from src.platform.account_context import AccountContextMiddleware
from tools.validation.browser_runtime import launch_chromium


class PublicOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")
        self.source_failures = set()
        self.source_requests = []
        self.source_entered = threading.Event()
        self.source_resume = threading.Event()
        self.hold_source = False
        self.no_leagues = False
        self.no_membership = False
        self.runtime = type("Runtime", (), {"get": AsyncMock(return_value=object())})()
        self.service = AccountService(self.store, client_factory=lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(self.sleeper), **kw))
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=self.service, required=True)
        app.include_router(create_accounts_router(service=self.service, runtime_manager=self.runtime))
        self.app = app
        self.client = TestClient(app, base_url="https://dtos.test", raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.account, _ = self.service.create_account("new-manager", "New manager", "isolated password only")
        self.token, self.csrf = self.service.new_session(self.account)
        self.client.cookies.set("dtos_session", self.token)

    def sleeper(self, request):
        path = request.url.path
        self.source_requests.append(path)
        if self.hold_source and '/user/' in path and '/leagues/' not in path:
            self.source_entered.set()
            if not self.source_resume.wait(5):
                raise AssertionError('Test source barrier was not released')
        if any(piece in path for piece in self.source_failures):
            raise httpx.ReadTimeout("private provider diagnostic", request=request)
        if "/user/" in path and "/leagues/" not in path:
            return httpx.Response(200, json={"user_id": "new-user", "username": "new-manager"})
        leagues = [{"league_id": lid, "name": name, "season": "2026", "sport": "nfl", "total_rosters": 12,
                    "scoring_settings": scoring, "roster_positions": slots}
                   for lid, name, scoring, slots in [("100", "First league", {"pass_td": 4}, ["QB", "SUPER_FLEX", "BN"]),
                                                     ("200", "Second league", {"pass_td": 6}, ["QB", "WR", "FLEX", "BN"])]]
        if "/leagues/nfl/" in path:
            return httpx.Response(200, json=leagues if path.endswith("2026") and not self.no_leagues else [])
        if path.endswith("/rosters"):
            return httpx.Response(200, json=[] if self.no_membership else [{"roster_id": 2 if "/200/" in path else 1, "owner_id": "new-user"}])
        if path.endswith("/users"):
            return httpx.Response(200, json=[{"user_id": "new-user", "display_name": "New manager"}])
        return httpx.Response(200, json=next((row for row in leagues if path.endswith("/" + row["league_id"])), None))

    def link(self):
        response = self.client.post("/account/sleeper", data={"csrf_token": self.csrf, "sleeper_username": "new-manager"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)

    def test_identity_timeout_is_actionable_and_retry_can_succeed(self):
        self.source_failures.add("/user/")
        response = self.client.post("/account/sleeper", data={"csrf_token": self.csrf, "sleeper_username": "new-manager"})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("Try again", response.text)
        self.assertNotIn("private provider", response.text)
        self.assertIsNone(self.store.context_for_session(self.token).sleeper_user_id)
        self.source_failures.clear()
        self.link()

    def test_discovered_add_timeout_does_not_change_scope(self):
        self.link()
        self.source_failures.add("/leagues/nfl/")
        response = self.client.post("/account/leagues/100", data={"csrf_token": self.csrf})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("Your leagues", response.text)
        self.assertIsNone(self.store.context_for_session(self.token).membership)
        self.assertEqual(self.store.memberships(self.account), [])
        self.source_failures.clear()
        response = self.client.post("/account/leagues/100", data={"csrf_token": self.csrf}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.context_for_session(self.token).controlled_roster_id, 1)

    def test_membership_timeout_does_not_grant_or_guess_ownership(self):
        self.link()
        self.source_failures.add("/rosters")
        response = self.client.post("/account/leagues/100", data={"csrf_token": self.csrf})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(self.store.memberships(self.account), [])
        self.source_failures.clear()
        response = self.client.post("/account/leagues/import", data={"csrf_token": self.csrf, "league_id": "200"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.context_for_session(self.token).controlled_roster_id, 2)

    def test_manual_import_invalid_and_provider_failure_have_distinct_recovery(self):
        self.link()
        response = self.client.post("/account/leagues/import", data={"csrf_token": self.csrf, "league_id": "not-a-league"})
        self.assertIn("Confirm the Sleeper league ID", response.text)
        self.assertIn('href="/account/leagues"', response.text)
        self.source_failures.add("/league/")
        response = self.client.post("/account/leagues/import", data={"csrf_token": self.csrf, "league_id": "100"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.text)
        self.assertEqual(self.store.memberships(self.account), [])

    def test_sign_in_has_recovery_route_without_changing_authentication(self):
        response = self.client.get("/account/sign-in")
        self.assertIn('href="/account/recover"', response.text)

    def test_browser_sign_in_limit_has_readable_wait_and_preserves_json_limit(self):
        for _ in range(5):
            self.client.post('/account/sign-in', data={'username': 'missing', 'password': 'wrong'}, follow_redirects=False)
        response = self.client.post('/account/sign-in', headers={'Accept': 'text/html'}, data={'username': 'missing', 'password': 'wrong'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['retry-after'], '900')
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('15 minutes', response.text)
        self.assertIn('href="/account/sign-in"', response.text)
        response = self.client.post('/account/sign-in', data={'username': 'missing', 'password': 'wrong'})
        self.assertEqual(response.json(), {'status': 'rate_limited'})

        response = self.client.post("/account/sign-in", data={"username": "new-manager", "password": "wrong"})
        self.assertIn("Check your details", response.text)
        self.assertIn('href="/account/recover"', response.text)

    def test_empty_discovery_and_unmapped_league_are_not_import_success(self):
        self.link()
        self.no_leagues = True
        response = self.client.get('/account/leagues')
        self.assertEqual(response.status_code, 200)
        self.assertIn('No eligible leagues found', response.text)
        self.no_leagues = False
        self.no_membership = True
        response = self.client.post('/account/leagues/import', data={'csrf_token': self.csrf, 'league_id': '100'})
        self.assertIn('could not confidently match your team', response.text)
        self.assertEqual(self.store.memberships(self.account), [])


    def test_new_account_form_and_empty_league_guidance(self):
        self.client.cookies.clear()
        self.assertIn('href="/account/create"', self.client.get('/account').text)
        response = self.client.post('/account/create', data={"display_name": "First visit", "username": "first-visit", "password": "isolated account password"})
        self.assertIn('Save your recovery codes', response.text)
        self.assertNotIn('location', response.headers)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('Connect your Sleeper account', self.client.get('/account').text)

    def test_failed_preparation_preserves_existing_active_league(self):
        self.link()
        self.client.post('/account/leagues/100', data={"csrf_token": self.csrf}, follow_redirects=False)
        self.runtime.get.side_effect = httpx.ReadTimeout('private preparation failure')
        response = self.client.post('/account/leagues/200', data={"csrf_token": self.csrf})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn('preparation', response.text.lower())
        self.assertEqual(self.store.context_for_session(self.token).active_league_id, '100')
        self.assertEqual([m.league_id for m in self.store.memberships(self.account)], ['100'])

    def test_failed_switch_keeps_active_scope_and_never_prepares_foreign_league(self):
        self.link()
        for league in ('200', '100'):
            response = self.client.post('/account/leagues/' + league, data={'csrf_token': self.csrf}, follow_redirects=False)
            self.assertEqual(response.status_code, 303, response.text)
        self.runtime.get.side_effect = httpx.ReadTimeout('private preparation failure')
        for path in ('/account/leagues/200/activate', '/api/account/active-league'):
            with self.subTest(path=path):
                response = self.client.post(path, **({'json': {'league_id': '200'}, 'headers': {'X-CSRF-Token': self.csrf}} if path.startswith('/api/') else {'data': {'csrf_token': self.csrf}}))
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(self.store.context_for_session(self.token).active_league_id, '100')
        self.runtime.get.reset_mock()
        response = self.client.post('/account/leagues/999/activate', data={'csrf_token': self.csrf})
        self.assertEqual(response.status_code, 403)
        self.runtime.get.assert_not_awaited()

    @contextmanager
    def browser(self, width, height):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(self.app, log_level='error'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(server.started)
        self.origin = f'http://127.0.0.1:{port}'
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.context.add_cookies([{'name': 'dtos_session', 'value': self.token, 'url': self.origin}])
                page.set_default_timeout(8000)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                # Native localhost navigation includes normal redirects. Only
                # external destinations are intercepted/blocked.
                page.route(re.compile(r'https?://(?!127\.0\.0\.1(?::|/))'), lambda route: route.abort())
                yield page
                self.assertEqual(errors, [])
            finally:
                browser.close()
                server.should_exit = True
                thread.join(5)
                listener.close()
                self.assertFalse(thread.is_alive(), 'Account fixture server did not stop')

    def test_rendered_new_user_timeout_retry_and_league_discovery(self):
        rows = []
        for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
            with self.subTest(width=width), self.browser(width, height) as page:
                # A fresh isolated account context has no Sleeper identity or imported league.
                self.client.get("/account")
                page.goto(self.origin + "/account/sleeper")
                bounds = page.locator('input[name="sleeper_username"]').bounding_box()
                card = page.locator('.card').bounding_box()
                self.assertLessEqual(bounds['x'] + bounds['width'], card['x'] + card['width'])
                self.assertGreaterEqual(float(page.locator('input[name="sleeper_username"]').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')), 16)
                if page.locator('input[name="sleeper_username"]').count() == 0:
                    self.source_failures.clear()
                    page.goto(self.origin + "/account/sleeper")
                page.locator('input[name="sleeper_username"]').fill("new-manager")
                self.source_failures.add("/user/")
                page.get_by_role("button", name="Find my Sleeper account", exact=True).click()
                self.assertIn("temporarily unavailable", page.locator("body").inner_text())
                page.get_by_role("link", name="Try again", exact=True).focus()
                self.assertTrue(page.get_by_role("link", name="Try again", exact=True).evaluate("e=>e===document.activeElement"))
                self.source_failures.clear()
                page.keyboard.press("Enter")
                page.locator('input[name="sleeper_username"]').fill("new-manager")
                page.get_by_role("button", name="Find my Sleeper account", exact=True).click()
                page.get_by_role("heading", name="First league", exact=True).wait_for()
                self.assertTrue(page.get_by_role("heading", name="Second league", exact=True).is_visible())
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                box = page.get_by_role("button", name="Add to DTOS", exact=True).first.bounding_box()
                self.assertGreaterEqual(box['height'], 44)
                reads = len(self.source_requests)
                before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(self.folder.name).iterdir() if p.is_file()}
                started = perf_counter()
                for _ in range(3):
                    self.client.get("/api/account")
                after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(self.folder.name).iterdir() if p.is_file()}
                self.assertEqual(before, after)
                self.assertEqual(reads, len(self.source_requests))
                rows.append({"width": width, "height": height, "import_action": box, "account_reads_ms": round((perf_counter()-started)*1000, 3), "durable_hashes_unchanged": True})
        target = os.environ.get("DTOS_PUBLIC_READINESS_EVIDENCE")
        if target:
            Path(target).write_text(json.dumps(rows, indent=2))

    def test_pending_connection_has_visible_status_and_history_recovery(self):
        with self.browser(320, 432) as page:
            page.goto(self.origin + '/account/sleeper')
            page.locator('input[name="sleeper_username"]').fill('new-manager')
            self.hold_source = True
            try:
                with page.expect_request('**/account/sleeper'):
                    pending = page.evaluate("""()=>{document.querySelector('form').requestSubmit();return {busy:document.querySelector('button')?.getAttribute('aria-busy'),disabled:document.querySelector('button')?.disabled,status:document.querySelector('[role=status]')?.textContent}}""")
                # Pump the browser transport after request interception so the
                # real local server can reach the deterministic source barrier.
                page.wait_for_timeout(100)
                self.assertTrue(self.source_entered.wait(3))
                self.assertEqual(pending['busy'], 'true')
                self.assertTrue(pending['disabled'])
                self.assertIn('Connecting', pending['status'])
            finally:
                self.hold_source = False
                self.source_resume.set()
            page.wait_for_url(self.origin + '/account/leagues')
            page.go_back(wait_until='load')
            self.assertTrue(page.get_by_role('button', name='Find my Sleeper account', exact=True).is_enabled())
            self.assertEqual(page.get_by_role('status').count(), 0)

    def test_market_warming_browser_retains_actions_without_overflow(self):
        from tests.test_market_warming_middleware import _Cache, _app
        cache = _Cache()
        self.app = _app(cache)
        for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
            with self.subTest(width=width), self.browser(width, height) as page:
                cache.warming = True
                response = page.goto(self.origin + '/market?q=quarterback')
                self.assertEqual(response.status, 503)
                self.assertTrue(page.get_by_role('heading', name='Market is preparing').is_visible())
                retry = page.get_by_role('link', name='Try Market again', exact=True)
                retry.focus()
                self.assertTrue(retry.evaluate('e=>e===document.activeElement'))
                self.assertGreaterEqual(float(retry.evaluate('e=>parseFloat(getComputedStyle(e).outlineWidth)')), 2)
                self.assertGreaterEqual(retry.bounding_box()['height'], 44)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                self.assertEqual(retry.get_attribute('href'), '/market?q=quarterback')
                cache.warming = False
                page.keyboard.press('Enter')
                page.wait_for_function("document.body.textContent.includes('ready')")
