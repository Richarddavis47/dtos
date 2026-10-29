"""Prepared facts -> HTTP -> phone UI; mutable work is disposable only."""

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tests import test_contextual_back as navigation
from tests import test_history_progress_presentation as history
from tests import test_personal_rankings_partial as partial
from tests import test_personal_trade_browser as personal_browser
from tests import test_trade_recommendation_clarity as decision
from tools.validation.browser_runtime import launch_chromium

SIZES = ((320, 432), (375, 667), (390, 844), (1280, 900))


class CustomerClarityTests(unittest.TestCase):
    def output(self, name, data):
        if os.getenv("DTOS_CUSTOMER_CLARITY_EVIDENCE"):
            root = Path(os.environ["DTOS_CUSTOMER_CLARITY_EVIDENCE"])
            root.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(json.dumps(data, indent=2, default=str))

    def fixture(self):
        helper = navigation.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        return helper, helper.fixture()

    def test_deep_market_back_keeps_one_control_layout_tab_order_and_bottom_nav(self):
        helper, f = self.fixture()
        original = deepcopy(f.editor.state())
        rows = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in SIZES:
                    page, requests, _, _, errors = helper.page(
                        browser, f, width, height
                    )
                    page.goto(helper.origin + "/league")
                    page.locator('.manager-nav a[href="/market"]').click()
                    page.wait_for_url("**/market")
                    page.wait_for_function(
                        '!!window.dtosNavigation && !!document.querySelector(".dtos-back-slot")'
                    )
                    layout = page.evaluate(
                        '({height:document.documentElement.scrollHeight, title:document.querySelector("h1").getBoundingClientRect().top+scrollY})'
                    )
                    before = len(requests)
                    page.evaluate("scrollTo(0,1000)")
                    page.wait_for_function(
                        'document.documentElement.classList.contains("dtos-back-docked")'
                    )
                    row = page.evaluate("""() => {
                      const b=document.querySelector('#dtos-back'),d=document.querySelector('.dtos-back-dock'),n=document.querySelector('.manager-nav');
                      return {width:innerWidth,height:innerHeight,scroll:scrollY,back:b.getBoundingClientRect().toJSON(),dock:d.getBoundingClientRect().toJSON(),nav:n.getBoundingClientRect().toJSON(),navFixed:getComputedStyle(n).position==='fixed',overflow:document.documentElement.scrollWidth>innerWidth,documentHeight:document.documentElement.scrollHeight,title:document.querySelector('h1').getBoundingClientRect().top+scrollY,single:document.querySelectorAll('#dtos-back').length,originalOrder:b.closest('.dtos-page-title')!==null,decorative:d.getAttribute('aria-hidden')};
                    }""")
                    self.assertEqual(
                        len(requests),
                        before,
                        "Scrolling must not request readiness or analytical work",
                    )
                    self.assertEqual(row["single"], 1)
                    self.assertTrue(row["originalOrder"])
                    self.assertEqual(row["decorative"], "true")
                    self.assertFalse(row["overflow"])
                    self.assertGreaterEqual(row["back"]["height"], 44)
                    self.assertGreaterEqual(row["back"]["width"], 44)
                    self.assertGreaterEqual(row["back"]["top"], 0)
                    self.assertLess(row["back"]["bottom"], height)
                    self.assertAlmostEqual(
                        row["documentHeight"], layout["height"], delta=1
                    )
                    self.assertAlmostEqual(row["title"], layout["title"], delta=1)
                    self.assertEqual(page.locator(".manager-nav a").count(), 5)
                    if row["navFixed"]:
                        self.assertLess(row["dock"]["bottom"], row["nav"]["top"])
                    back = page.locator("#dtos-back")
                    page.keyboard.press("Tab")
                    back.focus()
                    self.assertTrue(back.evaluate("e=>e===document.activeElement"))
                    self.assertNotEqual(
                        back.evaluate("e=>getComputedStyle(e).outlineStyle"), "none"
                    )
                    page.keyboard.press("Tab")
                    self.assertTrue(
                        back.evaluate(
                            "e=>!!(e.compareDocumentPosition(document.activeElement)&Node.DOCUMENT_POSITION_FOLLOWING)"
                        )
                    )
                    page.evaluate("scrollTo(0,1000)")
                    page.wait_for_function(
                        'document.documentElement.classList.contains("dtos-back-docked")'
                    )
                    root = os.getenv("DTOS_CUSTOMER_CLARITY_EVIDENCE")
                    if root:
                        Path(root).mkdir(parents=True, exist_ok=True)
                        page.screenshot(
                            path=str(Path(root) / f"back-after-{width}.png")
                        )
                    bounds = back.bounding_box()
                    if width < 760:
                        cdp = page.context.new_cdp_session(page)
                        cdp.send(
                            "Emulation.setTouchEmulationEnabled", {"enabled": True}
                        )
                        point = {
                            "x": bounds["x"] + bounds["width"] / 2,
                            "y": bounds["y"] + bounds["height"] / 2,
                        }
                        cdp.send(
                            "Input.dispatchTouchEvent",
                            {"type": "touchStart", "touchPoints": [point]},
                        )
                        cdp.send(
                            "Input.dispatchTouchEvent",
                            {"type": "touchEnd", "touchPoints": []},
                        )
                    else:
                        back.click()
                    page.wait_for_url("**/league")
                    self.assertFalse(errors, errors)
                    rows.append(row)
                    page.close()
            finally:
                browser.close()
        self.assertEqual(f.editor.state(), original)
        self.output("back-geometry.json", rows)

    def test_docked_trade_market_dossier_return_preserves_modes_package_and_fresh_entry(
        self,
    ):
        helper, f = self.fixture()
        original = deepcopy(f.editor.state())
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in SIZES:
                    for mode in ("neutral", "custom"):
                        page, requests, _, _, errors = helper.page(
                            browser, f, width, height
                        )
                        helper.ready(page)
                        helper.choose(page)
                        page.select_option("#trade-valuation-mode", mode)
                        before = helper.draft(page)
                        page.locator('.manager-nav a[href="/market"]').click()
                        page.wait_for_url("**/market")
                        form = page.locator('form[action="/market"]').first
                        form.locator("[name=q]").fill("c")
                        form.evaluate("f=>f.requestSubmit()")
                        page.wait_for_url("**/market?*q=c*")
                        page.locator(".market-asset").first.click()
                        page.locator("a").filter(
                            has_text="Open canonical dossier"
                        ).click()
                        page.wait_for_url("**/players/*")
                        page.evaluate("scrollTo(0,1000)")
                        page.wait_for_function(
                            'document.documentElement.classList.contains("dtos-back-docked")'
                        )
                        helper.back(page, "/market?*")
                        self.assertIn("q=c", page.url)
                        for _ in range(5):
                            if "/market" not in page.url:
                                break
                            old = page.url
                            page.locator("#dtos-back").click()
                            page.wait_for_url(lambda url: str(url) != old)
                        page.locator("#trade-partner").wait_for()
                        page.wait_for_function(
                            '!document.querySelector("#trade-context").textContent.includes("Loading")'
                        )
                        after = helper.draft(page)
                        self.assertEqual(
                            after["currentProposal"], before["currentProposal"]
                        )
                        self.assertEqual(after["valuationMode"], mode)
                        self.assertEqual(
                            after["currentProposal"]["received"], ["2028-R1-4"]
                        )
                        page.locator('.manager-nav a[href="/trades"]').click()
                        page.wait_for_url("**/trades")
                        helper.ready(page)
                        fresh = helper.draft(page)["currentProposal"]
                        self.assertEqual(fresh["sent"], [])
                        self.assertEqual(fresh["received"], [])
                        self.assertFalse(
                            any(
                                method == "POST" and path.startswith("/api/my-dtos")
                                for method, path, _ in requests
                            )
                        )
                        self.assertFalse(errors, errors)
                        page.close()
            finally:
                browser.close()
        self.assertEqual(f.editor.state(), original)

    def test_mixed_freshness_explains_timestamps_without_changing_evidence(self):
        from src.ui.source_provenance import source_presentation

        evidence = dict(
            projection_freshness=["Fresh", "Unavailable"],
            conclusion_state="provisional",
            source_observations=["2026-10-29T12:00:00Z", "Unavailable"],
            refresh={"retained_publication": True},
            scoring="supported",
        )
        original = deepcopy(evidence)
        with ExitStack() as stack:
            guards = [
                stack.enter_context(patch(name, side_effect=AssertionError(name)))
                for name in (
                    "services.sleeper.sleeper_get",
                    "services.trade_intelligence.generate_trade_workflow",
                    "src.core.fois.service.FOISService._generate_sync",
                    "src.core.trade_intelligence.lineup.optimal_legal_lineup",
                    "src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct",
                )
            ]
            summary, details = source_presentation(
                evidence, now=datetime(2026, 10, 29, 12, 1, tzinfo=timezone.utc)
            )
        self.assertNotIn("Fresh, Unavailable", summary)
        self.assertIn(
            "Some projection observations are recent; other update times are not verified",
            summary,
        )
        self.assertIn("provisional", summary)
        self.assertIn("latest refresh did not complete", summary)
        self.assertIn("Fresh", details)
        self.assertIn("Unavailable", details)
        self.assertEqual(evidence, original)
        self.assertTrue(all(g.call_count == 0 for g in guards))
        self.output(
            "mixed-source-copy.json",
            {
                "summary_html": summary,
                "details_html": details,
                "expensive_calls": 0,
                "input_unchanged": True,
            },
        )

    def test_history_completed_and_pending_are_separate_on_actual_http(self):
        producer = history.CanonicalHistoryProgressTests()
        producer.setUp()
        self.addCleanup(producer.doCleanups)
        job = producer.create_job(tuple(range(2021, 2027)))
        for season in range(2021, 2026):
            producer.checkpoint(job, season, "completed")
        producer.checkpoint(job, 2026, "pending")
        canonical = producer.canonical()
        fixture = history.HistoryPresentationTests()
        self.addCleanup(fixture.doCleanups)
        client, status = fixture.client(canonical)
        self.addCleanup(client.close)
        original = deepcopy(status)
        response = client.get("/history")
        self.assertEqual(response.status_code, 200)
        main = response.text.split("<details", 1)[0]
        self.assertNotIn("Completed With Pending", main)
        self.assertIn("Completed seasons ready; more evidence pending", main)
        self.assertIn("2021–2025 complete; 2026 pending provider evidence", main)
        self.assertIn("5/6 seasons", response.text)
        self.assertEqual(status, original)
        self.output(
            "history-http.json",
            {
                "status": response.status_code,
                "body": response.text,
                "canonical": canonical,
                "unchanged": True,
            },
        )

    def test_custom_warning_is_concise_while_all_limitations_remain_accessible(self):
        fixture = partial.PartialTradeHTTPTests(
            "test_supported_package_and_all_workflows_remain_usable_without_repricing"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.missing()
        helper = personal_browser.PersonalTradeBrowserTests()
        original = deepcopy(fixture.f.document())
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in SIZES:
                    page, _, errors = helper.page(
                        browser, fixture.f.fixture, width, height
                    )
                    page.goto("http://testserver/account/my-dtos")
                    page.locator(
                        '[data-asset-id="player:a"] .personal-values'
                    ).wait_for()
                    self.assertIn(
                        "6 saved assets",
                        page.locator("#personal-warnings").inner_text(),
                    )
                    self.assertIn(
                        "Neutral DTOS remains available",
                        page.locator("#personal-warnings").inner_text(),
                    )
                    self.assertFalse(
                        page.locator("#personal-warning-details").evaluate("e=>e.open")
                    )
                    page.locator("#personal-warning-details summary").focus()
                    page.keyboard.press("Enter")
                    self.assertTrue(
                        page.locator("#personal-warning-details").evaluate("e=>e.open")
                    )
                    expected = fixture.f.editor.state()["limitations"]
                    self.assertEqual(
                        page.locator("#personal-warning-list li").all_text_contents(),
                        expected,
                    )
                    self.assertEqual(
                        page.evaluate(
                            "document.documentElement.scrollWidth>innerWidth"
                        ),
                        False,
                    )
                    self.assertFalse(errors, errors)
                    page.close()
            finally:
                browser.close()
        self.assertEqual(fixture.f.document(), original)

    def test_multiweek_display_labels_totals_and_keeps_admitted_numbers(self):
        fixture = decision.RecommendationClarityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with fixture.f.browser(390, 844) as page:
            fixture.f.ready(page)
            page.select_option("#trade-partner", "2")
            page.select_option("#trade-strategy", "RETOOL")
            for side, asset in [
                ("sent", "a"),
                ("sent", "2029-R1-1"),
                ("received", "c"),
            ]:
                fixture.f.select(page, side, asset)
            page.get_by_role("button", name="Evaluate Trade", exact=True).click()
            page.locator("#trade-result .tw-evaluation-detail > summary").click()
            evaluation = fixture.f.responses[-1]["evaluation"]
            context = evaluation["decision_context"]
            current = context["lineup_comparisons"]["current_week"]
            self.assertAlmostEqual(current["delta"], 6.31)
            self.assertEqual(
                context["lineup_comparisons"]["next_n"]["weeks"], [2, 3, 4]
            )
            self.assertAlmostEqual(
                context["lineup_comparisons"]["next_n"]["delta"], 18.93
            )
            page.get_by_text(
                "Next-N and longer-period changes are totals across the listed weeks, not per-week averages.",
                exact=False,
            ).first.wait_for()
            self.assertIn("6.31", page.locator("#trade-result").inner_text())
            self.output(
                "multiweek-evidence.json",
                {
                    "comparisons": context["lineup_comparisons"],
                    "recommendation": evaluation["recommendation"],
                },
            )
