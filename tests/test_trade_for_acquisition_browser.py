"""Prepared-offer presentation, phone state and zero incidental HTTP work.

Selection/evaluator integration has separate source-backed controls. These
browser responses are explicitly disposable prepared-assessment fixtures.
"""

from contextlib import contextmanager
from unittest.mock import patch
from components.trade_workspace import trade_workspace
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from tests import test_trade_scout_state_browser as scout
from tests.test_trade_for_acquisition import panel, row, select


class AcquisitionBrowserTests(unittest.TestCase):
    @contextmanager
    def page(self, width, **kwargs):
        # Reuse the real, explicit-Generate Market handoff presentation contract.
        def render(view, *args):
            return trade_workspace(
                {
                    **view,
                    "market_need": {
                        "name": "X",
                        "reason": "Supported fixture position relevance.",
                    },
                },
                *args,
            )

        with (
            patch(
                "tests.test_trade_scout_state_browser.trade_workspace",
                side_effect=render,
            ),
            scout.ScoutWorkspaceStateBrowserTests().page(width, **kwargs) as result,
        ):
            yield result

    def offer_panel(self):
        assets = panel()
        rows = select(
            [
                row(assets, ["a"], ["target", "extra"]),
                row(assets, ["b"]),
                row(assets, ["d"], verdict="FAIR / OPTIONAL"),
            ],
            assets,
        )
        mapping = {
            "a": "player:a",
            "b": "player:b",
            "d": "player:d",
            "target": "player:x",
            "extra": "player:y",
        }
        # Preserve canonical assessment values; map only fixture identity spelling
        # into the existing browser harness's exact player namespace.
        for r in rows:
            r["evaluation"]["provenance"] = {
                "evaluation_id": "fixture-" + "-".join(r["proposal"]["assets_sent"])
            }
            for field in ("assets_sent", "assets_received"):
                r["proposal"][field] = [mapping.get(k, k) for k in r["proposal"][field]]
            r["acquisition_comparison"]["cost"]["extra_received_asset_ids"] = [
                mapping.get(k, k)
                for k in r["acquisition_comparison"]["cost"]["extra_received_asset_ids"]
            ]
        return rows

    def record(self, page, width, rows, requests):
        folder = os.environ.get("DTOS_ACQUISITION_EVIDENCE")
        if folder:
            root = Path(folder)
            root.mkdir(parents=True, exist_ok=True)
            (root / f"phone-{width}.json").write_text(
                json.dumps(
                    dict(
                        width=width,
                        physical_safari=False,
                        source="Disposable prepared-offer browser fixture",
                        rows=rows,
                        operations=[{"path": p, "payload": v} for p, v in requests],
                        no_overflow=page.evaluate(
                            "document.documentElement.scrollWidth"
                        )
                        <= width + 1,
                    ),
                    indent=2,
                )
                + "\n"
            )
            page.screenshot(path=str(root / f"phone-{width}.png"), full_page=True)

    def test_cost_fit_preview_comparison_back_reload_are_readonly(self):
        harness = scout.ScoutWorkspaceStateBrowserTests()
        rows = self.offer_panel()
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            with self.subTest(width=width):

                def api(route, payload):
                    self.assertTrue(
                        route.request.url.endswith("/generate"),
                        "Opening results must not evaluate or repair",
                    )
                    route.fulfill(
                        json={
                            "workflow": "trade_for",
                            "results": deepcopy(rows),
                            "count": len(rows),
                        }
                    )

                with self.page(width, api=api) as (page, requests):
                    page.set_viewport_size({"width": width, "height": height})
                    # Existing Market entry contract requires explicit Generate.
                    harness.ready(page, "/trades/trade-for?asset_id=player:x")
                    self.assertEqual(requests, [])
                    page.locator("#trade-find").focus()
                    page.locator("#trade-find").press("Enter")
                    page.locator(".tw-acquisition-role").first.wait_for()
                    self.assertIn(
                        "Best-supported fit found",
                        page.locator(".tw-offer").first.inner_text(),
                    )
                    cheap = (
                        page.locator(".tw-offer")
                        .filter(has_text="Lowest-cost supported offer found")
                        .first
                    )
                    self.assertIn(
                        "Gross outgoing Neutral Market cost: 100", cheap.inner_text()
                    )
                    self.assertIn("FAIR / OPTIONAL", cheap.inner_text())
                    best = page.locator(".tw-offer").first
                    self.assertIn(
                        "additional incoming assets worth 100", best.inner_text()
                    )
                    self.assertIn("not equivalent purchases", best.inner_text())
                    self.assertIn("not a global minimum", best.inner_text())
                    count = len(requests)
                    best.get_by_role(
                        "button", name="Add to comparison", exact=False
                    ).click()
                    cheap.get_by_role(
                        "button", name="Add to comparison", exact=False
                    ).click()
                    page.get_by_role(
                        "button", name="Compare selected offers", exact=True
                    ).click()
                    panel = page.locator("#trade-comparison")
                    panel.get_by_text("Best-supported fit found", exact=True).wait_for()
                    self.assertIn(
                        "Lowest-cost supported offer found", panel.inner_text()
                    )
                    self.assertIn("400", panel.inner_text())
                    self.assertIn("100", panel.inner_text())
                    self.assertEqual(len(requests), count)
                    page.get_by_role(
                        "button", name="Return to my offer or draft", exact=True
                    ).click()
                    cheap = (
                        page.locator(".tw-offer")
                        .filter(has_text="Lowest-cost supported offer found")
                        .first
                    )
                    if width == 390:
                        touch = page.context.new_cdp_session(page)
                        touch.send(
                            "Emulation.setTouchEmulationEnabled", {"enabled": True}
                        )
                        control = cheap.get_by_role(
                            "button", name="Open editable offer:", exact=False
                        )
                        control.scroll_into_view_if_needed()
                        box = control.bounding_box()
                        touch.send(
                            "Input.dispatchTouchEvent",
                            {
                                "type": "touchStart",
                                "touchPoints": [
                                    {
                                        "x": box["x"] + box["width"] / 2,
                                        "y": box["y"] + box["height"] / 2,
                                    }
                                ],
                            },
                        )
                        touch.send(
                            "Input.dispatchTouchEvent",
                            {"type": "touchEnd", "touchPoints": []},
                        )
                        touch.send(
                            "Emulation.setTouchEmulationEnabled", {"enabled": False}
                        )
                        touch.detach()
                    else:
                        cheap.get_by_role(
                            "button", name="Open editable offer:", exact=False
                        ).click()
                    self.assertIn(
                        "Lowest-cost supported offer found",
                        page.locator("#trade-result").inner_text(),
                    )
                    page.get_by_role(
                        "button", name="Adopt alternative", exact=True
                    ).click()
                    self.assertEqual(harness.proposal(page)["sent"], ["player:d"])
                    self.assertEqual(harness.proposal(page)["received"], ["player:x"])
                    page.reload()
                    page.locator("#trade-target:not([hidden])").wait_for()
                    self.assertEqual(harness.proposal(page)["sent"], ["player:d"])
                    self.assertEqual(len(requests), count)
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width + 1
                    )
                    self.record(page, width, rows, requests)

    def test_same_offer_roles_not_duplicate_and_unknown_cost_is_explicit(self):
        harness = scout.ScoutWorkspaceStateBrowserTests()
        assets = panel()
        only = select([row(assets, ["d"])], assets)[0]
        only["proposal"]["assets_sent"] = ["player:d"]
        only["proposal"]["assets_received"] = ["player:x"]
        with self.page(
            320,
            api=lambda route, payload: route.fulfill(
                json={"results": [only], "count": 1}
            ),
        ) as (page, requests):
            harness.ready(page, "/trades/trade-for?asset_id=player:x")
            page.click("#trade-find")
            page.locator(".tw-acquisition-role").wait_for()
            self.assertEqual(page.locator(".tw-offer").count(), 1)
            self.assertIn(
                "Best-supported fit found · Lowest-cost supported offer found",
                page.locator(".tw-acquisition-role").inner_text(),
            )
        unknown = deepcopy(only)
        unknown["acquisition_comparison"]["roles"] = ["best_fit"]
        unknown["acquisition_comparison"]["cost"] = {
            "availability": "unknown",
            "reason": "Complete compatible Neutral Market cost is unavailable for this assessment.",
        }
        with self.page(
            320,
            api=lambda route, payload: route.fulfill(
                json={"results": [unknown], "count": 1}
            ),
        ) as (page, requests):
            harness.ready(page, "/trades/trade-for?asset_id=player:x")
            page.click("#trade-find")
            page.locator(".tw-acquisition-role").wait_for()
            self.assertIn(
                "Complete compatible Neutral Market cost is unavailable",
                page.locator(".tw-offer").inner_text(),
            )
            self.assertNotIn(
                "Lowest-cost supported offer found",
                page.locator(".tw-offer").inner_text(),
            )
