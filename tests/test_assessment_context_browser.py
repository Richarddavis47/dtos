"""Released client, retained offer controls and shared session intent."""

import unittest
from tests import test_trade_scout_state_browser as scout


class AssessmentContextBrowserTests(unittest.TestCase):
    def test_original_strategy_survives_old_controls_preview_adopt_and_reload(self):
        fixture = scout.ScoutWorkspaceStateBrowserTests()
        for width, height in (
            (320, 432),
            (375, 667),
            (390, 844),
            (390, 1000),
            (1280, 900),
        ):
            for old, new, preview_first in (
                ("REBUILD", "WIN NOW", False),
                ("REBUILD", "WIN NOW", True),
                ("WIN NOW", "REBUILD", False),
                ("REBUILD", "REBUILD", False),
            ):
                with self.subTest(width=width, old=old, preview_first=preview_first):
                    data = fixture.workspace()
                    data["workspace_context"].update(
                        league_id="fixture",
                        roster_id=1,
                        strategy_scope="fixture-session",
                    )

                    def api(route, payload):
                        row = fixture.offer(
                            ["player:a", "player:d", "pick:2028:1:3"], ["player:x"]
                        )
                        row.update(
                            exploration=old != "WIN NOW",
                            search_result_type="supported_unfavorable"
                            if old != "WIN NOW"
                            else None,
                        )
                        row["evaluation"].update(
                            recommendation="WORTH PURSUING"
                            if old == "WIN NOW"
                            else "NOT WORTH IT",
                            dominant_reason=(payload["strategy"] or "Neutral")
                            + " original reasoning.",
                            provenance={
                                "evaluation_id": "original-"
                                + (payload["strategy"] or "Neutral"),
                                "inputs": {"projection_generation": "p1"},
                            },
                        )
                        if route.request.url.endswith("/evaluate"):
                            return route.fulfill(
                                json={
                                    "evaluation": {
                                        **row["evaluation"],
                                        "legal": True,
                                        "market_evidence": {"availability": "full"},
                                    },
                                    "assessment_source_identity": "compatible-fixture-source",
                                }
                            )
                        route.fulfill(
                            json={
                                "exploratory_results": [row]
                                if row["exploration"]
                                else [],
                                "results": [] if row["exploration"] else [row],
                                "count": 0 if row["exploration"] else 1,
                            }
                        )

                    with fixture.page(width, workspace=data, api=api) as (
                        page,
                        requests,
                    ):
                        page.set_viewport_size({"width": width, "height": height})
                        fixture.ready(page, "/trades/shop?asset_id=player:a")
                        page.select_option("#trade-strategy", old)
                        page.locator("#shop-refinements").evaluate("e=>e.open=true")
                        page.select_option("#shop-protected", "player:b")
                        page.click("#trade-find")
                        button = page.get_by_role(
                            "button", name="Open editable offer: preview", exact=True
                        )
                        button.wait_for()
                        if preview_first:
                            button.click()
                        second = page.context.new_page()
                        second.goto("https://dtos.test/trades/create")
                        second.locator('#trade-partner option[value="2"]').wait_for(
                            state="attached"
                        )
                        second.select_option("#trade-strategy", new)
                        shared = second.evaluate("document.cookie")
                        page.evaluate("window.dispatchEvent(new Event('focus'))")
                        if not preview_first:
                            button.click()
                        page.get_by_role(
                            "button", name="Adopt alternative", exact=True
                        ).click()
                        state = page.evaluate(
                            "JSON.parse(sessionStorage.getItem('dtos-trade-workspace:scout-session'))"
                        )
                        self.assertEqual(
                            state["currentAssessment"]["identity"]["strategy"], old
                        )
                        self.assertEqual(
                            state["currentAssessment"]["exploration"], old != "WIN NOW"
                        )
                        self.assertEqual(page.input_value("#trade-strategy"), new)
                        text = page.locator("#trade-result").inner_text()
                        if old != new:
                            self.assertIn("not revalidated", text)
                        else:
                            self.assertIn("not revalidated", text)
                            self.assertNotIn("evidence changed", text)
                        self.assertIn(old + " original reasoning.", text)
                        self.assertIn("This spends depth.", text)
                        self.assertEqual(
                            state["currentProposal"]["sent"],
                            ["player:a", "player:d", "pick:2028:1:3"],
                        )
                        self.assertEqual(page.evaluate("document.cookie"), shared)
                        self.assertEqual(state["protectedAssets"], ["player:b"])
                        page.reload()
                        page.get_by_role(
                            "button", name="Reevaluate Trade", exact=True
                        ).wait_for()
                        self.assertIn(
                            "not revalidated",
                            page.locator("#trade-result").inner_text(),
                        )
                        page.get_by_role(
                            "button", name="Reevaluate Trade", exact=True
                        ).click()
                        page.get_by_text(
                            new + " original reasoning.", exact=True
                        ).wait_for()
                        self.assertNotIn(
                            "not revalidated",
                            page.locator("#trade-result").inner_text(),
                        )
                        self.assertEqual(requests[-1][1]["strategy"], new)
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"),
                            width + 1,
                        )
                        second.close()


if __name__ == "__main__":
    unittest.main()
