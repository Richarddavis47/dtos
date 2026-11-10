"""Source-qualified need handoff; no new projections, prices or need rules."""

import copy
from datetime import datetime, timedelta, timezone
from html import unescape
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.team_trade_need import prepared_need, requested_position, position_matches
from src.core.intelligence.roster_diagnostics import (
    diagnose_league,
    prepared_diagnostics,
)
from tests import test_roster_diagnostic_http as http


class TeamTradeNeedTests(unittest.TestCase):
    def fixture(self):
        f = http.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.data = f.f.f.data
        # Actual source fixtures, both franchises' statuses and source clocks.
        for team in self.data["teams"]:
            for player in team["players"]:
                player["status"] = "Active"
                self.data["players"][player["id"]]["status"] = "Active"
        f.publish(datetime.now(timezone.utc).isoformat())
        self.snapshot = f.f.source.reader.snapshot()
        diagnose_league(self.data, self.snapshot)
        return f

    def test_rendered_current_need_and_destination_recheck(self):
        f = self.fixture()
        # Swap source projections to give the authorized franchise a supported
        # starter need. All point values remain native fixture Sleeper records.
        f.f.source.points = {k: 40 - v for k, v in f.f.source.points.items()}
        f.publish(datetime.now(timezone.utc).isoformat())
        diagnose_league(self.data, f.f.source.reader.snapshot())
        response = f.f.f.client.get("/teams/1")
        self.assertEqual(response.status_code, 200)
        match = re.search(r'id="my-team-trade-need"[^>]*href="([^"]+)"', response.text)
        self.assertIsNotNone(
            match, response.text[response.text.index("my-team-outlook") :][:5000]
        )
        href = unescape(match[1])
        self.assertIn("Explore QB trades", response.text)
        result = f.f.f.client.get(href)
        self.assertEqual(result.status_code, 200)
        self.assertIn("&quot;kind&quot;: &quot;starter&quot;", result.text)
        self.assertIn("Incoming player position", result.text)
        self.assertIn("Generate starts the search", result.text)
        # The opaque hint is not authorization or a saved preference.
        for bad in (href[:-1] + ("a" if href[-1] != "a" else "b"),):
            rejected = f.f.f.client.get(bad)
            self.assertIn("No roster-need filter was applied", rejected.text)
            self.assertIn('data-team-need="null"', rejected.text)
        # Requalification at render time, not the saved profile's old label.
        self.data["sync_status"] = {"last_refresh_failed": True}
        f.publish((datetime.now(timezone.utc) - timedelta(hours=8)).isoformat())
        expired = f.f.f.client.get(href)
        self.assertIn("No roster-need filter was applied", expired.text)
        self.assertNotIn('id="my-team-trade-need"', f.f.f.client.get("/teams/1").text)

    def test_need_requires_current_own_matching_prepared_evidence(self):
        self.fixture()
        diagnostic = prepared_diagnostics(self.data, self.snapshot)
        row = diagnostic["teams"]["1"]
        # Selection controls only: force a canonical flag in a copied diagnostic
        # to exercise all negative identity/qualification cases independently.
        for facts in row["positions"].values():
            facts.update(
                starter_need=False, resilience_need=False, quality_depth_need=False
            )
        row["positions"]["QB"].update(starter_need=True, conclusion_state="current")
        row["positions"]["QB"]["evidence"]["calculation_supported"] = True
        account = SimpleNamespace(
            account_id="test",
            session_id="test",
            membership=SimpleNamespace(league_id="league-1", roster_id=1),
        )
        with patch("services.team_trade_need.current_account", return_value=account):
            value = prepared_need(self.data, 1, diagnostic)
            self.assertEqual(value["kind"], "starter")
            for change in (
                "week",
                "league",
                "generation",
                "provisional",
                "missing",
                "franchise",
            ):
                altered = copy.deepcopy(diagnostic)
                if change == "week":
                    altered["week"] += 1
                if change == "league":
                    altered["league_id"] = "other"
                if change == "generation":
                    altered["projection_generation"] = None
                if change == "provisional":
                    altered["teams"]["1"]["positions"]["QB"]["conclusion_state"] = (
                        "provisional"
                    )
                with self.subTest(change=change):
                    self.assertIsNone(
                        prepared_need(
                            self.data,
                            2 if change == "franchise" else 1,
                            None if change == "missing" else altered,
                        )
                    )
            row["positions"]["QB"].update(starter_need=False, resilience_need=True)
            depth = prepared_need(self.data, 1, diagnostic)
            self.assertEqual(depth["kind"], "depth")
            self.assertIn("not a starter-upgrade verdict", depth["reason"])

    def test_league_positions_and_incoming_filter_are_request_only(self):
        self.fixture()
        for slots in (
            ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF", "BN"],
            ["QB", "SUPER_FLEX", "FLEX", "BN"],
        ):
            data = {**self.data, "roster_positions": slots}
            self.assertEqual(requested_position(data, "RB"), "RB")
            self.assertIsNone(requested_position(data, None))
            for invalid in ("K", "DEF", "FLEX", "SUPER_FLEX", "qb", {}, ["RB"]):
                with self.assertRaises(ValueError):
                    requested_position(data, invalid)
        data = {**self.data, "roster_positions": ["QB", "BN"]}
        with self.assertRaises(ValueError):
            requested_position(data, "RB")
        assets = {
            "player:a": SimpleNamespace(kind="player", position="RB"),
            "pick:exact": SimpleNamespace(kind="pick", position=None),
        }
        row = {"proposal": {"assets_received": ["pick:exact", "player:a"]}}
        self.assertTrue(position_matches(row, assets, "RB"))
        self.assertFalse(position_matches(row, assets, "QB"))
        self.assertTrue(position_matches(row, assets, None))

    def test_prepared_reader_never_prepares_on_miss(self):
        self.fixture()
        with patch(
            "src.core.intelligence.roster_diagnostics._compute",
            side_effect=AssertionError("new diagnostic on read"),
        ):
            changed = copy.deepcopy(self.data)
            changed["league"]["league_id"] = "other"
            self.assertIsNone(prepared_diagnostics(changed, self.snapshot))
            self.assertIsNone(prepared_need(changed, 1, None))

    def test_failed_refresh_and_different_account_do_not_reuse_need(self):
        f = self.fixture()
        f.f.source.points = {k: 40 - v for k, v in f.f.source.points.items()}
        f.publish(datetime.now(timezone.utc).isoformat())
        diagnose_league(self.data, f.f.source.reader.snapshot())
        page = f.f.f.client.get("/teams/1")
        href = unescape(
            re.search(r'id="my-team-trade-need"[^>]*href="([^"]+)"', page.text)[1]
        )
        with patch.object(
            f.f.source.reader,
            "refresh_evidence",
            return_value={"retained_publication": True},
        ):
            self.assertNotIn(
                'id="my-team-trade-need"', f.f.f.client.get("/teams/1").text
            )
            self.assertIn(
                "No roster-need filter was applied", f.f.f.client.get(href).text
            )
        # Authentication still gates the normal page, including the hint.
        original = f.f.f.client.cookies.get("dtos_session")
        f.f.f.client.cookies.clear()
        response = f.f.f.client.get(href, follow_redirects=False)
        self.assertIn(response.status_code, (303, 307))
        f.f.f.client.cookies.set("dtos_session", original)

    def test_real_recommended_position_filter_preserves_bilateral_verdicts(self):
        from tests import test_home_opportunity_integrity as fixtures
        from services.trade_intelligence import (
            generate_trade_workflow,
            build_trade_workspace,
        )

        f = fixtures.OpportunityIntegrityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.f.data
        before = copy.deepcopy(data)
        payload = {
            "workflow": "recommended",
            "active_roster_id": 1,
            "strategy": "REBUILD",
        }
        original = generate_trade_workflow(data, payload)
        filtered = generate_trade_workflow(
            data, {**payload, "recommendation_position": "QB"}
        )
        self.assertGreater(original["search_evidence"]["full_evaluations"], 0)
        self.assertGreater(len(original["results"]), 0)
        assets = {
            a.asset_id: a
            for pool in build_trade_workspace(data, 1)["pools"].values()
            for a in pool
        }
        original_rows = {
            str(row["proposal"]): row["evaluation"]["recommendation"]
            for row in original["results"]
        }
        for row in (
            filtered["results"]
            + filtered["exploratory_results"]
            + filtered["near_misses"]
        ):
            self.assertTrue(position_matches(row, assets, "QB"))
            if str(row["proposal"]) in original_rows:
                self.assertEqual(
                    row["evaluation"]["recommendation"],
                    original_rows[str(row["proposal"])],
                )
        self.assertLessEqual(filtered["search_evidence"]["full_evaluations"], 180)
        self.assertEqual(filtered["recommendation_position"], "QB")
        self.assertEqual(data, before)
