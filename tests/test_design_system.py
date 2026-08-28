"""Permanent Product Design System v1.0 regression contracts."""
from __future__ import annotations

import unittest

from src.ui.design_system import (
    DESIGN_SYSTEM_CSS,
    account_page_header,
    manager_navigation,
    page_header,
    recommendation_panel,
)
from routes.teams import TEAM_HQ_CSS
from tools.validation.smoke_http import (
    validate_asset_market_contract,
    validate_market_asset_contract,
    validate_product_contract,
)


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
            "Front Office Intelligence System",
            "Falcons Headquarters",
            "Bijan Robinson — Player Intelligence",
        ):
            with self.subTest(title=title):
                html = page_header(title, league_name="Dynasty League", last_updated="2026-08-03T12:00:00Z")
                self.assertIn('data-dtos-component="page-header"', html)
                self.assertIn('data-design-system="1.1"', html)
                self.assertIn(f"<h1>{title}</h1>", html)
                self.assertIn("League Sync", html)
                self.assertIn('class="ds-action primary"', html)

    def test_fois_header_uses_rankings_as_its_real_primary_action(self) -> None:
        html = page_header(
            "Front Office Intelligence System",
            league_name="Dynasty League",
            last_updated="today",
        )
        self.assertIn("Evaluate General Manager performance", html)
        self.assertIn('href="#gm-rankings"', html)
        self.assertIn(">View GM Rankings</a>", html)

    def test_account_header_uses_reduced_shared_shell_without_manager_navigation(self) -> None:
        html = account_page_header("Sign in", purpose="Return to your leagues.")
        self.assertIn('data-dtos-component="page-header"', html)
        self.assertIn('data-dtos-shell="account-onboarding"', html)
        self.assertIn("Account &amp; identity", html)
        self.assertIn("Return to your leagues.", html)
        self.assertNotIn("manager-nav", html)

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
        self.assertRegex(TEAM_HQ_CSS, r"max-width:460px[^}]+\.thq-intel\{grid-template-columns:1fr")
        navigation = manager_navigation("League")
        self.assertEqual(navigation.split("</nav>", 1)[0].count("<a "), 5)
        self.assertIn('aria-current="page">League</a>', navigation)
        self.assertIn("position:fixed", DESIGN_SYSTEM_CSS)

    def test_http_product_contract_rejects_generic_and_internal_labels(self) -> None:
        valid = page_header("Falcons Headquarters", league_name="Dynasty League", last_updated="today")
        validate_product_contract(valid.encode(), "/teams/1")
        with self.assertRaisesRegex(AssertionError, "generic"):
            validate_product_contract((valid + "<title>Team Detail</title>").encode(), "/teams/1")
        with self.assertRaisesRegex(AssertionError, "internal identifier"):
            validate_product_contract((valid + "<p>Roster ID: 1</p>").encode(), "/teams/1")

    def test_http_product_contract_accepts_semantic_primary_action_with_extra_classes(self) -> None:
        header = account_page_header("Sign in", purpose="Return to your leagues.")
        action = (
            '<form action="/account/sign-in" method="post">'
            '<button class="btn ds-action primary" data-dtos-action="primary" '
            'data-action-id="sign-in" type="submit">Sign in</button></form>'
        )
        validate_product_contract((header + action).encode(), "/")

    def test_http_product_contract_rejects_non_action_semantic_marker(self) -> None:
        header = account_page_header("Sign in", purpose="Return to your leagues.")
        with self.assertRaisesRegex(AssertionError, "primary page action is missing"):
            validate_product_contract(
                (header + '<div data-dtos-action="primary">Not an action</div>').encode(),
                "/",
            )

    def test_market_directory_contract_is_search_first_without_recommendation(self) -> None:
        header = page_header(
            "Asset Market", league_name="Dynasty League", last_updated="today",
        )
        market = (
            header
            + '<h2>Asset Market &amp; Dynasty Exchange</h2>'
            + '<form aria-label="Asset Market filters"></form>'
            + '<table><caption>Canonical dynasty asset rankings</caption></table>'
            + '<p>Values remain separate; unavailable evidence is never substituted.</p>'
            + '<p>Dataset <code>market-dataset-1</code></p>'
        ).encode()
        market_identity = validate_asset_market_contract(market, "/market")
        self.assertEqual(market_identity, "market-dataset-1")

    def test_market_detail_requires_canonical_brain_recommendation(self) -> None:
        valid = {
            "brain_snapshot_id": "brain-1",
            "recommendation": {
                "confidence": 82,
                "brain_snapshot_id": "brain-1",
                "decision_provenance": ["brain"],
                "primary_reason": "Canonical evidence supports review.",
                "supporting_evidence": ["Market evidence is current."],
            },
        }
        validate_market_asset_contract(valid, "/api/market/assets/player:1")
        invalid = {**valid, "recommendation": {"confidence": 82}}
        with self.assertRaisesRegex(AssertionError, "metadata is missing"):
            validate_market_asset_contract(invalid, "/api/market/assets/player:1")

    def test_non_market_recommendation_contract_remains_required(self) -> None:
        header = page_header(
            "Trade Intelligence", league_name="Dynasty League",
            last_updated="today",
        )
        with self.assertRaisesRegex(AssertionError, "recommendation contract"):
            validate_product_contract(header.encode(), "/trades", recommendation=True)


if __name__ == "__main__":
    unittest.main()
