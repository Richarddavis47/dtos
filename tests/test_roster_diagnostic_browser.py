"""Codex-hosted rendered admission states, not independent live acceptance."""

import json
import os
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright
from tests import test_roster_diagnostic_http as fixtures
from tools.validation.browser_runtime import launch_chromium


class DiagnosticBrowserTests(unittest.TestCase):
    def test_readable_stale_exclusions_and_missing_scoring_at_phone_widths(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        player = f.f.f.data["teams"][0]["players"][1]
        player["status"] = "Inactive"
        player["name"] = "Supported QB Reserve"
        f.f.f.data["players"][player["id"]].update(
            status="Inactive", name=player["name"]
        )
        f.publish("2020-01-01T00:00:00+00:00")
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for state in ("stale", "missing-scoring"):
                    if state == "missing-scoring":
                        f.f.f.data["league"].pop("scoring_settings")
                        f.f.f.data.pop("scoring_settings", None)
                        f.publish()
                    for width, height in (
                        (320, 432),
                        (375, 667),
                        (390, 682),
                        (390, 844),
                        (1280, 900),
                    ):
                        page = f.f.browser_page(browser, width, height)
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        for rid in (1, 2):
                            self.assertEqual(
                                page.goto(f"https://dtos.test/teams/{rid}").status, 200
                            )
                            room = page.locator("#positional-depth")
                            disclosure = room.get_by_text(
                                "Lineup eligibility and surplus", exact=True
                            ).first
                            disclosure.focus()
                            page.keyboard.press("Enter")
                            body = room.inner_text()
                            self.assertIn(
                                "Stale"
                                if state == "stale"
                                else "insufficient supported scoring evidence",
                                body,
                            )
                            self.assertNotIn("remove_one", body)
                            self.assertNotIn("'preserves_lineup'", body)
                            if rid == 1:
                                self.assertIn("Supported QB Reserve", body)
                                self.assertIn("excluded from usable cover", body)
                            self.assertLessEqual(
                                page.evaluate("document.documentElement.scrollWidth"),
                                width,
                            )
                            card = room.locator("article").first
                            box = card.bounding_box()
                            if width <= 390:
                                self.assertGreater(box["width"], width * 0.65)
                            measurements.append(
                                {
                                    "state": state,
                                    "width": width,
                                    "height": height,
                                    "roster_id": rid,
                                    "expanded_card": box,
                                }
                            )
                            # Pointer can close/reopen the actual native disclosure.
                            disclosure.click()
                            disclosure.click()
                            self.assertEqual(errors, [])
                        page.close()
            finally:
                browser.close()
        output = os.environ.get("DTOS_DIAGNOSTIC_BROWSER_EVIDENCE")
        if output:
            Path(output).write_text(json.dumps(measurements, indent=2))
