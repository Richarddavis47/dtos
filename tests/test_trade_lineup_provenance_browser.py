"""Canonical completed evidence -> private HTTP -> preview and rendered detail.

Only completed alternative transport is substituted; no live account is used.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from services.trade_decision import decision_context
from services.trade_explanation import render_trade_explanation
from tests import test_trade_recommendation_clarity as fixtures
import routes.trades as routes


class LineupProvenanceBrowserTests(unittest.TestCase):
    def test_conflicts_and_independent_weeks_across_http_preview_keep_adopt_reload(
        self,
    ):
        f = fixtures.RecommendationClarityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        original = routes.evaluate_trade_request
        state = {"case": "global", "evaluation": None}

        def evaluated(*args, **kwargs):
            result = original(*args, **kwargs)
            e = result["evaluation"]
            from services.recommended_trade_search import surface_evidence
            # A copied opportunity was prepared on the original valid result.
            # It must not revive a comparison after that result loses admission.
            state['opportunity'] = surface_evidence({'evaluation': e})
            if state["case"] == "global":
                e["multi_horizon_impact"]["projection_generation"] = (
                    "incompatible-test-publication"
                )
            else:
                e["multi_horizon_impact"]["sides"]["active"]["weekly"][3]["post"][
                    "projection_snapshot_id"
                ] = "incompatible-test-week"
            e["decision_context"] = decision_context(e)
            e["explanation_html"] = render_trade_explanation(e, league_id="league-1")
            state["evaluation"] = e
            return result

        def alternatives(*args, **kwargs):
            # Exact completed proposal, after the real producer and renderer.
            row = {
                "proposal": {
                    k: deepcopy(f.payload[k])
                    for k in (
                        "active_roster_id",
                        "partner_roster_id",
                        "assets_sent",
                        "assets_received",
                    )
                },
                "evaluation": deepcopy(state["evaluation"]),
                "opportunity": deepcopy(state['opportunity']),
                "exploration": True,
                "search_result_type": "MISSING REQUIRED EVIDENCE",
            }
            return {"results": [], "exploratory_results": [row], "count": 0}

        reports = []
        with (
            patch.object(routes, "evaluate_trade_request", side_effect=evaluated),
            patch.object(routes, "create_trade_alternatives", side_effect=alternatives),
        ):
            for case in ("global", "one-week"):
                state["case"] = case
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    with (
                        self.subTest(case=case, width=width),
                        f.f.browser(width, height) as page,
                    ):
                        f.f.ready(page)
                        page.select_option("#trade-partner", "2")
                        page.select_option("#trade-strategy", "RETOOL")
                        for side, pid in (
                            ("sent", "a"),
                            ("sent", "2029-R1-1"),
                            ("received", "c"),
                        ):
                            f.f.select(page, side, pid)
                        page.get_by_role(
                            "button", name="Evaluate Trade", exact=True
                        ).click()
                        primary = page.locator("#trade-result .tw-final-verdict")
                        primary.wait_for()
                        self.assertIn(
                            "Recommendation unavailable", primary.inner_text()
                        )
                        d = f.f.responses[-1]["evaluation"]["decision_context"]
                        if case == "global":
                            self.assertIsNone(d["lineup"]["delta"])
                        else:
                            self.assertAlmostEqual(d["lineup"]["delta"], 6.31)
                            self.assertIsNone(
                                d["lineup_comparisons"]["next_n"]["delta"]
                            )
                            self.assertAlmostEqual(
                                d["lineup_comparisons"]["playoff_window"]["delta"],
                                12.62,
                            )
                        page.locator(".tw-evaluation-detail > summary").click()
                        page.get_by_text(
                            "Supporting evidence and limitations", exact=True
                        ).click()
                        page.get_by_text(
                            "Weekly optimal-lineup detail", exact=True
                        ).click()
                        weekly = page.locator(".tw-evaluation-detail").inner_text()
                        self.assertIn(
                            "Week 3 · Optimal-lineup change: Unavailable", weekly
                        )
                        if case == "global":
                            self.assertIn(
                                "Week 2 · Optimal-lineup change: Unavailable", weekly
                            )
                        else:
                            self.assertIn(
                                "Week 2 · Optimal-lineup change: 6.31", weekly
                            )
                        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
                        if target:
                            Path(target).mkdir(parents=True, exist_ok=True)
                            page.screenshot(
                                path=str(Path(target, f"expanded-{case}-{width}.png")),
                                full_page=True,
                            )
                        saved = f.f.state(page)
                        original_draft = next(iter(saved.values()))["currentProposal"]
                        mode = next(iter(saved.values()))["valuationMode"]
                        page.locator("#trade-adjust").click()
                        page.locator("#trade-alternatives").click()
                        card = page.locator("#trade-result .tw-offer").first
                        card.wait_for()
                        self.assertNotIn(
                            "WORTH PURSUING", card.locator("h3").first.inner_text()
                        )
                        card.get_by_text(
                            "Why this offer · evidence and risks", exact=True
                        ).click()
                        self.assertNotIn(
                            "WORTH PURSUING",
                            card.locator(".tw-final-verdict").inner_text(),
                        )
                        card.get_by_role(
                            "button", name="Open editable offer: preview", exact=True
                        ).click()
                        page.get_by_role(
                            "button", name="Keep original", exact=True
                        ).click()
                        self.assertEqual(
                            next(iter(f.f.state(page).values()))["currentProposal"],
                            original_draft,
                        )
                        page.get_by_role(
                            "button", name="Open editable offer: preview", exact=True
                        ).click()
                        page.reload()
                        page.get_by_role(
                            "button", name="Adopt alternative", exact=True
                        ).wait_for()
                        page.locator("#trade-result details").evaluate_all(
                            "rows=>rows.forEach(e=>e.open=true)"
                        )
                        restored_text = page.locator("#trade-result").inner_text()
                        if case == "global":
                            self.assertNotIn("6.31", restored_text)
                            self.assertNotIn("18.93", restored_text)
                        else:
                            self.assertIn(
                                "Your team · Next-N: Unavailable", restored_text
                            )
                            self.assertNotIn("Your team · Next-N: 18.93", restored_text)
                            self.assertIn(
                                "Your team · Current week: 6.31", restored_text
                            )
                            self.assertIn(
                                "Your team · Playoff window: 12.62", restored_text
                            )
                            self.assertIn("Their team · Next-N: -18.93", restored_text)
                        page.get_by_role(
                            "button", name="Adopt alternative", exact=True
                        ).click()
                        page.reload()
                        page.locator("#trade-context").wait_for()
                        adopted = next(iter(f.f.state(page).values()))[
                            "currentProposal"
                        ]
                        self.assertEqual(adopted["sent"], ["a", "2029-R1-1"])
                        self.assertEqual(adopted["received"], ["c"])
                        self.assertEqual(
                            next(iter(f.f.state(page).values()))["valuationMode"], mode
                        )
                        self.assertLessEqual(
                            len(
                                json.dumps(
                                    next(iter(f.f.state(page).values()))[
                                        "currentAssessment"
                                    ]
                                )
                            ),
                            64000,
                        )
                        page.locator("#trade-result details").evaluate_all(
                            "rows=>rows.forEach(e=>e.open=true)"
                        )
                        adopted_text = page.locator("#trade-result").inner_text()
                        if case == "global":
                            self.assertNotIn("6.31", adopted_text)
                            self.assertNotIn("18.93", adopted_text)
                        else:
                            self.assertIn(
                                "Your team · Next-N: Unavailable", adopted_text
                            )
                            self.assertNotIn("Your team · Next-N: 18.93", adopted_text)
                            self.assertIn(
                                "Your team · Current week: 6.31", adopted_text
                            )
                            self.assertIn(
                                "Your team · Playoff window: 12.62", adopted_text
                            )
                            self.assertIn("Their team · Next-N: -18.93", adopted_text)
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"), width
                        )
                        reports.append(
                            dict(
                                case=case,
                                width=width,
                                height=height,
                                qualified=False,
                                package_preserved=True,
                                mode=mode,
                                restored_text=restored_text,
                                adopted_text=adopted_text,
                                saved_context_bytes=len(
                                    json.dumps(
                                        next(iter(f.f.state(page).values()))[
                                            "currentAssessment"
                                        ]
                                    )
                                ),
                            )
                        )
                        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
                        if target:
                            Path(target).mkdir(parents=True, exist_ok=True)
                            page.screenshot(
                                path=str(Path(target, f"provenance-{case}-{width}.png"))
                            )
        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
        if target:
            Path(target, "provenance-browser.json").write_text(
                json.dumps(reports, indent=2)
            )
