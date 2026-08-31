"""Structural visual-fidelity contracts for v1.10.68."""
from __future__ import annotations

import unittest

from playwright.sync_api import sync_playwright

from components.trade_intelligence import (
    TRADE_CSS,
    _canonical_card,
    _premium_trade_enhancement,
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
        ):
            self.assertIn(marker, html)
        self.assertEqual(html.count('class="ti-card-action"'), 1)

    def test_trade_css_changes_composition_not_only_color(self) -> None:
        for marker in (
            "min-height:190px", "grid-template-columns:1fr auto 1fr",
            ".ti-bilateral",
        ):
            self.assertIn(marker, TRADE_CSS)
        enhancement = _premium_trade_enhancement()
        self.assertIn(".ti-target-hero", enhancement)
        self.assertIn("width:110px", enhancement)


if __name__ == "__main__":
    unittest.main()
