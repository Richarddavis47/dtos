"""Real authenticated Market/Trade routes, prepared observations, bounded 2GiB CI.

Desktop Chromium and phone keyboard/touch emulation are not physical Safari.
"""

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests.test_market_roster_relevance import MarketNeedFixture


class MarketRosterBrowserTests(unittest.TestCase):
    def save(self, name, rows, page=None):
        folder = os.environ.get("DTOS_MARKET_NEED_EVIDENCE")
        if not folder:
            return
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        record = dict(
            commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            tree=subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], text=True
            ).strip(),
            observations=rows,
            scope="Disposable authenticated source/route/browser evidence; not owner live or physical Safari.",
        )
        (root / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n")
        if page:
            page.screenshot(path=str(root / (name + ".png")), full_page=True)

    def test_prepared_market_to_trade_and_back_preserves_existing_work(self):
        observations = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for sf in (False, True):
                    f = MarketNeedFixture(self, superflex=sf, depth=sf)
                    saved = f.f.editor.state()
                    for width, height in [
                        (320, 432),
                        (375, 667),
                        (390, 844),
                        (1280, 900),
                    ]:
                        touch = width < 1000
                        device = SimpleNamespace(
                            new_page=lambda **kwargs: browser.new_page(
                                has_touch=touch, **kwargs
                            )
                        )
                        page, requests, _, _, errors = f.helper.page(
                            device, f.f, width, height
                        )
                        try:
                            f.helper.ready(page)
                            original_url = page.url
                            f.helper.choose(page)
                            page.locator("#trade-run").click()
                            page.wait_for_function(
                                "document.querySelector('#trade-result').dataset.assessment==='true' && document.querySelector('#trade-builder').getAttribute('aria-busy')==='false'"
                            )
                            page.locator("#trade-result").get_by_role(
                                "button", name="Add to comparison", exact=True
                            ).click()
                            page.locator("#calculator-protect").click()
                            page.locator("#trade-constraint-asset").select_option("b")
                            page.locator("#calculator-lock").click()
                            page.locator("#trade-valuation-mode").select_option(
                                "custom"
                            )
                            before = f.helper.draft(page)
                            self.assertIn("b", before["protectedAssets"])
                            self.assertEqual(len(before["comparisonOffers"]), 1)
                            posts = sum(m == "POST" for m, _, _ in requests)
                            with patch(
                                "src.core.intelligence.roster_diagnostics._compute",
                                side_effect=AssertionError(
                                    "No new lineup preparation while reading Market or Trade For"
                                ),
                            ):
                                page.locator('.manager-nav a[href="/market"]').click()
                                page.wait_for_url("**/market")
                                page.locator("#market-search").fill(f.player_id)
                                page.locator('form[action="/market"]').evaluate(
                                    "f=>f.requestSubmit()"
                                )
                                page.wait_for_url("**/market?*q=2-RB-0*")
                                panel = page.locator("#market-roster-movement")
                                self.assertIn(
                                    "Observed change: +150.00 Market points",
                                    panel.inner_text(),
                                )
                                self.assertIn("FantasyCalc", panel.inner_text())
                                self.assertIn(
                                    "RB depth need" if sf else "RB starter need",
                                    panel.inner_text(),
                                )
                                self.save(
                                    f"market-{'superflex' if sf else 'oneqb-kdef'}-{width}",
                                    [
                                        dict(
                                            viewport=[width, height],
                                            source="prepared canonical sparse observations",
                                            no_search=True,
                                        )
                                    ],
                                    page,
                                )
                                link = panel.get_by_role(
                                    "link", name="Explore in Trade For", exact=True
                                )
                                self.assertEqual(link.count(), 1)
                                self.assertLessEqual(
                                    page.evaluate(
                                        "document.documentElement.scrollWidth"
                                    ),
                                    width,
                                )
                                requests_before = len(requests)
                                summary = panel.get_by_text(
                                    "Comparison coverage and limits", exact=True
                                )
                                summary.focus()
                                summary.press("Enter")
                                self.assertTrue(
                                    panel.locator("details").evaluate("e=>e.open")
                                )
                                self.assertEqual(len(requests), requests_before)
                                if touch:
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
                                    page.locator("#market-trade-origin").inner_text(),
                                )
                                self.assertTrue(
                                    page.locator("#trade-strategy").is_enabled()
                                )
                                page.locator("#trade-strategy").select_option("RETOOL")
                                self.assertEqual(
                                    sum(m == "POST" for m, _, _ in requests), posts
                                )
                                self.save(
                                    f"{'superflex' if sf else 'oneqb-kdef'}-{width}",
                                    [
                                        dict(
                                            viewport=[width, height],
                                            exact_target=f.asset_id,
                                            neutral_movement=150,
                                            kind="depth" if sf else "starter",
                                            no_extra_posts=True,
                                            no_solver_on_navigation=True,
                                            keyboard_disclosure=True,
                                            touch_emulation=touch,
                                            overflow=False,
                                        )
                                    ],
                                    page,
                                )
                                f.helper.back(page, "/market?*")
                                self.assertIn("q=2-RB-0", page.url)
                                # Applying a Market filter is a real history entry.
                                f.helper.back(page, "/market")
                                page.locator("#dtos-back").click()
                                page.wait_for_url(original_url)
                                page.wait_for_function(
                                    "document.querySelector('#trade-builder') && !document.querySelector('#trade-context').textContent.includes('Loading')"
                                )
                                after = f.helper.draft(page)
                                self.assertEqual(
                                    after["currentProposal"], before["currentProposal"]
                                )
                                self.assertEqual(after["valuationMode"], "custom")
                                self.assertEqual(
                                    after["protectedAssets"], before["protectedAssets"]
                                )
                                self.assertEqual(
                                    [r["proposal"] for r in after["comparisonOffers"]],
                                    [r["proposal"] for r in before["comparisonOffers"]],
                                )
                                self.assertIn(
                                    "retained",
                                    page.locator("#trade-result").inner_text().lower(),
                                )
                                page.reload(wait_until="networkidle")
                                page.wait_for_function(
                                    "!document.querySelector('#trade-context').textContent.includes('Loading')"
                                )
                                self.assertEqual(
                                    f.helper.draft(page)["currentProposal"],
                                    before["currentProposal"],
                                )
                            self.assertEqual(
                                sum(m == "POST" for m, _, _ in requests), posts
                            )
                            self.assertEqual(errors, [])
                            observations.append(
                                dict(
                                    shape="superflex" if sf else "oneqb-kdef",
                                    viewport=[width, height],
                                    roundtrip=True,
                                    exact_asset=True,
                                    draft_preserved=True,
                                    protections_preserved=True,
                                    comparison_preserved=True,
                                    retained_result=True,
                                    no_extra_posts=True,
                                    no_solver_on_navigation=True,
                                    errors=errors,
                                )
                            )
                        finally:
                            page.close()
                    self.assertEqual(f.f.editor.state()["revision"], saved["revision"])
                    self.assertEqual(f.f.editor.state()["rows"], saved["rows"])
            finally:
                browser.close()
        self.save("roundtrip", observations)

    def test_stale_handoff_and_league_switch_do_not_reuse_target_or_work(self):
        f = MarketNeedFixture(self)
        observations = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, requests, _, _, errors = f.helper.page(browser, f.f, 390, 844)
                try:
                    f.helper.ready(page)
                    f.helper.choose(page)
                    before = f.helper.draft(page)
                    old_scope = page.locator(
                        'meta[name="dtos-navigation-scope"]'
                    ).get_attribute("content")
                    page.goto(
                        f.helper.origin + "/market?q=2-RB-0", wait_until="networkidle"
                    )
                    link = (
                        page.locator("#market-roster-movement")
                        .get_by_role("link", name="Explore in Trade For")
                        .get_attribute("href")
                    )
                    f.f.capital.reader.begin_external_refresh()
                    f.f.capital.reader.fail_external_refresh(
                        RuntimeError("controlled fixture failure")
                    )
                    page.goto(f.helper.origin + link, wait_until="networkidle")
                    self.assertIn(
                        "No new target was applied",
                        page.locator("#market-trade-origin").inner_text(),
                    )
                    self.assertEqual(
                        page.locator("#trade-builder").get_attribute(
                            "data-preload-asset"
                        ),
                        "",
                    )
                    self.assertEqual(
                        f.helper.draft(page)["currentProposal"],
                        before["currentProposal"],
                    )
                    f.f.editor.store.upsert_membership(
                        "account-a",
                        {"league_id": "league-2", "season": "2026"},
                        "account-a",
                        1,
                        "Other fixture franchise",
                        "active",
                    )
                    f.f.editor.store.activate("account-a", "league-2")
                    f.data["league"]["league_id"] = "league-2"
                    page.goto(f.helper.origin + link, wait_until="networkidle")
                    self.assertIn(
                        "No new target was applied",
                        page.locator("#market-trade-origin").inner_text(),
                    )
                    self.assertNotEqual(
                        page.locator(
                            'meta[name="dtos-navigation-scope"]'
                        ).get_attribute("content"),
                        old_scope,
                    )
                    self.assertEqual(
                        page.locator("#trade-builder").get_attribute(
                            "data-preload-asset"
                        ),
                        "",
                    )
                    self.assertEqual(sum(m == "POST" for m, _, _ in requests), 0)
                    self.assertEqual(errors, [])
                    observations.append(
                        dict(
                            stale_link_withheld=True,
                            new_target_not_applied=True,
                            existing_draft_preserved=True,
                            league_switch_cleared_scope=True,
                            no_posts=True,
                            errors=errors,
                        )
                    )
                    self.save("stale-and-league", observations, page)
                finally:
                    page.close()
            finally:
                browser.close()
