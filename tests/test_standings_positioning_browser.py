"""Actual Home/League routes: both source fixtures, pointer and keyboard proof."""

import unittest
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.home import create_home_router
from tests.test_standings_positioning import source_fixture, SOURCES
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_runtime import launch_chromium


class StandingsPositioningBrowserTests(unittest.TestCase):
    def test_two_leagues_home_league_order_cutoff_full_width_explanations(self):
        import dtos_app

        fixtures = [source_fixture(0), source_fixture(1)]
        active = {"data": fixtures[0]}

        async def fresh():
            pass

        app = FastAPI()
        app.include_router(
            create_home_router(
                ensure_fresh=fresh,
                require_data=lambda: active["data"],
                page=dtos_app.page,
            )
        )
        app.mount("/static", StaticFiles(directory="static"), name="static")
        account = SimpleNamespace(
            membership=SimpleNamespace(league_id="1313066632158924800", roster_id=1)
        )
        with (
            patch("src.ui.badges.current_account", return_value=account),
            patch("routes.home.current_account", return_value=account),
            patch("routes.home.current_league_context", return_value=None),
            patch.object(dtos_app, "current_league_context", return_value=None),
            patch("routes.home.build_team_directory", return_value={}),
            patch(
                "routes.home.defending_champion",
                side_effect=lambda data: (
                    (2025, 1)
                    if data["league"]["league_id"] == "1313066632158924800"
                    else None
                ),
            ),
            patch(
                "src.ui.standings.defending_champion",
                side_effect=lambda data: (
                    (2025, 1)
                    if data["league"]["league_id"] == "1313066632158924800"
                    else None
                ),
            ),
            patch("services.attention_changes.pick_changes", return_value=([], {})),
            patch("services.home_attention.attention_state", return_value={"items": []}),
            patch("src.ui.front_office_brief.cards", return_value=""),
            patch(
                "services.sleeper.sleeper_get",
                side_effect=AssertionError("No source calls on reads"),
            ),
            sync_playwright() as p,
        ):
            client = TestClient(app)
            browser = launch_chromium(p, headless=True)
            try:
                for index in (0, 1, 0):
                    active["data"] = fixtures[index]
                    account.membership.league_id = active["data"]["league"]["league_id"]
                    account.membership.roster_id = 1 if index == 0 else 2
                    for width, height in (
                        (320, 432),
                        (320, 844),
                        (375, 432),
                        (375, 812),
                        (390, 677),
                        (390, 844),
                        (1280, 757),
                    ):
                        with (
                            self.subTest(league=index, width=width, height=height),
                            browser.new_context(
                                viewport={"width": width, "height": height}
                            ) as bc,
                        ):

                            def transport(route):
                                url = urlsplit(route.request.url)
                                if url.hostname == "sleepercdn.com":
                                    route.fulfill(
                                        status=200,
                                        content_type="image/png",
                                        body=image_bytes("standings"),
                                    )
                                elif url.hostname == "dtos.test":
                                    response = client.get(
                                        url.path
                                        + ("?" + url.query if url.query else "")
                                    )
                                    route.fulfill(
                                        status=response.status_code,
                                        content_type=response.headers.get(
                                            "content-type", "text/html"
                                        ),
                                        body=response.content,
                                    )
                                else:
                                    route.abort()

                            bc.route("**/*", transport)
                            page = bc.new_page()
                            for path in ("/", "/league"):
                                page.goto("https://dtos.test" + path)
                                table = page.locator(".compact-standings")
                                ids = table.locator("tr[data-roster-id]").evaluate_all(
                                    "(rows)=>rows.map(e=>Number(e.dataset.rosterId))"
                                )
                                self.assertEqual(ids, SOURCES[index]["expected_order"])
                                self.assertEqual(
                                    table.locator(".standings-you").count(), 1
                                )
                                self.assertEqual(
                                    table.locator(".playoff-boundary").count(),
                                    1 if index == 0 else 0,
                                )
                                self.assertIn(
                                    "Sleeper records and points · DTOS-organized order",
                                    page.locator(".standings-panel").inner_text(),
                                )
                                for team in active["data"]["teams"]:
                                    row = table.locator(
                                        f'tr[data-roster-id="{team["roster_id"]}"]'
                                    )
                                    self.assertIn(
                                        f"{team['wins']}-{team['losses']}-0",
                                        row.inner_text(),
                                    )
                                    for key in ("points_for", "points_against"):
                                        self.assertIn(
                                            f"{team[key]:.2f}", row.inner_text()
                                        )
                                    link = row.locator('a[href^="/teams/"]')
                                    link.scroll_into_view_if_needed()
                                    self.hit(link)
                                    link.focus()
                                    self.assertNotEqual(
                                        link.evaluate(
                                            "e=>getComputedStyle(e).outlineStyle"
                                        ),
                                        "none",
                                    )
                                panel = page.locator('.standings-panel')
                                evidence = page.get_by_text('Standings and playoff evidence', exact=True)
                                evidence.focus()
                                evidence.press('Enter')
                                trophy = panel.locator(
                                    '[data-badge="champion"] summary'
                                )
                                self.assertEqual(trophy.count(), 1 if index == 0 else 0)
                                if trophy.count():
                                    trophy.scroll_into_view_if_needed()
                                    self.hit(trophy)
                                    trophy.focus()
                                    trophy.press("Enter")
                                    self.assertTrue(
                                        trophy.evaluate("e=>e.parentElement.open")
                                    )
                                    explanation = trophy.locator("..").locator("p")
                                    self.assertTrue(explanation.is_visible())
                                    self.assertGreater(
                                        explanation.bounding_box()["width"],
                                        table.bounding_box()["width"] * 0.80,
                                    )
                                    self.assertIn(
                                        "2025 defending champion",
                                        explanation.inner_text(),
                                    )
                                    self.assertNotEqual(
                                        trophy.evaluate(
                                            "e=>getComputedStyle(e).outlineStyle"
                                        ),
                                        "none",
                                    )
                                disclosure = page.get_by_text(
                                    "Standings and playoff evidence", exact=True
                                )
                                disclosure.scroll_into_view_if_needed()
                                self.hit(disclosure)
                                disclosure.focus()
                                if not disclosure.evaluate("e=>e.parentElement.open"):
                                    disclosure.press("Enter")
                                self.assertTrue(
                                    disclosure.evaluate("e=>e.parentElement.open")
                                )
                                self.assertIn(
                                    "completed Week 3 to Week 4",
                                    disclosure.locator("..").inner_text(),
                                )
                                streak = panel.locator(
                                    '[data-badge="streak"] summary'
                                ).first
                                streak.scroll_into_view_if_needed()
                                streak.focus()
                                streak.press("Enter")
                                self.assertIn(
                                    "Head-to-head results",
                                    streak.locator("..").inner_text(),
                                )
                                if index == 1:
                                    self.assertIn(
                                        "division configuration is not confirmed",
                                        disclosure.locator("..").inner_text(),
                                    )
                                self.assertLessEqual(
                                    page.evaluate(
                                        "document.documentElement.scrollWidth"
                                    ),
                                    width,
                                )
                                cells = table.locator("tr[data-roster-id] td")
                                self.assertTrue(
                                    cells.evaluate_all(
                                        "(cells)=>cells.every(e=>e.scrollWidth<=e.clientWidth+1)"
                                    ), cells.evaluate_all("es=>es.map(e=>({text:e.textContent,width:e.clientWidth,scroll:e.scrollWidth,box:e.getBoundingClientRect().toJSON()}))")
                                )
            finally:
                browser.close()

    def hit(self, element):
        box = element.bounding_box()
        self.assertIsNotNone(box)
        point = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
        hit = element.evaluate("(e,p)=>e===document.elementFromPoint(p.x,p.y)||e.contains(document.elementFromPoint(p.x,p.y))", point)
        info = element.evaluate("(e,p)=>({name:e.textContent,box:e.getBoundingClientRect().toJSON(),point:p,hit:document.elementFromPoint(p.x,p.y)?.outerHTML.slice(0,300),viewport:innerHeight})",point)
        if not hit:
            from pathlib import Path
            import json
            Path('.validation/beginner-navigation/standings-hit.json').write_text(json.dumps(info,indent=2))
        self.assertTrue(hit, info)
