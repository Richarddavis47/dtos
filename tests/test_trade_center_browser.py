"""Real-browser Trade Center interaction regressions through v1.10.57."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from components.trade_intelligence import trade_workflow


class TradeCenterBrowserTests(unittest.TestCase):
    def test_asset_browser_filters_match_computed_visibility_at_all_breakpoints(self) -> None:
        html = trade_workflow({
            "active_team": {"roster_id": 1, "team_name": "Active"},
        }, "create")

        def assets(prefix: str) -> list[dict]:
            return [
                {"asset_id": f"{prefix}-qb", "label": f"{prefix} Quarterback", "raw_label": f"{prefix} Quarterback", "kind": "player", "position": "QB", "positional_rank": "QB1", "trade_value": 700},
                {"asset_id": f"{prefix}-rb", "label": f"{prefix} Running Back", "raw_label": f"{prefix} Running Back", "kind": "player", "position": "RB", "positional_rank": "RB1", "trade_value": 600},
                {"asset_id": f"{prefix}-wr", "label": f"{prefix} Receiver", "raw_label": f"{prefix} Receiver", "kind": "player", "position": "WR", "positional_rank": "WR1", "trade_value": 500},
                {"asset_id": f"{prefix}-te", "label": f"{prefix} Tight End", "raw_label": f"{prefix} Tight End", "kind": "player", "position": "TE", "positional_rank": "TE1", "trade_value": 400},
                {"asset_id": f"{prefix}-pick", "label": f"2028 Round 1 ({prefix})", "raw_label": f"2028 Round 1 ({prefix})", "kind": "pick", "projected_range": "MID", "projected_range_confidence": "MEDIUM", "trade_value": 450},
            ]

        workspace = {
            "workspace_context": {"binding": "fixture", "ownership_generation": "fixture"},
            "manager_context": {"league_id": "fixture"},
            "teams": [
                {"roster_id": 1, "team_name": "Active", "assets": assets("Active")},
                {"roster_id": 2, "team_name": "Partner", "assets": assets("Partner")},
                {"roster_id": 3, "team_name": "Other", "assets": assets("Other")},
            ],
        }
        viewports = ((1280, 900), (820, 1180), (390, 844))
        filters = ("ALL", "QB", "RB", "WR", "TE", "PICKS")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height in viewports:
                with self.subTest(viewport=f"{width}x{height}"):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_default_timeout(5_000)

                    def route(request_route) -> None:
                        if "/static/" in request_route.request.url:
                            path = request_route.request.url.split("dtos.test/", 1)[1]
                            request_route.fulfill(content_type="text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8", body=Path(path).read_text(encoding="utf-8"))
                        elif request_route.request.url.endswith("/trades/create"):
                            request_route.fulfill(status=200, content_type="text/html", body=html)
                        elif "/api/trades/workspace" in request_route.request.url:
                            request_route.fulfill(status=200, content_type="application/json", body=json.dumps(workspace))
                        else:
                            request_route.abort()

                    page.route("**/*", route)
                    page.goto(
                        "https://dtos.test/trades/create",
                        wait_until="domcontentloaded",
                        timeout=10_000,
                    )
                    page.get_by_label("Counterparty", exact=True).select_option("2")

                    def assert_filter(side: str, position: str) -> None:
                        if width < 760:
                            page.get_by_role("button", name=side, exact=True).click()
                        board = page.locator("#trade-sent-board" if side == "My assets" else "#trade-received-board")
                        board.get_by_role("button", name=position, exact=True).click()
                        expected = 5 if position == "ALL" else 1
                        semantic = board.locator(".tw-asset").count()
                        computed = board.locator(".tw-asset").evaluate_all(
                            "nodes => nodes.filter(node => getComputedStyle(node).display !== 'none' && node.getBoundingClientRect().height > 0).length"
                        )
                        self.assertEqual((semantic, computed), (expected, expected))
                        expected_prefix = "Active" if side == "My assets" else "Partner"
                        labels = board.locator(".tw-asset b").all_text_contents()
                        self.assertTrue(all(label.startswith(expected_prefix) or label.startswith("2028") and expected_prefix in label for label in labels))

                    for side in ("My assets", "Their assets"):
                        for position in filters:
                            assert_filter(side, position)

                    assert_filter("My assets", "ALL")
                    page.get_by_role("button", name="Add Active Quarterback — you send", exact=True).focus()
                    page.keyboard.press("Enter")
                    assert_filter("Their assets", "QB")
                    page.get_by_role("button", name="Add Partner Quarterback — you receive", exact=True).click()
                    self.assertEqual(page.locator("#trade-sent-chips .tw-asset").count(), 1)
                    self.assertEqual(page.locator("#trade-received-chips .tw-asset").count(), 1)
                    totals = page.locator(".ti-market-balance").inner_text()
                    assert_filter("Their assets", "PICKS")
                    self.assertEqual(page.locator("#trade-sent-chips .tw-asset").count(), 1)
                    self.assertEqual(page.locator("#trade-received-chips .tw-asset").count(), 1)
                    self.assertEqual(page.locator(".ti-market-balance").inner_text(), totals)
                    self.assertFalse(page.locator(":focus").evaluate("node => node.hidden"))
                    page.close()
            browser.close()

    def test_multi_asset_edit_adjust_and_repair_execute(self) -> None:
        html = trade_workflow({
            "active_team": {"roster_id": 1, "team_name": "Active"},
        }, "create")
        workspace = {
            "workspace_context": {"binding": "fixture", "ownership_generation": "fixture"},
            "manager_context": {"league_id": "fixture"},
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
                if "/static/" in request.url:
                    path = request.url.split("dtos.test/", 1)[1]
                    request_route.fulfill(content_type="text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8", body=Path(path).read_text(encoding="utf-8"))
                elif request.url.endswith("/trades/create"):
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
                    body = {
                        "count": 1,
                        "calculated": True,
                        "requested_mode": "MAKE_THIS_TRADE_WORK",
                        "returned_modes": ["MAKE_THIS_TRADE_WORK"],
                        "target_preservation_required": True,
                        "target_preserved": True,
                        "results": [evaluation(["p"], ["x", "y"])],
                        "quiet_state": None,
                    }
                    request_route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
                else:
                    request_route.abort()

            page.route("**/*", route)
            page.goto("https://dtos.test/trades/create")
            page.get_by_label("Counterparty", exact=True).select_option("2")
            self.assertEqual(page.get_by_role("button", name="My assets", exact=True).count(), 1)
            self.assertEqual(page.get_by_role("button", name="Their assets", exact=True).count(), 1)
            self.assertEqual(page.locator('#trade-sent-board').get_by_role("button", name="PICKS", exact=True).count(), 1)
            self.assertEqual(page.locator(".ti-market-balance").count(), 1)
            for value in ("a", "b", "p"):
                page.locator(f'#trade-sent-board button[data-asset-id="{value}"]').click()
            page.get_by_role("button", name="Their assets", exact=True).click()
            for value in ("x", "y"):
                page.locator(f'#trade-received-board button[data-asset-id="{value}"]').click()
            page.locator('#trade-tray-view').click()
            self.assertEqual(page.locator("#trade-sent-chips .tw-asset").count(), 3)
            self.assertEqual(page.locator("#trade-received-chips .tw-asset").count(), 2)
            remove_buttons = page.locator("#trade-sent-chips .tw-asset button")
            self.assertEqual(
                remove_buttons.evaluate_all("nodes => nodes.map(node => node.getAttribute('aria-label'))"),
                ["Remove Alpha — you send", "Remove Beta — you send", "Remove 2027 Round 1 — EARLY — you send"],
            )
            remove_buttons.nth(1).focus()
            page.keyboard.press("Enter")
            self.assertEqual(page.locator("#trade-sent-chips .tw-asset").count(), 2)
            page.click("#trade-run")
            page.locator('#trade-result h3').wait_for()
            self.assertEqual(requests[0]["assets_sent"], ["a", "p"])
            self.assertEqual(requests[0]["assets_received"], ["x", "y"])

            page.click("#trade-edit")
            self.assertEqual(page.locator("#trade-sent-chips .tw-asset").count(), 2)
            page.get_by_role("button", name="My assets", exact=True).click()
            page.locator('#trade-sent-board button[data-asset-id="d"]').click()
            page.click("#trade-run")
            page.locator('#trade-result h3').wait_for()
            self.assertEqual(requests[1]["assets_sent"], ["a", "p", "d"])

            page.click("#trade-adjust")
            page.fill("#trade-instruction", "Don't trade Alpha. Use picks instead.")
            page.click("#trade-apply-adjust")
            page.get_by_role('button', name='Open editable offer:', exact=False).click()
            self.assertEqual(page.locator('#trade-sent-chips .tw-asset').count(), 1)
            self.assertIn("2027 Round 1", page.locator("#trade-sent-chips .tw-asset").inner_text())
            self.assertIn("Don't trade Alpha", requests[-1]["instruction"])
            self.assertEqual(requests[-1]["repair_mode"], "MAKE_THIS_TRADE_WORK")
            self.assertEqual(page.locator("body").evaluate("node => node.scrollWidth <= node.clientWidth"), True)
            browser.close()


if __name__ == "__main__":
    unittest.main()
