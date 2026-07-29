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


class HistoryReliabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")

    def tearDown(self) -> None:
        self.temp.cleanup()

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
                "services.history.NflverseProvider.weekly",
                AsyncMock(side_effect=missing),
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
        self.assertEqual(weekly.await_count, 0)

    async def test_future_is_not_requested_and_historical_404_fails(self) -> None:
        import services.history as history_service

        request = httpx.Request("GET", "https://provider.example/2024")
        response = httpx.Response(404, request=request)
        missing = httpx.HTTPStatusError(
            "missing", request=request, response=response,
        )
        weekly = AsyncMock(side_effect=missing)
        with (
            patch.object(history_service, "historical_store", self.store),
            patch("services.history.NflverseProvider.weekly", weekly),
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
        self.assertEqual(weekly.await_count, 1)

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
                "services.history.NflverseProvider.weekly",
                AsyncMock(return_value=rows),
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
            patch(
                "services.history.NflverseProvider.weekly",
                AsyncMock(return_value=rows),
            ),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2022}, today=date(2023, 7, 1),
            )
        self.assertEqual(context_builder.call_count, 1)
        self.assertEqual(result["identity_context"]["batch_reuse_count"], 3)
        self.assertEqual(result["identity_context"]["gsis_count"], 1)

    async def test_startup_skips_current_completed_enrichment_checkpoint(self) -> None:
        import services.history as history_service

        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2022-01-01", {"provider_ids": {"GSIS": "gsis-1"}},
        )
        job = ImportJob(self.store, "L", (2022,), ("player_week",))
        job.create()
        self.store.checkpoint(
            checkpoint_key="L:2022:player_week:nflverse:1.1",
            job_id=job.job_id, league_id="L", season=2022, week=None,
            data_type="player_week", provider="nflverse",
            importer_version="1.1", status="completed",
            completed_at="2023-01-01T00:00:00+00:00",
        )
        weekly = AsyncMock(side_effect=AssertionError("redundant provider call"))
        with (
            patch.object(history_service, "historical_store", self.store),
            patch("services.history.NflverseProvider.weekly", weekly),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2022}, today=date(2023, 7, 1),
                skip_current=True,
            )
        self.assertEqual(result["segments"][0]["status"], "current")
        weekly.assert_not_awaited()

    async def test_preseason_pending_does_not_request_provider(self) -> None:
        import services.history as history_service

        weekly = AsyncMock(side_effect=AssertionError("preseason provider call"))
        with (
            patch.object(history_service, "historical_store", self.store),
            patch("services.history.NflverseProvider.weekly", weekly),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2026}, today=date(2026, 7, 28),
                skip_current=True,
            )
        self.assertEqual(result["pending"][0]["status"], "pending")
        weekly.assert_not_awaited()

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
