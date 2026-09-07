"""Rendered Trade Center accessibility regressions for v1.10.52."""
from __future__ import annotations

import unittest

from playwright.sync_api import sync_playwright

from components.trade_intelligence import trade_workflow
from tools.validation.browser_contract import A11Y_SCRIPT


class TradeCenterAccessibilityTests(unittest.TestCase):
    def test_all_workflows_and_viewports_follow_native_disclosure_visibility(self) -> None:
        view = {"active_team": {"roster_id": 1, "team_name": "Active"}}
        viewports = {
            "desktop": {"width": 1440, "height": 1200},
            "tablet": {"width": 1024, "height": 1366},
            "mobile": {"width": 390, "height": 844},
        }
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            for workflow in ("create", "recommended", "shop", "trade-for"):
                for viewport_name, viewport in viewports.items():
                    with self.subTest(workflow=workflow, viewport=viewport_name):
                        page.set_viewport_size(viewport)
                        page.set_content(trade_workflow(view, workflow))
                        disclosure = page.locator("details")
                        hidden_actions = disclosure.locator("button")
                        self.assertEqual(hidden_actions.count(), 8)
                        self.assertTrue(all(hidden_actions.evaluate_all(
                            "nodes => nodes.map(node => Boolean(node.textContent.trim()))"
                        )))
                        self.assertEqual(page.evaluate(A11Y_SCRIPT)["buttons_without_names"], 0)

                        # The assistance panel is intentionally unavailable before an
                        # evaluation. Exercise disclosure semantics in its real visible
                        # state rather than relying on CSS overriding HTML `hidden`.
                        self.assertFalse(disclosure.is_visible())
                        page.locator("#trade-assist").evaluate("node => { node.hidden = false; }")
                        self.assertTrue(disclosure.is_visible())
                        self.assertFalse(hidden_actions.first.is_visible())
                        disclosure.locator("summary").focus()
                        page.keyboard.press("Enter")
                        self.assertTrue(disclosure.evaluate("node => node.open"))
                        self.assertTrue(hidden_actions.first.is_visible())
                        self.assertEqual(page.evaluate(A11Y_SCRIPT)["buttons_without_names"], 0)
                        disclosure.locator("summary").focus()
                        page.keyboard.press("Enter")
                        self.assertFalse(disclosure.evaluate("node => node.open"))
                        self.assertFalse(hidden_actions.first.is_visible())

            page.evaluate("document.body.insertAdjacentHTML('beforeend', '<button id=unnamed></button>')")
            self.assertEqual(page.evaluate(A11Y_SCRIPT)["buttons_without_names"], 1)
            browser.close()


if __name__ == "__main__":
    unittest.main()
