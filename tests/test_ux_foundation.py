"""v1.10.43 manager-experience presentation contracts."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.home import create_home_router
from routes.matchups import _production_ranks
from src.ui import manager_navigation, player_summary


def _data() -> dict:
    return {
        "week": 4,
        "league": {"name": "Blueprint League", "season": "2026"},
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
    def _client(self) -> TestClient:
        app = FastAPI()

        async def fresh() -> None:
            return None

        app.include_router(create_home_router(
            ensure_fresh=fresh,
            require_data=_data,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        return TestClient(app)

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


if __name__ == "__main__":
    unittest.main()
