"""Structural visual-fidelity contracts for v1.10.68."""
from __future__ import annotations

import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from components.trade_intelligence import (
    TRADE_CSS,
    _canonical_card,
)
from src.ui.design_system import DESIGN_SYSTEM_CSS


class VisualFidelityTests(unittest.TestCase):
    def test_shared_shell_contains_command_and_podium_compositions(self) -> None:
        self.assertIn(".ux-command-grid", DESIGN_SYSTEM_CSS)
        self.assertIn(".ux-feature", DESIGN_SYSTEM_CSS)
        self.assertIn(".podium-grid", DESIGN_SYSTEM_CSS)
        self.assertIn('.podium-card[data-rank="1"]', DESIGN_SYSTEM_CSS)
        self.assertIn(".status-trophy", DESIGN_SYSTEM_CSS)

    def test_semantic_symbol_css_survives_python_string_rendering(self) -> None:
        self.assertIn('content:"🏆"', DESIGN_SYSTEM_CSS)
        self.assertIn('content:"🔥"', DESIGN_SYSTEM_CSS)
        self.assertNotIn("\x01F3C6", DESIGN_SYSTEM_CSS)
        self.assertNotIn("\x01F525", DESIGN_SYSTEM_CSS)
        self.assertFalse(any(ord(character) < 32 and character not in "\n\r\t" for character in DESIGN_SYSTEM_CSS))

    def test_browser_computes_trophy_and_fire_without_control_characters(self) -> None:
        markup = (
            f"<style>{DESIGN_SYSTEM_CSS}</style>"
            '<span id="trophy" class="status-trophy">Champion</span>'
            '<span id="fire" class="status-hot">W4</span>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(markup)
                content = page.evaluate(
                    """() => ({
                        trophy: getComputedStyle(document.querySelector('#trophy'), '::before').content,
                        fire: getComputedStyle(document.querySelector('#fire'), '::before').content,
                    })"""
                )
            finally:
                browser.close()
        self.assertEqual(content, {"trophy": '"🏆"', "fire": '"🔥"'})
        self.assertFalse(any("\\1" in value or "\x01" in value for value in content.values()))

    def test_trade_card_has_visual_packages_bilateral_reasoning_and_one_cta(self) -> None:
        row = {
            "active_team_name": "High Rollers",
            "partner_team_name": "Skyline Tigers",
            "proposal": {
                "assets_sent": ("player:1",),
                "assets_received": ("player:2",),
            },
            "proposal_presentation": {
                "send": [{"kind": "player", "asset_id": "1", "label": "Send Player", "position": "WR", "positional_rank": "WR12", "market_value": 500}],
                "receive": [{"kind": "player", "asset_id": "2", "label": "Target Player", "position": "QB", "positional_rank": "QB5", "market_value": 700}],
            },
            "evaluation": {
                "recommendation": "REVIEW",
                "dominant_reason": "Improves the starting lineup",
                "values": {"sent": 500, "received": 700},
                "dimensions": {
                    "value_fairness": {"assessment": "FAIR"},
                    "strategic_fit": {"assessment": "CLEAR"},
                    "counterparty_plausibility": {"assessment": "PLAUSIBLE"},
                    "best_for": {"active": "CONTENDER"},
                    "confidence": {"assessment": "HIGH"},
                },
                "perspectives": {"bilateral_reality": "PLAUSIBLE"},
                "why_you_would_do_it": "Adds a difference-maker.",
                "why_they_would_do_it": "Adds depth and flexibility.",
            },
        }
        html = _canonical_card(row)
        for marker in (
            "ti-franchises", "You send", "You receive",
            "Why you should consider this", "Why they should consider this",
            "View trade details",
            "Market fairness", "Roster fit", "Counterparty", "Evidence",
            "FAIR", "CLEAR", "PLAUSIBLE",
        ):
            self.assertIn(marker, html)
        self.assertEqual(html.count('class="ti-card-action"'), 1)
        self.assertIn("Improves the starting lineup", html)
        self.assertIn('href="/players/1"', html)
        self.assertIn('href="/players/2"', html)
        self.assertIn('<details class="ti-details">', html)
        self.assertNotIn('href="/trades/create"', html)

    def test_trade_css_changes_composition_not_only_color(self) -> None:
        for marker in (
            "grid-template-columns:1fr auto 1fr",
            ".ti-bilateral",
        ):
            self.assertIn(marker, TRADE_CSS)
        workspace = (Path(__file__).parents[1] / "static/css/trade_workspace.css").read_text(encoding="utf-8")
        for marker in (".tw-boards", ".tw-packages", ".tw-tray", "grid-template-columns:repeat(2,minmax(0,1fr))"):
            self.assertIn(marker, workspace)

    def test_compact_header_preserves_responsive_actions_and_flow(self) -> None:
        """Height is content-driven; interaction and document flow are the contract."""
        from dtos_app import CSS
        from src.ui.design_system import manager_navigation, page_header

        markup = (
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>{CSS}</style><main class="wrap">'
            '<aside aria-label="Account and league context"><details class="account-context">'
            '<summary><b>A long dynasty league name</b><span>Switch league</span></summary>'
            '<div class="ds-actions"><button>Another authorized league</button></div></details></aside>'
            + manager_navigation("Trade Intelligence")
            + page_header("Trade Intelligence", league_name="A long dynasty league name", last_updated="today")
            + TRADE_CSS
            + '<section class="ti-hero"><div><h2>A franchise with a long name</h2>'
            '<p>Review your current opportunities.</p></div><button class="ti-action">Choose franchise</button></section>'
            '<section id="content"><h2>Trade opportunities</h2></section></main>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for width in (320, 390, 768, 1280, 1600):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={"width": width, "height": 900})
                        page.set_content(markup)
                        metrics = page.evaluate("""() => {
                            const box = s => document.querySelector(s).getBoundingClientRect();
                            const hero = box('.ti-hero'), action = box('.ti-hero button');
                            const nav = box('.manager-nav');
                            return {
                                overflow: document.documentElement.scrollWidth > innerWidth,
                                follows: box('#content').top >= hero.bottom,
                                contained: action.top >= hero.top && action.bottom <= hero.bottom,
                                actionHeight: action.height,
                                primaryVisible: box('.ds-action.primary').height >= 44,
                                navHeights: [...document.querySelectorAll('.manager-nav a')].map(e => e.getBoundingClientRect().height),
                                navBottom: nav.bottom,
                                safeArea: getComputedStyle(document.querySelector('.wrap')).paddingBottom,
                            };
                        }""")
                        self.assertFalse(metrics["overflow"], metrics)
                        self.assertTrue(metrics["follows"], metrics)
                        self.assertTrue(metrics["contained"], metrics)
                        self.assertGreaterEqual(metrics["actionHeight"], 44)
                        self.assertTrue(metrics["primaryVisible"])
                        self.assertTrue(all(height >= 44 for height in metrics["navHeights"]))
                        if width <= 760:
                            self.assertLessEqual(metrics["navBottom"], 900)
                            self.assertGreaterEqual(float(metrics["safeArea"].removesuffix("px")), 88)
                        page.locator('.account-context summary').click()
                        self.assertTrue(page.get_by_role('button', name='Another authorized league').is_visible())
                        page.close()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
