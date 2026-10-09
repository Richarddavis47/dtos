"""Scout phone corrections: real FOIS cards and existing protected workspace state."""

from dataclasses import replace
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_fois_presentation as fois
from tests import test_technical_details_browser as technical
from tests import test_trade_calculator_browser as calculator
from tests import test_phone_design_browser as design


class PhoneVisualCorrectionTests(unittest.TestCase):
    def capture(self, page, width, surface):
        folder = os.environ.get("DTOS_PHONE_CORRECTION_CAPTURE")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(folder) / f"{width}-{surface}.png"), full_page=True)

    def test_real_fois_long_names_scores_and_desktop_do_not_overlap(self):
        import dtos_app

        fixture = fois.FOISPresentationTests()
        fixture.setUp()
        try:
            source = fixture._persist_profiles("active-league", 3)
            rows = tuple(replace(row, gm_name=name, overall_score=score,
                                 franchise_name="League-specific franchise with a long complete name")
                         for row, name, score in zip(source,
                             ("RichardDavis47", "VeryLongManagerIdentity" * 4, "GM"),
                             (86.34, 123456.789123, None)))
            with patch.object(fixture.repository, "league", return_value=rows), \
                    patch.object(fois, "_page", side_effect=dtos_app.page):
                html = fixture._client().get("/fois").text
            measurements = []

            def inspect(page, width):
                self.capture(page, width, "fois")
                for card in page.locator(".fois-leader").all():
                    result = card.evaluate("""e=>{
                        const rect=n=>{const r=document.createRange();r.selectNodeContents(n);return [...r.getClientRects()].map(r=>({x:r.x,y:r.y,right:r.right,bottom:r.bottom}));};
                        return {name:e.querySelector('h3').textContent,score:e.querySelector('.fois-score b').textContent,
                          names:rect(e.querySelector('h3 a')),scores:rect(e.querySelector('.fois-score b')),ranks:rect(e.querySelector('.fois-rank b')),right:e.getBoundingClientRect().right};
                    }""")
                    measurements.append({"width": width, **result})
                    if os.environ.get("DTOS_PHONE_CORRECTION_CAPTURE"):
                        Path(os.environ["DTOS_PHONE_CORRECTION_CAPTURE"], "fois-measurements.json").write_text(json.dumps(measurements, indent=2))
                    for name in result["names"]:
                        self.assertLessEqual(name["right"], result["right"] + 1)
                        for score in result["scores"]:
                            overlap = min(name["right"], score["right"]) > max(name["x"], score["x"]) and min(name["bottom"], score["bottom"]) > max(name["y"], score["y"])
                            self.assertFalse(overlap, result)
                    for score in result["scores"]:
                        self.assertLessEqual(score["right"], result["right"] + 1)
                    for rank in result["ranks"]:
                        self.assertLessEqual(rank["right"], result["right"] + 1)
                        if width < 600 or result["score"] == "—":
                            self.assertLessEqual(rank["bottom"], card.locator("h3").bounding_box()["y"] + 1)
                    self.assertGreaterEqual(card.locator(".ds-action").bounding_box()["height"], 43)
                    card.locator(".ds-action").click(trial=True)
                technical.TechnicalDetailsBrowserTests().assert_bounded(page, width)

            technical.TechnicalDetailsBrowserTests().browse({"/fois": html}, inspect)
        finally:
            fixture.tearDown()

    def test_shop_and_calculator_protection_details_are_state_bound(self):
        fixture = calculator.CalculatorBrowserTests()
        fixture.setUp()
        fixture.data["teams"][0]["assets"].append({
            "asset_id": "pick:2028:2:4", "label": "2028 Round 2 — Original franchise 4",
            "kind": "pick", "season": 2028, "round": 2,
            "original_roster_id": 4, "trade_value": 100,
        })
        for width in (320, 375, 390):
            with self.subTest(width=width), fixture.fixture.page(width, workspace=fixture.data) as (page, _):
                fixture.fixture.ready(page, "/trades/shop?asset_id=player:a")
                design.FocusedPhoneInteractionTests.theme(page)
                before = fixture.state(page)
                detail = page.locator("#trade-target [data-badge=protection]")
                detail.locator("summary").click()
                self.assertTrue(detail.evaluate("e=>e.open"))
                self.assertIn("outgoing Shop", detail.inner_text())
                self.assertNotIn("cannot be added", detail.inner_text())
                detail.locator("summary").click()
                self.assertFalse(detail.evaluate("e=>e.open"))
                self.assertEqual(fixture.state(page), before)
                page.select_option("#shop-protected", "player:b")
                page.click("#trade-edit")
                player_lock = page.locator('#trade-sent-board [data-badge=protection][data-asset-id="player:b"]')
                player_lock.locator("summary").click()
                self.assertIn("This player cannot be added to your outgoing offer", player_lock.inner_text())
                self.assertNotIn("required", player_lock.inner_text().lower())
                self.assertNotIn("player:b", fixture.state(page)["currentProposal"]["sent"])
                fixture.build(page)
                design.FocusedPhoneInteractionTests.theme(page)
                page.click("#calculator-protect")
                page.select_option("#trade-constraint-asset", "pick:2028:2:3")
                page.click("#calculator-lock")
                protected = fixture.state(page)
                summary = page.locator("#trade-balance [data-badge=protection-summary]")
                summary.locator("summary").focus()
                page.keyboard.press("Tab")
                page.keyboard.press("Shift+Tab")
                page.keyboard.press("Enter")
                self.assertTrue(summary.evaluate("e=>e.open"))
                self.assertEqual(summary.locator("summary").evaluate("e=>getComputedStyle(e).outlineStyle"), "solid")
                self.assertIn("pick:2028:2:3", summary.inner_text())
                self.assertIn("other picks in the same round", summary.inner_text())
                self.assertNotIn("pick:2028:2:4", summary.inner_text())
                self.assertNotIn("pick:2028:2:4", protected["protectedAssets"])
                self.capture(page, width, "protections")
                page.keyboard.press("Space")
                self.assertFalse(summary.evaluate("e=>e.open"))
                self.assertEqual(fixture.state(page), protected)
                page.click("#trade-release-lock")
                summary.locator("summary").click()
                self.assertNotIn("pick:2028:2:3", page.locator("#trade-balance [data-badge=protection-summary]").inner_text())
                self.assertIn("player:b", fixture.state(page)["protectedAssets"])
                page.select_option("#trade-constraint-asset", "player:b")
                page.click("#trade-release-lock")
                summary.locator("summary").click()
                self.assertEqual(fixture.state(page)["protectedAssets"], [])
                self.assertEqual(fixture.state(page)["requiredOutgoingAsset"], "player:a")
                self.assertIn("outgoing Shop anchor", page.locator("#trade-balance [data-badge=protection-summary]").inner_text())
                self.assertNotIn("cannot be added", page.locator("#trade-balance [data-badge=protection-summary]").inner_text())
                technical.TechnicalDetailsBrowserTests().assert_bounded(page, width)

    def test_required_incoming_target_and_preview_disclosures_preserve_offer(self):
        fixture = calculator.CalculatorBrowserTests()
        fixture.setUp()
        for width in (320, 375, 390):
            with self.subTest(width=width), fixture.fixture.page(width) as (page, _):
                fixture.fixture.ready(page, "/trades/trade-for?asset_id=player:x")
                design.FocusedPhoneInteractionTests.theme(page)
                before = fixture.state(page)
                detail = page.locator("#trade-target [data-badge=protection]")
                detail.locator("summary").click()
                self.assertIn("incoming Trade For target", detail.inner_text())
                self.assertNotIn("cannot be added", detail.inner_text())
                self.assertEqual(fixture.state(page), before)
                page.click("#trade-find")
                card = page.locator(".tw-offer").first
                lock = card.locator('[data-badge=protection][data-asset-id="player:x"]')
                lock.locator("summary").click()
                self.assertIn("incoming Trade For target", lock.inner_text())
                original = fixture.state(page)["currentProposal"]
                card.get_by_role("button", name="Open editable offer: preview").click()
                preview = page.locator("#trade-result .tw-offer [data-badge=protection]")
                preview.locator("summary").click()
                self.assertIn("player:x", preview.inner_text())
                self.assertEqual(fixture.state(page)["currentProposal"], original)
                page.get_by_role("button", name="Keep original", exact=True).click()
                self.assertEqual(fixture.state(page)["currentProposal"], original)
                technical.TechnicalDetailsBrowserTests().assert_bounded(page, width)

    def test_unavailable_dossier_card_keeps_status_word_intact(self):
        import dtos_app

        html = dtos_app.page("Player dossier", '<section id="selected-asset"><div class="summary-grid">' +
                             ''.join(f'<article class="metric"><b>Unavailable</b><span>{label}</span></article>'
                                     for label in ("Market", "Intrinsic", "Contender", "Rebuilder")) + '</div></section>').body.decode()

        def inspect(page, width):
            self.capture(page, width, "unavailable")
            for value in page.locator(".metric b").all():
                result = value.evaluate("""e=>{const r=document.createRange();r.selectNodeContents(e);const a=[...r.getClientRects()];return {lines:new Set(a.map(r=>r.y)).size,right:Math.max(...a.map(r=>r.right)),card:e.parentElement.getBoundingClientRect().right};}""")
                self.assertEqual(result["lines"], 1)
                self.assertLessEqual(result["right"], result["card"] + 1)
            technical.TechnicalDetailsBrowserTests().assert_bounded(page, width)

        technical.TechnicalDetailsBrowserTests().browse({"/players/fixture": html}, inspect)
