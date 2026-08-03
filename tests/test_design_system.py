"""Permanent Product Design System v1.0 regression contracts."""
from __future__ import annotations

import unittest

from src.ui.design_system import DESIGN_SYSTEM_CSS, page_header, recommendation_panel
from tools.validation.smoke_http import validate_product_contract


class DesignSystemTests(unittest.TestCase):
    def test_major_page_headers_share_required_contract(self) -> None:
        for title in (
            "Teams",
            "Week 1 Matchups",
            "Transactions Center",
            "Draft Capital",
            "League Settings",
            "League History",
            "Trade Intelligence",
            "Falcons Headquarters",
            "Bijan Robinson — Player Intelligence",
        ):
            with self.subTest(title=title):
                html = page_header(title, league_name="Dynasty League", last_updated="2026-08-03T12:00:00Z")
                self.assertIn('data-dtos-component="page-header"', html)
                self.assertIn('data-design-system="1.0"', html)
                self.assertIn(f"<h1>{title}</h1>", html)
                self.assertIn("League Sync", html)
                self.assertIn('class="ds-action primary"', html)

    def test_recommendation_contract_is_explainable_and_collapsed(self) -> None:
        html = recommendation_panel(
            title="Strengthen the running back room",
            recommendation="Target a weekly starter without moving a cornerstone.",
            confidence=82,
            primary_reason="The roster has contender leverage but limited injury protection.",
            evidence=("Current window is Playoff Window.", "Running back depth ranks eighth."),
            expected_impact="Improve weekly floor while preserving long-term flexibility.",
            action_label="Review Trade Options",
            action_href="/trades",
            limitations=("No live injury projection provider is configured.",),
        )
        for label in ("Recommendation", "82%", "Primary reason", "Expected impact", "Supporting Evidence", "Limitations"):
            self.assertIn(label, html)
        self.assertIn("<details>", html)
        self.assertNotIn("<details open", html)

    def test_mobile_and_accessibility_primitives_are_permanent(self) -> None:
        self.assertIn("focus-visible", DESIGN_SYSTEM_CSS)
        self.assertIn("overflow-x:auto", DESIGN_SYSTEM_CSS)
        self.assertIn("@media(max-width:760px)", DESIGN_SYSTEM_CSS)
        self.assertIn("min-height:44px", DESIGN_SYSTEM_CSS)

    def test_http_product_contract_rejects_generic_and_internal_labels(self) -> None:
        valid = page_header("Falcons Headquarters", league_name="Dynasty League", last_updated="today")
        validate_product_contract(valid.encode(), "/teams/1")
        with self.assertRaisesRegex(AssertionError, "generic"):
            validate_product_contract((valid + "<title>Team Detail</title>").encode(), "/teams/1")
        with self.assertRaisesRegex(AssertionError, "internal identifier"):
            validate_product_contract((valid + "<p>Roster ID: 1</p>").encode(), "/teams/1")


if __name__ == "__main__":
    unittest.main()
