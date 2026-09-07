"""Real orchestration regressions for a single generation-bound team assessment."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.teams import create_teams_router

from services.team_headquarters import build_team_headquarters
from src.core.intelligence.cache import IntelligenceCache
from src.core.intelligence.context import build_context
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from src.core.intelligence.team_assessment import build_team_assessment
from tests.test_trade_intelligence import fixture_data


class CanonicalTeamAssessmentTests(TestCase):
    def setUp(self):
        self.data = fixture_data()
        self.data["week"] = 0  # NFL preseason state; published forecast is week 1.
        for team in self.data["teams"]:
            team.update(wins=0, losses=0, ties=0, points_for=0, max_points=0)
        self.snapshot = {
            "league_id": "league-1", "week": 1,
            "projection_snapshot_id": "projection-A", "generated_at": "2026-09-01T00:00:00Z",
            "players": {p["id"]: {"week": 1, "weekly_projected_points": 20,
                "weekly_floor": 12, "weekly_ceiling": 28}
                for team in self.data["teams"] for p in team["players"]},
        }
        self.snapshot_patch = patch("src.core.projection_intelligence.projection_service.snapshot", side_effect=lambda: self.snapshot)
        self.snapshot_patch.start()
        self.addCleanup(self.snapshot_patch.stop)
        self.engine = IntelligenceOrchestrator(cache=IntelligenceCache())

    def test_preseason_assessment_uses_one_window_and_real_projection_week(self):
        result = self.engine.analyze(self.data, 1)
        a = result.team_assessment
        self.assertIs(a.team, result.roster.team_intelligence[1])
        self.assertIs(a, result.roster.assessment)
        self.assertEqual(result.roster.identity, a.team.competitive_window.classification.value)
        self.assertEqual(result.roster.metrics["Weekly Floor"], a.weekly_floor)
        self.assertEqual(a.team.competitive_window, result.recommendation.competitive_window)
        self.assertTrue(result.recommendation.current_outlook.startswith(a.team.current_contending.grade + " ("))
        self.assertEqual(a.projected_points, 100)
        self.assertEqual(a.weekly_floor, 60)
        self.assertEqual(a.weekly_ceiling, 140)
        self.assertEqual(a.projection_week, 1)
        self.assertEqual(result.player_values[next(iter(result.player_values))].projection.projected_points, 20)

    def test_publication_invalidates_without_data_object_change(self):
        before = self.engine.analyze(self.data, 1).team_assessment
        self.snapshot = deepcopy(self.snapshot)
        self.snapshot["projection_snapshot_id"] = "projection-B"
        for row in self.snapshot["players"].values():
            row["weekly_projected_points"] = 21
        after = self.engine.analyze(self.data, 1).team_assessment
        self.assertNotEqual(before.generation, after.generation)
        self.assertEqual(before.projected_points, 100)
        self.assertEqual(after.projected_points, 105)

    def test_missing_bounds_are_not_zero_and_real_zero_is_preserved(self):
        for row in self.snapshot["players"].values():
            row.update(weekly_projected_points=0, weekly_floor=None, weekly_ceiling=None)
        a = self.engine.analyze(self.data, 1).team_assessment
        self.assertEqual(a.projected_points, 0)
        self.assertIsNone(a.weekly_floor)
        self.assertIsNone(a.weekly_ceiling)
        self.assertTrue(any("bounds are unavailable" in s for s in a.limitations))

    def test_switch_return_and_foreign_projection_fail_closed(self):
        before = self.engine.analyze(self.data, 1).team_assessment
        foreign = deepcopy(self.data)
        foreign["league"]["league_id"] = "league-2"
        other = self.engine.analyze(foreign, 1).team_assessment
        after = self.engine.analyze(self.data, 1).team_assessment
        self.assertEqual(before, after)
        self.assertNotEqual(before.generation, other.generation)
        self.assertIsNone(other.projected_points)
        self.assertEqual(other.league_id, "league-2")

    def test_brain_publication_invalidates_same_data(self):
        before = build_context(self.data, 1).snapshot_key
        self.data["valuation_intelligence"] = {"semantic_generation": "next"}
        self.assertNotEqual(before, build_context(self.data, 1).snapshot_key)

    def test_evidence_generation_is_not_python_object_identity(self):
        self.assertEqual(build_context(self.data, 1).evidence_generation, build_context(deepcopy(self.data), 1).evidence_generation)

    def test_inflight_context_keeps_its_snapshot(self):
        context = build_context(self.data, 1)
        team = self.engine.analyze(self.data, 1).team_assessment.team
        self.snapshot = deepcopy(self.snapshot)
        self.snapshot["players"] = {}
        a = build_team_assessment(context, team)
        self.assertEqual(a.projected_points, 100)

    def test_headquarters_exposes_shared_assessment(self):
        with patch("services.team_headquarters.intelligence_orchestrator", self.engine):
            view = build_team_headquarters(self.data, 1)
        self.assertIs(view["assessment"].team, view["team_intelligence"])
        self.assertEqual(view["unified_recommendation"].current_outlook, view["assessment"].current_outlook)
        self.assertEqual(view["unified_recommendation"].why[0], view["assessment"].team.explanation[0])
        self.assertNotIn("35% current-outlook weight.", view["unified_recommendation"].why)

    def test_rendered_team_hq_uses_canonical_bounds_and_explicit_diagnostics(self):
        async def noop():
            pass

        app = FastAPI()
        app.include_router(create_teams_router(ensure_fresh=noop, require_data=lambda: self.data,
            state={}, page=lambda title, body: HTMLResponse(body)))
        from tests.test_team_headquarters import TeamHeadquartersRequestSchedulingTests
        with patch("services.team_headquarters.intelligence_orchestrator", self.engine), patch(
            "routes.teams.historical_graph", side_effect=TeamHeadquartersRequestSchedulingTests._history_graph,
        ), TestClient(app) as client:
            response = client.get("/teams/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Weekly Ceiling (points)</span><b>140.0", response.text)
        self.assertIn("Weekly Floor (points)</span><b>60.0", response.text)
        self.assertNotIn("Weekly Ceiling</span><b>0/100", response.text)
        self.assertIn("Legacy diagnostic:", response.text)
        self.assertIn("Not the current team assessment", response.text)
