"""Canonical historical-progress presentation and inspection regressions."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from routes.history import create_history_router
from routes.inspect import create_inspection_router
from services.history import canonical_history_progress


def progress_contract(**changes: object) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "completed_with_pending",
        "display_status": "Completed with pending season",
        "completed_steps": 5,
        "total_steps": 6,
        "percentage": 83,
        "completed_seasons": [2021, 2022, 2023, 2024, 2025],
        "pending_seasons": [2026],
        "failed_seasons": [],
        "current_season": 2026,
        "current_data_type": "player_week",
        "consistent": True,
        "terminal": True,
        "pending_reason": (
            "Active/current-season player-week evidence is not yet complete "
            "or available."
        ),
    }
    result.update(changes)
    return result


def job(status: str, progress: dict[str, object]) -> dict[str, object]:
    return {
        "job_id": "job-1",
        "status": status,
        "requested_data_types": ["player_week"],
        "current_season": 2026,
        "current_data_type": "player_week",
        "retry_count": 0,
        "last_progress_at": "2026-08-06T12:00:00+00:00",
        "progress": progress,
    }


class CanonicalHistoryProgressTests(unittest.TestCase):
    def test_pending_active_season_is_an_honest_terminal_state(self) -> None:
        result = canonical_history_progress(
            "L", jobs=[job("completed_with_pending", progress_contract())],
        )
        self.assertEqual(result["status"], "completed_with_pending")
        self.assertEqual((result["completed_steps"], result["total_steps"]), (5, 6))
        self.assertEqual(result["completed_seasons"], [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(result["pending_seasons"], [2026])
        self.assertTrue(result["terminal"])
        self.assertIn("current-season", str(result["pending_reason"]))

    def test_completed_running_failed_and_inconsistent_states_stay_distinct(self) -> None:
        complete = progress_contract(
            completed_steps=6, pending_seasons=[], completed_seasons=list(range(2021, 2027)),
        )
        self.assertEqual(
            canonical_history_progress("L", jobs=[job("completed", complete)])["status"],
            "completed",
        )
        running = progress_contract(completed_steps=2, pending_seasons=[], percentage=33)
        self.assertEqual(
            canonical_history_progress("L", jobs=[job("running", running)])["status"],
            "running",
        )
        failed = progress_contract(completed_steps=2, pending_seasons=[], failed_seasons=[2023])
        self.assertEqual(
            canonical_history_progress("L", jobs=[job("failed", failed)])["status"],
            "failed",
        )
        corrupt = progress_contract(completed_steps=78, consistent=False)
        result = canonical_history_progress("L", jobs=[job("completed", corrupt)])
        self.assertEqual(result["status"], "inconsistent")
        self.assertNotEqual(result["display_status"], "Completed")

    def test_non_player_week_jobs_are_not_the_canonical_enrichment_source(self) -> None:
        foundation = job("completed", progress_contract(completed_steps=66, total_steps=66))
        foundation["requested_data_types"] = ["league_season", "player_week"]
        result = canonical_history_progress("L", jobs=[foundation])
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["completed_steps"], 0)


class HistoryPresentationTests(unittest.TestCase):
    def client(self, canonical: dict[str, object]) -> tuple[TestClient, dict[str, object]]:
        persisted = job(str(canonical["status"]), canonical)
        status = {
            "jobs": [persisted],
            "latest": {"status": "complete"},
            "canonical_progress": canonical,
        }
        app = FastAPI()

        def page(_title: str, body: str) -> HTMLResponse:
            return HTMLResponse(body)

        patches = (
            patch("routes.history.history_records", side_effect=[
                {"count": 6, "records": []}, {"count": 50, "records": []},
            ]),
            patch("routes.history.data_quality", return_value={"blocking_count": 0}),
            patch("routes.history.import_status", return_value=status),
            patch("routes.history.import_completeness", return_value={"status": "complete"}),
            patch("routes.history.provider_coverage", return_value={"providers": [{"name": "nflverse"}]}),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        app.include_router(create_history_router(league_id="L", page=page))
        return TestClient(app), status

    def test_history_matches_canonical_pending_contract_without_mutation(self) -> None:
        canonical = progress_contract()
        client, status = self.client(canonical)
        before = copy.deepcopy(status)
        response = client.get("/history")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("completed_with_pending", html)
        self.assertIn("5/6 seasons", html)
        self.assertIn("(83%)", html)
        self.assertIn("2021, 2022, 2023, 2024, 2025", html)
        self.assertIn("2026", html)
        self.assertIn("Foundation import:</b> Complete", html)
        self.assertNotIn("<b>complete</b> · 83%", html)
        self.assertEqual(status, before)

    def test_history_renders_completed_and_running_counters_exactly(self) -> None:
        complete = progress_contract(
            status="completed", display_status="Completed", completed_steps=6,
            total_steps=6, percentage=100, pending_seasons=[], pending_reason=None,
        )
        self.assertIn("6/6 seasons", self.client(complete)[0].get("/history").text)
        running = progress_contract(
            status="running", display_status="Running", completed_steps=2,
            total_steps=6, percentage=33, pending_seasons=[], pending_reason=None,
            terminal=False,
        )
        html = self.client(running)[0].get("/history").text
        self.assertIn("running", html)
        self.assertIn("2/6 seasons", html)


class HistoricalInspectionContractTests(unittest.TestCase):
    def test_inspection_and_coverage_expose_the_same_canonical_contract(self) -> None:
        canonical = progress_contract()
        state = {"data": {"league": {"league_id": "L"}}}
        app = FastAPI()

        @app.get("/history")
        async def history() -> HTMLResponse:
            return HTMLResponse("history")

        graph = Mock()
        graph.coverage.return_value = {"asset_event_count": 30726}
        with patch("routes.inspect.canonical_history_progress", return_value=canonical), patch(
            "routes.historical_assets.canonical_history_progress", return_value=canonical,
        ), patch("routes.historical_assets.historical_graph", return_value=graph):
            app.include_router(create_inspection_router(
                state=state, route_provider=lambda: app.routes, league_id="L",
            ))
            app.include_router(create_historical_assets_router(
                league_id="L", require_data=lambda: state["data"],
                page=lambda _title, body: HTMLResponse(body),
            ))
            client = TestClient(app)
            health = client.get("/api/inspect/health").json()
            page = client.get("/api/inspect/pages/history").json()
            coverage = client.get("/api/history/coverage").json()
        self.assertEqual(health["historical_progress"], canonical)
        self.assertEqual(page["historical_progress"], canonical)
        self.assertEqual(coverage["canonical_progress"], canonical)
        self.assertEqual(coverage["asset_event_count"], 30726)


if __name__ == "__main__":
    unittest.main()
