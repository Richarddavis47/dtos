"""Real-browser Trade Center interaction regressions for v1.10.50."""
from __future__ import annotations

import json
import unittest

from playwright.sync_api import sync_playwright

from components.trade_intelligence import trade_workflow


class TradeCenterBrowserTests(unittest.TestCase):
    def test_multi_asset_edit_adjust_and_repair_execute(self) -> None:
        html = trade_workflow({
            "active_team": {"roster_id": 1, "team_name": "Active"},
        }, "create")
        workspace = {
            "teams": [
                {"roster_id": 1, "team_name": "Active", "assets": [
                    {"asset_id": "a", "label": "Alpha", "kind": "player"},
                    {"asset_id": "b", "label": "Beta", "kind": "player"},
                    {"asset_id": "p", "label": "2027 Round 1 — EARLY", "kind": "pick"},
                    {"asset_id": "d", "label": "Delta", "kind": "player"},
                ]},
                {"roster_id": 2, "team_name": "Partner", "assets": [
                    {"asset_id": "x", "label": "Xray", "kind": "player"},
                    {"asset_id": "y", "label": "Yankee", "kind": "player"},
                    {"asset_id": "z", "label": "Zulu", "kind": "player"},
                ]},
            ],
        }
        requests: list[dict] = []

        def evaluation(sent: list[str], received: list[str], *, rejected: bool = False) -> dict:
            return {
                "workflow": "create",
                "proposal": {"active_roster_id": 1, "partner_roster_id": 2, "assets_sent": sent, "assets_received": received},
                "evaluation": {
                    "recommendation": "REJECT" if rejected else "WORTH PURSUING",
                    "dominant_reason": "Needs a real adjustment." if rejected else "Both managers have a concrete reason.",
                    "generated_trade_eligible": not rejected,
                    "perspectives": {"bilateral_reality": "NOT REALISTIC" if rejected else "REALISTIC"},
                    "values": {"sent": 700, "received": 710, "ratio": 1.014},
                    "why_you_would_do_it": "Adds neutral market value.",
                    "why_they_would_do_it": "Adds needed draft liquidity.",
                    "repair_paths": ["MAKE THIS TRADE WORK", "ALTERNATIVE CONSTRUCTION", "ALTERNATIVE TARGET"] if rejected else [],
                },
            }

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_default_timeout(5_000)

            def route(request_route) -> None:
                request = request_route.request
                if request.url.endswith("/trades/create"):
                    request_route.fulfill(status=200, content_type="text/html", body=html)
                elif "/api/trades/workspace" in request.url:
                    request_route.fulfill(status=200, content_type="application/json", body=json.dumps(workspace))
                elif request.url.endswith("/api/trades/evaluate"):
                    payload = request.post_data_json
                    requests.append(payload)
                    request_route.fulfill(status=200, content_type="application/json", body=json.dumps(evaluation(payload["assets_sent"], payload["assets_received"], rejected=len(requests) == 1)))
                elif request.url.endswith("/api/trades/assist"):
                    payload = request.post_data_json
                    requests.append(payload)
                    body = {"count": 1, "calculated": True, "results": [evaluation(["p"], ["x"])], "quiet_state": None}
                    request_route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
                else:
                    request_route.abort()

            page.route("**/*", route)
            page.goto("https://dtos.test/trades/create")
            page.wait_for_function("document.querySelectorAll('#trade-sent option').length === 4")
            for value in ("a", "b", "p"):
                page.select_option("#trade-sent", value)
                page.click("#trade-add-sent")
            for value in ("x", "y"):
                page.select_option("#trade-received", value)
                page.click("#trade-add-received")
            self.assertEqual(page.locator("#trade-sent-chips .ti-chip").count(), 3)
            self.assertEqual(page.locator("#trade-received-chips .ti-chip").count(), 2)
            page.locator("#trade-sent-chips .ti-chip").nth(1).locator("button").click()
            self.assertEqual(page.locator("#trade-sent-chips .ti-chip").count(), 2)
            page.click("#trade-run")
            page.wait_for_selector("text=MAKE THIS TRADE WORK")
            self.assertEqual(requests[0]["assets_sent"], ["a", "p"])
            self.assertEqual(requests[0]["assets_received"], ["x", "y"])

            page.click("#trade-edit")
            self.assertEqual(page.locator("#trade-sent-chips .ti-chip").count(), 2)
            page.select_option("#trade-sent", "d")
            page.click("#trade-add-sent")
            page.click("#trade-run")
            self.assertEqual(requests[1]["assets_sent"], ["a", "p", "d"])

            page.click("#trade-adjust")
            page.fill("#trade-instruction", "Don't trade Alpha. Use picks instead.")
            page.click("#trade-apply-adjust")
            page.wait_for_function("document.querySelectorAll('#trade-sent-chips .ti-chip').length === 1")
            self.assertIn("2027 Round 1", page.locator("#trade-sent-chips .ti-chip").inner_text())
            self.assertIn("Don't trade Alpha", requests[-1]["instruction"])
            self.assertEqual(page.locator("body").evaluate("node => node.scrollWidth <= node.clientWidth"), True)
            browser.close()


if __name__ == "__main__":
    unittest.main()
