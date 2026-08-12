from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import APIRouter, FastAPI

from routes.matchups import _starter_projection_html
from src.core.inspection.live import LiveInspection, matchup_semantic, public_surface_registry


PROGRESS = {
    "canonical_history_progress": {
        "status": "completed_with_pending", "completed_steps": 5,
        "total_steps": 6, "configured_seasons": [2021, 2022, 2023, 2024, 2025, 2026],
        "completed_seasons": [2021, 2022, 2023, 2024, 2025],
    }
}


class LiveInspectionTests(unittest.TestCase):
    def test_matchup_starter_card_labels_both_canonical_sources(self):
        html = _starter_projection_html({
            "sleeper_projection": 24.18, "dtos_projection": 25.73,
        })
        self.assertIn("Sleeper Projection", html)
        self.assertIn("24.18", html)
        self.assertIn("DTOS Projection", html)
        self.assertIn("25.73", html)
        self.assertIn("DTOS +1.55", html)
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

    def test_matchup_semantic_preserves_missing_and_reconciles_totals(self):
        data = {"matchups": {"1": [{"roster_id": 1, "team": "Alpha", "owner": "A",
                 "points": 4, "lineup": [{"id": "10", "name": "Josh", "position": "QB",
                 "nfl_team": "BUF", "slot": "QB", "points": 4},
                {"id": "11", "name": "Missing", "position": "RB", "slot": "RB", "points": 0}]},
                {"roster_id": 2, "team": "Beta", "owner": "B", "points": 0, "lineup": []}]}}
        snapshot = {"projection_snapshot_id": "snap", "players": {
            "10": {"sleeper_projection": 24.18, "dtos_projection": 25.73,
                   "projection_snapshot_id": "snap"}}}
        result = matchup_semantic(data, "1", snapshot)
        self.assertEqual(result["teams"][0]["displayed_totals"],
                         result["teams"][0]["canonical_totals"])
        self.assertEqual(result["teams"][0]["coverage"]["sleeper"], "1/2")
        self.assertEqual(result["teams"][0]["starters"][0]["displayed"],
                         result["teams"][0]["starters"][0]["canonical"] |
                         {"actual_points": 4})
        self.assertEqual(result["teams"][0]["starters"][1]["projection_state"], "unavailable")

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
