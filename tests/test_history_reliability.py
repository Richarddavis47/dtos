from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx

from src.core.historical_memory.aggregation import aggregate_production
from src.core.historical_memory.enrichment import (
    build_identity_context,
    enrich_rows,
    prepare_enrichment_records,
)
from src.core.historical_memory.importer import HistoricalImporter
from src.core.historical_memory.jobs import (
    ImportJob,
    classify_failure,
    completeness_report,
    recover_stalled_jobs,
    utcnow,
    with_retry,
)
from src.core.historical_memory.providers import (
    classify_nflverse_404,
    normalize_nflverse_row,
)
from src.core.historical_memory.scoring import calculate_fantasy_points
from src.core.historical_memory.season_state import SeasonState, classify_season
from src.core.historical_memory.store import HistoricalStore
from tools.history_enrich import exit_code


def streaming_provider(
    rows: list[dict[str, Any]] | None = None,
    error: Exception | None = None,
) -> Mock:
    async def batches(
        _season: int, batch_size: int,
    ):
        if error is not None:
            raise error
        supplied = rows or []
        for offset in range(0, len(supplied), batch_size):
            yield supplied[offset:offset + batch_size]

    return Mock(side_effect=batches)


class HistoryReliabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def enrichment_job(self, seasons: tuple[int, ...]) -> ImportJob:
        job = ImportJob(
            self.store, "L", seasons, ("player_week",),
            requested_by="test", provider="nflverse",
        )
        job.create()
        self.assertTrue(job.acquire())
        return job

    def enrichment_checkpoint(
        self, job: ImportJob, season: int, status: str = "completed",
    ) -> None:
        self.store.checkpoint(
            checkpoint_key=f"L:{season}:player_week:nflverse:1.2",
            job_id=job.job_id, league_id="L", season=season, week=None,
            data_type="player_week", provider="nflverse",
            importer_version="1.2", status=status,
            completed_at=utcnow().isoformat(),
        )

    def commit_empty_enrichment_batch(
        self, job: ImportJob, season: int, sequence: int,
    ) -> dict[str, int]:
        now = utcnow()
        return self.store.commit_enrichment_batch(
            raw_records=[], derived_records=[],
            progress={
                "batch_key": f"L:{season}:nflverse:{sequence}:1.2",
                "job_id": job.job_id, "lease_owner": job.worker_identity,
                "league_id": "L", "season": season, "week": 1,
                "provider": "nflverse", "batch_sequence": sequence,
                "raw_records_received": 0,
                "batch_started_at": now.isoformat(),
                "batch_completed_at": now.isoformat(),
                "last_durable_event_identity": None,
            },
            lease_expires_at=(now + timedelta(minutes=15)).isoformat(),
        )

    async def test_transient_failure_retries_and_permanent_does_not(self) -> None:
        transient = AsyncMock(side_effect=[httpx.ConnectError("dns"), {"ok": True}])
        result, retries = await with_retry(
            transient, base_delay=0, jitter=lambda: 0,
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(retries, 1)
        permanent = AsyncMock(side_effect=ValueError("bad payload"))
        with self.assertRaises(ValueError):
            await with_retry(permanent, base_delay=0)
        self.assertEqual(permanent.await_count, 1)

    async def test_truncated_http_read_is_bounded_and_retryable(self) -> None:
        request = httpx.Request(
            "GET",
            "https://api.sleeper.app/v1/league/2025/matchups/12",
        )
        read_error = httpx.ReadError(
            "peer closed connection before complete body",
            request=request,
        )
        transient = AsyncMock(
            side_effect=[read_error, read_error, {"ok": True}]
        )
        result, retries = await with_retry(
            transient,
            base_delay=0,
            jitter=lambda: 0,
            operation_name="Sleeper 2025 matchup week 12",
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(retries, 2)
        self.assertEqual(transient.await_count, 3)
        self.assertEqual(classify_failure(read_error), "retryable")

        persistent = AsyncMock(side_effect=read_error)
        with self.assertRaises(httpx.ReadError):
            await with_retry(
                persistent,
                base_delay=0,
                jitter=lambda: 0,
                operation_name="Sleeper 2025 matchup week 12",
            )
        self.assertEqual(persistent.await_count, 4)

    async def test_rate_limit_is_classified_and_retry_after_honored(self) -> None:
        request = httpx.Request("GET", "https://provider.example")
        response = httpx.Response(
            429, request=request, headers={"Retry-After": "0"},
        )
        error = httpx.HTTPStatusError("limited", request=request, response=response)
        operation = AsyncMock(side_effect=[error, []])
        _, retries = await with_retry(operation, base_delay=0)
        self.assertEqual(retries, 1)
        self.assertEqual(classify_failure(error), "rate_limited")

    async def test_persistent_lock_prevents_duplicate_and_expiry_recovers(self) -> None:
        first = ImportJob(self.store, "L", (2022,), ("matchup",))
        second = ImportJob(self.store, "L", (2022,), ("matchup",))
        first.create()
        second.create()
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        self.store.update_job(
            first.job_id,
            lock_expiration=(utcnow() - timedelta(seconds=1)).isoformat(),
        )
        self.assertEqual(recover_stalled_jobs(self.store, "L"), 1)
        recovered = next(
            row for row in self.store.jobs("L") if row["job_id"] == first.job_id
        )
        self.assertEqual(recovered["status"], "queued")

    async def test_bounded_batch_uses_one_transaction_and_is_idempotent(self) -> None:
        records = [
            {
                "record_key": f"L:player_week:2022:1:{index}",
                "entity_type": "player_week",
                "league_id": "L",
                "season": 2022,
                "week": 1,
                "player_id": str(index),
                "source_record_id": str(index),
                "observed_at": "2022-09-01T00:00:00+00:00",
                "retrieved_at": "2026-07-29T00:00:00+00:00",
                "provider": "Sleeper",
                "availability": "observed",
                "confidence": 95,
                "calculation_method": "provider_record",
                "schema_version": "1.0",
                "payload": {"fantasy_points": float(index)},
            }
            for index in range(100)
        ]
        with patch.object(
            self.store, "connection", wraps=self.store.connection,
        ) as connection:
            self.assertEqual(self.store.append_many(records), (100, 0))
            self.assertEqual(connection.call_count, 1)
        with patch.object(
            self.store, "connection", wraps=self.store.connection,
        ) as connection:
            self.assertEqual(self.store.append_many(records), (0, 100))
            self.assertEqual(connection.call_count, 1)

    def test_batch_sequence_never_advances_season_progress(self) -> None:
        job = self.enrichment_job((2021, 2022))
        self.commit_empty_enrichment_batch(job, 2021, 78)
        stored = self.store.jobs("L")[0]
        self.assertEqual((stored["completed_steps"], stored["total_steps"]), (0, 2))
        self.assertEqual(self.store.enrichment_batches("L")[0]["batch_sequence"], 78)

    def test_completed_season_advances_once_and_replay_does_not_advance(self) -> None:
        job = self.enrichment_job((2021, 2022))
        self.enrichment_checkpoint(job, 2021)
        self.enrichment_checkpoint(job, 2021)
        self.commit_empty_enrichment_batch(job, 2021, 1)
        self.commit_empty_enrichment_batch(job, 2021, 1)
        stored = self.store.jobs("L")[0]
        self.assertEqual((stored["completed_steps"], stored["total_steps"]), (1, 2))

    def test_six_seasons_never_exceed_six_completed_steps(self) -> None:
        seasons = tuple(range(2021, 2027))
        job = self.enrichment_job(seasons)
        for season in seasons:
            self.enrichment_checkpoint(job, season)
        stored = self.store.jobs("L")[0]
        self.assertEqual((stored["completed_steps"], stored["total_steps"]), (6, 6))
        with self.assertRaisesRegex(ValueError, "completed_steps"):
            self.store.update_job(job.job_id, completed_steps=7)

    def test_partial_and_pending_progress_is_checkpoint_derived(self) -> None:
        job = self.enrichment_job((2021, 2022, 2023))
        self.enrichment_checkpoint(job, 2021)
        self.enrichment_checkpoint(job, 2022, "pending")
        progress = self.store.enrichment_job_progress(job.job_id)
        self.assertEqual(progress["completed_steps"], 1)
        self.assertEqual(progress["total_steps"], 3)
        self.assertEqual(progress["completed_seasons"], [2021])
        self.assertEqual(progress["pending_seasons"], [2022])
        self.assertTrue(progress["consistent"])

    def test_invalid_persisted_progress_repairs_idempotently_without_evidence_changes(self) -> None:
        job = self.enrichment_job(tuple(range(2021, 2027)))
        for season in range(2021, 2026):
            self.enrichment_checkpoint(job, season)
        self.commit_empty_enrichment_batch(job, 2021, 1)
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE import_jobs SET completed_steps=78 WHERE job_id=?",
                (job.job_id,),
            )
        before_count, _ = self.store.records("L", "player_raw_week")
        before_batches = self.store.enrichment_batches("L")
        reopened = HistoricalStore(self.store.path)
        repaired = reopened.jobs("L")[0]
        self.assertEqual((repaired["completed_steps"], repaired["total_steps"]), (5, 6))
        self.assertEqual(len(reopened.progress_repairs()), 1)
        self.assertEqual(reopened.progress_repairs()[0]["previous_completed_steps"], 78)
        self.assertEqual(reopened.progress_repairs()[0]["details"]["pending_seasons"], [])
        self.assertEqual(reopened.records("L", "player_raw_week")[0], before_count)
        self.assertEqual(reopened.enrichment_batches("L"), before_batches)
        reopened_again = HistoricalStore(self.store.path)
        self.assertEqual(len(reopened_again.progress_repairs()), 1)
        self.assertEqual(reopened_again.jobs("L")[0]["completed_steps"], 5)

    def test_pending_season_remains_pending_during_progress_repair(self) -> None:
        job = self.enrichment_job((2021, 2022))
        self.enrichment_checkpoint(job, 2021)
        self.enrichment_checkpoint(job, 2022, "pending")
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE import_jobs SET completed_steps=78 WHERE job_id=?",
                (job.job_id,),
            )
        reopened = HistoricalStore(self.store.path)
        progress = reopened.enrichment_job_progress(job.job_id)
        self.assertEqual(progress["completed_steps"], 1)
        self.assertEqual(progress["pending_seasons"], [2022])

    def test_completion_status_rejects_contradictory_counters(self) -> None:
        job = self.enrichment_job((2021, 2022))
        self.enrichment_checkpoint(job, 2021)
        with self.assertRaisesRegex(ValueError, "consistent progress"):
            self.store.update_job(job.job_id, status="completed")

        foundation = ImportJob(
            self.store, "foundation", (2021, 2022),
            ("league_season", "matchup"), requested_by="test",
        )
        foundation.create()
        self.store.update_job(
            foundation.job_id, completed_steps=2, status="completed",
        )
        self.assertEqual(self.store.jobs("foundation")[0]["status"], "completed")

        mixed = ImportJob(
            self.store, "mixed", (2021, 2022),
            ("player_week", "matchup"), requested_by="test",
        )
        mixed.create()
        self.store.update_job(mixed.job_id, completed_steps=2, status="completed")
        self.assertEqual(self.store.jobs("mixed")[0]["status"], "completed")

        with self.assertRaisesRegex(ValueError, "completed_steps"):
            self.store.update_job(foundation.job_id, completed_steps=5)

    def test_import_status_exposes_the_same_canonical_progress(self) -> None:
        import services.history as history_service

        job = self.enrichment_job((2021, 2022))
        self.enrichment_checkpoint(job, 2021)
        self.enrichment_checkpoint(job, 2022, "pending")
        with patch.object(history_service, "historical_store", self.store):
            status = history_service.import_status("L")
        job_status = next(row for row in status["jobs"] if row["job_id"] == job.job_id)
        self.assertEqual(job_status["completed_steps"], 1)
        self.assertEqual(job_status["progress"]["completed_steps"], 1)
        self.assertEqual(job_status["progress"]["pending_seasons"], [2022])
        self.assertTrue(job_status["progress"]["consistent"])

    async def test_checkpoint_and_job_state_survive_store_restart(self) -> None:
        job = ImportJob(self.store, "L", (2022,), ("matchup",))
        job.create()
        self.store.checkpoint(
            checkpoint_key="L:2022:matchup:Sleeper:1.1",
            job_id=job.job_id, league_id="L", season=2022, week=1,
            data_type="matchup", provider="Sleeper", importer_version="1.1",
            status="completed", completed_at=utcnow().isoformat(),
            records_written=2,
        )
        reopened = HistoricalStore(self.store.path)
        self.assertEqual(reopened.jobs("L")[0]["requested_seasons"], [2022])
        self.assertEqual(reopened.checkpoints("L")[0]["status"], "completed")

    async def test_nflverse_normalization_preserves_zero_and_missing(self) -> None:
        row = normalize_nflverse_row({
            "season": "2022", "week": "1", "player_id": "gsis-1",
            "attempts": "0", "passing_yards": "", "carries": "4",
        })
        self.assertEqual(row["raw_stats"]["pass_att"], 0)
        self.assertIsNone(row["raw_stats"]["pass_yd"])
        self.assertEqual(row["metric_status"]["pass_att"], "observed")
        self.assertEqual(row["metric_status"]["pass_yd"], "unavailable")

    async def test_enrichment_is_idempotent_and_uses_stable_id(self) -> None:
        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Same Name", 100,
            "2022-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        rows = [normalize_nflverse_row({
            "season": "2022", "week": "1", "player_id": "gsis-1",
            "attempts": "20", "passing_yards": "250", "passing_tds": "2",
        })]
        settings = {"pass_yd": .04, "pass_td": 4}
        first = enrich_rows(self.store, "L", rows, settings)
        second = enrich_rows(self.store, "L", rows, settings)
        self.assertEqual(first["written"], 2)
        self.assertEqual(second["written"], 0)
        count, records = self.store.records(
            "L", "player_raw_week", player_id="sleeper-1",
        )
        self.assertEqual(count, 1)
        self.assertEqual(records[0]["payload"]["provider_player_id"], "gsis-1")

    async def test_scoring_marks_missing_components_incomplete(self) -> None:
        result = calculate_fantasy_points(
            {"pass_yd": 250, "pass_int": 1},
            {"pass_yd": .04, "pass_td": 4, "pass_int": -2},
        )
        self.assertEqual(result["fantasy_points"], 8)
        self.assertEqual(result["availability"], "incomplete")
        self.assertEqual(result["missing_components"], ["pass_td"])

    async def test_aggregates_preserve_missing_and_add_rates(self) -> None:
        result = aggregate_production([
            {"fantasy_points": 0}, {"fantasy_points": None},
            {"fantasy_points": 24},
        ])
        self.assertEqual(result["games_played"], 2)
        self.assertEqual(result["availability_rate"], 0.667)
        self.assertEqual(result["boom_week_rate"], .5)

    async def test_completeness_does_not_call_unsupported_complete(self) -> None:
        report = completeness_report(self.store, "L", (2022,))
        self.assertEqual(report["status"], "incomplete")
        self.assertIn(
            "player_usage", report["seasons"][0]["unsupported_categories"],
        )
        self.assertTrue(report["seasons"][0]["missing_categories"])

    async def test_season_classification_is_nfl_aware_and_deterministic(self) -> None:
        preseason = classify_season(2026, today=date(2026, 7, 28))
        active = classify_season(2026, today=date(2026, 9, 20))
        january = classify_season(2025, today=date(2026, 1, 2))
        future = classify_season(2027, today=date(2026, 12, 1))
        self.assertEqual(preseason.state, SeasonState.PRE_REGULAR)
        self.assertEqual(active.state, SeasonState.ACTIVE)
        self.assertEqual(january.state, SeasonState.ACTIVE)
        self.assertEqual(future.state, SeasonState.FUTURE)

    async def test_nflverse_404_semantics_preserve_historical_failure(self) -> None:
        completed = classify_season(2024, today=date(2026, 7, 28))
        preseason = classify_season(2026, today=date(2026, 7, 28))
        future = classify_season(2027, today=date(2026, 7, 28))
        unsupported = classify_season(
            1998, today=date(2026, 7, 28), minimum_supported=1999,
        )
        self.assertEqual(classify_nflverse_404(completed).status, "failed")
        self.assertEqual(classify_nflverse_404(preseason).status, "pending")
        self.assertEqual(
            classify_nflverse_404(future).status, "not_yet_available",
        )
        self.assertEqual(
            classify_nflverse_404(unsupported).status, "unsupported",
        )

    async def test_active_404_requires_prior_coverage_to_be_pending(self) -> None:
        active = classify_season(2026, today=date(2026, 9, 20))
        self.assertEqual(classify_nflverse_404(active).status, "failed")
        self.assertEqual(
            classify_nflverse_404(active, prior_week_count=1).status,
            "pending",
        )

    async def test_pending_checkpoint_is_distinct_from_failure(self) -> None:
        job = ImportJob(self.store, "L", (2026,), ("player_week",))
        job.create()
        self.store.checkpoint(
            checkpoint_key="L:2026:player_week:nflverse:1.1",
            job_id=job.job_id, league_id="L", season=2026, week=None,
            data_type="player_week", provider="nflverse",
            importer_version="1.1", status="pending",
            completed_at=utcnow().isoformat(),
            error="Regular season has not begun.",
        )
        checkpoint = self.store.checkpoints("L")[0]
        self.assertEqual(checkpoint["status"], "pending")
        self.assertEqual(checkpoint["records_written"], 0)
        self.assertIn("not begun", checkpoint["error"])
        report = completeness_report(self.store, "L", (2026,))
        season = report["seasons"][0]
        self.assertEqual(season["status"], "pending")
        self.assertEqual(season["failed_categories"], [])
        self.assertEqual(season["pending_categories"], ["player_week"])

    async def test_enrichment_job_succeeds_with_preseason_pending(self) -> None:
        import services.history as history_service

        request = httpx.Request("GET", "https://provider.example/2026")
        response = httpx.Response(404, request=request)
        missing = httpx.HTTPStatusError(
            "missing", request=request, response=response,
        )
        with (
            patch.object(history_service, "historical_store", self.store),
            patch(
                "services.history.NflverseProvider.weekly_batches",
                streaming_provider(error=missing),
            ) as weekly,
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2026}, today=date(2026, 7, 28),
            )
        self.assertEqual(result["status"], "completed_with_pending")
        self.assertEqual(result["pending"][0]["status"], "pending")
        self.assertEqual(result["errors"], [])
        self.assertEqual(self.store.jobs("L")[0]["failed_records"], 0)
        self.assertEqual(self.store.jobs("L")[0]["retry_count"], 0)
        self.assertEqual(exit_code(result), 0)
        self.assertEqual(weekly.call_count, 0)

    async def test_future_is_not_requested_and_historical_404_fails(self) -> None:
        import services.history as history_service

        request = httpx.Request("GET", "https://provider.example/2024")
        response = httpx.Response(404, request=request)
        missing = httpx.HTTPStatusError(
            "missing", request=request, response=response,
        )
        weekly = streaming_provider(error=missing)
        with (
            patch.object(history_service, "historical_store", self.store),
            patch("services.history.NflverseProvider.weekly_batches", weekly),
        ):
            future = await history_service.enrich_player_history(
                "L", seasons={2027}, today=date(2026, 7, 28),
            )
            historical = await history_service.enrich_player_history(
                "L", seasons={2024}, today=date(2026, 7, 28),
            )
        self.assertEqual(future["status"], "completed_with_pending")
        self.assertEqual(future["pending"][0]["status"], "not_yet_available")
        self.assertEqual(historical["status"], "failed")
        self.assertEqual(exit_code(historical), 1)
        self.assertEqual(weekly.call_count, 1)
        self.assertEqual(weekly.call_args.args[0], 2024)

    async def test_pending_segment_can_transition_to_imported(self) -> None:
        import services.history as history_service

        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2026-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        rows = [normalize_nflverse_row({
            "season": "2026", "week": "1", "player_id": "gsis-1",
            "carries": "0", "rushing_yards": "",
        })]
        with (
            patch.object(history_service, "historical_store", self.store),
            patch(
                "services.history.NflverseProvider.weekly_batches",
                streaming_provider(rows),
            ),
        ):
            pending = await history_service.enrich_player_history(
                "L", seasons={2026}, today=date(2026, 7, 28),
            )
            imported = await history_service.enrich_player_history(
                "L", seasons={2026}, today=date(2026, 9, 20),
            )
        self.assertEqual(pending["status"], "completed_with_pending")
        self.assertEqual(imported["status"], "complete")
        self.assertEqual(imported["written"], 2)
        raw_count, raw = self.store.records("L", "player_raw_week")
        self.assertEqual(raw_count, 1)
        self.assertEqual(raw[0]["payload"]["raw_stats"]["rush_att"], 0)
        self.assertIsNone(raw[0]["payload"]["raw_stats"]["rush_yd"])

    async def test_stale_sleeper_refresh_is_nonblocking_and_deduplicated(self) -> None:
        import services.sleeper as sleeper_service

        original_state = dict(sleeper_service.STATE)
        sleeper_service.STATE.update({
            "data": {"league": {"league_id": "L"}},
            "last_sync": None,
        })
        sleeper_service._SLEEPER_SYNC_TASK = None
        release = asyncio.Event()

        async def blocked_sync(force_players: bool = False) -> dict[str, Any]:
            await release.wait()
            return sleeper_service.STATE

        try:
            with patch.object(sleeper_service, "sync_sleeper", blocked_sync):
                started = time.perf_counter()
                await sleeper_service.ensure_data_fresh()
                first = sleeper_service._SLEEPER_SYNC_TASK
                await sleeper_service.ensure_data_fresh()
                self.assertLess(time.perf_counter() - started, .25)
                self.assertIs(first, sleeper_service._SLEEPER_SYNC_TASK)
                self.assertIsNotNone(first)
                release.set()
                await first
        finally:
            sleeper_service.STATE.clear()
            sleeper_service.STATE.update(original_state)
            sleeper_service._SLEEPER_SYNC_TASK = None

    async def test_sleeper_sync_worker_does_not_starve_request_loop(self) -> None:
        import services.sleeper as sleeper_service

        async def blocking_worker(force_players: bool = False) -> dict[str, Any]:
            time.sleep(.2)
            return {"force_players": force_players}

        with patch.object(sleeper_service, "_sync_sleeper", blocking_worker):
            started = time.perf_counter()
            task = asyncio.create_task(sleeper_service.sync_sleeper())
            await asyncio.sleep(.03)
            request_loop_delay = time.perf_counter() - started
            self.assertLess(request_loop_delay, .1)
            self.assertFalse(task.done())
            self.assertEqual(await task, {"force_players": False})

    async def test_status_contract_does_not_call_refresh(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from routes.api import create_api_router

        ensure = AsyncMock(side_effect=AssertionError("provider I/O requested"))
        app = FastAPI()
        app.include_router(create_api_router(
            ensure_fresh=ensure,
            require_data=lambda: {},
            sync_sleeper=AsyncMock(),
            state={"data": {}, "last_sync": None, "last_error": None},
            league_id="L",
        ))
        response = TestClient(app).get("/api/status")
        self.assertEqual(response.status_code, 200)
        ensure.assert_not_awaited()

    async def test_large_import_batches_do_not_starve_event_loop(self) -> None:
        league = {
            "league_id": "source", "season": "2022", "name": "League",
            "settings": {}, "scoring_settings": {},
        }
        players = [f"p{index}" for index in range(250)]
        matchup = {
            "matchup_id": 1, "roster_id": 1, "points": 100,
            "starters": players[:10], "players": players,
            "players_points": {player: 0 for player in players},
        }

        async def fetch(path: str) -> Any:
            if path.endswith("/users"):
                return [{"user_id": "u1", "display_name": "Owner"}]
            if path.endswith("/rosters"):
                return [{"roster_id": 1, "owner_id": "u1", "settings": {}}]
            if path.endswith("/drafts") or "bracket" in path:
                return []
            if "/matchups/" in path:
                return [matchup]
            if "/transactions/" in path:
                return []
            return {}

        importer = HistoricalImporter(self.store, fetch)
        run_id = ImportJob(
            self.store, "L", (2022,), ("player_week",),
            requested_by="test",
        ).create()
        original = self.store.append_many

        def deliberately_slow_batch(rows: list[dict[str, Any]]) -> tuple[int, int]:
            time.sleep(.03)
            return original(rows)

        ticks = 0
        finished = asyncio.Event()

        async def heartbeat() -> None:
            nonlocal ticks
            while not finished.is_set():
                ticks += 1
                await asyncio.sleep(.005)

        pulse = asyncio.create_task(heartbeat())
        with patch.object(self.store, "append_many", deliberately_slow_batch):
            await importer._import_season(
                run_id, "L", "source", 2022, league, 1,
            )
        finished.set()
        await pulse
        self.assertGreater(ticks, 5)
        self.assertEqual(self.store.jobs("L")[0]["failed_records"], 0)

    async def test_identity_context_is_built_once_and_reused_by_batches(self) -> None:
        import services.history as history_service

        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2022-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        rows = [
            normalize_nflverse_row({
                "season": "2022", "week": str(index + 1),
                "player_id": "gsis-1", "carries": "0",
            })
            for index in range(120)
        ]
        context_builder = Mock(
            wraps=lambda store: build_identity_context(store),
        )
        with (
            patch.object(history_service, "historical_store", self.store),
            patch.object(
                history_service, "build_identity_context", context_builder,
            ),
            patch.object(history_service, "ENRICHMENT_BATCH_SIZE", 50),
            patch(
                "services.history.NflverseProvider.weekly_batches",
                streaming_provider(rows),
            ),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2022}, today=date(2023, 7, 1),
            )
        self.assertEqual(context_builder.call_count, 1)
        self.assertEqual(result["identity_context"]["batch_reuse_count"], 3)
        self.assertEqual(result["identity_context"]["gsis_count"], 1)

    def test_v1710_compatible_evidence_retains_identical_record_keys(self) -> None:
        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2022-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        row = normalize_nflverse_row({
            "season": "2022", "week": "3", "player_id": "gsis-1",
            "carries": "4", "rushing_yards": "21",
        })
        raw, derived, unresolved = prepare_enrichment_records(
            "L", [row], {}, build_identity_context(self.store),
        )
        self.assertEqual(unresolved, 0)
        self.assertEqual(
            raw[0]["record_key"],
            "L:player_raw_week:2022:3:nflverse:2022:3:gsis-1:1.2",
        )
        self.assertEqual(
            derived[0]["record_key"],
            "L:player_fantasy_week:2022:3:sleeper-1:1.2",
        )

    def test_replay_against_v1710_evidence_inserts_no_logical_duplicates(self) -> None:
        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2022-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        row = normalize_nflverse_row({
            "season": "2022", "week": "3", "player_id": "gsis-1",
            "carries": "4", "rushing_yards": "21",
        })
        context = build_identity_context(self.store)
        first = enrich_rows(self.store, "L", [row], {}, context)
        replay = enrich_rows(self.store, "L", [row], {}, context)
        self.assertEqual(first, {"written": 2, "unchanged": 0, "unresolved": 0})
        self.assertEqual(replay, {"written": 0, "unchanged": 2, "unresolved": 0})
        raw_count, _ = self.store.records("L", "player_raw_week")
        derived_count, _ = self.store.records("L", "player_fantasy_week")
        self.assertEqual((raw_count, derived_count), (1, 1))

    async def test_startup_skips_current_completed_enrichment_checkpoint(self) -> None:
        import services.history as history_service

        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2022-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        job = ImportJob(self.store, "L", (2022,), ("player_week",))
        job.create()
        self.store.checkpoint(
            checkpoint_key="L:2022:player_week:nflverse:1.2",
            job_id=job.job_id, league_id="L", season=2022, week=None,
            data_type="player_week", provider="nflverse",
            importer_version="1.2", status="completed",
            completed_at="2023-01-01T00:00:00+00:00",
        )
        weekly = streaming_provider(error=AssertionError("redundant provider call"))
        with (
            patch.object(history_service, "historical_store", self.store),
            patch("services.history.NflverseProvider.weekly_batches", weekly),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2022}, today=date(2023, 7, 1),
                skip_current=True,
            )
        self.assertEqual(result["segments"][0]["status"], "current")
        weekly.assert_not_called()

    async def test_preseason_pending_does_not_request_provider(self) -> None:
        import services.history as history_service

        weekly = streaming_provider(error=AssertionError("preseason provider call"))
        with (
            patch.object(history_service, "historical_store", self.store),
            patch("services.history.NflverseProvider.weekly_batches", weekly),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2026}, today=date(2026, 7, 28),
                skip_current=True,
            )
        self.assertEqual(result["pending"][0]["status"], "pending")
        weekly.assert_not_called()

    async def test_failed_latest_attempt_preserves_completed_foundation(self) -> None:
        import services.history as history_service

        observed = utcnow().isoformat()
        self.store.append(
            record_key="L:league_season:2025", entity_type="league_season",
            league_id="L", season=2025, source_record_id="source",
            observed_at=observed, retrieved_at=observed, provider="Sleeper",
            availability="observed", confidence=100,
            calculation_method="test", schema_version="1.0", payload={},
        )
        self.store.start_run("complete-run", "L", observed, "not supplied")
        self.store.update_run(
            "complete-run", status="complete", checkpoint="2025:complete",
            written=1, unchanged=0, errors=[], completed_at=observed,
        )
        self.store.start_run("failed-run", "L", observed, "not supplied")
        self.store.update_run(
            "failed-run", status="partial", checkpoint="2026:league",
            written=0, unchanged=0, errors=["provider failed"],
            completed_at=observed,
        )
        enrichment = AsyncMock(return_value={"status": "complete"})
        backfill = AsyncMock(side_effect=AssertionError("redundant backfill"))
        with (
            patch.object(history_service, "historical_store", self.store),
            patch.object(
                history_service, "enrich_player_history", enrichment,
            ),
            patch.object(history_service, "backfill_history", backfill),
        ):
            result = await history_service.ensure_history_backfill(
                AsyncMock(), league_id="L",
            )
            status = history_service.import_status("L")
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["run_id"], "complete-run")
        self.assertEqual(status["latest_attempt"]["run_id"], "failed-run")
        self.assertEqual(
            status["latest_completed_foundation"]["run_id"], "complete-run",
        )
        backfill.assert_not_awaited()

    async def test_invalid_complete_without_records_is_not_foundation(self) -> None:
        observed = utcnow().isoformat()
        self.store.start_run("empty-complete", "L", observed, "not supplied")
        self.store.update_run(
            "empty-complete", status="complete", checkpoint="complete",
            written=0, unchanged=0, errors=[], completed_at=observed,
        )
        self.assertIsNone(self.store.latest_completed_foundation("L"))
