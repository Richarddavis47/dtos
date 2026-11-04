"""Disposable authenticated Chromium opt-in/reversal, not physical Safari acceptance."""

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests.test_personal_rankings_browser import PersonalEditorFixture
from src.core.accounts.personal_store import (
    load_personal,
    RELATIVE_METHOD,
    ABSOLUTE_METHOD,
)
from tools.validation.browser_runtime import launch_chromium


class RelativeMethodBrowserTests(unittest.TestCase):
    def test_four_viewports_preview_confirm_reverse_and_stale_publication(self):
        output = (
            Path(os.environ["DTOS_RELATIVE_EVIDENCE"])
            if os.getenv("DTOS_RELATIVE_EVIDENCE")
            else None
        )
        if output:
            output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1440, 1000)):
                    with self.subTest(width=width):
                        f = PersonalEditorFixture()
                        page = None
                        try:

                            def saved():
                                return load_personal(f.store, f.account_id, "100", 1)

                            def command(name, **extra):
                                state = f.client.get("/api/my-dtos").json()
                                r = f.client.post(
                                    "/api/my-dtos",
                                    json={
                                        "command": name,
                                        "context": state["context"],
                                        "expected_revision": state["revision"],
                                        "market_generation": state["generation"],
                                        **extra,
                                    },
                                    headers={"x-csrf-token": f.csrf},
                                )
                                self.assertEqual(r.status_code, 200, r.text)
                                return r.json()

                            command("initialize")
                            command("tiers", asset_id="player:2", tier_start=True)
                            command(
                                "preferences",
                                asset_id="player:2",
                                preferences={"protect": True},
                            )
                            f.market.rows[1]["values"]["market_value"] = None
                            before = deepcopy(saved())
                            page = f.browser_page(
                                browser, width, height, touch=width < 500
                            )
                            errors = []
                            page.on("pageerror", lambda e: errors.append(str(e)))
                            page.goto("https://dtos.test/account/my-dtos")
                            page.wait_for_function(
                                "!document.querySelector('#personal-method-preview').disabled"
                            )
                            if output:
                                page.screenshot(
                                    path=str(output / f"compact-{width}.png"),
                                    full_page=True,
                                )
                            page.locator("#personal-active-method").press("Enter")
                            button = page.locator("#personal-method-preview")
                            button.wait_for(state="visible")
                            page.wait_for_function(
                                "!document.querySelector('#personal-method-preview').disabled"
                            )
                            self.assertIn(
                                "Absolute Slot",
                                page.locator("#personal-active-method").inner_text(),
                            )
                            self.assertTrue(
                                page.locator(
                                    "#personal-method-select"
                                ).evaluate("""e => {
                                const style = getComputedStyle(e), canvas = document.createElement('canvas');
                                const ctx = canvas.getContext('2d'); ctx.font = style.font;
                                return [...e.options].every(o => ctx.measureText(o.text).width +
                                    parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 24 <= e.clientWidth);
                            }""")
                            )
                            if output:
                                page.screenshot(
                                    path=str(output / f"absolute-{width}.png"),
                                    full_page=True,
                                )
                            button.focus()
                            page.keyboard.press("Enter")
                            dialog = page.locator("#personal-method-dialog")
                            dialog.wait_for(state="visible")
                            self.assertEqual(
                                page.evaluate("document.activeElement.id"),
                                "personal-method-cancel",
                            )
                            self.assertEqual(saved(), before)
                            title_box = page.locator(
                                "#personal-method-title"
                            ).bounding_box()
                            dialog_box = dialog.bounding_box()
                            self.assertGreaterEqual(title_box["y"], dialog_box["y"])
                            self.assertLess(
                                title_box["y"] + title_box["height"], height
                            )
                            self.assertIn("not recommendations", dialog.inner_text())
                            self.assertIn(
                                "No preferences changed",
                                page.locator("#personal-status").inner_text(),
                            )
                            self.assertIn("Market publication", dialog.inner_text())
                            self.assertLessEqual(
                                dialog.evaluate("e=>e.scrollWidth-e.clientWidth"), 1
                            )
                            if output:
                                page.screenshot(
                                    path=str(output / f"comparison-{width}.png")
                                )
                            page.keyboard.press("Escape")
                            dialog.wait_for(state="hidden")
                            page.wait_for_function(
                                "document.activeElement.id === 'personal-method-preview'"
                            )
                            self.assertEqual(saved(), before)
                            button.click()
                            dialog.wait_for(state="visible")
                            confirm = page.locator("#personal-method-confirm")
                            confirm.scroll_into_view_if_needed()
                            box = confirm.bounding_box()
                            self.assertGreaterEqual(box["height"], 44)
                            if width < 500:
                                page.touchscreen.tap(
                                    box["x"] + box["width"] / 2,
                                    box["y"] + box["height"] / 2,
                                )
                            else:
                                confirm.click()
                            page.wait_for_function(
                                "document.querySelector('#personal-active-method').textContent.includes('Relative Priced-Order')"
                            )
                            self.assertEqual(
                                saved()["valuation_method"], RELATIVE_METHOD
                            )
                            page.wait_for_function(
                                "document.activeElement.id === 'personal-method-preview'"
                            )
                            for key in (
                                "order",
                                "tiers",
                                "preferences",
                                "baseline",
                                "mode",
                            ):
                                self.assertEqual(saved()[key], before[key])
                            self.assertLessEqual(
                                page.evaluate(
                                    "document.documentElement.scrollWidth-innerWidth"
                                ),
                                0,
                            )
                            if output:
                                page.screenshot(
                                    path=str(output / f"relative-{width}.png"),
                                    full_page=True,
                                )
                            page.reload()
                            page.locator("#personal-active-method").press("Enter")
                            page.wait_for_function(
                                "!document.querySelector('#personal-method-preview').disabled"
                            )
                            self.assertIn(
                                "Relative Priced-Order",
                                page.locator("#personal-active-method").inner_text(),
                            )
                            # Source changes while modal is open: confirmation fails without a write.
                            button.click()
                            dialog.wait_for(state="visible")
                            retained = saved()
                            f.market.rows[1]["values"]["market_value"] = 980
                            f.market.semantic_generation += "-new"
                            confirm.click()
                            page.locator("#personal-error").wait_for(state="visible")
                            self.assertEqual(saved(), retained)
                            page.locator("#personal-retry").click()
                            page.wait_for_function(
                                "!document.querySelector('#personal-method-preview').disabled"
                            )
                            self.assertTrue(
                                page.locator(
                                    "#personal-publication-review"
                                ).is_visible()
                            )
                            self.assertIn(
                                "1 newly priced",
                                page.locator(
                                    "#personal-publication-review"
                                ).inner_text(),
                            )
                            page.locator("#personal-method-select").select_option(
                                ABSOLUTE_METHOD
                            )
                            button.click()
                            dialog.wait_for(state="visible")
                            confirm.click()
                            page.wait_for_function(
                                "document.querySelector('#personal-active-method').textContent.includes('Absolute Slot')"
                            )
                            self.assertEqual(
                                saved()["valuation_method"], ABSOLUTE_METHOD
                            )
                            self.assertEqual(saved()["order"], before["order"])
                            self.assertFalse(errors, errors)
                            if output:
                                (output / f"controls-{width}.json").write_text(
                                    json.dumps(
                                        {
                                            "viewport": [width, height],
                                            "keyboard": True,
                                            "touch": width < 500,
                                            "no_document_or_dialog_overflow": True,
                                            "preview_writes": 0,
                                            "explicit_opt_in_and_reversal": True,
                                            "stale_confirmation_denied": True,
                                            "order_tiers_flags_preserved": True,
                                            "physical_Safari": False,
                                        },
                                        indent=2,
                                    )
                                )
                        finally:
                            if page:
                                page.close()
                            f.close()
            finally:
                browser.close()
