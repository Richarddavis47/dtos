"""Saved ranks -> private HTTP -> actual Trade client, controlled Chromium only."""

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from tests import test_personal_rankings as personal
from tests import test_personal_trade_browser as browser_fixture
from tests import test_trade_recommendation_clarity as clarity
from services.trade_intelligence import build_trade_workspace
from tools.validation.browser_runtime import launch_chromium


class RecommendationClarityBrowserTests(unittest.TestCase):
    def test_saved_custom_counterparty_limited_cards_preview_and_neutral(self):
        f = personal.PersonalRankingsTradeHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.capital.data
        data["teams"][0]["strategy"] = "RETOOL"
        data["teams"][1]["strategy"] = "RETOOL"
        # Canonical exact third-round pick; no mutation of real account state.
        data["teams"][0]["picks_owned"].append(
            dict(year=2028, round=3, original_roster_id=3, current_owner_id=1)
        )
        q = deepcopy(data["market_data"]["pick_quotes"]["FantasyCalc"][-1])
        q.update(round=3)
        data["market_data"]["pick_quotes"]["FantasyCalc"].append(q)
        workspace = build_trade_workspace(data, 1)
        f.editor.market.rows = []
        for pool in workspace["pools"].values():
            for asset in pool:
                key = (
                    "player:" + asset.asset_id
                    if asset.kind == "player"
                    else f"pick:{asset.season}:{asset.round}:{asset.original_roster_id}"
                )
                f.editor.market.rows.append(
                    f.editor.market.row(
                        key, asset.trade_value, asset.position or "PICK", asset.label
                    )
                )
        f.editor.initialize()
        before = f.editor.state()
        import dtos_app

        # Use the full production CSS, not only the token subset in the older harness.
        self.enterContext(
            patch.object(browser_fixture, "DESIGN_SYSTEM_CSS", dtos_app.CSS)
        )
        harness = browser_fixture.PersonalTradeBrowserTests()
        reports = []
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                with self.subTest(width=width):
                    page, records, errors = harness.page(browser, f, width, height)
                    page.goto("http://testserver/trades/create")
                    page.locator("#trade-partner").select_option("2")
                    page.locator("#trade-strategy").select_option("RETOOL")
                    page.locator(
                        '#trade-sent-board button[data-asset-id="2028-R3-3"]'
                    ).click()
                    if page.locator('[data-side="received"]').is_visible():
                        page.locator('[data-side="received"]').click()
                    page.locator(
                        '#trade-received-board button[data-asset-id="2028-R1-4"]'
                    ).click()
                    page.locator("#trade-run").click()
                    primary = page.locator("#trade-result .dtos-explanation > p").first
                    primary.wait_for()
                    e = records[-1]["response"]["evaluation"]
                    self.assertFalse(e["generated_trade_eligible"])
                    self.assertIn("COUNTERPARTY LIMITED", primary.inner_text())
                    self.assertNotIn("WORTH PURSUING", primary.inner_text())
                    self.assertIn(
                        "not the bilateral verdict",
                        page.locator("#trade-result").inner_text(),
                    )
                    details = page.locator(".tw-evaluation-detail > summary")
                    # Enter through keyboard modality, verify native disclosure and visible focus.
                    page.keyboard.press("Tab")
                    details.focus()
                    details.press("Enter")
                    self.assertIsNotNone(
                        page.locator(".tw-evaluation-detail").get_attribute("open")
                    )
                    outline = details.evaluate(
                        "(e)=>({style:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth})"
                    )
                    self.assertNotEqual(outline["style"], "none")
                    self.assertNotEqual(outline["width"], "0px")
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    if width < 500:
                        details.press("Enter")
                        box = details.bounding_box()
                        touch = page.context.new_cdp_session(page)
                        point = {
                            "x": box["x"] + box["width"] / 2,
                            "y": box["y"] + box["height"] / 2,
                        }
                        touch.send(
                            "Input.dispatchTouchEvent",
                            {"type": "touchStart", "touchPoints": [point]},
                        )
                        touch.send(
                            "Input.dispatchTouchEvent",
                            {"type": "touchEnd", "touchPoints": []},
                        )
                        self.assertIsNotNone(
                            page.locator(".tw-evaluation-detail").get_attribute("open")
                        )
                        touch.detach()
                    page.locator("#trade-valuation-mode").select_option("neutral")
                    page.locator("#trade-run").click()
                    page.wait_for_function(
                        "document.querySelector('#trade-result')?.textContent.includes('COUNTERPARTY LIMITED')"
                    )
                    self.assertEqual(errors, [])
                    reports.append(
                        dict(
                            width=width,
                            height=height,
                            headline=primary.inner_text(),
                            outline=outline,
                            neutral_market=e["market_evidence"],
                            qualified=e["generated_trade_eligible"],
                            document_width=page.evaluate(
                                "document.documentElement.scrollWidth"
                            ),
                        )
                    )
                    target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
                    if target:
                        Path(target).mkdir(parents=True, exist_ok=True)
                        page.screenshot(
                            path=str(Path(target, f"limited-{width}.png")),
                            full_page=True,
                        )
                    page.close()
            browser.close()
        self.assertEqual(f.editor.state(), before)
        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
        if target:
            Path(target, "browser.json").write_text(json.dumps(reports, indent=2))

    def test_exact_gain_primary_detail_and_touch_all_viewports(self):
        f = clarity.RecommendationClarityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            with self.subTest(width=width), f.f.browser(width, height) as page:
                f.f.ready(page)
                page.locator("#trade-partner").select_option("2")
                page.locator("#trade-strategy").select_option("RETOOL")
                for side, pid in (
                    ("sent", "a"),
                    ("sent", "2029-R1-1"),
                    ("received", "c"),
                ):
                    f.f.select(page, side, pid)
                page.get_by_role("button", name="Evaluate Trade", exact=True).click()
                primary = page.locator("#trade-result .tw-decision")
                primary.wait_for()
                self.assertIn("6.31", primary.inner_text())
                self.assertIn("Season 2026, week 2", primary.inner_text())
                self.assertIn("11", primary.inner_text())
                self.assertNotIn(
                    "Starting-lineup improvement is unavailable", primary.inner_text()
                )
                summary = page.locator(".tw-evaluation-detail > summary")
                summary.click()
                page.get_by_text(
                    "Supporting evidence and limitations", exact=True
                ).click()
                page.get_by_text("Weekly optimal-lineup detail", exact=True).click()
                self.assertIn(
                    "Week 2", page.locator(".tw-evaluation-detail").inner_text()
                )
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"), width
                )
                target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
                if target:
                    Path(target).mkdir(parents=True, exist_ok=True)
                    page.screenshot(
                        path=str(Path(target, f"gain-{width}.png")), full_page=True
                    )
