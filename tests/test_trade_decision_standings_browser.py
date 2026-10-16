"""Shared standings renderer density; actual Home/League routes have separate gates."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from src.ui.standings import render_standings
from tests.test_standings_positioning import source_fixture
from tools.validation.browser_runtime import launch_chromium


class TradeDecisionStandingsBrowserTests(unittest.TestCase):
    def test_shared_headers_aligned_values_and_accessible_badges(self):
        import dtos_app

        geometry = []
        fixtures = [source_fixture(0), source_fixture(1)]
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for league in (0, 1):
                    data = fixtures[league]
                    with patch("src.ui.badges.current_account", return_value=None):
                        html = dtos_app.page(
                            "League", render_standings(data)
                        ).body.decode()
                    for width, height in [
                        (320, 432),
                        (320, 844),
                        (375, 667),
                        (390, 682),
                        (390, 844),
                        (1280, 900),
                    ]:
                        page = browser.new_page(
                            viewport={"width": width, "height": height}
                        )
                        page.route("**/*", lambda route: route.abort())
                        page.route(
                            "**/static/css/matchups.css",
                            lambda route: route.fulfill(
                                content_type="text/css",
                                body=Path("static/css/matchups.css").read_text(),
                            ),
                        )
                        page.route(
                            "https://dtos.test/league",
                            lambda route: route.fulfill(
                                content_type="text/html", body=html
                            ),
                        )
                        page.goto("https://dtos.test/league")
                        table = page.locator(".compact-standings")
                        header = table.locator("thead")
                        rows = table.locator("tr[data-roster-id]")
                        geometry.append(
                            {
                                "league": data["league"]["league_id"],
                                "width": width,
                                "height": height,
                                "table_height": round(
                                    table.bounding_box()["height"], 2
                                ),
                                "first_row_height": round(
                                    rows.first.bounding_box()["height"], 2
                                ),
                                "header_height": round(
                                    header.bounding_box()["height"], 2
                                ),
                                "overflow": page.evaluate(
                                    "document.documentElement.scrollWidth>innerWidth"
                                ),
                            }
                        )
                        output = os.environ.get("DTOS_STANDINGS_DECISION_EVIDENCE")
                        if output:
                            Path(output).write_text(json.dumps(geometry, indent=2))
                        self.assertTrue(header.is_visible())
                        self.assertFalse(geometry[-1]["overflow"])
                        for i in range(rows.count()):
                            row = rows.nth(i)
                            pf, pa = row.locator("td").nth(2), row.locator("td").nth(3)
                            self.assertAlmostEqual(
                                pf.bounding_box()["y"], pa.bounding_box()["y"], delta=1
                            )
                            self.assertEqual(
                                row.locator('td[data-label="PF"]').count(), 1
                            )
                            link = row.locator('a[href^="/teams/"]')
                            link.focus()
                            self.assertEqual(
                                link.evaluate("e=>e===document.activeElement"), True
                            )
                        page.close()
                self.assertTrue(all(row["header_height"] >= 20 for row in geometry))
            finally:
                browser.close()
