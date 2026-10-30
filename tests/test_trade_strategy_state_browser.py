"""Released client -> real account/Trade/Team HTTP; no owner preference writes."""

import json
from contextlib import closing
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
import socket
import threading
import time
import uvicorn
from starlette.staticfiles import StaticFiles

from playwright.sync_api import Error as PlaywrightError, sync_playwright
from tests import test_roster_diagnostic_http as fixtures
from tools.validation.browser_runtime import launch_chromium


class StrategyStateBrowserTests(unittest.TestCase):
    def fixture(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.f.static.close)
        return f

    def rows(self, f):
        with closing(f.f.f.store.connect()) as c:
            return [dict(x) for x in c.execute("SELECT * FROM account_franchise_goals")]

    def page(self, browser, f, width=375, height=667, overrides=None):
        app = f.f.f.client.app
        if not any(getattr(route, "path", None) == "/static" for route in app.routes):
            app.mount(
                "/static",
                StaticFiles(directory=Path(__file__).resolve().parents[1] / "static"),
            )
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()

        def stop():
            server.should_exit = True
            thread.join(8)
            listener.close()
            if thread.is_alive():
                raise AssertionError("Owned fixture server did not stop")

        self.addCleanup(stop)
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(server.started)
        page = browser.new_page(viewport=dict(width=width, height=height))
        page._test_origin = origin
        page.context.add_cookies(
            [
                dict(
                    name="dtos_session",
                    value=f.f.f.client.cookies.get("dtos_session"),
                    url=origin,
                )
            ]
        )
        page.set_default_timeout(15000)
        records, held, errors = [], [], []
        state = dict(hold=False)
        page.on("pageerror", lambda e: errors.append(str(e)))

        def transport(route):
            request, u = route.request, urlsplit(route.request.url)
            if u.hostname != "127.0.0.1":
                return route.fulfill(status=200, body="")
            if u.path in (overrides or {}):
                return route.fulfill(
                    status=200, content_type="text/javascript", body=overrides[u.path]
                )
            response = page.request.fetch(
                request.url,
                method=request.method,
                data=request.post_data,
                headers=request.headers,
                max_redirects=0,
            )
            if request.method == "POST":
                records.append(
                    dict(
                        path=u.path,
                        status=response.status,
                        payload=request.post_data_json
                        if request.headers.get("content-type", "").startswith(
                            "application/json"
                        )
                        else None,
                    )
                )
            if u.path == "/api/trades/generate" and state["hold"]:
                held.append((route, response))
                return
            route.fulfill(
                status=response.status,
                headers=dict(response.headers),
                body=response.body(),
            )

        page.route("**/*", transport)
        return page, records, held, errors, state

    def ready(self, page):
        page.goto(page._test_origin + "/trades/recommended?front_office=1")
        page.wait_for_function("!document.querySelector('#trade-find').disabled")

    def test_three_temporary_choices_never_save_or_change_legacy_goal(self):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, _ = self.page(browser, f)
                self.ready(page)
                cookie = page.evaluate("document.cookie")
                for value in ("WIN NOW", "RETOOL", "REBUILD", ""):
                    page.select_option("#trade-strategy", value)
                    page.reload()
                    page.wait_for_function(
                        "!document.querySelector('#trade-find').disabled"
                    )
                    self.assertEqual(page.input_value("#trade-strategy"), value)
                    self.assertEqual(page.evaluate("document.cookie"), cookie)
                    self.assertEqual(self.rows(f), [])
                page.select_option("#trade-strategy", "REBUILD")
                page.goto(page._test_origin + "/teams/1")
                self.assertEqual(page.input_value("#my-team-strategy"), "")
                self.assertEqual(self.rows(f), [])
                self.assertFalse(
                    any(x["path"] == "/account/franchise-goal" for x in records)
                )
                self.assertEqual(errors, [])
                page.close()
            finally:
                browser.close()

    def test_existing_legacy_goal_is_not_reset_by_temporary_trade_choices(self):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, _ = self.page(browser, f)
                self.ready(page)
                page.evaluate("""async () => {
                  const w=await (await fetch('/api/trades/workspace')).json(), c=w.workspace_context;
                  const value={scope:c.strategy_scope,rows:[[c.league_id+':'+c.roster_id,'REBUILD']]};
                  document.cookie='dtos_strategy='+btoa(JSON.stringify(value)).replaceAll('+','-').replaceAll('/','_').replaceAll('=','')+'; Path=/; SameSite=Strict';
                }""")
                original = page.evaluate("document.cookie")
                for strategy in ("WIN NOW", "RETOOL", ""):
                    page.select_option("#trade-strategy", strategy)
                    page.reload()
                    page.wait_for_function(
                        "!document.querySelector('#trade-find').disabled"
                    )
                    self.assertEqual(page.input_value("#trade-strategy"), strategy)
                    self.assertEqual(page.evaluate("document.cookie"), original)
                page.goto(page._test_origin + "/teams/1")
                self.assertEqual(page.input_value("#my-team-strategy"), "REBUILD")
                self.assertEqual(self.rows(f), [])
                self.assertFalse(
                    any(x["path"] == "/account/franchise-goal" for x in records)
                )
                self.assertEqual(errors, [])
                page.close()
            finally:
                browser.close()

    def test_explicit_goal_save_and_unsaved_preview_are_separate_from_active_trade(
        self,
    ):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, _ = self.page(browser, f)
                page.goto(page._test_origin + "/teams/1?goal_saved=1")
                self.assertEqual(
                    page.locator("#my-team-strategy-feedback").inner_text(), ""
                )
                page.select_option("#my-team-strategy", "REBUILD")
                self.assertEqual(self.rows(f), [])
                self.assertIn(
                    "Unsaved", page.locator("#my-team-strategy-feedback").inner_text()
                )
                page.reload()
                self.assertEqual(page.input_value("#my-team-strategy"), "")
                page.select_option("#my-team-strategy", "WIN NOW")
                page.locator("#my-team-save-goal").focus()
                self.assertNotEqual(
                    page.locator("#my-team-save-goal").evaluate(
                        "e=>getComputedStyle(e).outlineStyle"
                    ),
                    "none",
                )
                page.locator("#my-team-save-goal").press("Enter")
                page.wait_for_url("**/teams/1?goal_saved=1")
                self.assertEqual(self.rows(f)[0]["strategy"], "WIN NOW")
                self.assertIn(
                    "Franchise goal saved",
                    page.locator("#my-team-strategy-feedback").inner_text(),
                )
                self.ready(page)
                self.assertEqual(page.input_value("#trade-strategy"), "WIN NOW")
                page.select_option("#trade-strategy", "RETOOL")
                page.reload()
                page.wait_for_function(
                    "!document.querySelector('#trade-find').disabled"
                )
                self.assertEqual(page.input_value("#trade-strategy"), "RETOOL")
                self.assertEqual(self.rows(f)[0]["strategy"], "WIN NOW")
                page.goto(page._test_origin + "/teams/1")
                self.assertEqual(page.input_value("#my-team-strategy"), "WIN NOW")
                self.assertEqual(
                    sum(x["path"] == "/account/franchise-goal" for x in records), 1
                )
                self.assertEqual(errors, [])
                page.close()
            finally:
                browser.close()

    def test_cancelled_generation_and_late_response_cannot_save_goal_or_restore_old_intent(
        self,
    ):
        f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, _, held, errors, state = self.page(browser, f)
                self.ready(page)
                page.select_option("#trade-strategy", "REBUILD")
                state["hold"] = True
                page.locator("#trade-find").click()
                page.wait_for_function(
                    "document.querySelector('#recommendation-status').dataset.state==='loading'"
                )
                deadline = time.monotonic() + 10
                while not held and time.monotonic() < deadline:
                    page.wait_for_timeout(20)
                self.assertEqual(len(held), 1)
                page.locator("#trade-cancel").click()
                page.select_option("#trade-strategy", "RETOOL")
                for route, response in held:
                    try:
                        route.fulfill(
                            status=response.status,
                            headers=dict(response.headers),
                            body=response.body(),
                        )
                    except PlaywrightError:
                        pass  # Aborted browser transport is expected; never an engine pass.
                page.wait_for_timeout(80)
                self.assertEqual(page.input_value("#trade-strategy"), "RETOOL")
                self.assertTrue(page.locator("#trade-result").is_hidden())
                self.assertEqual(self.rows(f), [])
                self.assertEqual(errors, [])
                page.close()
            finally:
                browser.close()

    def test_discovery_scope_and_explicit_save_controls_at_four_viewports(self):
        results = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    f = self.fixture()
                    page, records, _, errors, _ = self.page(browser, f, width, height)
                    self.ready(page)
                    page.select_option("#trade-strategy", "REBUILD")
                    page.locator("#trade-find").focus()
                    page.locator("#trade-find").press("Enter")
                    page.wait_for_function(
                        "document.querySelector('#recommendation-status').dataset.state==='complete'"
                    )
                    scope = page.get_by_role("note", name="Discovery coverage")
                    self.assertEqual(scope.count(), 1)
                    scope_text = scope.inner_text()
                    self.assertIn("not every theoretical trade", scope_text)
                    self.assertEqual(
                        scope.evaluate("e=>getComputedStyle(e).display"), "block"
                    )
                    self.assertNotIn(
                        "DISCOVERYNOT EXHAUSTIVE",
                        page.locator("#trade-result").inner_text(),
                    )
                    self.assertEqual(self.rows(f), [])
                    self.assertIsNone(records[-1]["payload"]["asset_id"])
                    self.assertEqual(records[-1]["payload"]["assets_sent"], [])
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    bad = page.locator("main *").evaluate_all(
                        'es=>es.filter(e=>e.getBoundingClientRect().width>innerWidth+1).map(e=>e.tagName+"."+e.className)'
                    )
                    self.assertEqual(bad, [])
                    root = os.environ.get("DTOS_STRATEGY_STATE_EVIDENCE")
                    if root:
                        Path(root).mkdir(parents=True, exist_ok=True)
                        page.screenshot(
                            path=str(Path(root, f"discovery-{width}.png")),
                            full_page=True,
                        )
                    page.goto(page._test_origin + "/teams/1")
                    select = page.locator("#my-team-strategy")
                    self.assertEqual(select.input_value(), "")
                    for choice in ("", "WIN NOW", "RETOOL", "REBUILD"):
                        select.select_option(choice)
                        fit = select.evaluate(
                            """e=>{const s=getComputedStyle(e), c=document.createElement('canvas').getContext('2d');c.font=s.font;return {required:c.measureText(e.selectedOptions[0].text).width+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+28,width:e.clientWidth}}"""
                        )
                        self.assertLessEqual(
                            fit["required"], fit["width"], (width, choice, fit)
                        )
                    select.select_option("REBUILD")
                    save = page.locator("#my-team-save-goal")
                    save.scroll_into_view_if_needed()
                    box = save.bounding_box()
                    self.assertGreaterEqual(box["height"], 44)
                    if width < 500:
                        touch = page.context.new_cdp_session(page)
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
                    else:
                        save.click()
                    page.wait_for_url("**/teams/1?goal_saved=1")
                    self.assertEqual(self.rows(f)[0]["strategy"], "REBUILD")
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertEqual(errors, [])
                    results.append(
                        dict(
                            width=width,
                            height=height,
                            scope=scope_text,
                            keyboard=True,
                            chromium_touch=width < 500,
                            explicit_save=True,
                            automatic_goal_writes=0,
                            overflow=bad,
                        )
                    )
                    if root:
                        page.screenshot(
                            path=str(Path(root, f"explicit-goal-{width}.png")),
                            full_page=True,
                        )
                    page.close()
            finally:
                browser.close()
        if os.getenv("DTOS_STRATEGY_STATE_EVIDENCE"):
            Path(os.environ["DTOS_STRATEGY_STATE_EVIDENCE"], "browser.json").write_text(
                json.dumps(results, indent=2)
            )
