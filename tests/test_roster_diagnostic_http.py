"""Actual publication, team HTML and bilateral HTTP qualification controls."""

import unittest
from unittest.mock import AsyncMock, patch
from tests import test_home_opportunity_integrity as fixtures
from routes.teams import create_teams_router
from src.core.intelligence.team_strength import prepare_for_data
from src.core.intelligence.roster_diagnostics import team_diagnostics


class DiagnosticHTTPTests(unittest.TestCase):
    def setUp(self):
        import dtos_app

        self.f = fixtures.OpportunityIntegrityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.enterContext(
            patch(
                "src.core.projection_intelligence.projection_service",
                self.f.source.reader,
            )
        )
        self.f.f.client.app.include_router(
            create_teams_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.f.f.data,
                page=dtos_app.page,
                state={"data": self.f.f.data},
            )
        )

    def publish(self, updated=None):
        self.f.source.publish()
        if updated:
            for rows in self.f.source.payloads.values():
                for row in rows:
                    row["updated_at"] = updated
            self.f.source.reader.publish_horizon(
                self.f.source.payloads,
                data=self.f.f.data,
                league_id="league-1",
                season=2026,
                current_week=2,
            )
            with patch(
                "services.global_evidence.retained_global_evidence", return_value=None
            ):
                prepare_for_data(self.f.source.reader, self.f.f.data)

    def test_inactive_retired_out_shared_roster_and_trade_evidence(self):
        for status in ("Inactive", "Retired", "Out"):
            with self.subTest(status=status):
                player = self.f.f.data["teams"][0]["players"][1]
                player["status"] = status
                self.f.f.data["players"][player["id"]]["status"] = status
                self.publish()
                team = team_diagnostics(
                    self.f.f.data, 1, self.f.source.reader.snapshot()
                )
                self.assertIn(player["id"], team["excluded_player_ids"])
                for rid in (1, 2):
                    response = self.f.f.client.get(f"/teams/{rid}")
                    self.assertEqual(response.status_code, 200)
                response = self.f.evaluate()
                self.assertEqual(response.status_code, 200)
                package = response.json()["evaluation"]["dimensions"][
                    "roster_diagnostics"
                ]
                self.assertEqual(
                    package["sides"]["active"]["eligibility"], team["eligibility"]
                )

    def test_actual_stale_publication_reaches_team_and_evaluator(self):
        self.publish("2020-01-01T00:00:00+00:00")
        for rid in (1, 2):
            response = self.f.f.client.get(f"/teams/{rid}")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Stale", response.text)
            self.assertIn("provisional", response.text)
            self.assertNotIn("Supported current-week positional strength:", response.text)
        response = self.f.evaluate()
        self.assertEqual(response.status_code, 200)
        side = response.json()["evaluation"]["dimensions"]["roster_diagnostics"][
            "sides"
        ]["active"]
        self.assertEqual(side["evidence"]["conclusion_state"], "provisional")
        self.assertIn("Stale", side["summary"])

    def test_missing_scoring_preserves_html_without_false_zero_diagnostic(self):
        self.f.f.data["league"].pop("scoring_settings")
        self.f.f.data.pop("scoring_settings", None)
        self.publish()
        for rid in (1, 2):
            response = self.f.f.client.get(f"/teams/{rid}")
            self.assertEqual(response.status_code, 200)
            self.assertIn("insufficient supported scoring evidence", response.text)
        response = self.f.evaluate()
        if response.status_code == 200:
            side = response.json()["evaluation"]["dimensions"]["roster_diagnostics"][
                "sides"
            ]["active"]
            self.assertIsNone(side["post_optimal_points"])
            self.assertEqual(side["evidence"]["conclusion_state"], "unavailable")
        else:
            self.assertEqual(response.status_code, 422)
            self.assertIn("projection", response.text.lower())
