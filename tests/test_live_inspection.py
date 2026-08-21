from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import APIRouter, FastAPI

from routes.matchups import _starter_projection_html
from src.core.inspection.live import LiveInspection, matchup_semantic, public_surface_registry
from src.core.inspection.live_browser import (
    matchup_projection_mismatches,
    projection_total_mismatches,
)


PROGRESS = {
    "canonical_history_progress": {
        "status": "completed_with_pending", "completed_steps": 5,
        "total_steps": 6, "configured_seasons": [2021, 2022, 2023, 2024, 2025, 2026],
        "completed_seasons": [2021, 2022, 2023, 2024, 2025],
    }
}


class LiveInspectionTests(unittest.TestCase):
    def test_matchup_starter_card_labels_only_canonical_sleeper(self):
        html = _starter_projection_html({
            "canonical_projection": 24.18, "projection_availability": "projected",
        })
        self.assertIn("Sleeper canonical projection", html)
        self.assertIn("24.18", html)
        self.assertNotIn("DTOS Projection", html)
        missing = _starter_projection_html({})
        self.assertIn("Projection unavailable", missing)
        self.assertIn("Technical Details", missing)

    def test_synthetic_future_public_route_registers_automatically(self):
        app = FastAPI()
        router = APIRouter(tags=["future intelligence"])

        @router.get("/future-feature")
        async def future_feature():
            return {"ok": True}

        app.include_router(router)
        surfaces = public_surface_registry(app.routes)
        future = next(row for row in surfaces if row.route == "/future-feature")
        self.assertTrue(future.inspection_enabled)
        self.assertTrue(future.dins_enabled)
        self.assertEqual(future.category, "Future Intelligence")

    def test_removed_route_disappears_and_approved_exclusion_is_explicit(self):
        app = FastAPI()
        surfaces = public_surface_registry(app.routes)
        self.assertNotIn("/removed-feature", {row.route for row in surfaces})

        router = APIRouter()

        @router.get("/robots.txt")
        async def robots(): return ""

        app.include_router(router)
        excluded = next(row for row in public_surface_registry(app.routes)
                        if row.route == "/robots.txt")
        self.assertFalse(excluded.inspection_enabled)
        self.assertEqual(excluded.exclusion_reason, "crawler_control")

    def test_validation_only_routes_are_not_public_visual_surfaces(self):
        app = FastAPI()

        @app.get("/__validation__/fixture-contract")
        async def fixture_contract(): return {"ok": True}

        self.assertNotIn(
            "/__validation__/fixture-contract",
            {row.route for row in public_surface_registry(app.routes)},
        )

    def test_machine_current_visual_routes_are_not_browser_capture_surfaces(self):
        app = FastAPI()

        @app.get("/current-visual")
        async def current_visual(): return {"kind": "current_visual_discovery"}

        @app.get("/current-visual/manifest.json")
        async def current_visual_manifest(): return {"captures": []}

        surfaces = {
            row.route: row for row in public_surface_registry(app.routes)
            if row.route.startswith("/current-visual")
        }
        self.assertEqual(set(surfaces), {
            "/current-visual", "/current-visual/manifest.json",
        })
        for surface in surfaces.values():
            self.assertEqual(surface.surface_type, "api")
            self.assertIsNone(surface.human_url)
            self.assertFalse(surface.dins_enabled)

    def test_matchup_semantic_preserves_missing_and_reconciles_totals(self):
        data = {"matchups": {"1": [{"roster_id": 1, "team": "Alpha", "owner": "A",
                 "points": 4, "lineup": [{"id": "10", "name": "Josh", "position": "QB",
                 "nfl_team": "BUF", "slot": "QB", "points": 4},
                {"id": "11", "name": "Missing", "position": "RB", "slot": "RB", "points": 0}]},
                {"roster_id": 2, "team": "Beta", "owner": "B", "points": 0, "lineup": []}]}}
        snapshot = {"projection_snapshot_id": "snap", "players": {
            "10": {"canonical_projection": 24.18,
                   "projection_snapshot_id": "snap"}}}
        result = matchup_semantic(data, "1", snapshot)
        self.assertEqual(result["teams"][0]["displayed_totals"],
                         result["teams"][0]["canonical_totals"])
        self.assertEqual(result["teams"][0]["coverage"]["canonical"], "1/2")
        self.assertEqual(result["teams"][0]["starters"][0]["displayed"],
                         result["teams"][0]["starters"][0]["canonical"] |
                         {"actual_points": 4})
        self.assertEqual(result["teams"][0]["starters"][1]["projection_state"], "unavailable")
        self.assertIsNone(result["teams"][1]["canonical_totals"]["canonical_projection"])
        self.assertEqual(result["teams"][1]["canonical_totals"]["availability"], "unavailable")

    def test_projection_total_reconciliation_is_availability_aware(self):
        unavailable = {"team_name": "Alpha", "canonical_totals": {
            "canonical_projection": None, "raw_aggregate": 0.0, "availability": "unavailable",
        }}
        available_zero = {"team_name": "Alpha", "canonical_totals": {
            "canonical_projection": 0.0, "raw_aggregate": 0.0, "availability": "available",
        }}
        available_value = {"team_name": "Alpha", "canonical_totals": {
            "canonical_projection": 7.5, "raw_aggregate": 7.5, "availability": "available",
        }}
        self.assertEqual(projection_total_mismatches(unavailable, ["Alpha Pregame projection Projection unavailable"]), [])
        self.assertEqual(projection_total_mismatches(available_zero, ["Alpha Pregame projection 0.0"]), [])
        self.assertEqual(projection_total_mismatches(available_value, ["Alpha Pregame projection 7.5"]), [])
        self.assertIn("missing_projection_total_state_missing", projection_total_mismatches(unavailable, ["Alpha Pregame projection 0.0"]))
        self.assertIn("available_projection_total_rendered_unavailable", projection_total_mismatches(available_zero, ["Alpha Projection unavailable"]))
        self.assertIn("available_projection_total_rendered_unavailable", projection_total_mismatches(available_value, ["Alpha Projection unavailable"]))
        self.assertIn("canonical_projection_total_mismatch", projection_total_mismatches(available_value, ["Alpha Pregame projection 8.5"]))

    def test_starter_reconciliation_distinguishes_unavailable_zero_and_nonzero(self):
        def semantic(value, state):
            return {
                "presentation_state": "pregame",
                "teams": [{
                    "team_name": "Alpha",
                    "starters": [{"player_name": "Josh", "projection_state": state,
                                  "canonical": {"canonical_projection": value}}],
                    "canonical_totals": {
                        "canonical_projection": value,
                        "availability": "unavailable" if value is None else "available",
                    },
                }],
            }

        self.assertEqual(matchup_projection_mismatches(
            semantic(None, "unavailable"), "Alpha Josh Projection unavailable",
            ["Josh Projection unavailable"], ["Alpha Projection unavailable"],
        ), [])
        self.assertEqual(matchup_projection_mismatches(
            semantic(0.0, "projected_zero"), "Alpha Josh Sleeper canonical projection 0.00",
            ["Josh Sleeper canonical projection 0.00"], ["Alpha Pregame projection 0.00"],
        ), [])
        self.assertEqual(matchup_projection_mismatches(
            semantic(7.5, "available"), "Alpha Josh Sleeper canonical projection 7.50",
            ["Josh Sleeper canonical projection 7.50"], ["Alpha Pregame projection 7.50"],
        ), [])
        self.assertIn("missing_projection_state_missing", matchup_projection_mismatches(
            semantic(None, "unavailable"), "Alpha Josh Sleeper canonical projection 0.00",
            ["Josh Sleeper canonical projection 0.00"], ["Alpha Pregame projection 0.00"],
        ))
        self.assertIn("canonical_projection_mismatch", matchup_projection_mismatches(
            semantic(0.0, "projected_zero"), "Alpha Josh Projection unavailable",
            ["Josh Projection unavailable"], ["Alpha Projection unavailable"],
        ))
        self.assertIn("canonical_projection_mismatch", matchup_projection_mismatches(
            semantic(7.5, "available"), "Alpha Josh Sleeper canonical projection 8.50",
            ["Josh Sleeper canonical projection 8.50"], ["Alpha Pregame projection 8.50"],
        ))
        in_game_unavailable = semantic(None, "unavailable")
        in_game_unavailable["presentation_state"] = "in-game"
        self.assertIn("missing_projection_state_missing", matchup_projection_mismatches(
            in_game_unavailable, "Alpha Josh Actual 4.00",
            ["Josh Actual 4.00"], ["Alpha Actual 4.00"],
        ))

    def test_matchup_semantic_preserves_available_zero_total(self):
        data = {"matchups": {"1": [{
            "roster_id": 1, "team": "Alpha", "owner": "A", "points": 0,
            "lineup": [{"id": "10", "name": "Josh", "position": "QB", "points": 0}],
        }]}}
        snapshot = {"players": {"10": {"canonical_projection": 0.0}}}
        team = matchup_semantic(data, "1", snapshot)["teams"][0]
        self.assertEqual(team["canonical_totals"]["canonical_projection"], 0.0)
        self.assertEqual(team["canonical_totals"]["availability"], "available")

    def test_live_matchup_reconciles_unavailable_projection_at_aggregate_boundary(self):
        semantic = {
            "presentation_state": "in-game",
            "teams": [{
                "team_name": "Alpha",
                "starters": [{"player_name": "Josh", "canonical": {
                    "canonical_projection": None,
                }}],
                "canonical_totals": {
                    "canonical_projection": None,
                    "availability": "unavailable",
                },
            }],
        }
        visible = "Alpha Josh ACTUAL 4.0 Projection unavailable Pregame projections unavailable"
        self.assertEqual(matchup_projection_mismatches(
            semantic, visible, ["Josh ACTUAL 4.0 Projection unavailable"],
            ["Alpha ACTUAL 4.0 Projection unavailable"],
        ), [])
        self.assertIn("aggregate_projection_unavailable_state_missing", matchup_projection_mismatches(
            semantic, "Alpha Josh ACTUAL 4.0", ["Josh ACTUAL 4.0"], ["Alpha ACTUAL 4.0"],
        ))

    @patch("src.core.inspection.live.history_progress_contracts", return_value=PROGRESS)
    def test_root_is_bounded_complete_and_dynamic(self, _progress):
        app = FastAPI()

        @app.get("/teams")
        async def teams(): return {}

        data = {"league": {"league_id": "league", "name": "League"},
                "teams": [{"roster_id": 1}], "matchups": {"1": []},
                "players": {"10": {}}, "pick_ledger": [{}]}
        inspector = LiveInspection(state={"data": data}, routes=app.routes,
                                   league_id="league", projection_snapshot=None,
                                   market=None, fois_scores=())
        root = inspector.root()
        self.assertEqual(root["status"], "complete")
        self.assertEqual(root["counts"]["teams"], 1)
        self.assertEqual(root["side_effect_contract"]["market_constructions"], 0)
        self.assertNotIn("players", root)


if __name__ == "__main__":
    unittest.main()
