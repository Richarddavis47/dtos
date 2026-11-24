"""Actual publisher/preparation/HTTP rendering in controlled Chromium only."""

import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests.lineup_review_fixture import authenticated_prepared
from tools.validation.browser_runtime import launch_chromium


class LineupReviewBrowserTests(unittest.TestCase):
    def _home_with_early_fallback(self, *, confirmed):
        from unittest.mock import patch
        from services.matchup_season import season_week_view

        fixture, data, service, _ = authenticated_prepared(
            self, empty=False, uncertain="r", separate_early_rb=True,
            points=None if confirmed else {"bq": 1},
        )
        view = season_week_view(data, 8, service, review_roster_id=1)
        review = next(side["lineup_review"] for group in view["groups"].values()
                      for side in group if side["roster_id"] == 1)
        self.assertEqual(review["fallback"]["starter"], "Example R 1")
        self.assertEqual(review["actionable"], confirmed)
        if confirmed:
            self.assertLess(review["fallback"]["kickoff_deadline"], review["kickoff_deadline"])
        with patch("services.trade_intelligence._trade_projection_service", return_value=service), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = fixture.f.browser_page(browser, 390, 844)
                page.goto("https://dtos.test/")
                action = page.locator("#home-priority").get_by_role("link", name="Review lineup", exact=True)
                action.wait_for()
                directory = os.environ.get("DTOS_BRIEF_EVIDENCE")
                if directory:
                    case = "confirmed" if confirmed else "conditional-only"
                    page.screenshot(path=str(Path(directory, f"home-early-backup-{case}-390.png")))
                fragment = "lineup-action" if confirmed else "lineup-recheck"
                self.assertEqual(action.get_attribute("href"), "/teams/1#" + fragment)
                copy = page.locator("#home-priority").inner_text()
                if confirmed:
                    self.assertIn("Check your Week 8 lineup", copy)
                    self.assertNotIn("If Example R 1", copy)
                    action.click()
                    page.wait_for_url("**/teams/1#lineup-action")
                    self.assertTrue(page.locator('#team-lineup').is_visible())
                    self.assertTrue(page.locator('#lineup-action .thq-lineup-deadline time').is_visible())
                    self.assertIn('Higher-projected lineup available', page.locator('#lineup-action').inner_text())
                else:
                    self.assertIn("Have a backup ready", copy)
                    self.assertIn("If Example R 1 can’t play", copy)
                    page.close()
                    starter = data["players"]["1-r"]
                    name = "Example Starter With A Long Multi-Part Name"
                    starter.update(name=name, full_name=name)
                    page = fixture.f.browser_page(browser, 320, 432, touch=True)
                    page.goto("https://dtos.test/")
                    action = page.locator("#home-priority").get_by_role("link", name="Review lineup", exact=True)
                    action.wait_for()
                    self.assertIn(name, page.locator("#home-priority").inner_text())
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 320)
                    action.scroll_into_view_if_needed()
                    self.assertTrue(action.evaluate("""e => {
                        const box = e.getBoundingClientRect();
                        const nav = document.querySelector('.manager-nav').getBoundingClientRect();
                        const hits = [box.top + 2, box.top + box.height / 2, box.bottom - 2];
                        return box.height >= 44 && box.top >= 0 && box.bottom <= nav.top
                            && hits.every(y => e.contains(document.elementFromPoint(box.left + box.width / 2, y)));
                    }"""))
                    if directory:
                        page.screenshot(path=str(Path(directory, "home-long-action-320.png")))
                    action.tap()
                    page.wait_for_url("**/teams/1#lineup-recheck")
                    self.assertTrue(page.locator('#lineup-recheck [data-lineup-review="fallback"]').is_visible())
            finally:
                browser.close()

    def test_home_prioritizes_confirmed_change_over_earlier_fallback(self):
        self._home_with_early_fallback(confirmed=True)

    def test_home_keeps_conditional_fallback_when_it_is_the_only_lineup_action(self):
        self._home_with_early_fallback(confirmed=False)

    def test_signed_in_home_uses_verified_lineup_and_expires_with_keyboard_focus(self):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch
        fixture, data, service, _ = authenticated_prepared(self)
        with patch("services.trade_intelligence._trade_projection_service", return_value=service), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = fixture.f.browser_page(browser, 390, 844)
                page.clock.install(time=datetime.now(timezone.utc) - timedelta(hours=1))
                requests = []
                page.on('request', lambda request: requests.append(request.method))
                page.goto('https://dtos.test/')
                top = page.locator('#home-priority')
                action = top.get_by_role('link', name='Review lineup', exact=True)
                action.wait_for()
                self.assertIn('starting slot is empty', top.inner_text())
                self.assertEqual(action.get_attribute('href'), '/teams/1#lineup-action')
                self.assertEqual(action.get_attribute('data-dtos-action'), 'primary')
                directory = os.environ.get('DTOS_BRIEF_EVIDENCE')
                if directory:
                    page.screenshot(path=str(Path(directory, 'home-lineup-priority-390.png')))
                action.focus()
                page.clock.fast_forward(16 * 60 * 1000)
                calm = top.get_by_role('link', name='Open My Team', exact=True)
                self.assertTrue(calm.evaluate('e=>e===document.activeElement'))
                self.assertIn('lineup check expired', top.inner_text())
                self.assertTrue(all(method == 'GET' for method in requests))
                data['season_matchups']['weeks']['8']['observed_at'] = '2000-01-01T00:00:00+00:00'
                with page.expect_response('**/api/trades/home-opportunities?*'):
                    page.reload()
                page.wait_for_function("document.querySelector('#home-opportunities').dataset.state")
                self.assertEqual(action.count(), 0)
            finally:
                browser.close()

    def test_phone_desktop_exact_lineups_disclosures_navigation_and_expiry(self):
        fixture, data, service, _ = authenticated_prepared(self)
        client = fixture.f.f.client
        reports = []
        directory = os.environ.get("DTOS_LINEUP_REVIEW_EVIDENCE")
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    context = browser.new_context(
                        viewport=dict(width=width, height=height)
                    )

                    def transport(route):
                        from urllib.parse import urlsplit

                        path = urlsplit(route.request.url)
                        if path.hostname != "dtos.test":
                            route.fulfill(
                                status=200,
                                content_type="text/html",
                                body="<h1>External destination</h1>",
                            )
                            return
                        response = client.get(
                            path.path + ("?" + path.query if path.query else "")
                        )
                        if response.status_code == 404 and path.path.startswith(
                            "/static/"
                        ):
                            response = fixture.f.static.get(path.path)
                        route.fulfill(
                            status=response.status_code,
                            headers=dict(response.headers),
                            body=response.content,
                        )

                    context.route("**/*", transport)
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    self.assertEqual(
                        page.goto("https://dtos.test/matchups/1?week=8").status, 200
                    )
                    review = page.get_by_role("region", name="Lineup review")
                    self.assertEqual(review.count(), 1)
                    initial_box = review.bounding_box()
                    self.assertIn("+25.00 projected points", review.inner_text())
                    self.assertIn("Example BQ 1 (QB)", review.inner_text())
                    self.assertIn("Empty slot", review.inner_text())
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertEqual(
                        page.locator('[data-roster-section="lineup"]')
                        .get_by_text("Empty slot", exact=True)
                        .count(),
                        1,
                    )
                    summary = page.get_by_text(
                        "Lineup and projection evidence", exact=True
                    )
                    page.keyboard.press("Tab")
                    summary.focus()
                    self.assertNotEqual(
                        summary.evaluate("e=>getComputedStyle(e).outlineStyle"), "none"
                    )
                    summary.press("Enter")
                    self.assertTrue(summary.evaluate("e=>e.parentElement.open"))
                    text = summary.evaluate("e=>e.parentElement.innerText")
                    self.assertIn("Example BQ 1", text)
                    self.assertNotIn("· 1-bq", text)
                    # No content box may accidentally exceed the phone width.
                    bad = page.locator("main *").evaluate_all(
                        'es=>es.filter(e=>e.getBoundingClientRect().width>innerWidth+1).map(e=>e.tagName+"."+e.className)'
                    )
                    self.assertEqual(bad, [])
                    action = review.get_by_role("link", name="Review in Sleeper")
                    self.assertGreaterEqual(action.bounding_box()["height"], 44)
                    action.focus()
                    self.assertNotEqual(
                        action.evaluate("e=>getComputedStyle(e).outlineStyle"), "none"
                    )
                    page.evaluate("window.scrollTo(0,0)")
                    row = dict(
                        width=width,
                        height=height,
                        review=initial_box,
                        text=review.inner_text(),
                        disclosure_keyboard=True,
                        overflow=bad,
                    )
                    if directory:
                        Path(directory).mkdir(parents=True, exist_ok=True)
                        page.screenshot(
                            path=str(Path(directory, f"lineup-{width}.png")),
                            full_page=True,
                        )
                        Path(directory, f"lineup-{width}.html").write_text(
                            page.content(), encoding="utf-8"
                        )
                    # Expiry must retract the imperative suggestion in an open
                    # tab without a network call, reload or focus reset.
                    action.focus()
                    page.locator("[data-review-until]").evaluate(
                        'e=>e.dataset.reviewUntil="2000-01-01T00:00:00Z"'
                    )
                    page.evaluate(
                        'document.dispatchEvent(new Event("visibilitychange"))'
                    )
                    self.assertEqual(
                        review.get_attribute("data-lineup-review"), "expired"
                    )
                    self.assertFalse(
                        review.get_by_text(
                            "Apply these changes together in Sleeper.", exact=False
                        ).is_visible()
                    )
                    self.assertTrue(action.evaluate("e=>document.activeElement===e"))
                    row["expiry_focus_preserved"] = True
                    # Pointer and emulated touch use the same native disclosure.
                    summary.click()
                    self.assertFalse(summary.evaluate("e=>e.parentElement.open"))
                    cdp = context.new_cdp_session(page)
                    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
                    summary.scroll_into_view_if_needed()
                    box = summary.bounding_box()
                    point = dict(
                        x=box["x"] + box["width"] / 2, y=box["y"] + box["height"] / 2
                    )
                    cdp.send(
                        "Input.dispatchTouchEvent",
                        dict(type="touchStart", touchPoints=[point]),
                    )
                    cdp.send(
                        "Input.dispatchTouchEvent",
                        dict(type="touchEnd", touchPoints=[]),
                    )
                    self.assertTrue(summary.evaluate("e=>e.parentElement.open"))
                    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
                    page.get_by_role(
                        "link", name="All Week 8 matchups", exact=True
                    ).click()
                    self.assertEqual(page.url, "https://dtos.test/matchups?week=8")
                    page.get_by_role("link", name="Next week", exact=True).click()
                    self.assertEqual(page.url, "https://dtos.test/matchups?week=9")
                    self.assertEqual(
                        page.get_by_text(
                            "Higher-projected lineup available", exact=True
                        ).count(),
                        0,
                    )
                    self.assertEqual(errors, [])
                    reports.append(row)
                    context.close()
            finally:
                browser.close()
        if directory:
            Path(directory, "browser-results.json").write_text(
                json.dumps(reports, indent=2)
            )

    def test_slow_customer_clock_cannot_extend_verified_action_window(self):
        from datetime import datetime, timedelta, timezone
        from tests.lineup_review_fixture import prepared, http

        data, service, _ = prepared(self)
        client = http(self, data, service)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page()
                page.clock.install(time=datetime.now(timezone.utc) - timedelta(hours=1))

                def transport(route):
                    from urllib.parse import urlsplit

                    path = urlsplit(route.request.url)
                    response = client.get(
                        path.path + ("?" + path.query if path.query else "")
                    )
                    route.fulfill(
                        status=response.status_code,
                        headers=dict(response.headers),
                        body=response.content,
                    )

                page.route("**/*", transport)
                page.goto("https://dtos.test/matchups/1?week=8")
                panel = page.get_by_role("region", name="Lineup review")
                self.assertEqual(
                    panel.get_attribute("data-lineup-review"), "actionable"
                )
                page.clock.fast_forward(16 * 60 * 1000)
                self.assertEqual(panel.get_attribute("data-lineup-review"), "expired")
                self.assertEqual(
                    panel.get_by_text("Higher-projected lineup available").count(), 0
                )
            finally:
                browser.close()

    def test_expiring_a_focused_evidence_disclosure_keeps_visible_keyboard_focus(self):
        from tests.lineup_review_fixture import prepared, http
        from urllib.parse import urlsplit

        data, service, _ = prepared(self)
        client = http(self, data, service)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page()

                def transport(route):
                    path = urlsplit(route.request.url)
                    response = client.get(
                        path.path + ("?" + path.query if path.query else "")
                    )
                    route.fulfill(
                        status=response.status_code,
                        headers=dict(response.headers),
                        body=response.content,
                    )

                page.route("**/*", transport)
                page.goto("https://dtos.test/matchups/1?week=8")
                panel = page.get_by_role("region", name="Lineup review")
                summary = panel.locator("summary")
                page.keyboard.press("Tab")
                summary.focus()
                summary.press("Enter")
                panel.evaluate('e=>e.dataset.reviewUntil="2000-01-01T00:00:00Z"')
                page.evaluate('document.dispatchEvent(new Event("visibilitychange"))')
                action = panel.get_by_role("link", name="Review in Sleeper")
                self.assertTrue(action.evaluate("e=>document.activeElement===e"))
                self.assertNotEqual(
                    action.evaluate("e=>getComputedStyle(e).outlineStyle"), "none"
                )
                self.assertTrue(panel.get_by_role("status").is_visible())
                self.assertIn("expired", panel.get_by_role("status").inner_text())
            finally:
                browser.close()


class LineupFallbackBrowserTests(unittest.TestCase):
    def test_phone_fallback_in_lineup_section_and_expiry(self):
        from urllib.parse import urlsplit

        fixture, _, _, _ = authenticated_prepared(self, empty=False, uncertain="w", earlier_backup=True)
        directory = os.environ.get("DTOS_LINEUP_REVIEW_EVIDENCE")
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width in (320, 390, 1280):
                    context = browser.new_context(viewport={"width": width, "height": 844})
                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.hostname != "dtos.test":
                            route.abort()
                            return
                        response = fixture.f.f.client.get(url.path + ("?" + url.query if url.query else ""))
                        if response.status_code == 404 and url.path.startswith("/static/"):
                            response = fixture.f.static.get(url.path)
                        route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                    context.route("**/*", transport)
                    page = context.new_page()
                    self.assertEqual(page.goto("https://dtos.test/teams/1").status, 200)
                    self.assertTrue(page.locator("#full-roster").is_visible())
                    page.locator('.thq-tabs a[href="#team-lineup"]').click()
                    panel = page.get_by_role("region", name="Lineup fallback")
                    self.assertTrue(panel.is_visible())
                    self.assertIn("Example W 1 is ruled out", panel.inner_text())
                    self.assertIn("Example BQ 1 in for Example S 1", panel.inner_text())
                    self.assertIn("starts before the starter", panel.inner_text())
                    self.assertFalse(page.locator("#full-roster").is_visible())
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    action = panel.get_by_role("link", name="Review in Sleeper")
                    action.focus()
                    self.assertGreaterEqual(action.bounding_box()["height"], 44)
                    if directory:
                        Path(directory).mkdir(parents=True, exist_ok=True)
                        panel.screenshot(path=str(Path(directory, f"fallback-{width}.png")))
                    panel.evaluate('e=>e.dataset.reviewUntil="2000-01-01T00:00:00Z"')
                    page.evaluate('document.dispatchEvent(new Event("visibilitychange"))')
                    self.assertIn("fallback check has expired", panel.inner_text())
                    self.assertNotIn("Example W 1 is ruled out", panel.inner_text())
                    context.close()
            finally:
                browser.close()


class LineupRecheckBrowserTests(unittest.TestCase):
    def test_same_page_recheck_updates_rb_fallback_and_uses_local_date(self):
        from datetime import datetime
        from urllib.parse import urlsplit
        from zoneinfo import ZoneInfo

        from tests.lineup_review_fixture import publish_rb_lineup, recheck_fixture

        fixture, client, data, service, state, sync = recheck_fixture(self)
        game = datetime.fromisoformat(data["team_strength"]["lineup_review_schedule"]["games"]["8:BUF"]["kickoff"])
        timezone = "Pacific/Kiritimati" if game.hour >= 10 else "Etc/GMT+12"
        local = game.astimezone(ZoneInfo(timezone))
        self.assertNotEqual(game.date(), local.date())
        backup_starts = True
        result = "updated"
        requests = []

        async def refresh(**_):
            state["preparation_state"] = "waiting_for_capacity" if result == "deferred" else "ready"
            state["last_error"] = "fixture method failed" if result == "failed" else None
            if result == "updated":
                await publish_rb_lineup(data, service, backup_starts=backup_starts)
            return state

        sync.side_effect = refresh
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            context = browser.new_context(viewport={"width": 320, "height": 844},
                                          locale="en-US", timezone_id=timezone)

            def transport(route):
                request = route.request
                url = urlsplit(request.url)
                if url.hostname != "dtos.test":
                    route.abort()
                    return
                path = url.path + ("?" + url.query if url.query else "")
                if request.method == "POST":
                    requests.append(path)
                response = client.request(request.method, path, headers={
                    k: v for k, v in request.headers.items()
                    if k in {"accept", "x-csrf-token", "x-dtos-lineup-recheck"}
                })
                if response.status_code == 404 and url.path.startswith("/static/"):
                    response = fixture.f.static.get(path)
                route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)

            context.route("**/*", transport)
            page = context.new_page()
            try:
                for path in ("/teams/1#team-lineup", "/matchups/1?week=8"):
                    backup_starts = True
                    result = "updated"
                    page.goto("https://dtos.test" + path)
                    panel = page.locator("#lineup-recheck")
                    old = panel.get_attribute("data-lineup-observed")
                    button = page.get_by_role("button", name="Recheck lineup")
                    sync_before = len(requests)
                    page.reload()
                    self.assertEqual(len(requests), sync_before)
                    self.assertFalse(panel.get_by_text("can cover RB").count())
                    button.click()
                    message = panel.get_by_text("Submitted lineup rechecked.", exact=True)
                    message.wait_for()
                    self.assertEqual(page.url, "https://dtos.test" + path)
                    self.assertGreater(panel.get_attribute("data-lineup-observed"), old)
                    fallback = panel.get_by_role("region", name="Lineup fallback")
                    self.assertIn("If Example BQ 1 is ruled out, Example R 1 can cover RB.", fallback.inner_text())
                    game_lock = fallback.locator("time").first
                    self.assertIn(local.strftime("%b ") + str(local.day), game_lock.inner_text())
                    self.assertEqual(datetime.fromisoformat(game_lock.get_attribute("datetime")), game)
                    self.assertIn("Submitted lineup last checked:", panel.inner_text())
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 320)
                    evidence = os.environ.get("DTOS_LINEUP_REVIEW_EVIDENCE")
                    if evidence:
                        name = "my-team" if path.startswith("/teams") else "matchups"
                        panel.screenshot(path=str(Path(evidence, f"lineup-recheck-{name}-320.png")))
                    if path.startswith("/teams"):
                        for status, wording in (
                            ("deferred", "waiting for capacity"),
                            ("failed", "The lineup recheck failed"),
                        ):
                            result = status
                            button.click()
                            page.get_by_text(wording, exact=False).wait_for()
                            self.assertFalse(fallback.get_by_text("can cover RB").is_visible())
                            self.assertEqual(page.url, "https://dtos.test" + path)
                    result = "updated"
                    backup_starts = False
                    button.click()
                    panel.get_by_text("No conditional fallback is shown.", exact=False).wait_for()
                    self.assertEqual(fallback.count(), 0)
            finally:
                browser.close()
