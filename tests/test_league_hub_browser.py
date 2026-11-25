"""Prepared synthetic standings, score state and scoped League navigation."""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from routes.home import create_home_router
from routes.matchups import create_matchups_router
from services.matchup_season import prepare_season_matchups, season_week_view
from tools.validation.browser_runtime import launch_chromium


def league_fixture(size=10, playoff_count=6, *, divisions=0, completed=2, live=False):
    league_id = f"fixture-{size}"
    rules = {
        "leg": 3, "last_scored_leg": completed, "start_week": 1,
        "playoff_week_start": 14, "playoff_round_type": 0, "playoff_type": 0,
        "num_teams": size, "playoff_teams": playoff_count, "divisions": divisions,
        "league_average_match": 0,
    }
    league = dict(league_id=league_id, name=f"League {size}", season="2026",
                  status="in_season", sport="nfl", settings=rules)

    def rows(week):
        for rid in range(1, size + 1):
            points = (1200-rid*20 if week == 1 else 700+rid*10 if week == 2 else
                      (15 if rid == 1 else 0) if live and week == 3 else 0)
            yield dict(roster_id=rid, matchup_id=(rid+1)//2, points=points,
                       starters=[str(rid)], players=[str(rid)])

    async def read_fixture(path):
        return list(rows(int(path.rsplit("/", 1)[-1])))

    data = dict(league=league, week=3, roster_positions=["QB"], players={},
                teams=[dict(roster_id=rid, team_name=f"Franchise {rid} with a long name",
                            division=2 if divisions and rid > size-4 else 1,
                            players=[], wins=1 if completed == 2 or rid % 2 else 0,
                            losses=1 if completed == 2 or not rid % 2 else 0, ties=0,
                            points_for=1900-rid*10 if completed == 2 else 1200-rid*20,
                            points_against=120)
                       for rid in range(size, 0, -1)])
    data["season_matchups"] = asyncio.run(
        prepare_season_matchups(league, 3, list(rows(3)), read_fixture, observed_at="fixture")
    )
    pinned = dict(league_id=league_id, season=2026, horizon_generation="fixture-horizon")

    def snapshot(week, *, generation_snapshot):
        return dict(pinned, week=week, projection_snapshot_id=f"week-{week}",
                    players={"1": {"canonical_projection": 0}, "2": {"canonical_projection": 57.25}})
    return data, SimpleNamespace(snapshot=lambda: pinned, week_snapshot=snapshot)


class LeagueHubBrowserTests(unittest.TestCase):
    def test_tables_and_selected_matchup_scores_through_normal_routes(self):
        import dtos_app

        ten, ten_reader = league_fixture()
        twelve, twelve_reader = league_fixture(12, 4, divisions=2, live=True)
        first, first_reader = league_fixture(10, None, completed=1)
        state = dict(data=ten, reader=ten_reader)
        membership = SimpleNamespace(league_id="fixture-10", roster_id=1, franchise_name="Franchise 1",
                                     league_name="A Long League Name for Phone Layout")
        account = SimpleNamespace(membership=membership, display_name="Manager",
                                  account_id="disposable", csrf_token="fixture-only")
        navigation = {"scope": "a" * 64, "team": "/teams/1"}
        app = FastAPI()

        async def fresh():
            pass

        @app.get("/api/account/navigation-context")
        def navigation_context():
            return navigation

        shared = dict(ensure_fresh=fresh, require_data=lambda: state["data"], page=dtos_app.page)
        app.include_router(create_home_router(**shared))
        app.include_router(create_matchups_router(**shared))
        app.mount("/static", StaticFiles(directory="static"), name="static")
        client = TestClient(app)
        path = os.environ.get("DTOS_LEAGUE_HUB_EVIDENCE")
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)

        def context():
            data = state["data"]
            return SimpleNamespace(league_id=data["league"]["league_id"], state={"data": data}, projection=state["reader"])

        def transport(route):
            url = urlsplit(route.request.url)
            if url.hostname != "dtos.test":
                return route.abort()
            response = client.get(url.path + ("?" + url.query if url.query else ""))
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)

        with (
            patch("routes.home.current_account", return_value=account),
            patch("routes.matchups.current_account", return_value=account),
            patch("src.ui.badges.current_account", return_value=account),
            patch("dtos_app.current_account", return_value=account),
            patch.object(dtos_app.account_store, "memberships", return_value=[]),
            patch("dtos_app.current_league_context", side_effect=context),
            patch("routes.home.current_league_context", side_effect=context),
            patch("routes.matchups.current_league_context", side_effect=context),
            patch("services.contextual_navigation.navigation_context", return_value=navigation),
            patch("services.sleeper.sleeper_get", side_effect=AssertionError("Provider read on navigation")),
            sync_playwright() as engine,
        ):
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in ((320, 432), (390, 844), (1280, 900)):
                    with self.subTest(width=width), browser.new_context(
                            viewport={"width": width, "height": height}, has_touch=width < 600) as chromium:
                        chromium.route("**/*", transport)
                        page = chromium.new_page()
                        state.update(data=ten, reader=ten_reader)
                        membership.league_id = "fixture-10"
                        navigation["scope"] = "a" * 64
                        page.goto("https://dtos.test/league")
                        table = page.locator(".league-standings-table")
                        rows = table.locator("tr[data-roster-id]")
                        self.assertEqual(rows.count(), 10)
                        self.assertEqual(rows.evaluate_all("rows=>rows.map(r=>Number(r.dataset.rosterId))"), list(range(1, 11)))
                        self.assertEqual(table.locator(".standings-you").get_attribute("data-roster-id"), "1")
                        self.assertEqual(table.locator(".league-cutoff").evaluate("r=>r.previousElementSibling.dataset.rosterId"), "6")
                        self.assertEqual(rows.first.locator('[aria-label="Rank unchanged"]').inner_text(), "0")
                        self.assertTrue(table.get_by_label("Rank up 4").count())
                        self.assertTrue(table.get_by_label("Rank down 1").count())
                        self.assertIn("W1", table.inner_text())
                        self.assertIn("L1", table.inner_text())
                        self.assertIn("Through completed Week 2", page.locator(".league-reporting-week").inner_text())
                        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                        overflows = table.locator("td, th").evaluate_all(
                            "cells=>cells.filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)")
                        self.assertEqual(overflows, [])
                        self.assertIn("Projected points", page.locator(".league-matchup-preview").inner_text())
                        self.assertIn("0.00", page.locator(".league-matchup-preview").inner_text())
                        self.assertIn("57.25", page.locator(".league-matchup-preview").inner_text())
                        self.assertEqual(page.get_by_role("link", name="All matchups").get_attribute("href"), "/matchups?week=3")
                        if path:
                            page.screenshot(path=str(Path(path, f"league-{width}.png")), full_page=True)
                        previous = page.get_by_role("link", name="Previous matchup week, Week 2")
                        previous.focus()
                        previous.press("Enter")
                        expect(page.locator(".league-matchup-preview")).to_contain_text("Final score")
                        expect(page.locator(".league-reporting-week")).to_contain_text("Through completed Week 2")
                        game = page.get_by_role("link", name="View matchup")
                        if width < 600:
                            game.tap()
                        else:
                            game.click()
                        page.wait_for_url("**/matchups/1?week=2")
                        page.locator("#dtos-back").click()
                        page.wait_for_url("**/league?week=2")
                        expect(page.locator(".league-matchup-preview")).to_contain_text("Final score")
                        self.assertEqual(page.get_by_role("link", name="Week 2 recap").get_attribute("href"), "/reports/weekly?week=2")

                        state.update(data=twelve, reader=twelve_reader)
                        membership.league_id = "fixture-12"
                        navigation["scope"] = "b" * 64
                        page.goto("https://dtos.test/league")
                        self.assertEqual(rows.count(), 12)
                        self.assertEqual(table.locator(".league-cutoff").evaluate("r=>r.previousElementSibling.dataset.rosterId"), "4")
                        self.assertIn("Number of spots only", table.inner_text())
                        self.assertIn("Current playoff position", rows.nth(8).inner_text())
                        self.assertEqual(page.get_by_role("link", name="View playoff race").get_attribute("href"), "/teams/1#season-so-far")
                        self.assertIn("Live score", page.locator(".league-matchup-preview").inner_text())
                        self.assertIn("15", page.locator(".league-matchup-preview").inner_text())

                        state.update(data=first, reader=first_reader)
                        membership.league_id = "fixture-10"
                        navigation["scope"] = "a" * 64
                        page.goto("https://dtos.test/league")
                        self.assertEqual(table.locator(".league-cutoff").count(), 0)
                        self.assertEqual(table.get_by_label("Prior-week rank comparison unavailable").count(), 10)
                        self.assertIn("could not be verified", page.locator(".league-standings").inner_text())
                        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
            finally:
                browser.close()

    def test_preview_reuses_supported_scores_without_lineup_analysis(self):
        data, reader = league_fixture()
        full = season_week_view(data, 3, reader)
        with patch("src.core.intelligence.lineup_review.review_lineup", side_effect=AssertionError):
            preview = season_week_view(data, 3, reader, preview_roster_id=1)
        self.assertEqual(list(preview["groups"]), ["1"])
        self.assertEqual(preview["states"]["1"], full["states"]["1"])
        for actual, expected in zip(preview["groups"]["1"], full["groups"]["1"]):
            for field in ("roster_id", "actual", "projection", "supported_slots"):
                self.assertEqual(actual[field], expected[field])
        self.assertEqual(season_week_view(data, 3, reader, preview_roster_id=99)["groups"], {})
