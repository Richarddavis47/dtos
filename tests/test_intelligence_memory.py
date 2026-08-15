"""v1.10.19 Sleeper-backed cache and permanent intelligence-memory regressions."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse

from routes.historical_assets import create_historical_assets_router

from src.core.intelligence_memory.chain import discover_season_chain
from src.core.intelligence_memory.confidence import temporal_confidence
from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint,
    PickLineage, ProvenanceType, SourceObservation,
)
from src.core.intelligence_memory.season_cache import SleeperSeasonCache
from src.core.intelligence_memory.equivalence import compare_provider_to_legacy
from src.core.intelligence_memory.market import (
    current_market_value, select_historical_market,
)
from src.core.intelligence_memory.fois import fois_process_evidence
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.triggers import (
    current_market_checkpoint, historical_backfill_checkpoint,
    material_teammate_impacts, trade_assessment,
)


def checkpoint(**changes) -> IntelligenceCheckpoint:
    base = IntelligenceCheckpoint(
        checkpoint_id="",
        asset_id="player:10213",
        asset_type="player",
        league_id="L",
        scoring_profile_id="scoring:one",
        timestamp="2025-09-01T12:00:00+00:00",
        season=2025,
        week=1,
        trigger_type=CheckpointTrigger.TRADE_EXECUTION,
        provenance_type=ProvenanceType.LIVE_CAPTURED,
        dtos_value=8100,
        intrinsic_value=8000,
        contender_value=8300,
        rebuilder_value=7900,
        market_value=8050,
        confidence=94,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        model_version="brain-1",
        brain_identity="brain:semantic-one",
        related_event_id="trade-1",
        observations=(SourceObservation(
            provider="dynastyprocess", raw_value=8050,
            normalized_value=8050,
            observed_at="2025-09-01T00:00:00+00:00",
            source_identity="git:abc", temporal_distance_seconds=43_200,
        ),),
        knowledge_state="generic_player_at_execution",
    )
    return replace(base, **changes)


class SeasonChainTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_actual_year_one_without_calendar_cutoff(self) -> None:
        leagues = {
            "current": {"season": "2026", "previous_league_id": "middle"},
            "middle": {"season": "2018", "previous_league_id": "origin"},
            "origin": {"season": "2009", "previous_league_id": None},
        }

        async def fetch(league_id: str):
            return leagues[league_id]

        chain = await discover_season_chain("current", fetch)
        self.assertTrue(chain.terminated)
        self.assertEqual(chain.year_one, 2009)
        self.assertEqual([row.season for row in chain.seasons], [2026, 2018, 2009])

    async def test_three_eight_and_fifteen_year_chains_have_no_fixed_start(self) -> None:
        for depth in (3, 8, 15):
            leagues = {
                str(index): {
                    "season": str(2040 - index),
                    "previous_league_id": str(index + 1) if index + 1 < depth else None,
                }
                for index in range(depth)
            }

            async def fetch(league_id: str, values=leagues):
                return values[league_id]

            chain = await discover_season_chain("0", fetch)
            self.assertEqual(len(chain.seasons), depth)
            self.assertEqual(chain.year_one, 2040 - (depth - 1))

    async def test_missing_provider_season_is_unavailable_not_fabricated(self) -> None:
        async def fetch(league_id: str):
            if league_id == "current":
                return {"season": "2026", "previous_league_id": "missing"}
            return None

        chain = await discover_season_chain("current", fetch)
        self.assertFalse(chain.terminated)
        self.assertEqual(chain.seasons[-1].availability, "unavailable")
        self.assertEqual(chain.termination_reason, "provider_unavailable")

    async def test_cycle_fails_safely(self) -> None:
        async def fetch(league_id: str):
            return {"season": "2026", "previous_league_id": league_id}

        chain = await discover_season_chain("L", fetch)
        self.assertEqual(chain.termination_reason, "cycle_detected")


class SeasonCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.cache = SleeperSeasonCache(Path(self.temporary.name) / "cache")

    async def asyncTearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def facts() -> dict:
        return {
            "league": {"season": "2024"}, "users": [], "rosters": [],
            "matchups": {"1": []}, "transactions": {"1": []}, "drafts": [],
            "draft_picks": [], "traded_picks": [], "winners_bracket": [],
            "losers_bracket": [],
        }

    async def test_deleted_cache_rebuilds_from_provider(self) -> None:
        calls = 0

        async def fetch(_league: str, _season: int):
            nonlocal calls
            calls += 1
            return self.facts()

        first = await self.cache.get_or_rebuild("L", 2024, fetch)
        second = await self.cache.get_or_rebuild("L", 2024, fetch)
        self.assertEqual(calls, 1)
        self.assertEqual(first.checksum, second.checksum)
        self.cache.delete("L", 2024)
        await self.cache.get_or_rebuild("L", 2024, fetch)
        self.assertEqual(calls, 2)

    async def test_provider_loss_becomes_unavailable_without_hidden_fallback(self) -> None:
        async def unavailable(_league: str, _season: int):
            return None

        result = await self.cache.get_or_rebuild("L", 1999, unavailable)
        self.assertEqual(result.status, "unavailable")
        self.assertFalse(self.cache._path("L", 1999).exists())

    async def test_cache_is_compact_disposable_and_checksummed(self) -> None:
        row = self.cache.normalize("L", 2024, self.facts())
        path = self.cache.write(row)
        self.assertLess(path.stat().st_size, 2_000)
        self.assertEqual(self.cache.read("L", 2024), row)
        self.assertEqual(self.cache.health()["ownership"], "disposable_provider_cache")


class CheckpointStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "intelligence.sqlite3"
        self.store = IntelligenceCheckpointStore(self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_checkpoint_is_durable_immutable_and_deduplicated(self) -> None:
        stored, inserted = self.store.put(checkpoint())
        duplicate, inserted_again = self.store.put(checkpoint(checkpoint_id="different"))
        self.assertTrue(inserted)
        self.assertFalse(inserted_again)
        self.assertEqual(stored.checkpoint_id, duplicate.checkpoint_id)
        restarted = IntelligenceCheckpointStore(self.path)
        self.assertEqual(restarted.checkpoints()[0], stored)

    def test_model_upgrade_does_not_rewrite_historical_checkpoint(self) -> None:
        old, _ = self.store.put(checkpoint())
        new, inserted = self.store.put(checkpoint(model_version="brain-2"))
        self.assertTrue(inserted)
        self.assertNotEqual(old.checkpoint_id, new.checkpoint_id)
        self.assertEqual(len(self.store.checkpoints()), 2)

    def test_global_observation_deduplicates_across_leagues(self) -> None:
        global_row = checkpoint(league_id=None, scoring_profile_id=None)
        one, _ = self.store.put(global_row)
        two, inserted = self.store.put(global_row)
        self.assertFalse(inserted)
        self.assertEqual(one.checkpoint_id, two.checkpoint_id)

    def test_provider_cache_deletion_does_not_delete_checkpoint(self) -> None:
        stored, _ = self.store.put(checkpoint())
        cache = SleeperSeasonCache(Path(self.temporary.name) / "cache")
        cache.write(cache.normalize("L", 2024, {"league": {}}))
        cache.delete("L", 2024)
        self.assertEqual(self.store.checkpoints()[0].checkpoint_id, stored.checkpoint_id)

    def test_pick_lineage_never_rewrites_execution_time_generic_identity(self) -> None:
        original = PickLineage("lineage", "pick:2026:1:R1", 2026, 1, "R1")
        self.store.put_lineage(original)
        later = replace(
            original, exact_slot="1.04", selected_player_id="player:rookie",
            slot_known_at="2026-04-01T00:00:00+00:00",
        )
        _, inserted = self.store.put_lineage(later)
        self.assertFalse(inserted)
        historical, _ = self.store.put(checkpoint(
            asset_id=original.generic_pick_id, asset_type="future_pick",
            knowledge_state="generic_future_first",
        ))
        self.assertEqual(historical.knowledge_state, "generic_future_first")

    def test_storage_health_separates_permanent_intelligence(self) -> None:
        self.store.put(checkpoint())
        health = self.store.health()
        self.assertEqual(health["ownership"], "permanent_dtos_intelligence")
        self.assertEqual(health["checkpoint_count"], 1)
        self.assertFalse(health["daily_logging"])
        self.assertIn("1000_leagues", self.store.storage_estimates())


class IntelligenceSemanticsTests(unittest.TestCase):
    def test_provenance_eligibility(self) -> None:
        self.assertTrue(ProvenanceType.LIVE_CAPTURED.definitive_process_evidence)
        self.assertTrue(ProvenanceType.HISTORICAL_SOURCE_BACKFILL.definitive_process_evidence)
        self.assertFalse(ProvenanceType.RECONSTRUCTED.definitive_process_evidence)
        self.assertFalse(ProvenanceType.UNAVAILABLE.definitive_process_evidence)

    def test_current_provider_outage_never_uses_historical_value(self) -> None:
        unavailable = current_market_checkpoint(checkpoint(), current_provider_available=False)
        self.assertIsNone(unavailable.market_value)
        self.assertEqual(unavailable.knowledge_state, "current_market_unavailable")

    def test_missing_historical_source_is_unavailable_not_reconstructed(self) -> None:
        unavailable = historical_backfill_checkpoint(
            checkpoint(), legitimate_historical_observation=False,
        )
        self.assertEqual(unavailable.provenance_type, ProvenanceType.UNAVAILABLE)
        self.assertIsNone(unavailable.market_value)

    def test_single_source_backfill_is_legitimate(self) -> None:
        result = historical_backfill_checkpoint(
            checkpoint(), legitimate_historical_observation=True,
        )
        self.assertEqual(result.provenance_type, ProvenanceType.HISTORICAL_SOURCE_BACKFILL)

    def test_partial_trade_does_not_treat_unavailable_pick_as_zero(self) -> None:
        available = checkpoint(checkpoint_id="player")
        missing = checkpoint(
            checkpoint_id="pick", asset_id="pick:2026:1:R1", asset_type="future_pick",
            market_value=None, provenance_type=ProvenanceType.UNAVAILABLE,
            evidence_completeness=EvidenceCompleteness.UNAVAILABLE,
        )
        result = trade_assessment({"one": [available, missing], "two": [available]})
        self.assertEqual(result.status, EvidenceCompleteness.PARTIAL)
        self.assertIsNone(result.side_totals["one"])
        self.assertFalse(result.process_grade_eligible)

    def test_temporal_confidence_and_material_event_downgrade(self) -> None:
        event = "2025-09-08T00:00:00+00:00"
        self.assertEqual(temporal_confidence("2025-09-07T12:00:00+00:00", event)[0], 95)
        self.assertEqual(temporal_confidence("2025-09-04T00:00:00+00:00", event)[0], 65)
        self.assertLessEqual(temporal_confidence(
            "2025-09-07T12:00:00+00:00", event,
            intervening_material_event=True,
        )[0], 40)
        self.assertEqual(temporal_confidence("2025-09-09T00:00:00+00:00", event)[0], 0)

    def test_only_material_teammates_receive_checkpoint_trigger(self) -> None:
        before = {"incumbent": 5000, "quarterback": 6000, "depth": 1000}
        after = {"incumbent": 4600, "quarterback": 5900, "depth": 1100}
        self.assertEqual(material_teammate_impacts(before, after), ("incumbent",))

    def test_historical_selection_uses_newest_pre_event_snapshot_only(self) -> None:
        observations = (
            SourceObservation("dynastyprocess", 7000, "2025-08-31T00:00:00+00:00", "git:old", 0, normalized_value=7000),
            SourceObservation("dynastyprocess", 7100, "2025-09-01T00:00:00+00:00", "git:new", 0, normalized_value=7100),
            SourceObservation("dynastyprocess", 9000, "2025-09-03T00:00:00+00:00", "git:future", 0, normalized_value=9000),
        )
        selected = select_historical_market(observations, "2025-09-02T00:00:00+00:00")
        self.assertEqual(selected.value, 7100)
        self.assertFalse(selected.consensus)
        self.assertEqual(selected.reason, "single_source_historical_evidence")

    def test_unapproved_fantasycalc_history_is_schema_supported_but_not_selected(self) -> None:
        observation = SourceObservation(
            "fantasycalc", 8000, "2025-09-01T00:00:00+00:00", "history:one", 0,
            normalized_value=8000,
        )
        selected = select_historical_market([observation], "2025-09-02T00:00:00+00:00")
        self.assertEqual(selected.provenance, ProvenanceType.UNAVAILABLE)

    def test_current_market_requires_fresh_provider_evidence(self) -> None:
        self.assertEqual(current_market_value(8000, fresh=True, provider_available=True), (8000, "current_market_fresh"))
        self.assertEqual(current_market_value(8000, fresh=False, provider_available=True), (None, "current_market_unavailable"))

    def test_equivalence_never_uses_hidden_legacy_fallback(self) -> None:
        result = compare_provider_to_legacy({"league": {}}, {"league": 1, "trades": 12})
        self.assertFalse(result["historical_memory_fallback"])
        transaction = next(row for row in result["categories"] if row["category"] == "transactions")
        self.assertFalse(transaction["provider_available"])

    def test_fois_excludes_reconstructed_and_reduces_completeness(self) -> None:
        live = checkpoint(checkpoint_id="live")
        reconstructed = checkpoint(
            checkpoint_id="reconstructed",
            provenance_type=ProvenanceType.RECONSTRUCTED,
        )
        result = fois_process_evidence([live, reconstructed])
        self.assertEqual(result["definitive_checkpoint_ids"], ["live"])
        self.assertEqual(result["excluded_checkpoint_ids"], ["reconstructed"])
        self.assertEqual(result["confidence_multiplier"], 0.5)


class TriggerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = IntelligenceCheckpointStore(Path(self.temporary.name) / "memory.sqlite3")
        self.service = IntelligenceMemoryService(self.store)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def context(self) -> dict:
        return {
            "asset_id": "player:1", "asset_type": "player",
            "timestamp": "2026-01-01T00:00:00+00:00", "season": 2026,
            "provenance": ProvenanceType.LIVE_CAPTURED,
            "league_id": "L", "confidence": 80,
            "completeness": EvidenceCompleteness.COMPLETE,
        }

    def test_scheduled_benchmark_is_idempotent(self) -> None:
        _, first = self.service.capture_benchmark(CheckpointTrigger.SEASON_START, **self.context())
        _, second = self.service.capture_benchmark(CheckpointTrigger.SEASON_START, **self.context())
        self.assertTrue(first)
        self.assertFalse(second)

    def test_waiver_and_drop_are_distinct_triggers(self) -> None:
        waiver, _ = self.service.capture_waiver_or_drop(dropped=False, **self.context())
        dropped, _ = self.service.capture_waiver_or_drop(dropped=True, **self.context())
        self.assertEqual(waiver.trigger_type, CheckpointTrigger.WAIVER_ADD)
        self.assertEqual(dropped.trigger_type, CheckpointTrigger.DROP)

    def test_nfl_draft_captures_only_material_teammate(self) -> None:
        rows = self.service.capture_nfl_draft_impacts(
            {"player:1": 5000, "player:2": 5000},
            {"player:1": 4600, "player:2": 4900},
            timestamp="2026-04-25T00:00:00+00:00", season=2026,
            provenance=ProvenanceType.LIVE_CAPTURED,
            confidence=90, completeness=EvidenceCompleteness.COMPLETE,
        )
        self.assertEqual([row.asset_id for row in rows], ["player:1"])

    def test_inactive_league_has_no_implicit_work(self) -> None:
        self.assertEqual(self.store.health()["checkpoint_count"], 0)


class IntelligenceMemoryApiTests(unittest.TestCase):
    def test_public_health_is_bounded_and_separates_ownership(self) -> None:
        from dtos_app import app

        response = TestClient(app).get("/api/intelligence-memory/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["checkpoint_store"]["ownership"], "permanent_dtos_intelligence")
        self.assertEqual(payload["provider_cache"]["ownership"], "disposable_provider_cache")
        self.assertFalse(payload["automatic_backfill"])
        self.assertEqual(payload["legacy_historical_memory"], "physically_retired_fail_closed")

    def test_history_coverage_declares_no_hidden_fallback(self) -> None:
        app = FastAPI()
        graph = Mock()
        graph.coverage.return_value = {"asset_event_count": 0}
        progress = {
            "canonical_history_progress": {}, "latest_job_progress": None,
            "active_job_progress": None, "foundation_progress": None,
        }
        with patch(
            "routes.historical_assets.historical_graph", return_value=graph,
        ), patch(
            "routes.historical_assets.history_progress_contracts",
            return_value=progress,
        ):
            app.include_router(create_historical_assets_router(
                league_id="L", require_data=lambda: {"league": {"league_id": "L"}},
                page=lambda _title, body: HTMLResponse(body),
            ))
            response = TestClient(app).get("/api/history/coverage")
        self.assertEqual(response.status_code, 200)
        contract = response.json()["provider_memory_contract"]
        self.assertFalse(contract["historical_memory_fallback"])
        self.assertIsNone(contract["fixed_start_year"])
