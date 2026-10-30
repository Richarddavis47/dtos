"""Store -> authenticated HTTP -> complete rendered navigation journeys.

All mutable state is disposable. Chromium/CDP is not physical Safari.
"""

import copy
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from tools.validation.browser_runtime import launch_chromium
from tests import test_personal_rankings as personal


class ContextualBackTests(unittest.TestCase):
    def fixture(self):
        import dtos_app
        from routes.navigation import create_navigation_router
        from routes.trades import create_trades_router
        from routes.home import create_home_router
        from routes.teams import create_teams_router
        from routes.transactions import create_transactions_router
        from routes.market import create_market_router
        from routes.personal_rankings import create_personal_rankings_router
        from routes.accounts import create_accounts_router
        from services.personal_rankings import (
            personal_bootstrap,
            resolve_personal_context,
            validate_personal_context,
        )

        f = personal.PersonalRankingsTradeHTTPTests(
            "test_calculator_keeps_canonical_and_personal_costs_distinct"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        e = f.editor
        self.enterContext(patch.object(dtos_app, "account_store", e.store))
        deps = dict(store=e.store, market_reader=e.market)
        e.app.router.routes.clear()
        common = dict(
            ensure_fresh=AsyncMock(), require_data=lambda: e.data, page=dtos_app.page
        )
        e.app.include_router(create_navigation_router())
        e.app.include_router(
            create_trades_router(
                **common,
                personal_resolver=lambda d, p: resolve_personal_context(d, p, **deps),
                personal_validator=lambda d, p, c: validate_personal_context(
                    d, p, c, **deps
                ),
                personal_bootstrap=lambda d, a: personal_bootstrap(d, a, **deps),
            )
        )
        e.app.include_router(
            create_personal_rankings_router(
                service=e.service,
                require_data=lambda: e.data,
                market_model=lambda: e.market,
                page=dtos_app.page,
            )
        )
        e.app.include_router(create_home_router(**common))
        e.app.include_router(create_teams_router(**common, state={"data": e.data}))
        e.app.include_router(
            create_transactions_router(
                **common, state={"data": e.data}, refresh_transactions=AsyncMock()
            )
        )
        e.app.include_router(
            create_accounts_router(
                service=e.service, runtime_manager=SimpleNamespace(get=AsyncMock())
            )
        )
        # Prepared source adapter, not a Market factory: navigation must reuse
        # frozen compatible facts. All prices come from this same Trade source.
        data = e.data

        class PreparedNavigationMarket:
            semantic_generation = "navigation-frozen-A"
            dataset_version = "navigation-frozen-history-empty"

            def __init__(self):
                self.data = data
                self.rows = [
                    dict(
                        r,
                        canonical_url="/players/" + r["asset_id"].split(":", 1)[1],
                        historical_availability="unavailable",
                        availability="rostered",
                    )
                    for r in e.market.rows
                    if r["asset_id"].startswith("player:")
                ]

            def identity(self):
                return {
                    "league_id": "league-1",
                    "market_generation": self.semantic_generation,
                }

            def directory(self, offset=0, limit=10, **kw):
                rows = sorted(
                    [
                        r
                        for r in self.rows
                        if not kw.get("position") or r["position"] == kw["position"]
                    ],
                    key=lambda r: (-(r["values"]["market_value"] or 0), r["asset_id"]),
                )
                if kw.get("q"):
                    rows = [
                        r
                        for r in rows
                        if kw["q"].casefold() in r["display_name"].casefold()
                    ]
                return {
                    **self.identity(),
                    "total": len(rows),
                    "assets": copy.deepcopy(rows[offset : offset + limit]),
                }

            def search(self, q, limit=10, **kw):
                return self.directory(limit=limit, q=q, **kw)

            def detail(self, key, front_office=None):
                row = next((r for r in self.rows if r["asset_id"] == key), None)
                if row is None:
                    return None
                return {
                    **self.identity(),
                    "asset": copy.deepcopy(row),
                    "history": {},
                    "value_layers": {},
                    "historical_dataset_version": self.dataset_version,
                    "recommendation": {
                        "primary_reason": "Prepared compatible fixture price; historical evidence is not supplied.",
                        "confidence": None,
                        "missing_evidence": ["Historical observations"],
                        "brain_snapshot_id": "navigation-frozen-A",
                    },
                }

        model = PreparedNavigationMarket()
        state = {"data": data, "last_sync": "2026-10-01T00:00:00+00:00"}
        e.app.include_router(
            create_market_router(
                require_data=lambda: e.data,
                page=dtos_app.page,
                state=state,
                league_id="league-1",
                context_resolver=lambda: SimpleNamespace(
                    state=state,
                    league_id="league-1",
                    market=SimpleNamespace(get=lambda *a, **k: model),
                    projection=f.capital.reader,
                ),
            )
        )
        e.initialize()
        f.static = TestClient(dtos_app.app)
        return f

    def page(self, browser, f, width=375, height=667):
        p = browser.new_page(viewport=dict(width=width, height=height))
        p.set_default_timeout(9000)
        requests = []
        held = []
        control = {"hold": False}
        errors = []
        p.on("pageerror", lambda x: errors.append(str(x)))
        # Real loopback HTTP preserves native redirects. Playwright interception
        # cannot replay redirected requests reliably; no auth behavior is faked.
        pending = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.serve()

            def do_POST(self):
                self.serve()

            def serve(self):
                u = urlsplit(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                response = f.editor.client.request(
                    self.command,
                    self.path,
                    content=body,
                    headers={
                        k: v
                        for k, v in self.headers.items()
                        if k.lower() in ["content-type", "x-csrf-token", "accept"]
                    },
                    follow_redirects=False,
                )
                if response.status_code == 404 and u.path.startswith("/static/"):
                    response = f.static.get(u.path)
                requests.append((self.command, u.path, response.status_code))
                if (
                    control["hold"]
                    and self.command == "POST"
                    and u.path.startswith("/api/trades/")
                ):
                    event = Event()
                    pending.append(event)
                    held.append(
                        (SimpleNamespace(fulfill=lambda **kw: event.set()), response)
                    )
                    event.wait(15)
                self.send_response(response.status_code)
                for k, v in response.headers.items():
                    if k.lower() not in [
                        "content-length",
                        "transfer-encoding",
                        "connection",
                        "content-encoding",
                    ]:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                try:
                    self.wfile.write(response.content)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.origin = "http://127.0.0.1:" + str(server.server_port)

        def cleanup():
            for event in pending:
                event.set()
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())

        self.addCleanup(cleanup)
        p.route("https://sleepercdn.com/**", lambda r: r.fulfill(status=200, body=""))
        return p, requests, held, control, errors

    def ready(self, p, path="/trades/create"):
        p.goto(self.origin + "" + path)
        p.wait_for_function(
            "!document.querySelector('#trade-context').textContent.includes('Loading')"
        )

    @staticmethod
    def draft(p):
        return p.evaluate(
            "JSON.parse(sessionStorage.getItem('dtos-trade-workspace:'+document.querySelector('meta[name=dtos-navigation-scope]').content))"
        )

    def choose(self, p):
        p.select_option("#trade-partner", "2")
        p.select_option("#trade-strategy", "REBUILD")
        p.locator('#trade-sent-board button[data-asset-id="a"]').click()
        if p.locator("[data-side=received]").is_visible():
            p.locator("[data-side=received]").click()
        p.locator('#trade-received-board button[data-asset-id="2028-R1-4"]').click()

    def back(self, p, path):
        p.locator("#dtos-back").click()
        p.wait_for_url("**" + path)

    def test_scope_is_opaque_private_live_and_provider_free(self):
        f = self.fixture()
        client = f.editor.client
        with (
            patch(
                "services.sleeper.sleeper_get", side_effect=AssertionError("provider")
            ),
            patch(
                "src.core.fois.service.FOISService._generate_sync",
                side_effect=AssertionError("FOIS"),
            ),
        ):
            one = client.get("/api/account/navigation-context")
        self.assertEqual(one.status_code, 200)
        self.assertIn("no-store", one.headers["cache-control"])
        d = one.json()
        self.assertEqual(set(d), {"scope", "team"})
        self.assertEqual(len(d["scope"]), 64)
        w = client.get("/api/trades/workspace").json()
        self.assertEqual(d["scope"], w["workspace_context"]["binding"])
        raw = json.dumps(d)
        self.assertNotIn("account-a", raw)
        self.assertNotIn("league-1", raw)
        self.assertNotIn(f.editor.csrf, raw)
        other = f.editor.service.new_session("account-b")[0]
        with TestClient(f.editor.app) as c:
            self.assertEqual(c.get("/api/account/navigation-context").status_code, 401)
            c.cookies.set("dtos_session", other)
            self.assertNotEqual(
                c.get("/api/account/navigation-context").json()["scope"], d["scope"]
            )
        f.editor.store.revoke_session(f.editor.tokens["account-a"][0])
        self.assertEqual(client.get("/api/account/navigation-context").status_code, 401)

    def test_league_team_depth_back_and_phone_controls(self):
        f = self.fixture()
        rows = []
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                for w, h in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    p, requests, _, _, errors = self.page(b, f, w, h)
                    p.goto(self.origin + "/league")
                    p.locator('.manager-nav a[href="/teams/1"]').click()
                    p.wait_for_url("**/teams/1")
                    p.locator('a[href="#positional-depth"]').first.click()
                    p.wait_for_url("**#positional-depth")
                    back = p.locator("#dtos-back")
                    p.keyboard.press("Tab")
                    back.focus()
                    self.assertNotEqual(
                        back.evaluate("e=>getComputedStyle(e).outlineStyle"), "none"
                    )
                    p.keyboard.press("Enter")
                    p.wait_for_url("**/teams/1")
                    if w < 760:
                        back.scroll_into_view_if_needed()
                        box = back.bounding_box()
                        touch = p.context.new_cdp_session(p)
                        touch.send(
                            "Emulation.setTouchEmulationEnabled", {"enabled": True}
                        )
                        touch.send(
                            "Input.dispatchTouchEvent",
                            dict(
                                type="touchStart",
                                touchPoints=[
                                    dict(
                                        x=box["x"] + box["width"] / 2,
                                        y=box["y"] + box["height"] / 2,
                                    )
                                ],
                            ),
                        )
                        touch.send(
                            "Input.dispatchTouchEvent",
                            dict(type="touchEnd", touchPoints=[]),
                        )
                        touch.send(
                            "Emulation.setTouchEmulationEnabled", {"enabled": False}
                        )
                        p.wait_for_url("**/league")
                    else:
                        self.back(p, "/league")
                    p.locator("#dtos-back").focus()
                    p.evaluate(
                        "()=>{window.dtosNavigation.restoreView();return new Promise(requestAnimationFrame)}"
                    )
                    self.assertEqual(
                        p.locator("#dtos-back").evaluate(
                            "e=>document.activeElement===e"
                        ),
                        True,
                    )
                    bounds = p.locator("#dtos-back").bounding_box()
                    self.assertGreaterEqual(bounds["height"], 44)
                    self.assertLess(bounds["y"], h)
                    self.assertLessEqual(
                        p.evaluate("document.documentElement.scrollWidth"), w
                    )
                    self.assertEqual(p.locator(".manager-nav a").count(), 5)
                    self.assertFalse(errors, errors)
                    rows.append(dict(width=w, height=h, back=bounds, overflow=False))
                    out = os.getenv("DTOS_CONTEXTUAL_BACK_EVIDENCE")
                    if out:
                        Path(out).mkdir(parents=True, exist_ok=True)
                        p.screenshot(path=str(Path(out) / f"back-{w}.png"))
                    p.close()
            finally:
                b.close()
        if os.getenv("DTOS_CONTEXTUAL_BACK_EVIDENCE"):
            (
                Path(os.environ["DTOS_CONTEXTUAL_BACK_EVIDENCE"]) / "geometry.json"
            ).write_text(json.dumps(rows, indent=2))

    def test_trade_market_dossier_back_preserves_custom_exact_package_and_filters(self):
        f = self.fixture()
        original = f.editor.state()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    p, requests, _, _, errors = self.page(b, f, width, height)
                    self.ready(p)
                    self.choose(p)
                    p.select_option("#trade-valuation-mode", "custom")
                    if p.locator("[data-side=sent]").is_visible():
                        p.locator("[data-side=sent]").click()
                    p.locator("#trade-sent-board input[type=search]").fill("a")
                    p.locator("#trade-run").click()
                    p.wait_for_function(
                        "document.querySelector('#trade-result').dataset.assessment==='true' && document.querySelector('#trade-builder').getAttribute('aria-busy')==='false'"
                    )
                    before = self.draft(p)
                    posts = sum(m == "POST" for m, _, _ in requests)
                    p.locator('.manager-nav a[href="/market"]').click()
                    p.wait_for_url("**/market")
                    form = p.locator('form[action="/market"]').first
                    form.locator("[name=q]").fill("c")
                    form.evaluate("f=>f.requestSubmit()")
                    p.wait_for_url("**/market?*q=c*")
                    p.locator(".market-asset").first.click()
                    p.locator("a").filter(has_text="Open canonical dossier").click()
                    p.wait_for_url("**/players/*")
                    p.locator("#dtos-back").click()
                    p.wait_for_url("**/market?*")
                    self.assertIn("q=c", p.url)
                    for _ in range(5):
                        if "/market" not in urlsplit(p.url).path:
                            break
                        prior_url = p.url
                        p.locator("#dtos-back").click()
                        p.wait_for_url(lambda url: str(url) != prior_url)
                        p.wait_for_load_state("domcontentloaded")
                        if p.locator("#trade-builder").count():
                            break
                    p.locator("#trade-partner").wait_for()
                    p.wait_for_function(
                        "!document.querySelector('#trade-context').textContent.includes('Loading')"
                    )
                    after = self.draft(p)
                    self.assertEqual(
                        after["currentProposal"], before["currentProposal"]
                    )
                    self.assertEqual(after["valuationMode"], "custom")
                    self.assertEqual(
                        p.locator("#trade-sent-board input[type=search]").input_value(),
                        "a",
                    )
                    self.assertEqual(sum(m == "POST" for m, _, _ in requests), posts)
                    self.assertIn(
                        "retained", p.locator("#trade-result").inner_text().lower()
                    )
                    self.assertFalse(errors, errors)
                    self.assertEqual(f.editor.state()["rows"], original["rows"])
                    self.assertEqual(f.editor.state()["revision"], original["revision"])
                    self.assertFalse(
                        p.evaluate("document.documentElement.scrollWidth>innerWidth")
                    )
                    if os.getenv("DTOS_CONTEXTUAL_BACK_EVIDENCE"):
                        out = Path(os.environ["DTOS_CONTEXTUAL_BACK_EVIDENCE"])
                        out.mkdir(parents=True, exist_ok=True)
                        p.screenshot(
                            path=str(out / f"trade-return-{width}.png"), full_page=True
                        )
                    p.close()
            finally:
                b.close()

    def test_neutral_context_return_and_deliberate_trade_tab_have_different_reset_contracts(
        self,
    ):
        f = self.fixture()
        from src.core.accounts.goal_store import save_goal
        save_goal(f.editor.store, f.editor.store.context_for_session(f.editor.tokens["account-a"][0]), "WIN NOW", 0)
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = self.page(b, f)
                self.ready(p)
                self.choose(p)
                p.select_option("#trade-valuation-mode", "neutral")
                before = self.draft(p)["currentProposal"]
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                self.back(p, "/trades/create")
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(self.draft(p)["currentProposal"], before)
                self.assertEqual(
                    p.locator("#trade-valuation-mode").input_value(), "neutral"
                )
                p.reload()
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(self.draft(p)["currentProposal"], before)
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                p.locator('.manager-nav a[href="/trades"]').click()
                p.wait_for_url("**/trades")
                p.locator('.tw-entry-actions a[href*="/trades/calculator"]').click()
                p.locator("#trade-partner").wait_for()
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(
                    self.draft(p)["currentProposal"],
                    {"sent": [], "received": [], "partner": 0},
                )
                # Fresh primary entry uses the franchise goal, not an old Trade choice.
                self.assertEqual(p.locator("#trade-strategy").input_value(), "WIN NOW")
                self.assertFalse(any(m == "POST" for m, _, _ in requests))
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_departure_cancels_pending_work_without_restarting_or_accepting_late_results(
        self,
    ):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, held, control, errors = self.page(b, f)
                self.ready(p)
                self.choose(p)
                original = self.draft(p)["currentProposal"]
                control["hold"] = True
                p.locator("#trade-run").click()
                p.wait_for_function(
                    "document.querySelector('#trade-board').getAttribute('aria-busy')==='true'"
                )
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                self.back(p, "/trades/create")
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(self.draft(p)["currentProposal"], original)
                self.assertIn(
                    "previous operation stopped",
                    p.locator("#recommendation-status").inner_text(),
                )
                self.assertEqual(sum(m == "POST" for m, _, _ in requests), 1)
                for route, response in held:
                    try:
                        route.fulfill(
                            status=response.status_code,
                            headers=dict(response.headers),
                            body=response.content,
                        )
                    except Exception as exc:
                        self.assertTrue(
                            any(
                                x in str(exc).lower()
                                for x in ["closed", "handled", "cancel", "invalid"]
                            ),
                            str(exc),
                        )
                self.assertNotEqual(
                    p.locator("#trade-result").get_attribute(
                        "data-assessment-freshness"
                    ),
                    "current",
                )
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_preview_keep_adopt_adjust_and_source_changes_survive_a_contextual_return(
        self,
    ):
        f = self.fixture()
        self.assertEqual(
            f.editor.post("reorder", asset_id="player:a", to_position=1).status_code,
            200,
        )
        saved = f.editor.state()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = self.page(b, f)
                self.ready(p, "/trades/calculator")
                self.choose(p)
                original = self.draft(p)["currentProposal"]
                p.locator("#trade-balance-offer").click()
                p.get_by_role(
                    "button", name="Preview adjustment", exact=True
                ).first.click()
                before = self.draft(p)
                self.assertIsNotNone(before["previewProposal"])
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                f.capital.points["c"] = 21
                f.capital.publish()
                self.back(p, "/trades/calculator")
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                after = self.draft(p)
                self.assertEqual(after["currentProposal"], original)
                self.assertEqual(
                    after["previewProposal"]["assets_sent"],
                    before["previewProposal"]["assets_sent"],
                )
                self.assertTrue(after["previewProposal"]["preview_context"]["restored"])
                p.get_by_role("button", name="Keep original", exact=True).click()
                self.assertEqual(self.draft(p)["currentProposal"], original)
                # A deliberate new balance request obtains current evidence;
                # returning never silently reruns or revalidates the old one.
                p.locator("#trade-balance-offer").click()
                p.get_by_role(
                    "button", name="Preview adjustment", exact=True
                ).first.click()
                expected = self.draft(p)["previewProposal"]
                p.get_by_role("button", name="Adopt alternative", exact=True).click()
                adopted = self.draft(p)["currentProposal"]
                self.assertEqual(adopted["sent"], expected["assets_sent"])
                self.assertEqual(adopted["received"], expected["assets_received"])
                p.locator("#trade-adjust").click()
                p.locator("#trade-instruction").fill("keep this incoming asset")
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                self.back(p, "/trades/calculator")
                p.wait_for_function(
                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(self.draft(p)["currentProposal"], adopted)
                self.assertEqual(
                    p.locator("#trade-instruction").input_value(),
                    "keep this incoming asset",
                )
                self.assertEqual(f.editor.state()["revision"], saved["revision"])
                self.assertEqual(f.editor.state()["rows"], saved["rows"])
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_direct_entry_refresh_browser_traversal_and_disclosures_do_not_loop(self):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, _, _, _, errors = self.page(b, f)
                p.goto(self.origin + "/players/c")
                self.assertEqual(
                    p.locator("#dtos-back").get_attribute("href"), "/market"
                )
                self.back(p, "/market")
                p.locator('.manager-nav a[href="/teams/1"]').click()
                p.wait_for_url("**/teams/1")
                count = p.evaluate(
                    "JSON.parse(sessionStorage.getItem('dtos-contextual-navigation:v1')).entries.length"
                )
                p.locator("#my-team-roster > summary").click()
                p.locator("#my-team-roster > summary").click()
                self.assertEqual(
                    p.evaluate(
                        "JSON.parse(sessionStorage.getItem('dtos-contextual-navigation:v1')).entries.length"
                    ),
                    count,
                )
                p.locator('a[href="#draft-capital"]').first.click()
                p.wait_for_url("**#draft-capital")
                p.go_back()
                p.wait_for_url("**/teams/1")
                p.go_forward()
                p.wait_for_url("**#draft-capital")
                p.reload()
                self.back(p, "/teams/1")
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                p.go_back()
                p.wait_for_url("**/teams/1")
                p.go_forward()
                p.wait_for_url("**/market")
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_scope_changes_and_expired_sessions_fail_closed_on_back_and_bfcache(self):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, _, _, _, errors = self.page(b, f)
                self.ready(p)
                self.choose(p)
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                f.editor.use_account("account-b")
                p.locator("#dtos-back").click()
                p.wait_for_url(self.origin + "/")
                self.assertEqual(p.locator("#trade-builder").count(), 0)
                f.editor.use_account("account-a")
                self.ready(p)
                # Real selected membership changes; identical roster IDs cannot
                # make a former league's navigation history trustworthy.
                f.editor.store.upsert_membership(
                    "account-a",
                    {"league_id": "league-2", "name": "Other"},
                    "account-a",
                    1,
                    "Other",
                    "active",
                )
                f.editor.store.activate("account-a", "league-2")
                f.editor.data["league"]["league_id"] = "league-2"
                p.evaluate(
                    "dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));"
                )
                p.wait_for_url(self.origin + "/")
                self.assertEqual(p.locator("#trade-builder").count(), 0)
                f.editor.store.activate("account-a", "league-1")
                f.editor.data["league"]["league_id"] = "league-1"
                self.ready(p)
                f.editor.store.revoke_session(f.editor.tokens["account-a"][0])
                p.evaluate(
                    "dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));"
                )
                p.wait_for_url(re.compile(r"/account/sign-in\?next=/$"))
                self.assertEqual(p.locator("#trade-builder").count(), 0)
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_untrusted_history_error_retry_and_bounded_navigation_state(self):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, _, _, _, errors = self.page(b, f)
                p.goto(self.origin + "/league")
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                p.route(
                    "**/api/account/navigation-context",
                    lambda r: r.fulfill(status=503, json={"status": "unavailable"}),
                )
                p.locator("#dtos-back").click()
                p.locator("#dtos-back-status").get_by_text(
                    "Back could not verify", exact=False
                ).wait_for()
                self.assertIn("/market", p.url)
                p.unroute("**/api/account/navigation-context")
                self.back(p, "/league")
                p.evaluate(
                    """() => {const k='dtos-contextual-navigation:v1',x=JSON.parse(sessionStorage.getItem(k));x.entries[0].url='https://evil.invalid/account';sessionStorage.setItem(k,JSON.stringify(x));} """
                )
                p.reload()
                self.assertEqual(p.locator("#dtos-back").get_attribute("href"), "/")
                for n in range(36):
                    p.evaluate(
                        "n=>{const a=document.createElement('a');a.href='/league?view='+n;a.id='fixture-next';a.textContent='Next';document.body.append(a);a.click();}",
                        n,
                    )
                    p.wait_for_url("**/league?view=" + str(n))
                state = p.evaluate(
                    "sessionStorage.getItem('dtos-contextual-navigation:v1')"
                )
                self.assertLessEqual(len(json.loads(state)["entries"]), 32)
                self.assertLess(len(state), 65536)
                self.assertNotIn("currentProposal", state)
                self.assertNotIn("csrf", state)
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_storage_denial_and_no_prior_context_have_truthful_safe_fallbacks(self):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, _, _, _, errors = self.page(b, f)
                p.add_init_script(
                    "Storage.prototype.getItem=()=>{throw new DOMException('fixture blocked','SecurityError')};Storage.prototype.setItem=()=>{throw new DOMException('fixture blocked','SecurityError')}"
                )
                self.ready(p)
                self.assertIn(
                    "return context", p.locator("#dtos-navigation-storage").inner_text()
                )
                self.assertTrue(p.locator("#trade-run").is_visible())
                p.goto(self.origin + "/players/c")
                self.assertEqual(
                    p.locator("#dtos-back").get_attribute("href"), "/market"
                )
                self.back(p, "/market")
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_a_late_back_scope_check_cannot_override_new_primary_navigation(self):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, _, _, _, errors = self.page(b, f)
                self.ready(p)
                self.choose(p)
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                held = []
                p.route("**/api/account/navigation-context", lambda r: held.append(r))
                p.locator("#dtos-back").click()
                p.wait_for_function(
                    "document.querySelector('#dtos-back').getAttribute('aria-busy')==='true'"
                )
                p.locator('.manager-nav a[href="/trades"]').click()
                p.wait_for_url("**/trades")
                for r in held:
                    try:
                        r.fulfill(json={"scope": "0" * 64})
                    except Exception as exc:
                        self.assertTrue(
                            any(
                                x in str(exc).lower()
                                for x in ["closed", "handled", "cancel", "invalid"]
                            ),
                            str(exc),
                        )
                p.wait_for_timeout(60)
                self.assertEqual(urlsplit(p.url).path, "/trades")
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_my_dtos_return_preserves_editor_view_without_writing_rankings(self):
        f = self.fixture()
        original = f.editor.state()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = self.page(b, f)
                p.goto(self.origin + "/account/my-dtos")
                p.locator(".personal-row").first.wait_for()
                self.assertTrue(p.locator("#dtos-back").is_visible())
                self.assertGreaterEqual(
                    p.locator("#dtos-back").bounding_box()["height"], 44
                )
                p.locator("#personal-search").fill("c")
                p.locator("#personal-position").select_option("QB")
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                self.back(p, "/account/my-dtos")
                p.locator(".personal-row").first.wait_for()
                self.assertEqual(p.locator("#personal-search").input_value(), "c")
                self.assertEqual(p.locator("#personal-position").input_value(), "QB")
                self.assertEqual(f.editor.state()["rows"], original["rows"])
                self.assertEqual(f.editor.state()["revision"], original["revision"])
                self.assertFalse(any(m == "POST" for m, _, _ in requests))
                self.assertFalse(errors, errors)
            finally:
                b.close()

    def test_prepared_contextual_return_adds_no_provider_or_intelligence_work(self):
        from contextlib import ExitStack
        import importlib

        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = self.page(b, f)
                self.ready(p)
                self.choose(p)
                guarded_names = [
                    "src.core.data_platform.provider_activation.refresh_public_market",
                    "src.core.data_platform.platform.DataPlatform.refresh",
                    "src.core.projection_intelligence.service.ProjectionService.generate",
                    "src.core.projection_intelligence.service.ProjectionService.publish_horizon",
                    "services.global_evidence.retained_global_evidence",
                    "services.sleeper.sleeper_get",
                    "services.trade_intelligence.generate_trade_workflow",
                    "src.core.fois.service.FOISService._generate_sync",
                    "src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct",
                ]
                with ExitStack() as stack:
                    guarded = {
                        name: stack.enter_context(
                            patch(name, side_effect=AssertionError(name))
                        )
                        for name in guarded_names
                    }
                    solvers = {}
                    for name in [
                        "src.core.trade_intelligence.lineup_memo",
                        "src.core.intelligence.roster_evidence",
                        "src.core.roster_intelligence.engine",
                        "src.core.intelligence.team_strength",
                    ]:
                        mod = importlib.import_module(name)
                        solvers[name] = stack.enter_context(
                            patch.object(
                                mod,
                                "optimal_legal_lineup",
                                wraps=mod.optimal_legal_lineup,
                            )
                        )
                    p.locator('.manager-nav a[href="/market"]').click()
                    p.wait_for_url("**/market")
                    before = {name: spy.call_count for name, spy in solvers.items()}
                    count = len(requests)
                    self.back(p, "/trades/create")
                    p.wait_for_function(
                        "!document.querySelector('#trade-context').textContent.includes('Loading')"
                    )
                    after = {name: spy.call_count for name, spy in solvers.items()}
                    self.assertEqual(before, after)
                    self.assertTrue(
                        all(spy.call_count == 0 for spy in guarded.values())
                    )
                    self.assertFalse(
                        any(method == "POST" for method, _, _ in requests[count:])
                    )
                    self.assertFalse(errors, errors)
                    if os.getenv("DTOS_CONTEXTUAL_BACK_EVIDENCE"):
                        out = Path(os.environ["DTOS_CONTEXTUAL_BACK_EVIDENCE"])
                        out.mkdir(parents=True, exist_ok=True)
                        (out / "prepared-read-costs.json").write_text(
                            json.dumps(
                                dict(
                                    guarded_calls={
                                        name: spy.call_count
                                        for name, spy in guarded.items()
                                    },
                                    solver_before=before,
                                    solver_after=after,
                                    return_requests=requests[count:],
                                    scope="Prepared disposable HTTP, preparation excluded; not production capacity",
                                ),
                                indent=2,
                            )
                        )
            finally:
                b.close()

    def test_history_filters_survive_a_contextual_return_without_replaying_refresh(
        self,
    ):
        f = self.fixture()
        with sync_playwright() as pw:
            b = launch_chromium(pw, headless=True)
            try:
                p, requests, _, _, errors = self.page(b, f)
                path = "/transactions?team=1&type=trade&status=complete&q=alpha&page=2&per_page=25"
                p.goto(self.origin + path)
                p.locator('.manager-nav a[href="/market"]').click()
                p.wait_for_url("**/market")
                self.back(p, path)
                self.assertEqual(urlsplit(p.url).query, urlsplit(path).query)
                self.assertFalse(
                    any(
                        method == "POST" or "refresh" in urlsplit(url).path
                        for method, url, _ in requests
                    )
                )
                self.assertFalse(errors, errors)
            finally:
                b.close()


if __name__ == "__main__":
    unittest.main()
