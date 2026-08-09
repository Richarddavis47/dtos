"""Canonical historical-progress presentation and inspection regressions."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from routes.history import create_history_router
from routes.inspect import create_inspection_router
from services.history import canonical_history_progress
from src.core.historical_memory.jobs import ImportJob, utcnow
from src.core.historical_memory.models import IMPORTER_VERSION
from src.core.historical_memory.store import HistoricalStore


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
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = HistoricalStore(Path(self.temporary.name) / "history.sqlite3")

    def create_job(
        self, seasons: tuple[int, ...], *, status: str = "completed_with_pending",
    ) -> ImportJob:
        result = ImportJob(
            self.store, "L", seasons, ("player_week",),
            requested_by="test", provider="nflverse",
        )
        result.create()
        self.store.update_job(result.job_id, status=status)
        return result

    def checkpoint(self, job: ImportJob, season: int, status: str) -> None:
        if status == "completed":
            observed = utcnow().isoformat()
            player_id = f"player-{season}"
            self.store.upsert_identity(
                player_id, "Sleeper", player_id, f"Player {season}", 100,
                observed, {"provider_ids": {"GSIS": f"gsis-{season}"}},
            )
            self.store.append(
                record_key=f"L:player_week:{season}:1:{player_id}:1.2",
                entity_type="player_week", league_id="L", season=season,
                week=1, player_id=player_id,
                source_record_id=f"{season}:1:{player_id}",
                observed_at=observed, retrieved_at=observed,
                provider="nflverse", availability="observed", confidence=100,
                calculation_method="player_week_enrichment",
                schema_version="1.0", payload={"points": 1.0},
            )
        self.store.checkpoint(
            checkpoint_key=f"L:{season}:player_week:nflverse:{IMPORTER_VERSION}",
            job_id=job.job_id, league_id="L", season=season, week=None,
            data_type="player_week", provider="nflverse",
            importer_version=IMPORTER_VERSION, status=status,
            completed_at=utcnow().isoformat(),
        )

    def canonical(self) -> dict[str, object]:
        with patch("services.history.historical_store", self.store):
            return canonical_history_progress("L", current_year=2026)

    def test_pending_active_season_is_an_honest_terminal_state(self) -> None:
        broad = self.create_job(tuple(range(2021, 2027)))
        for season in range(2021, 2026):
            self.checkpoint(broad, season, "completed")
        self.checkpoint(broad, 2026, "pending")
        result = self.canonical()
        self.assertEqual(result["status"], "completed_with_pending")
        self.assertEqual((result["completed_steps"], result["total_steps"]), (5, 6))
        self.assertEqual(result["completed_seasons"], [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(result["pending_seasons"], [2026])
        self.assertTrue(result["terminal"])
        self.assertIn("current-season", str(result["pending_reason"]))

    def test_latest_narrow_job_does_not_replace_six_season_progress(self) -> None:
        broad = self.create_job(tuple(range(2021, 2027)))
        for season in range(2021, 2026):
            self.checkpoint(broad, season, "completed")
        self.checkpoint(broad, 2026, "pending")
        narrow = self.create_job((2026,))
        self.checkpoint(narrow, 2026, "pending")
        with patch("services.history.historical_store", self.store):
            status = __import__("services.history", fromlist=["import_status"]).import_status("L")
        self.assertEqual(status["canonical_history_progress"]["completed_steps"], 5)
        self.assertEqual(status["canonical_history_progress"]["total_steps"], 6)
        self.assertEqual(status["latest_job_progress"]["completed_steps"], 0)
        self.assertEqual(status["latest_job_progress"]["total_steps"], 1)

    def test_completed_current_checkpoint_transitions_to_six_of_six(self) -> None:
        job = self.create_job(tuple(range(2021, 2027)))
        for season in range(2021, 2027):
            self.checkpoint(job, season, "completed")
        self.store.update_job(job.job_id, status="completed")
        result = self.canonical()
        self.assertEqual(result["status"], "completed")
        self.assertEqual((result["completed_steps"], result["total_steps"]), (6, 6))

    def test_invalidated_checkpoint_reduces_progress_without_mutating_evidence(self) -> None:
        job = self.create_job(tuple(range(2021, 2027)))
        for season in range(2021, 2026):
            self.checkpoint(job, season, "completed")
        self.checkpoint(job, 2026, "pending")
        before = self.store.records("L", limit=1)[0]
        self.store.upsert_identity(
            "replacement", "Sleeper", "player-2021", "Replacement", 100,
            utcnow().isoformat(), {"provider_ids": {"GSIS": "new-gsis"}},
        )
        result = self.canonical()
        self.assertEqual(result["completed_steps"], 4)
        self.assertEqual(result["invalidated_seasons"], [2021])
        self.assertEqual(self.store.records("L", limit=1)[0], before)

    def test_overlapping_jobs_and_failed_job_counters_do_not_double_count(self) -> None:
        first = self.create_job(tuple(range(2021, 2027)))
        second = self.create_job((2024, 2025, 2026), status="failed")
        for season in range(2021, 2026):
            self.checkpoint(first if season < 2024 else second, season, "completed")
        self.checkpoint(second, 2026, "pending")
        result = self.canonical()
        self.assertEqual(result["completed_steps"], 5)
        self.assertEqual(result["completed_seasons"], [2021, 2022, 2023, 2024, 2025])


class HistoryPresentationTests(unittest.TestCase):
    def client(self, canonical: dict[str, object]) -> tuple[TestClient, dict[str, object]]:
        persisted = job(str(canonical["status"]), canonical)
        status = {
            "jobs": [persisted],
            "latest": {"status": "complete"},
            "canonical_progress": canonical,
            "canonical_history_progress": canonical,
            "latest_job_progress": {
                "status": canonical["status"],
                "completed_steps": canonical["completed_steps"],
                "total_steps": canonical["total_steps"],
                "current_season": canonical.get("current_season"),
                "current_data_type": "player_week",
            },
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
        contracts = {
            "canonical_history_progress": canonical,
            "latest_job_progress": {"completed_steps": 0, "total_steps": 1},
            "active_job_progress": None,
            "foundation_progress": {"status": "complete"},
        }
        with patch("routes.inspect.history_progress_contracts", return_value=contracts), patch(
            "routes.historical_assets.history_progress_contracts", return_value=contracts,
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
        self.assertEqual(health["history_progress_contracts"], contracts)
        self.assertEqual(page["historical_progress"], canonical)
        self.assertEqual(page["history_progress_contracts"], contracts)
        self.assertEqual(coverage["canonical_progress"], canonical)
        self.assertEqual(coverage["latest_job_progress"]["total_steps"], 1)
        self.assertEqual(coverage["asset_event_count"], 30726)


if __name__ == "__main__":
    unittest.main()
