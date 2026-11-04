"""Real-router shared theme and interactive phone UX contracts."""

import unittest
import os
from pathlib import Path

from tests import test_product_browser_journey as journey
from tests import test_trade_calculator_browser as calculator
from tests import test_trade_scout_state_browser as scout
from src.ui.theme import DESIGN_SYSTEM_CSS
from src.ui.design_system import manager_navigation
from src.ui.badges import explained_badge


class SharedPhoneDesignBrowserTests(journey.ProductBrowserJourneyTests):
    viewports = tuple(
        {"width": width, "height": 900 if width == 1280 else 844}
        for width in (320, 375, 390, 1280)
    )

    def audit_page(self, page, path, viewport):
        self.assertEqual(
            page.evaluate("getComputedStyle(document.body).backgroundColor"),
            "rgb(20, 22, 23)",
        )
        self.assertEqual(
            page.evaluate(
                'getComputedStyle(document.documentElement).getPropertyValue("--accent-primary").trim()'
            ),
            "#80df42",
        )
        self.assertEqual(
            page.locator(".manager-nav a").all_text_contents(),
            ["Home", "My Team", "Trade", "League", "Market"],
        )
        for node in page.locator(
            "button:visible, summary:visible, .manager-nav a"
        ).all():
            self.assertGreaterEqual(
                node.bounding_box()["height"], 43, (path, node.inner_text())
            )
        if path == "/":
            self.assertIn("Official record:", page.locator(".ux-feature").inner_text())
            context = page.locator(".home-secondary-controls details").filter(
                has=page.locator("summary", has_text="Assessment context and roster shortcuts")
            )
            self.assertFalse(context.evaluate("e=>e.open"))
            context.locator("summary").click()
            self.assertIn("DTOS strength assessment:", context.inner_text())
            self.assertIn("separate from official standings", context.inner_text())
            context.locator("summary").click()
            self.assertEqual(page.locator(".ux-feature .ds-you").count(), 1)
            self.assertFalse(
                page.locator(".ds-home-detail").first.get_attribute("open")
            )
            # Return to keyboard modality after exercising the pointer disclosure.
            page.keyboard.press("Tab")
            page.locator(".ux-primary-action").focus()
            self.assertTrue(
                page.locator(".ux-primary-action").evaluate(
                    "e=>e===document.activeElement && e.matches(':focus-visible')"
                )
            )
            self.assertEqual(
                page.locator(".ux-primary-action").evaluate(
                    "e=>getComputedStyle(e).outlineStyle"
                ),
                "solid",
            )
        if path in ("/market", "/teams/1"):
            self.assertGreater(page.locator(".ds-position").count(), 0)
            self.assertEqual(
                page.locator(".ds-position").first.evaluate(
                    "e=>getComputedStyle(e).color"
                ),
                {"QB":"rgb(255, 208, 204)", "RB":"rgb(182, 242, 231)", "WR":"rgb(206, 227, 255)", "TE":"rgb(255, 236, 175)"}[page.locator(".ds-position").first.get_attribute("data-position")],
            )
        if path == "/league":
            # Complete source records now support explicitly statistical placements.
            self.assertEqual(
                page.locator(".compact-standings .standing-rank").all_text_contents(),
                ["#1", "#2", "#3"],
            )
            self.assertEqual(page.locator(".standings-explanations").count(), 0)
            self.assertEqual(page.locator(".standing-inline").all_text_contents(), ["🥇", "🥈", "🥉"])
            page.locator("#standings-evidence > summary").click()
            self.assertIn("DTOS-organized", page.locator("#standings-evidence").inner_text())
            # Absent championship/source-rank evidence still cannot be manufactured.
            self.assertEqual(page.locator("[data-badge=champion]").count(), 0)
            self.assertIn("not Sleeper-supplied playoff seeds", page.locator(".standings-panel").inner_text())


class FocusedPhoneInteractionTests(unittest.TestCase):
    @staticmethod
    def theme(page):
        page.add_style_tag(
            content="*{box-sizing:border-box}body{margin:0;color:var(--text)}"
            + DESIGN_SYSTEM_CSS
        )
        page.evaluate(
            """navigation => {
            const wrapper=document.createElement('div');wrapper.className='wrap';
            while(document.body.firstChild) wrapper.append(document.body.firstChild);
            document.body.append(wrapper);wrapper.insertAdjacentHTML('beforeend',navigation);
        }""",
            manager_navigation("Trade Calculator", roster_id=1),
        )

    @staticmethod
    def capture(page, width, name):
        folder = os.environ.get("DTOS_PHONE_VISUAL_DIR")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(folder) / f"{width}-{name}.png"))

    def test_balance_visible_changes_preview_exact_locks_and_protection_label(self):
        fixture = calculator.CalculatorBrowserTests()
        fixture.setUp()
        for width in (320, 375, 390):
            with (
                self.subTest(width=width),
                fixture.fixture.page(
                    width, workspace=fixture.data, api=fixture.balancing
                ) as (page, _),
            ):
                fixture.build(page)
                self.theme(page)
                original = fixture.state(page)["currentProposal"]
                page.click("#calculator-protect")
                label = page.locator("label[for=trade-constraint-asset]").bounding_box()
                control = page.locator("#trade-constraint-asset").bounding_box()
                self.assertGreaterEqual(control["y"], label["y"] + label["height"])
                self.assertGreater(label["width"], 210)
                page.select_option("#trade-constraint-asset", "pick:2028:2:3")
                page.click("#calculator-lock")
                page.click("#trade-balance-offer")
                preview = page.get_by_role(
                    "button", name="Preview adjustment", exact=True
                )
                preview.wait_for()
                preview.scroll_into_view_if_needed()
                self.assertLessEqual(
                    preview.bounding_box()["y"] + preview.bounding_box()["height"],
                    page.locator(".manager-nav").bounding_box()["y"],
                )
                self.capture(page, width, "balancing-options")
                self.assertIn(
                    "Add 2028 Round 1", page.locator(".tw-adjustment").inner_text()
                )
                self.assertIn(
                    "your outgoing package", page.locator(".tw-adjustment").inner_text()
                )
                self.assertIn("You send:", page.locator(".tw-offer").inner_text())
                self.assertIn("You receive:", page.locator(".tw-offer").inner_text())
                self.assertIn("Current Market: You send", page.locator(".tw-offer").inner_text())
                self.assertEqual(
                    page.locator("#trade-result").evaluate(
                        "e=>e.parentElement.id"
                    ),
                    "trade-balancing",
                )
                self.assertEqual(page.locator("#trade-result").evaluate("e=>e.previousElementSibling.id"), "calculator-balance-status")
                self.assertEqual(fixture.state(page)["currentProposal"], original)
                preview.click()
                page.get_by_role("button", name="Keep original", exact=True).click()
                self.assertEqual(fixture.state(page)["currentProposal"], original)
                preview.click()
                page.get_by_role("button", name="Adopt alternative", exact=True).click()
                self.assertIn(
                    "pick:2028:1:3", fixture.state(page)["currentProposal"]["sent"]
                )
                self.assertIn("pick:2028:2:3", fixture.state(page)["protectedAssets"])
                page.get_by_role(
                    "button", name="Keep incoming target", exact=True
                ).click()
                detail = page.locator("#calculator-received [data-badge=protection]")
                detail.locator("summary").click()
                self.assertIn("player:x", detail.inner_text())
                self.assertIn("incoming Trade For target", detail.inner_text())
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"), width + 1
                )

    def test_next_five_feedback_is_near_action_and_stale_completion_clears(self):
        fixture = scout.ScoutWorkspaceStateBrowserTests()
        for width in (320, 375, 390):
            pending = []
            with (
                self.subTest(width=width),
                fixture.page(
                    width, api=lambda route, payload: pending.append(route)
                ) as (page, _),
            ):
                fixture.ready(page, "/trades/recommended")
                self.theme(page)
                # Next 5 is now a follow-up to an explicit first search.
                page.locator("#trade-find").click()
                page.wait_for_timeout(30)
                pending.pop(0).fulfill(json={"workflow": "recommended", "results": [], "count": 0})
                page.wait_for_function("!document.querySelector('#trade-find').disabled")
                button = page.locator("#recommendation-refresh")
                button.click()
                status = page.locator("#recommendation-status")
                self.assertIn("Searching supported trades", status.inner_text())
                self.assertEqual(status.get_attribute("data-state"), "loading")
                self.assertTrue(button.is_disabled())
                self.capture(page, width, "next-five-loading")
                self.assertEqual(
                    button.evaluate("e=>getComputedStyle(e).cursor"), "not-allowed"
                )
                a, b = button.bounding_box(), status.bounding_box()
                self.assertLess(b["y"] - a["y"] - a["height"], 16)
                self.assertLess(b["y"] + b["height"], 844)
                pending[0].fulfill(
                    json={
                        "results": [fixture.offer(["player:a"], ["player:x"])],
                        "count": 1,
                    }
                )
                page.wait_for_function(
                    '!document.querySelector("#recommendation-refresh").disabled'
                )
                self.assertIn("No qualified recommendations", status.inner_text())
                page.select_option("#trade-strategy", "REBUILD")
                self.assertIn("Strategy changed", status.inner_text())
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"), width + 1
                )

    def test_badge_touch_keyboard_explanations_and_theme_contrast(self):
        from tools.validation.browser_runtime import launch_chromium
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page(viewport={"width": 320, "height": 844})
                page.set_content(
                    "<main>"
                    + explained_badge(
                        "↑2", "Official standings: Week 4 to Week 5.", "movement"
                    )
                    + "</main>"
                )
                self.theme(page)
                summary = page.locator(".ds-badge-detail > summary")
                summary.focus()
                page.keyboard.press("Enter")
                self.assertTrue(page.locator(".ds-badge-detail").evaluate("e=>e.open"))
                self.assertIn("Week 4 to Week 5", page.locator(".ds-badge-detail").inner_text())
                self.assertGreaterEqual(summary.bounding_box()["height"], 44)
                contrast = page.evaluate("""() => {
                    const rgb = v => v.match(/[\\d.]+/g).slice(0,3).map(Number);
                    const lum = a => a.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
                    const colors=getComputedStyle(document.documentElement);
                    const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
                    const sample=document.createElement('span');document.body.append(sample);
                    const color = name => {sample.style.color='var('+name+')';return rgb(getComputedStyle(sample).color)};
                    return ['--text-primary','--text-secondary','--text-muted'].map(name=>ratio(color(name),color('--surface-elevated')));
                }""")
                self.assertTrue(all(value >= 4.5 for value in contrast), contrast)
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"), 321
                )
            finally:
                browser.close()
