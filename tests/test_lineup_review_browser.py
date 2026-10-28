"""Actual publisher/preparation/HTTP rendering in controlled Chromium only."""

import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests.lineup_review_fixture import authenticated_prepared
from tools.validation.browser_runtime import launch_chromium


class LineupReviewBrowserTests(unittest.TestCase):
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
