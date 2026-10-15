"""Codex-hosted actual ASGI routes/scripts and responsive Chromium controls."""

from datetime import timedelta
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tests import test_roster_diagnostic_aging as fixtures
from src.core.intelligence import roster_diagnostics as diagnostics
from tools.validation.browser_runtime import launch_chromium


class DiagnosticAgingBrowserTests(unittest.TestCase):
    def test_team_clock_and_incoming_package_evidence(self):
        f = fixtures.DiagnosticAgingTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.data["teams"][1]["players"][0].update(
            status="Questionable", name="Incoming Quarterback"
        )
        f.data["players"]["c"].update(
            status="Questionable", name="Incoming Quarterback"
        )
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in (
                    (320, 432),
                    (375, 667),
                    (390, 682),
                    (390, 844),
                    (1280, 900),
                ):
                    page = f.f.f.browser_page(browser, width, height)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    for seconds, label in (
                        (0, "Fresh"),
                        (3600, "Aging"),
                        (21600, "Stale"),
                    ):
                        with patch.object(
                            diagnostics,
                            "_now",
                            return_value=f.observed + timedelta(seconds=seconds),
                        ):
                            for rid in (1, 2):
                                self.assertEqual(
                                    page.goto(f"https://dtos.test/teams/{rid}").status,
                                    200,
                                )
                                room = page.locator("#positional-depth")
                                summary = room.get_by_text(
                                    "Lineup eligibility and surplus", exact=True
                                ).first
                                summary.focus()
                                page.keyboard.press("Enter")
                                self.assertIn(label, room.inner_text())
                                self.assertIn(
                                    "Projection source observation:", room.inner_text()
                                )
                                self.assertNotIn("remove_one", room.inner_text())
                                self.assertLessEqual(
                                    page.evaluate(
                                        "document.documentElement.scrollWidth"
                                    ),
                                    width,
                                )
                                measurements.append(
                                    {
                                        "width": width,
                                        "height": height,
                                        "roster": rid,
                                        "source_age": label,
                                        "expanded_card": room.locator(
                                            "article"
                                        ).first.bounding_box(),
                                    }
                                )
                                summary.click()
                                summary.click()
                    with patch.object(diagnostics, "_now", return_value=f.observed):
                        page.goto("https://dtos.test/trades/create?front_office=1")
                        page.get_by_label("Counterparty", exact=True).select_option("2")
                        page.get_by_label("Your strategy", exact=True).select_option(
                            "WIN NOW"
                        )
                        page.locator(
                            '#trade-sent-board button[data-asset-id="2028-R1-3"]'
                        ).click()
                        if width < 760:
                            page.get_by_role(
                                "button", name="Their assets", exact=True
                            ).click()
                        page.locator(
                            '#trade-received-board button[data-asset-id="c"]'
                        ).click()
                        page.get_by_role(
                            "button", name="Evaluate Trade", exact=True
                        ).click()
                        summary = page.get_by_text(
                            "Your team roster evidence · provisional", exact=True
                        )
                        page.locator("#trade-result .dtos-explanation").wait_for()
                        self.assertGreater(
                            summary.count(),
                            0,
                            page.locator("#trade-result").inner_text(),
                        )
                        summary.wait_for()
                        summary.focus()
                        page.keyboard.press("Enter")
                        detail = summary.locator("..")
                        text = detail.inner_text()
                        self.assertIn("Before: current", text)
                        self.assertIn("After: provisional", text)
                        self.assertIn("Incoming Quarterback: questionable", text)
                        self.assertIn("not dependable cover", text)
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"), width
                        )
                        measurements.append(
                            {
                                "width": width,
                                "height": height,
                                "state": "incoming-questionable",
                                "trade_evidence": detail.bounding_box(),
                            }
                        )
                        summary.click()
                        summary.click()
                    self.assertEqual(errors, [])
                    page.close()
            finally:
                browser.close()
        output = os.environ.get("DTOS_AGING_BROWSER_EVIDENCE")
        if output:
            Path(output).write_text(json.dumps(measurements, indent=2))
