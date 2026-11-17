"""Real prepared publication and rendered shared outlook; disposable fixtures."""

from datetime import datetime, timezone
import os
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_roster_diagnostic_http as fixtures


class PositionalPresentationBrowserTests(unittest.TestCase):
    def test_missing_rb_evidence_keeps_independent_qb_on_home_and_my_team(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.f.f.data
        data["teams"][0]["players"].append(
            dict(
                id="missing-rb",
                name="Missing reserve",
                position="RB",
                roster_slot="Bench",
            )
        )
        data["players"]["missing-rb"] = dict(position="RB", full_name="Missing reserve")
        f.publish(datetime.now(timezone.utc).isoformat())
        root = (
            Path(os.environ["DTOS_POSITION_SCOPE_EVIDENCE"])
            if os.environ.get("DTOS_POSITION_SCOPE_EVIDENCE")
            else None
        )
        if root:
            root.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    page = f.f.browser_page(browser, width, height)
                    requests = []
                    page.on("request", lambda r: requests.append((r.method, r.url)))
                    try:
                        for path, label, selector in (
                            ("/teams/1", "my-team", "#my-team-outlook"),
                            ("/", "home", '[aria-label="Franchise outlook"]'),
                        ):
                            page.goto("https://dtos.test" + path)
                            page.wait_for_load_state("networkidle")
                            card = page.locator(selector)
                            if label == "home":
                                card.locator("summary").press("Enter")
                            self.assertIn(
                                "Supported positional strength: QB", card.inner_text()
                            )
                            self.assertIn("Provisional", card.inner_text())
                            self.assertIn(
                                "Unknown depth is not a weakness", card.inner_text()
                            )
                            self.assertLessEqual(
                                page.evaluate(
                                    "document.documentElement.scrollWidth-innerWidth"
                                ),
                                0,
                            )
                            if root:
                                page.screenshot(
                                    path=str(root / f"{label}-{width}.png"),
                                    full_page=True,
                                )
                            if label == "my-team":
                                card.locator("summary").focus()
                                card.locator("summary").press("Enter")
                                self.assertIn(
                                    "not confirmed participation", card.inner_text()
                                )
                                if root:
                                    page.screenshot(
                                        path=str(
                                            root / f"{label}-expanded-{width}.png"
                                        ),
                                        full_page=True,
                                    )
                        self.assertFalse(
                            any(method == "POST" for method, url in requests)
                        )
                    finally:
                        page.close()
            finally:
                browser.close()
