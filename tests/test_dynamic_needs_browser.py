"""Released routers/scripts, authenticated canonical source; responsive Chromium."""

from unittest import TestCase
from unittest.mock import AsyncMock, patch
from playwright.sync_api import sync_playwright
from routes.teams import create_teams_router
from tests import test_home_opportunity_integrity as fixtures
from tools.validation.browser_runtime import launch_chromium
from src.core.intelligence.roster_diagnostics import team_diagnostics


class DynamicNeedsBrowserTests(TestCase):
    def test_my_team_opponent_trade_and_home_share_qualified_evidence(self):
        import dtos_app

        f = fixtures.OpportunityIntegrityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.enterContext(
            patch(
                "src.core.projection_intelligence.projection_service", f.source.reader
            )
        )
        f.f.client.app.include_router(
            create_teams_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: f.f.data,
                page=dtos_app.page,
                state={"data": f.f.data},
            )
        )
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [
                    (320, 432),
                    (375, 667),
                    (390, 682),
                    (390, 844),
                    (1280, 900),
                ]:
                    page = f.browser_page(browser, width, height)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    for rid in (1, 2):
                        self.assertEqual(
                            page.goto("https://dtos.test/teams/" + str(rid)).status, 200
                        )
                        room = page.locator("#positional-depth")
                        room.wait_for()
                        expected = team_diagnostics(
                            f.f.data,
                            rid,
                            f.source.reader.snapshot(),
                            strategy="REBUILD" if rid == 1 else "WIN NOW",
                        )["positions"]["QB"]
                        self.assertIn(
                            expected["classification"].lower(),
                            room.inner_text().lower(),
                        )
                        summary = room.get_by_text(
                            "Lineup eligibility and surplus", exact=True
                        ).first
                        summary.focus()
                        page.keyboard.press("Enter")
                        self.assertIn("remove_one", room.inner_text())
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"), width
                        )
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").first.wait_for()
                    self.assertIn(
                        f.row["evaluation"]["why_you_would_do_it"],
                        page.locator(".home-opportunity").first.inner_text(),
                    )
                    page.get_by_role("link", name="Explore / Edit").first.click()
                    page.get_by_role(
                        "button", name="Adopt alternative", exact=True
                    ).click()
                    page.get_by_role("button", name="Reevaluate Trade").click()
                    page.wait_for_function(
                        "document.querySelector('#trade-result').dataset.assessmentFreshness==='current'"
                    )
                    self.assertIn(
                        "replacement",
                        page.locator("#trade-result").text_content().lower(),
                    )
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width
                    )
                    self.assertEqual(errors, [])
                    page.close()
            finally:
                browser.close()
