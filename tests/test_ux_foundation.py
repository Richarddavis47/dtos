"""Manager-experience presentation contracts."""
from __future__ import annotations

import unittest
from time import perf_counter
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.home import create_home_router, home_body_render_cache
from routes.matchups import (
    _game_state,
    _production_ranks,
    _team_score_html,
    _team_projection_value,
    create_matchups_router,
)
from src.ui import manager_navigation, player_summary
from src.ui.intelligence_presentation import (
    league_is_preseason,
    matchup_score_hierarchy,
    numeric_evidence,
    projection_presentation_value,
    record_evidence,
)


def _data(*, preseason: bool = False) -> dict:
    return {
        "week": 4,
        "preseason": preseason,
        "league": {
            "league_id": "league", "name": "Blueprint League", "season": "2026",
        },
        "teams": [
            {
                "roster_id": 1, "team_name": "North Stars", "owner": "Alex",
                "wins": 3, "losses": 1, "ties": 0, "points_for": 500,
                "players": [{"id": "10213", "name": "Example Player"}],
                "picks_owned": [{"season": "2027", "round": 1}],
            },
            {
                "roster_id": 2, "team_name": "South Stars", "owner": "Blair",
                "wins": 2, "losses": 2, "ties": 0, "points_for": 450,
                "players": [], "picks_owned": [],
            },
        ],
        "matchups": {
            "1": [
                {"team": "North Stars", "lineup": [{"id": "p1", "position": "WR", "points": 20}]},
                {"team": "South Stars", "lineup": [{"id": "p2", "position": "WR", "points": 10}]},
            ]
        },
        "transactions": [],
    }


class UXFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        home_body_render_cache.__init__(
            "manager_home_body", max_entries=24, max_bytes=2_097_152,
        )

    def _client(self, data: dict | None = None) -> TestClient:
        app = FastAPI()

        async def fresh() -> None:
            return None

        app.include_router(create_home_router(
            ensure_fresh=fresh,
            require_data=lambda: data or _data(),
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        return TestClient(app)

    def test_home_reuses_exact_generation_during_visual_capture_activity(self) -> None:
        data = _data()
        generation = ["generation-one"]
        app = FastAPI()

        async def fresh() -> None:
            return None

        app.include_router(create_home_router(
            ensure_fresh=fresh,
            require_data=lambda: data,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
            generation_provider=lambda: generation[0],
        ))
        client = TestClient(app)
        with patch(
            "routes.home.build_team_directory",
            return_value={1: {"rank": 1}, 2: {"rank": 2}},
        ) as build:
            first = client.get("/?front_office=1")
            repeated = [client.get("/?front_office=1") for _ in range(10)]
            generation[0] = "generation-two"
            changed = client.get("/?front_office=1")
        self.assertEqual(first.status_code, 200)
        self.assertTrue(all(response.content == first.content for response in repeated))
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(build.call_count, 2)
        health = home_body_render_cache.health()
        self.assertEqual(health["manager_home_body_render_cache_hits"], 10)
        self.assertEqual(health["manager_home_body_render_cache_misses"], 2)

    def test_warm_home_stays_bounded_during_background_capture(self) -> None:
        data = _data()
        app = FastAPI()

        async def fresh() -> None:
            return None

        app.include_router(create_home_router(
            ensure_fresh=fresh,
            require_data=lambda: data,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
            generation_provider=lambda: "capture-generation",
        ))
        client = TestClient(app)
        with patch(
            "routes.home.build_team_directory",
            return_value={1: {"rank": 1}, 2: {"rank": 2}},
        ) as build:
            expected = client.get("/?front_office=1").content
            samples = []
            for _ in range(10):
                started = perf_counter()
                response = client.get("/?front_office=1")
                samples.append((perf_counter() - started) * 1000)
                self.assertEqual(response.content, expected)
        self.assertEqual(build.call_count, 1)
        self.assertLess(max(samples), 500)

    def test_primary_navigation_has_exactly_five_manager_destinations(self) -> None:
        html = manager_navigation("Home")
        primary = html.split("</nav>", 1)[0]
        self.assertEqual(primary.count("<a "), 5)
        for label in ("Home", "My Team", "Trade", "League", "Market"):
            self.assertIn(f">{label}</a>", primary)
        self.assertIn('aria-current="page">Home</a>', primary)
        self.assertIn("More league tools", html)
        self.assertNotIn(">FOIS</a>", primary)

    def test_home_uses_manager_briefing_hierarchy(self) -> None:
        with patch("routes.home.build_team_directory", return_value={
            1: {"rank": 1}, 2: {"rank": 2},
        }):
            html = self._client().get("/?front_office=1").text
        headings = (
            "Weekly Recap", "What Should I Do?", "Rankings", "This Week",
            "Market Movers", "League Activity", "My Assets",
        )
        positions = [html.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("North Stars", html)
        self.assertIn("Current-season standings and FOIS remain distinct", html)
        self.assertNotIn("system health", html.casefold())

    def test_league_hub_keeps_fois_and_current_rankings_distinct(self) -> None:
        html = self._client().get("/league").text
        self.assertIn("Current Rankings", html)
        self.assertIn("Current-season results—not FOIS", html)
        self.assertIn("General-manager performance and confidence", html)
        self.assertIn("League Intelligence", html)

    def test_production_rank_is_derived_from_cached_actual_points(self) -> None:
        ranks = _production_ranks(_data())
        self.assertEqual(ranks, {"p1": "WR #1", "p2": "WR #2"})

    def test_player_summary_uses_provider_headshot_and_safe_fallback(self) -> None:
        html = player_summary(
            player_id="10213", name="Example Player", position="WR",
            nfl_team="BUF", context="WR #3",
        )
        self.assertIn("sleepercdn.com/content/nfl/players/10213.jpg", html)
        self.assertIn('alt="Example Player headshot"', html)
        self.assertIn("player-headshot-fallback", html)
        self.assertIn("WR · BUF · WR #3", html)

    def test_missing_numeric_evidence_is_not_zero(self) -> None:
        self.assertEqual(numeric_evidence(None), "Not yet available")
        self.assertEqual(numeric_evidence(0), "0")
        self.assertEqual(record_evidence(0, 0, 0, season_started=False), "Regular-season record not started")
        self.assertEqual(record_evidence(0, 0, 0, season_started=True), "0-0-0")

    def test_preseason_home_uses_honest_compact_states(self) -> None:
        data = _data(preseason=True)
        with patch("routes.home.build_team_directory", return_value={1: {"rank": 1}, 2: {"rank": 2}}):
            html = self._client(data).get("/?front_office=1").text
        self.assertIn("Preseason Briefing", html)
        self.assertIn("Preseason team outlook and FOIS remain distinct", html)
        self.assertNotIn("0-0-0", html)
        self.assertNotIn("0.00", html)
        self.assertNotIn("completed-week", html)

    def test_preseason_is_inferred_from_week_one_without_results(self) -> None:
        data = _data(preseason=False)
        data.pop("preseason")
        data["week"] = 1
        for team in data["teams"]:
            team.update(wins=0, losses=0, ties=0, points_for=0)
        for sides in data["matchups"].values():
            for side in sides:
                for player in side["lineup"]:
                    player["points"] = 0
        self.assertTrue(league_is_preseason(data))
        with patch("routes.home.build_team_directory", return_value={1: {"rank": 1}, 2: {"rank": 2}}):
            html = self._client(data).get("/?front_office=1").text
        self.assertIn("Preseason Briefing", html)
        self.assertNotIn("0-0-0", html)

    def test_legitimate_week_one_result_is_not_preseason(self) -> None:
        data = _data(preseason=False)
        data.pop("preseason")
        data["teams"][0]["wins"] = 1
        data["teams"][0]["points_for"] = 101.5
        self.assertFalse(league_is_preseason(data))

    def test_preseason_league_does_not_render_fake_current_results(self) -> None:
        data = _data(preseason=True)
        with patch("routes.home.build_team_directory", return_value={1: {"rank": 1}, 2: {"rank": 2}}):
            html = self._client(data).get("/league").text
        self.assertIn("Preseason League Briefing", html)
        self.assertIn("Preseason Rankings", html)
        self.assertNotIn("0-0-0", html)
        self.assertNotIn("0.00", html)

    def test_pregame_matchup_makes_projection_primary(self) -> None:
        rows = matchup_score_hierarchy(actual=0, pregame=168.4, state="pregame")
        self.assertEqual(rows, (("Pregame projection", "168.4"),))
        html = _team_score_html(actual=0, projected=168.4, state="pregame")
        self.assertIn("Pregame projection", html)
        self.assertIn("168.40", html)
        self.assertNotIn("Actual", html)
        self.assertNotIn("0.00", html)
        self.assertEqual(matchup_score_hierarchy(actual=0, pregame=0, state="pregame"), (("Pregame projection", "0"),))
        self.assertIn("Pregame projection</small><b>0.00", _team_score_html(actual=0, projected=0, state="pregame"))
        self.assertIsNone(projection_presentation_value(0.0, "0/11"))
        self.assertEqual(projection_presentation_value(0.0, "1/11"), 0.0)
        self.assertIsNone(_team_projection_value({"canonical_projection_total": 0.0, "canonical_projection_coverage": "0/11"}))
        self.assertEqual(_team_projection_value({"canonical_projection_total": 0.0, "canonical_projection_coverage": "1/11"}), 0.0)

    def test_matchup_score_hierarchy_changes_with_game_state(self) -> None:
        live = matchup_score_hierarchy(actual=42.5, pregame=38.2, state="in-game", live_projected_final=55.1)
        self.assertEqual([label for label, _ in live], ["Actual", "Live projected final", "Pregame projection"])
        final = matchup_score_hierarchy(actual=61.7, pregame=38.2, state="final", live_projected_final=65.0)
        self.assertEqual([label for label, _ in final], ["Final actual", "Pregame projection"])

    def test_matchup_score_hierarchy_preserves_projection_availability_by_game_state(self) -> None:
        live_missing = matchup_score_hierarchy(
            actual=42.5, pregame=None, state="in-game", live_projected_final=None,
        )
        self.assertEqual(live_missing, (
            ("Actual", "42.5"),
            ("Pregame projection", "Projection unavailable"),
        ))
        live_available = matchup_score_hierarchy(
            actual=42.5, pregame=38.2, state="in-game", live_projected_final=55.1,
        )
        self.assertEqual([label for label, _ in live_available], [
            "Actual", "Live projected final", "Pregame projection",
        ])
        final_missing = matchup_score_hierarchy(
            actual=61.7, pregame=None, state="final",
        )
        self.assertEqual(final_missing, (
            ("Final actual", "61.7"),
            ("Pregame projection", "Projection unavailable"),
        ))

    def test_preseason_production_rank_does_not_rank_tied_zeroes(self) -> None:
        data = _data(preseason=True)
        self.assertEqual(_production_ranks(data), {})
        self.assertEqual(_game_state(data, list(data["matchups"]["1"])), "pregame")

    def test_pregame_matchup_routes_do_not_headline_actual_zeroes(self) -> None:
        data = {
            "week": 1,
            "preseason": True,
            "matchups": {
                "1": [
                    {
                        "roster_id": 1, "team": "North", "owner": "Alex",
                        "record": "0-0-0", "points": 0.0,
                        "lineup": [{"id": "p1", "name": "Alpha Runner", "position": "RB", "nfl_team": "BUF", "slot": "RB", "points": 0.0}],
                        "bench": [],
                    },
                    {
                        "roster_id": 2, "team": "South", "owner": "Blair",
                        "record": "0-0-0", "points": 0.0,
                        "lineup": [{"id": "p2", "name": "Beta Runner", "position": "RB", "nfl_team": "MIA", "slot": "RB", "points": 0.0}],
                        "bench": [],
                    },
                ],
            },
        }
        projection = {
            "status": "North favored",
            "largest_advantage": "North at RB",
            "highest_volatility": "No material volatility",
            "confidence": "moderate",
            "missing": 0,
            "sides": [
                {"roster_id": 1, "projected": 168.4, "floor": 150.0, "ceiling": 185.0, "sleeper_total": 168.4, "sleeper_coverage": "1/1", "sleeper_status": "available", "players": [{"player_id": "p1", "canonical_projection": 18.2}]},
                {"roster_id": 2, "projected": 157.2, "floor": 140.0, "ceiling": 174.0, "sleeper_total": 157.2, "sleeper_coverage": "1/1", "sleeper_status": "available", "players": [{"player_id": "p2", "canonical_projection": 16.5}]},
            ],
        }
        app = FastAPI()

        async def fresh() -> None:
            return None

        app.include_router(create_matchups_router(
            ensure_fresh=fresh,
            require_data=lambda: data,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        with (
            patch("routes.matchups.matchup_player_values", return_value={}),
            patch("routes.matchups.matchup_projection", return_value=projection),
        ):
            client = TestClient(app)
            directory = client.get("/matchups").text
            detail = client.get("/matchups/1").text
        self.assertIn("Pregame projection", directory)
        self.assertIn("Pregame projection", detail)
        self.assertNotIn("scoreboard-score", detail)
        self.assertNotIn("<small>Actual</small>", detail)
        self.assertNotIn("<small>Actual</small><b>0.00", directory)
        self.assertNotIn("<small>Actual</small><b>0.00", detail)
        self.assertNotIn("0-0-0", directory)
        self.assertNotIn("0-0-0", detail)
        self.assertNotIn("Market", detail)


if __name__ == "__main__":
    unittest.main()
