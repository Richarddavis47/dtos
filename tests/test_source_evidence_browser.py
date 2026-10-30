"""Codex-operated isolated authenticated real routes and released scripts, not Scout live acceptance."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_source_evidence_presentation as fixtures
from src.core.intelligence import roster_diagnostics as diagnostics


class SourceEvidenceBrowserTests(unittest.TestCase):
    def test_high_cardinality_phone_and_desktop(self):
        captures = json.loads(
            Path("tests/fixtures/dynamic_league_settings.json").read_text()
        )["leagues"]
        measurements = []
        baseline = os.environ.get("DTOS_PROVENANCE_BASELINE") == "1"
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for count, capture in zip((238, 200), captures):
                    f = fixtures.high_cardinality(count, capture)
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
                            page.on("pageerror", lambda e: errors.append(str(e)))
                            with patch.object(
                                diagnostics, "_now", return_value=f.observed
                            ):
                                for rid in (1, 2):
                                    self.assertEqual(
                                        page.goto(
                                            f"https://dtos.test/teams/{rid}"
                                        ).status,
                                        200,
                                    )
                                    card = page.locator(
                                        "#positional-depth article"
                                    ).first
                                    summary = card.get_by_text(
                                        "Lineup eligibility and surplus", exact=True
                                    )
                                    closed = card.bounding_box()["height"]
                                    summary.focus()
                                    page.keyboard.press("Enter")
                                    detail = summary.locator("..")
                                    scenarios = detail.locator("li").first
                                    summary_source = detail.locator(
                                        ".diagnostic-source-summary"
                                    )
                                    row = dict(
                                        league=capture["league_id"],
                                        observations=count,
                                        width=width,
                                        height=height,
                                        roster=rid,
                                        collapsed_card_height=closed,
                                        expanded_card_height=card.bounding_box()[
                                            "height"
                                        ],
                                        expanded_evidence_height=detail.bounding_box()[
                                            "height"
                                        ],
                                        first_scenario_offset=scenarios.bounding_box()[
                                            "y"
                                        ]
                                        - detail.bounding_box()["y"],
                                    )
                                    if not baseline:
                                        self.assertEqual(summary_source.count(), 1)
                                        row["source_summary_height"] = (
                                            summary_source.bounding_box()["height"]
                                        )
                                        provenance = detail.get_by_text(
                                            "Detailed source provenance", exact=True
                                        )
                                        panel = provenance.locator("..")
                                        self.assertIsNone(panel.get_attribute("open"))
                                        self.assertLess(
                                            row["first_scenario_offset"], 1000
                                        )
                                        for _ in range(2):
                                            provenance.scroll_into_view_if_needed()
                                            self.assertTrue(
                                                provenance.evaluate(
                                                    "(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}"
                                                )
                                            )
                                            provenance.focus()
                                            page.keyboard.press("Enter")
                                            self.assertIsNotNone(
                                                panel.get_attribute("open")
                                            )
                                            for stamp in diagnostics.team_diagnostics(
                                                f.data, rid, f.service.snapshot()
                                            )["evidence"]["source_observations"]:
                                                self.assertIn(
                                                    stamp, panel.text_content()
                                                )
                                            self.assertGreater(
                                                float(
                                                    provenance.evaluate(
                                                        "(e)=>getComputedStyle(e).outlineWidth"
                                                    ).replace("px", "")
                                                ),
                                                0,
                                            )
                                            provenance.click()
                                    self.assertLessEqual(
                                        page.evaluate(
                                            "document.documentElement.scrollWidth"
                                        ),
                                        width,
                                    )
                                    self.assertEqual(errors, [])
                                    measurements.append(row)
                            page.close()
                    finally:
                        f.doCleanups()
            finally:
                browser.close()
        output = os.environ.get("DTOS_PROVENANCE_MEASUREMENTS")
        if output:
            Path(output).write_text(json.dumps(measurements, indent=2))

    def test_trade_high_cardinality_provenance(self):
        captures = json.loads(
            Path("tests/fixtures/dynamic_league_settings.json").read_text()
        )["leagues"]
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for count, capture in zip((238, 200), captures):
                    f = fixtures.high_cardinality(count, capture)
                    try:
                        for width in (320, 375, 390, 1280):
                            page = f.f.f.browser_page(browser, width, 844)
                            with patch.object(
                                diagnostics, "_now", return_value=f.observed
                            ):
                                page.goto(
                                    "https://dtos.test/trades/create?front_office=1"
                                )
                                page.get_by_label(
                                    "Counterparty", exact=True
                                ).select_option("2")
                                page.get_by_label(
                                    "Trade strategy", exact=True
                                ).select_option("WIN NOW")
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
                                result = page.locator("#trade-result")
                                evidence = (
                                    result.locator("summary")
                                    .filter(has_text="Your team roster evidence")
                                    .first
                                )
                                evidence.wait_for()
                                evidence.click()
                                detail = evidence.locator("..")
                                self.assertEqual(
                                    detail.locator(
                                        ".diagnostic-source-summary"
                                    ).count(),
                                    2,
                                )
                                panels = detail.locator(".diagnostic-source-provenance")
                                self.assertEqual(panels.count(), 2)
                                for panel in panels.all():
                                    self.assertIsNone(panel.get_attribute("open"))
                                    panel.locator(":scope > summary").click()
                                    for stamp in diagnostics.team_diagnostics(
                                        f.data, 1, f.service.snapshot()
                                    )["evidence"]["source_observations"]:
                                        self.assertIn(stamp, panel.text_content())
                                    panel.locator(":scope > summary").click()
                                self.assertLessEqual(
                                    page.evaluate(
                                        "document.documentElement.scrollWidth"
                                    ),
                                    width,
                                )
                            page.close()
                    finally:
                        f.doCleanups()
            finally:
                browser.close()
