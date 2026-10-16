"""P2 controls through actual publisher, authenticated HTTP and released client."""

import json
import copy
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from tests import test_trade_decision_http_browser as decision


class TradeP2BrowserTests(unittest.TestCase):
    def setUp(self):
        self.f = decision.DecisionHTTPBrowserTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.geometry = []

    def tearDown(self):
        target = os.environ.get("DTOS_TRADE_P2_EVIDENCE")
        if target:
            path = Path(target)
            previous = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps(previous + self.geometry, indent=2))

    def build(self, page, *, pick=False, strategy="WIN NOW"):
        self.f.ready(page)
        page.select_option("#trade-partner", "2")
        page.select_option("#trade-strategy", strategy)
        self.f.select(page, "sent", "a")
        if pick:
            self.f.select(page, "sent", "2029-R1-1")
        self.f.select(page, "received", "c")

    def test_selected_names_have_readable_width_and_exact_identity(self):
        for width in (320, 375, 390):
            with self.subTest(width=width), self.f.browser(width=width) as page:
                self.build(page, pick=True)
                page.click("#trade-view")
                row = page.locator('#trade-sent-chips button[data-asset-id="a"]')
                name = row.locator("b")
                box = name.bounding_box()
                self.geometry.append({"case": "selected", "width": width,
                                      "name": name.inner_text(), "name_width": box["width"],
                                      "row_height": row.bounding_box()["height"],
                                      "overflow": page.evaluate("document.documentElement.scrollWidth>innerWidth")})
                self.assertEqual(name.inner_text(), "Jayden Daniels")
                self.assertGreaterEqual(box["width"], 100)
                self.assertIn("QB", row.inner_text())
                self.assertIn("BUF", row.inner_text())
                self.assertIn("you send", row.get_attribute("aria-label"))
                pick = page.locator('#trade-sent-chips button[data-asset-id="2029-R1-1"]')
                self.assertIn("2029", pick.inner_text())
                self.assertIn("Round 1", pick.inner_text())
                self.assertIn("Original", pick.inner_text())
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)

    def test_balance_complete_offer_before_concise_reason_and_no_raw_floats(self):
        self.f.f.points.update(a=20.125, c=27.700000000000003)
        self.f.f.publish()
        for width in (320, 375, 390):
            with self.subTest(width=width), self.f.browser(width=width) as page:
                self.build(page)
                page.click("#trade-balance-offer")
                page.get_by_role("button", name="Preview adjustment", exact=True).first.wait_for()
                response = self.f.responses[-1]
                self.assertTrue(response["results"])
                self.assertTrue(all("c" in row["proposal"]["assets_received"] for row in response["results"]))
                card = page.locator(".tw-offer").first
                paragraphs = card.locator(":scope > p").all_text_contents()
                box = card.bounding_box()
                self.geometry.append({"case": "balance", "width": width,
                                      "height": box["height"], "primary_paragraphs": paragraphs,
                                      "complete_offer_offset": card.locator(".tw-offer-package").first.bounding_box()["y"] - box["y"],
                                      "market_offset": card.locator(".tw-offer-market").bounding_box()["y"] - box["y"],
                                      "explanation_offset": card.get_by_text("Why consider:", exact=False).bounding_box()["y"] - box["y"]})
                send = next(i for i, text in enumerate(paragraphs) if text.startswith("You send:"))
                reason = next(i for i, text in enumerate(paragraphs) if text.startswith("Why"))
                market = next(i for i, text in enumerate(paragraphs) if text.startswith("Current Market:"))
                self.assertLess(send, reason)
                self.assertLess(market, reason)
                self.assertIn("Add", card.locator(".tw-adjustment").inner_text())
                self.assertGreater(card.locator(".tw-adjustment").bounding_box()["y"], card.locator(".tw-offer-market").bounding_box()["y"])
                self.assertLessEqual(max(map(len, paragraphs)), 400)
                self.assertIsNone(re.search(r"\d+\.\d{5,}", " ".join(paragraphs)))
                self.assertIn("Josh Allen", " ".join(paragraphs))
                self.assertIn("Major drawback:", " ".join(paragraphs))
                detail = card.locator(":scope > details").first
                self.assertIsNone(detail.get_attribute("open"))
                summary = detail.locator(":scope > summary")
                summary.focus()
                page.keyboard.press("Enter")
                self.assertIsNotNone(detail.get_attribute("open"))
                self.assertTrue(summary.evaluate("e=>e===document.activeElement"))
                page.keyboard.press("Enter")
                self.assertIsNone(detail.get_attribute("open"))
                preview = card.get_by_role("button", name="Preview adjustment", exact=True)
                preview.scroll_into_view_if_needed()
                self.assertTrue(preview.evaluate("e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}"))
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)

    def test_first_incomplete_http_evaluation_is_current_attempt_not_retained(self):
        with self.f.browser() as page:
            self.build(page, pick=True, strategy="")
            page.get_by_role("button", name="Evaluate Trade", exact=True).click()
            page.locator(".dtos-explanation").wait_for()
            response = self.f.responses[-1]
            self.assertIsNone(response["evaluation"]["recommendation"])
            self.assertTrue(response["assessment_source_identity"])
            text = page.locator("#trade-result").inner_text()
            self.geometry.append({"case": "fresh-incomplete", "text": text,
                                  "freshness": page.locator("#trade-result").get_attribute("data-assessment-freshness")})
            self.assertIn("Choose", text)
            self.assertIn("945", text)
            self.assertIn("929", text)
            self.assertNotIn("Previous assessment", text)
            self.assertNotIn("NOT REVALIDATED", text)
            self.assertEqual(page.locator("#trade-result").get_attribute("data-assessment-state"), "fresh_incomplete")
            self.assertTrue(page.get_by_role("button", name="Choose analysis strategy", exact=True).is_visible())

    def test_actual_scoring_projection_market_zero_and_strategy_attempt_matrix(self):
        baseline, points = copy.deepcopy(self.f.data), dict(self.f.f.points)
        for case in ("strategy", "scoring", "projection", "Market", "zero", "complete"):
            with self.subTest(case=case):
                self.f.data.clear()
                self.f.data.update(copy.deepcopy(baseline))
                self.f.f.points.clear()
                self.f.f.points.update(points)
                if case == "scoring":
                    self.f.data["league"].pop("scoring_settings")
                elif case == "projection":
                    self.f.f.points.clear()
                elif case == "Market":
                    self.f.data["market_data"] = {}
                elif case == "zero":
                    self.f.f.points["a"] = 0
                if case != "scoring":
                    self.f.f.publish()
                with self.f.browser() as page:
                    self.build(page, pick=True, strategy="" if case == "strategy" else "WIN NOW")
                    page.click("#trade-run")
                    page.locator(".dtos-explanation").wait_for()
                    e = self.f.responses[-1]["evaluation"]
                    state = e["assessment_state"]["state"]
                    self.assertIn(state, ("fresh_complete", "fresh_incomplete"))
                    self.assertEqual(page.locator("#trade-result").get_attribute("data-assessment-state"), state)
                    self.assertEqual(page.locator("#trade-result").get_attribute("data-assessment-freshness"), "current")
                    text = page.locator("#trade-result").inner_text()
                    self.assertNotIn("Previous assessment", text)
                    if state == "fresh_incomplete":
                        self.assertIn("Current evaluation completed", text)
                        self.assertTrue(page.get_by_role("button", name="Reevaluate Trade", exact=True).is_enabled())
                        self.assertNotIn("NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER", text)
                    if case == "zero":
                        self.assertEqual(e["player_facts"]["a"]["projection"]["value"], 0)
                        self.assertEqual(e["player_facts"]["a"]["projection"]["availability"], "available")
                    if case == "Market":
                        self.assertIsNone(e["market_evidence"]["sent"]["total"])

    def test_actual_previous_assessment_separate_from_latest_incomplete_and_recovery(self):
        with self.f.browser() as page:
            self.build(page, pick=True)
            page.click("#trade-run")
            page.locator(".dtos-explanation").wait_for()
            old = self.f.responses[-1]["evaluation"]
            self.assertEqual(old["assessment_state"]["state"], "fresh_complete")
            saved = self.f.data["market_data"]
            self.f.data["market_data"] = {}
            page.click("#trade-run")
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_incomplete'")
            previous = page.locator('#trade-result > details').filter(has=page.get_by_text("Previous assessment · NOT REVALIDATED", exact=True))
            self.assertEqual(previous.count(), 1)
            self.assertIsNone(previous.get_attribute("open"))
            self.assertIn(old["recommendation"], previous.text_content())
            self.assertIn("Current evaluation completed", page.locator("#trade-result").inner_text())
            self.f.data["market_data"] = saved
            page.get_by_role("button", name="Reevaluate Trade", exact=True).click()
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_complete'")
            self.assertEqual(page.locator('#trade-result > details').filter(has=page.get_by_text("Previous assessment · NOT REVALIDATED", exact=True)).count(), 0)
            page.reload()
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='retained'")
            self.assertIn("NOT REVALIDATED", page.locator("#trade-result").inner_text())
            page.get_by_role("button", name="Reevaluate Trade", exact=True).click()
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_complete'")

    def test_failed_attempt_without_and_with_real_previous_assessment(self):
        for has_previous in (False, True):
            with self.subTest(previous=has_previous), self.f.browser() as page:
                self.build(page, pick=True)
                if has_previous:
                    page.click("#trade-run")
                    page.locator(".dtos-explanation").wait_for()
                with patch("routes.trades.evaluate_trade_request", side_effect=RuntimeError("controlled failure")):
                    page.click("#trade-run")
                    page.wait_for_function("!document.querySelector('#trade-run').disabled")
                state = page.locator("#trade-result").get_attribute("data-assessment-state")
                self.assertEqual(state, "retained" if has_previous else "failed")
                text = page.locator("#trade-result").inner_text()
                self.assertNotIn("controlled failure", text)
                if has_previous:
                    self.assertIn("NOT REVALIDATED", text)
                else:
                    self.assertNotIn("Previous assessment", text)
                self.assertTrue(page.get_by_role("button", name="Reevaluate Trade", exact=True).is_enabled())

    def test_real_delayed_evaluation_after_rendered_reset_cannot_restore_state(self):
        with self.f.browser() as page:
            self.build(page, pick=True)
            pending = []
            page.route("**/api/trades/evaluate", lambda route: pending.append(route))
            page.click("#trade-run")
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='evaluating'")
            self.assertEqual(len(pending), 1)
            response = self.f.auth.client.post("/api/trades/evaluate", json=pending[0].request.post_data_json, headers={"X-CSRF-Token": self.f.auth.csrf})
            self.assertEqual(response.status_code, 200)
            page.on("dialog", lambda dialog: dialog.accept())
            page.click("#trade-start-new")
            self.f.ready(page)
            pending[0].fulfill(status=200, content_type="application/json", body=response.content)
            self.assertEqual(next(iter(self.f.state(page).values()))["currentProposal"], {"sent": [], "received": [], "partner": 0})
            self.assertEqual(page.locator("#trade-result").get_attribute("data-assessment-state"), "not_evaluated")
            self.assertFalse(page.locator("#trade-result").is_visible())

    def test_long_selected_identity_targets_calculator_preview_and_adoption(self):
        name = "Marquez Valdes-Scantling Jr."
        self.f.data["players"]["a"]["full_name"] = name
        self.f.data["teams"][0]["players"][0]["name"] = name
        for width, height in ((320, 432), (375, 667), (390, 682), (390, 844), (1280, 900)):
            with self.subTest(width=width, height=height), self.f.browser(width=width, height=height) as page:
                self.build(page)
                calc = page.locator("#calculator-sent .tw-calculator-asset").first
                self.assertIn(name, calc.inner_text())
                self.assertIn("QB", calc.inner_text())
                self.assertIn("BUF", calc.inner_text())
                self.assertGreaterEqual(calc.get_by_role("button", name="Remove", exact=False).bounding_box()["height"], 44)
                page.click("#trade-balance-offer")
                page.get_by_role("button", name="Preview adjustment", exact=True).first.wait_for()
                original = next(iter(self.f.state(page).values()))["currentProposal"]
                page.get_by_role("button", name="Preview adjustment", exact=True).first.click()
                self.assertEqual(next(iter(self.f.state(page).values()))["currentProposal"], original)
                package = page.locator(".tw-balance-offer .tw-offer-package").first
                self.assertIn(name, package.inner_text())
                self.assertGreater(package.bounding_box()["width"], 150)
                page.get_by_role("button", name="Keep original", exact=True).click()
                self.assertEqual(next(iter(self.f.state(page).values()))["currentProposal"], original)
                page.get_by_role("button", name="Preview adjustment", exact=True).first.click()
                page.get_by_role("button", name="Adopt alternative", exact=True).click()
                selected = page.locator('#trade-sent-chips button[data-asset-id="a"]')
                self.assertIn(name, selected.inner_text())
                self.assertGreaterEqual(selected.locator("b").bounding_box()["width"], 100)
                self.assertEqual(selected.get_attribute("aria-pressed"), "true")
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)

        for path, pid in (("shop", "a"), ("trade-for", "c")):
            with self.subTest(target=path), self.f.browser(width=320) as page:
                self.f.ready(page, f"/trades/{path}?front_office=1&asset_id={pid}")
                page.locator("#recommendation-status[data-search-state=complete]").wait_for()
                target = page.locator("#trade-target")
                self.assertIn(name if pid == "a" else "Josh Allen", target.inner_text())
                self.assertIn("QB", target.inner_text())
                self.assertIn("BUF", target.inner_text())
                self.assertIn("Required", target.inner_text())
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 320)

    def test_unknown_price_and_exact_acquired_pick_identity_stay_readable(self):
        self.f.data["market_data"] = {}
        with self.f.browser(width=320) as page:
            self.build(page)
            self.f.select(page, "sent", "2028-R1-3")
            page.click("#trade-view")
            player = page.locator('#trade-sent-chips button[data-asset-id="a"]')
            pick = page.locator('#trade-sent-chips button[data-asset-id="2028-R1-3"]')
            self.assertGreaterEqual(player.locator("b").bounding_box()["width"], 100)
            self.assertIn("Unavailable", player.inner_text())
            self.assertIn("2028", pick.inner_text())
            self.assertIn("Round 1", pick.inner_text())
            self.assertIn("Original", pick.inner_text())
            self.assertGreaterEqual(pick.bounding_box()["height"], 44)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 320)


if __name__ == "__main__":
    unittest.main()
