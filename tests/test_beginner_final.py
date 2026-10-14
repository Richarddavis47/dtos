"""Final beginner corrections through released HTTP and canonical boundaries."""

import unittest
from html import unescape
from urllib.parse import urlencode
from unittest.mock import AsyncMock, patch

from components.commissioner import league_intelligence
from routes.home import create_home_router
from routes.teams import create_teams_router
from tests import test_beginner_market as market_base
from tests import test_trade_workspace_batch1 as trade_base
from tests import test_historical_tracker_phase2 as history_base
from tests.test_historical_tracker_phase2 import PICK, ROOT, DAY


class FinalMarketTests(unittest.TestCase):
    def setUp(self):
        self.f = market_base.BeginnerMarketTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_settled_market_reads_have_no_durable_growth(self):
        import hashlib
        from pathlib import Path

        paths = [
            "/market?q=2029+Round+2&position=PICK",
            "/api/market/search?q=free+agents+Boston&availability=taxi",
        ]
        for path in paths:
            self.f.get(path)
        root = Path(self.f.fixture.temp.name)

        def snapshot():
            return {
                str(p.relative_to(root)): (
                    p.stat().st_size,
                    hashlib.sha256(p.read_bytes()).hexdigest(),
                )
                for p in root.rglob("*")
                if p.is_file()
            }

        before = snapshot()
        for _ in range(10):
            for path in paths:
                self.f.get(path)
        self.assertTrue(before)
        self.assertEqual(snapshot(), before)

    def test_pick_link_carries_same_market_origin_as_player(self):
        for asset_id in ("pick:2029:2:2", "player:13346"):
            url = "/market?" + urlencode(
                dict(
                    q="2029 Round 2"
                    if asset_id.startswith("pick")
                    else "Denzel Boston",
                    position="PICK" if asset_id.startswith("pick") else "WR",
                    sort="confidence",
                    direction="asc",
                    offset=10,
                    limit=10,
                    selected=asset_id,
                    front_office=1,
                )
            )
            html = unescape(self.f.get(url).text)
            self.assertIn("from_market=", html)
            self.assertIn("market_league=league-1", html)

    def test_text_and_structured_availability_are_intersected(self):
        f = self.f.fixture
        f.data["teams"][0]["players"].append({"id": "44", "roster_slot": "Taxi"})
        f.data["asset_market_semantic_revision"] = "taxi-current-observation"
        taxi = self.f.get("/api/market/search?q=Boston&availability=taxi").json()
        self.assertEqual([r["asset_id"] for r in taxi["results"]], ["player:44"])
        conflict = self.f.get(
            "/api/market/search?"
            + urlencode({"q": "free agents Boston", "availability": "taxi"})
        ).json()
        self.assertEqual(conflict["results"], [])
        self.assertEqual(conflict["total"], 0)
        free = self.f.get("/api/market/search?q=free%20agents%20Boston").json()
        self.assertNotIn("player:44", [r["asset_id"] for r in free["results"]])


class FinalPickOriginTests(unittest.TestCase):
    def setUp(self):
        self.f = history_base.TrackerPhase2Tests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)

    def test_actual_pick_route_honors_market_then_independent_origins(self):
        origin = "/market?" + urlencode(
            dict(
                q="2029 Round 2",
                position="PICK",
                availability="owned_pick",
                sort="confidence",
                direction="asc",
                offset=10,
                limit=10,
                selected="pick:2026:2:7",
                front_office=1,
            )
        )
        url = (
            "/picks/"
            + PICK
            + "?"
            + urlencode(
                dict(
                    from_market=origin,
                    market_league=DAY,
                    front_office=1,
                    from_team=1,
                    from_trade=ROOT,
                )
            )
        )
        r = self.f.client.get(url)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("Back to Market", r.text)
        self.assertNotIn("Back to My Team draft capital", r.text)
        self.assertIn("Consumed by verified draft conversion", r.text)
        self.assertNotIn(">Shop Asset<", r.text)
        for params, label in [
            ({"from_team": 1}, "Back to My Team draft capital"),
            ({"from_trade": ROOT}, "Back to original trade timeline"),
        ]:
            with self.subTest(params=params):
                r = self.f.client.get("/picks/" + PICK + "?" + urlencode(params))
                self.assertEqual(r.status_code, 200)
                self.assertIn(label, r.text)
        invalid = self.f.client.get(
            "/picks/"
            + PICK
            + "?"
            + urlencode(
                {"from_market": "https://evil.example/market", "market_league": DAY}
            )
        )
        self.assertNotIn("Back to Market", invalid.text)
        foreign = self.f.client.get(
            "/picks/"
            + PICK
            + "?"
            + urlencode({"from_market": origin, "market_league": "foreign"})
        )
        self.assertNotIn("Back to Market", foreign.text)


class FinalHomeTests(unittest.TestCase):
    def setUp(self):
        import dtos_app

        self.f = trade_base.AuthenticatedTradeBoundaryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.data["teams"][1]["team_name"] = "Runaway McBride"
        self.f.client.app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.f.data,
                page=dtos_app.page,
            )
        )
        self.f.client.app.include_router(
            create_teams_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.f.data,
                page=dtos_app.page,
                state={"data": self.f.data},
            )
        )
        self.actor_patch = patch.object(dtos_app, "account_store", self.f.store)
        self.actor_patch.start()
        self.addCleanup(self.actor_patch.stop)

    def test_selector_targets_authorized_team_route_not_owned_home(self):
        own = self.f.client.get("/?front_office=2")
        self.assertEqual(own.status_code, 200)
        self.assertIn("Team 1", own.text)
        self.assertNotIn('action="/" class="card"><label for="front-office"', own.text)
        self.assertIn("/teams/", own.text)

    def test_opponent_stays_read_only_and_foreign_or_missing_is_rejected(self):
        r = self.f.client.get("/teams/2")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("Runaway McBride", r.text)
        self.assertNotIn('id="my-team-strategy"', r.text)
        self.assertNotIn("/trades/shop?", r.text)
        self.assertEqual(self.f.client.get("/teams/999").status_code, 404)
        self.assertEqual(
            self.f.client.get("/api/leagues/1319750579458686976/teams").status_code, 403
        )


class FinalCommissionerTests(unittest.TestCase):
    def test_missing_nonfinite_and_zero_supported_values(self):
        keys = (
            "average_roster_age",
            "draft_concentration",
            "average_team_grade",
            "league_strength",
            "league_parity",
            "contenders",
            "rebuilders",
            "strongest_position",
            "weakest_position",
            "championship_favorite",
            "most_draft_capital",
            "least_draft_capital",
            "most_flexible_roster",
            "oldest_team",
            "youngest_team",
            "trending_up",
            "trending_down",
        )
        for missing in (None, float("nan"), "null", "None"):
            data = dict.fromkeys(keys, missing)
            html = league_intelligence({"league_intelligence": data})
            for raw in (">None<", ">null<", ">nan<", "Noneth"):
                self.assertNotIn(raw, html)
            self.assertIn("Unavailable", html)
        supported = dict.fromkeys(keys, None)
        supported.update(average_team_grade=0, contenders=3)
        html = league_intelligence({"league_intelligence": supported})
        self.assertIn("<b>0</b>", html)
        self.assertIn("<b>3</b>", html)
