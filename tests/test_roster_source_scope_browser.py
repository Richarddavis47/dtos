"""Source-scoped findings through real authenticated phone routes, never owner live."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_roster_source_scope as fixtures
from src.core.intelligence import roster_diagnostics as diagnostics


class RosterSourceScopeBrowserTests(unittest.TestCase):
    def fixture(self, **kwargs):
        helper = fixtures.RosterSourceScopeTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture(**kwargs)
        helper.add_unused(f)
        helper.publish(f)
        return helper, f

    def save(self, name, record, page):
        folder = os.environ.get("DTOS_ROSTER_SOURCE_SCOPE_EVIDENCE")
        if not folder:
            return
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        record.update(
            commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            tree=subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], text=True
            ).strip(),
            working_tree_clean=not subprocess.check_output(
                ["git", "status", "--porcelain"], text=True
            ).strip(),
            scope="Disposable retained Sleeper-source fixture; Chromium emulation, not owner live or physical Safari.",
        )
        (root / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n")
        page.screenshot(path=str(root / (name + ".png")), full_page=True)

    def test_my_team_market_exact_trade_for_back_preserves_draft_and_controls(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for sf in (False, True):
                    helper, f = self.fixture(superflex=sf, depth=sf)
                    saved = f.f.editor.state()
                    for width, height in (
                        (320, 432),
                        (375, 667),
                        (390, 844),
                        (1280, 900),
                    ):
                        with self.subTest(superflex=sf, width=width):
                            device = SimpleNamespace(
                                new_page=lambda **kw: browser.new_page(
                                    has_touch=width < 1000, **kw
                                )
                            )
                            page, requests, _, _, errors = f.helper.page(
                                device, f.f, width, height
                            )
                            try:
                                f.helper.ready(page)
                                original = page.url
                                f.helper.choose(page)
                                page.locator("#calculator-protect").click()
                                page.locator("#trade-constraint-asset").select_option(
                                    "b"
                                )
                                page.locator("#calculator-lock").click()
                                page.locator("#trade-valuation-mode").select_option(
                                    "custom"
                                )
                                before = f.helper.draft(page)
                                posts = sum(m == "POST" for m, _, _ in requests)
                                with patch.object(
                                    diagnostics,
                                    "_compute",
                                    side_effect=AssertionError(
                                        "Navigation must use prepared evidence"
                                    ),
                                ):
                                    page.locator(".manager-nav").get_by_role(
                                        "link", name="My Team", exact=True
                                    ).click()
                                    page.wait_for_url("**/teams/1*")
                                    self.assertIn(
                                        "Explore RB trades",
                                        page.locator("body").inner_text(),
                                    )
                                    page.locator(
                                        '.manager-nav a[href="/market"]'
                                    ).click()
                                    page.wait_for_url("**/market")
                                    page.locator("#market-search").fill(f.player_id)
                                    page.locator('form[action="/market"]').evaluate(
                                        "f=>f.requestSubmit()"
                                    )
                                    page.wait_for_url("**/market?*q=2-RB-0*")
                                    panel = page.locator("#market-roster-movement")
                                    self.assertIn(
                                        "RB depth need" if sf else "RB starter need",
                                        panel.inner_text(),
                                    )
                                    disclosure = panel.get_by_text(
                                        "Comparison coverage and limits", exact=True
                                    )
                                    disclosure.focus()
                                    disclosure.press("Enter")
                                    self.assertTrue(
                                        panel.locator("details").evaluate("e=>e.open")
                                    )
                                    self.assertLessEqual(
                                        page.evaluate(
                                            "document.documentElement.scrollWidth"
                                        ),
                                        width,
                                    )
                                    link = panel.get_by_role(
                                        "link", name="Explore in Trade For", exact=True
                                    )
                                    if width < 1000:
                                        link.tap()
                                    else:
                                        link.focus()
                                        link.press("Enter")
                                    page.wait_for_url("**/trades/trade-for?*")
                                    page.wait_for_function(
                                        "document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')"
                                    )
                                    self.assertEqual(
                                        page.locator("#trade-builder").get_attribute(
                                            "data-preload-asset"
                                        ),
                                        f.player_id,
                                    )
                                    self.assertIn(
                                        f.player_id,
                                        page.locator("#trade-target").inner_text(),
                                    )
                                    self.assertIn(
                                        "Opened from Market",
                                        page.locator(
                                            "#market-trade-origin"
                                        ).inner_text(),
                                    )
                                    page.locator("#trade-strategy").select_option(
                                        "RETOOL"
                                    )
                                    self.assertEqual(
                                        sum(m == "POST" for m, _, _ in requests), posts
                                    )
                                    self.save(
                                        f"{'sf' if sf else 'oneqb-kdef'}-{width}",
                                        dict(
                                            viewport=[width, height],
                                            unrostered_missing_projection=True,
                                            exact_target=f.asset_id,
                                            my_team_supported=True,
                                            explicit_generate_required=True,
                                            keyboard=True,
                                            touch_emulation=width < 1000,
                                            no_navigation_solver=True,
                                        ),
                                        page,
                                    )
                                    f.helper.back(page, "/market?*")
                                    f.helper.back(page, "/market")
                                    f.helper.back(page, "/teams/1")
                                f.helper.back(
                                    page, original.removeprefix(f.helper.origin)
                                )
                                page.wait_for_function(
                                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                                )
                                after = f.helper.draft(page)
                                for key in (
                                    "currentProposal",
                                    "protectedAssets",
                                    "valuationMode",
                                    "comparisonOffers",
                                ):
                                    self.assertEqual(after[key], before[key], key)
                                self.assertEqual(
                                    sum(m == "POST" for m, _, _ in requests), posts
                                )
                                self.assertEqual(errors, [])
                            finally:
                                page.close()
                    self.assertEqual(f.f.editor.state()["revision"], saved["revision"])
                    self.assertEqual(f.f.editor.state()["rows"], saved["rows"])
            finally:
                browser.close()

    def test_relevant_unknown_aging_and_failed_refresh_still_withhold_actions(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for reason in (
                    "unknown-k",
                    "unknown-def",
                    "eligible-missing",
                    "aging",
                    "failed-refresh",
                ):
                    helper, f = self.fixture()
                    if reason.startswith("unknown-"):
                        position = "K" if reason == "unknown-k" else "DEF"
                        pid = "1-" + position + "-0"
                        next(
                            p for p in f.data["teams"][0]["players"] if p["id"] == pid
                        )["status"] = "Unknown"
                        f.data["players"][pid]["status"] = "Unknown"
                        helper.publish(f)
                    elif reason == "eligible-missing":
                        pid = helper.add_unused(f, slot="Bench", status="Active")
                        helper.publish(f)
                        self.assertIsNone(
                            f.f.capital.reader.snapshot()["players"][pid][
                                "canonical_projection"
                            ]
                        )
                    elif reason == "failed-refresh":
                        f.f.capital.reader.begin_external_refresh()
                        f.f.capital.reader.fail_external_refresh(
                            RuntimeError("controlled fixture failure")
                        )
                    clock = datetime.now(timezone.utc) + timedelta(
                        hours=2 if reason == "aging" else 0
                    )
                    page, requests, _, _, errors = f.helper.page(browser, f.f, 320, 432)
                    try:
                        with patch.object(diagnostics, "_now", return_value=clock):
                            page.goto(
                                f.helper.origin + "/teams/1", wait_until="networkidle"
                            )
                            self.assertNotIn(
                                "Explore RB trades", page.locator("body").inner_text()
                            )
                            page.goto(
                                f.helper.origin + "/market?q=2-RB-0",
                                wait_until="networkidle",
                            )
                            panel = page.locator("#market-roster-movement")
                            self.assertEqual(
                                panel.get_by_role(
                                    "link", name="Explore in Trade For"
                                ).count(),
                                0,
                            )
                            self.assertIn(
                                "Observed change: +150.00 Market points",
                                panel.inner_text(),
                            )
                            self.assertLessEqual(
                                page.evaluate("document.documentElement.scrollWidth"),
                                320,
                            )
                            self.assertEqual(
                                sum(m == "POST" for m, _, _ in requests), 0
                            )
                            self.assertEqual(errors, [])
                            self.save(
                                reason,
                                dict(
                                    reason=reason,
                                    neutral_preserved=True,
                                    personalized_action_withheld=True,
                                    no_posts=True,
                                ),
                                page,
                            )
                    finally:
                        page.close()
            finally:
                browser.close()
