from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.intelligence_memory import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceMemoryService,
    ProvenanceType, SourceObservation,
)
from src.core.intelligence_memory.market_memory import (
    MarketObservationMaterialityPolicy, market_context_id,
)
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.pipeline import CheckpointPipeline


class GlobalSparseMarketMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = IntelligenceCheckpointStore(Path(self.temporary.name) / "memory.sqlite3")
        self.service = IntelligenceMemoryService(self.store)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def evidence(*, value: int = 8000, observed_at: str = "2026-01-01T00:00:00Z"):
        return (SourceObservation(
            provider="canonical-market", raw_value=value, normalized_value=value,
            observed_at=observed_at, source_identity=f"feed:{value}",
            temporal_distance_seconds=0,
        ),)

    def capture(
        self, *, league: str, event: str, value: int | None = 8000,
        timestamp: str = "2026-01-01T00:00:00Z", confidence: int = 90,
        observations=None, asset_id: str = "player:10213",
        provenance: ProvenanceType = ProvenanceType.LIVE_CAPTURED,
    ):
        return self.service.capture(
            asset_id=asset_id,
            asset_type="future_pick" if asset_id.startswith("pick:") else "player",
            timestamp=timestamp, season=2026,
            trigger=CheckpointTrigger.TRADE_EXECUTION, provenance=provenance,
            league_id=league, scoring_profile_id=f"league-specific:{league}",
            market_value=value, intrinsic_value=value, confidence=confidence,
            completeness=(EvidenceCompleteness.COMPLETE if value is not None
                          else EvidenceCompleteness.UNAVAILABLE),
            model_version="market-v1", brain_identity="brain-semantic-1",
            event_id=event,
            observations=(self.evidence(value=value or 0, observed_at=timestamp)
                          if observations is None and value is not None else observations or ()),
        )

    def test_same_state_is_global_and_reused_across_leagues(self) -> None:
        first, _ = self.capture(league="A", event="trade-A")
        second, _ = self.capture(league="B", event="trade-B", timestamp="2026-02-01T00:00:00Z")
        self.assertEqual(first.global_market_observation_id, second.global_market_observation_id)
        health = self.store.market_memory_health()
        self.assertEqual(health["observation_count"], 1)
        self.assertEqual(health["reference_count"], 2)
        self.assertEqual(health["observations_reused"], 1)
        self.assertEqual(health["cross_league_reuse_count"], 1)
        self.assertFalse(health["league_id_in_observation_identity"])

    def test_time_and_provider_timestamp_do_not_create_observation(self) -> None:
        first, _ = self.capture(league="A", event="one")
        evidence = self.evidence(value=8000, observed_at="2026-06-01T00:00:00Z")
        second, _ = self.capture(
            league="A", event="two", timestamp="2026-06-01T00:00:00Z",
            observations=evidence,
        )
        self.assertEqual(first.global_market_observation_id, second.global_market_observation_id)
        self.assertEqual(self.store.market_memory_health()["observation_count"], 1)

    def test_material_change_creates_one_new_observation(self) -> None:
        original, _ = self.capture(league="A", event="one")
        changed, _ = self.capture(
            league="B", event="two", value=8300,
            timestamp="2026-02-01T00:00:00Z",
        )
        self.assertNotEqual(original.global_market_observation_id, changed.global_market_observation_id)
        self.assertEqual(self.store.market_memory_health()["observation_count"], 2)

    def test_unavailable_never_uses_historical_observation_as_current(self) -> None:
        self.capture(league="A", event="available")
        unavailable, _ = self.capture(
            league="B", event="unavailable", value=None,
            timestamp="2026-02-01T00:00:00Z",
        )
        self.assertIsNone(unavailable.global_market_observation_id)
        health = self.store.market_memory_health()
        self.assertEqual(health["unavailable_references"], 1)
        self.assertEqual(health["historical_observation_current_fallback"], 0)

    def test_pick_market_class_shares_state_but_lineage_stays_league_scoped(self) -> None:
        one, _ = self.capture(league="A", event="pick-a", value=4500, asset_id="pick:2028:1")
        two, _ = self.capture(
            league="B", event="pick-b", value=4500, asset_id="pick:2028:1",
            timestamp="2026-02-01T00:00:00Z",
        )
        self.assertEqual(one.global_market_observation_id, two.global_market_observation_id)
        rows = self.store.checkpoints(asset_id="pick:2028:1")
        self.assertEqual({row.league_id for row in rows}, {"A", "B"})

    def test_one_hundred_concurrent_events_create_one_observation_and_replay_none(self) -> None:
        def run(index: int):
            return self.capture(league=f"L{index}", event=f"trade-{index}")[0]
        with ThreadPoolExecutor(max_workers=12) as executor:
            list(executor.map(run, range(100)))
        health = self.store.market_memory_health()
        self.assertEqual(health["observation_count"], 1)
        self.assertEqual(health["reference_count"], 100)
        with ThreadPoolExecutor(max_workers=12) as executor:
            list(executor.map(run, range(100)))
        replay = self.store.market_memory_health()
        self.assertEqual(replay["observation_count"], 1)
        self.assertEqual(replay["reference_count"], 100)

    def test_materially_changed_replay_cannot_create_an_orphan_observation(self) -> None:
        original, created = self.capture(league="A", event="trade-A")
        replay, replay_created = self.capture(
            league="A", event="trade-A", value=9000,
            timestamp="2026-02-01T00:00:00Z",
        )
        self.assertTrue(created)
        self.assertFalse(replay_created)
        self.assertEqual(replay.checkpoint_id, original.checkpoint_id)
        self.assertEqual(replay.market_value, original.market_value)
        health = self.store.market_memory_health()
        self.assertEqual(health["observation_count"], 1)
        self.assertEqual(health["reference_count"], 1)

    def test_historical_event_never_uses_a_later_observation(self) -> None:
        later, _ = self.capture(
            league="A", event="later", timestamp="2026-06-01T00:00:00Z",
        )
        earlier, _ = self.capture(
            league="B", event="earlier", timestamp="2026-01-01T00:00:00Z",
        )
        self.assertNotEqual(later.global_market_observation_id, earlier.global_market_observation_id)

    def test_context_identity_excludes_league_scoring_hash(self) -> None:
        self.assertEqual(
            market_context_id(asset_type="player", scoring_profile_id="league-A"),
            market_context_id(asset_type="player", scoring_profile_id="league-B"),
        )
        self.assertNotEqual(
            market_context_id(asset_type="player", scoring_profile_id="A", format_class="superflex"),
            market_context_id(asset_type="player", scoring_profile_id="A", format_class="one-qb"),
        )

    def test_materiality_policy_is_centralized_and_versioned(self) -> None:
        policy = MarketObservationMaterialityPolicy()
        self.assertEqual(policy.version, "1.0")
        self.assertEqual(policy.canonical_value_delta, 250.0)
        self.assertEqual(policy.canonical_relative_delta, 0.08)
        self.assertEqual(policy.provider_value_delta, 250.0)
        self.assertEqual(policy.provider_relative_delta, 0.08)
        self.assertEqual(policy.confidence_delta, 10)
        self.assertEqual(policy.market_tier_width, 1000)

    def test_materiality_detects_relative_and_market_tier_transitions(self) -> None:
        relative, _ = self.capture(league="A", event="relative", value=950)
        reused, _ = self.capture(
            league="B", event="small", value=925,
            timestamp="2026-02-01T00:00:00Z",
        )
        changed, _ = self.capture(
            league="C", event="large", value=850,
            timestamp="2026-03-01T00:00:00Z",
        )
        tier_before, _ = self.capture(
            league="A", event="tier-before", value=1990,
            timestamp="2026-04-01T00:00:00Z", asset_id="player:tier",
        )
        tier_after, _ = self.capture(
            league="B", event="tier-after", value=2010,
            timestamp="2026-05-01T00:00:00Z", asset_id="player:tier",
        )
        self.assertEqual(relative.global_market_observation_id, reused.global_market_observation_id)
        self.assertNotEqual(relative.global_market_observation_id, changed.global_market_observation_id)
        self.assertNotEqual(tier_before.global_market_observation_id, tier_after.global_market_observation_id)

    def test_provider_set_and_confidence_changes_are_material(self) -> None:
        original, _ = self.capture(league="A", event="one")
        changed_confidence, _ = self.capture(
            league="B", event="two", confidence=75,
            timestamp="2026-02-01T00:00:00Z",
        )
        self.assertNotEqual(
            original.global_market_observation_id,
            changed_confidence.global_market_observation_id,
        )
        other_provider = (SourceObservation(
            provider="independent-market", raw_value=8000, normalized_value=8000,
            observed_at="2026-03-01T00:00:00Z", source_identity="independent:1",
            temporal_distance_seconds=0,
        ),)
        changed_provider, _ = self.capture(
            league="C", event="three", confidence=75,
            timestamp="2026-03-01T00:00:00Z", observations=other_provider,
        )
        self.assertNotEqual(
            changed_confidence.global_market_observation_id,
            changed_provider.global_market_observation_id,
        )

    def test_existing_checkpoint_migration_preserves_embedded_evidence(self) -> None:
        from tests.test_intelligence_memory import checkpoint
        first, _ = self.store.put(checkpoint(league_id="A", related_event_id="A"))
        second, _ = self.store.put(checkpoint(
            checkpoint_id="B", league_id="B", related_event_id="B",
        ))
        restarted = IntelligenceCheckpointStore(self.store.path)
        rows = restarted.checkpoints()
        self.assertEqual({row.checkpoint_id for row in rows}, {first.checkpoint_id, second.checkpoint_id})
        self.assertTrue(all(row.market_value == 8050 for row in rows))
        self.assertEqual(len({row.global_market_observation_id for row in rows}), 1)
        migration = restarted.market_memory_health()["checkpoint_migration"]
        self.assertEqual(migration["migratable_exactly"], 2)
        self.assertEqual(migration["migratable_with_shared_observation"], 1)
        again = IntelligenceCheckpointStore(self.store.path)
        self.assertEqual(again.market_memory_health()["observation_count"], 1)
        self.assertEqual(again.market_memory_health()["reference_count"], 2)
        self.assertEqual(
            again.market_memory_health()["checkpoint_migration"]["migratable_exactly"], 2,
        )

    def test_reconstructed_checkpoint_remains_legacy_embedded(self) -> None:
        from tests.test_intelligence_memory import checkpoint
        self.store.put(checkpoint(provenance_type=ProvenanceType.RECONSTRUCTED))
        restarted = IntelligenceCheckpointStore(self.store.path)
        health = restarted.market_memory_health()
        self.assertEqual(health["observation_count"], 0)
        self.assertEqual(health["checkpoint_migration"]["legacy_embedded_evidence"], 1)

    def test_global_benchmark_replays_across_leagues_without_duplication(self) -> None:
        pipeline = CheckpointPipeline(self.service)
        base = {
            "league": {"league_id": "A", "season": "2026", "status": "in_season",
                       "settings": {"playoff_week_start": 15}},
            "week": 1,
            "relevant_player_universe": {"members": [{
                "player_id": "10213", "reason_codes": ["historical_traded"],
            }]},
            "valuation_intelligence": {"assets": {"player:10213": {
                "valuation_layers": {
                    "market_value": {"value": 8000},
                    "intrinsic_dtos_value": {"value": 8100},
                },
            }}},
        }
        pipeline.ingest_scheduled(base, observed_at="ignored")
        pipeline.ingest_scheduled({
            **base, "league": {**base["league"], "league_id": "B"},
        }, observed_at="ignored")
        health = self.store.market_memory_health()
        self.assertEqual(health["observation_count"], 1)
        self.assertEqual(health["reference_count"], 1)
        self.assertIsNone(self.store.checkpoints()[0].league_id)

    def test_nfl_draft_impact_never_writes_unrelated_asset(self) -> None:
        results = self.service.capture_nfl_draft_impacts(
            {"player:chase": 9000, "player:teammate": 5000, "player:dak": 8000},
            {"player:chase": 8600, "player:teammate": 4700, "player:dak": 8000},
            timestamp="2026-04-25T00:00:00Z", season=2026,
            provenance=ProvenanceType.LIVE_CAPTURED, league_id=None,
            scoring_profile_id=None, confidence=80,
            completeness=EvidenceCompleteness.COMPLETE,
            model_version="market-v1", event_id="nfl-draft-impact",
        )
        self.assertEqual({row.asset_id for row in results}, {"player:chase", "player:teammate"})
        self.assertEqual(self.store.checkpoints(asset_id="player:dak"), [])

    def test_reads_do_not_write(self) -> None:
        self.capture(league="A", event="one")
        before = self.store.market_memory_health()
        for _ in range(20):
            self.store.observations(asset_id="player:10213")
            self.store.checkpoints(asset_id="player:10213")
        after = self.store.market_memory_health()
        self.assertEqual(before["observation_count"], after["observation_count"])
        self.assertEqual(before["reference_count"], after["reference_count"])

    def test_failed_reference_write_rolls_back_observation_and_checkpoint(self) -> None:
        with patch.object(
            self.store, "_put_reference_on_connection",
            side_effect=RuntimeError("synthetic reference failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic reference failure"):
                self.capture(league="A", event="rollback")
        health = self.store.market_memory_health()
        self.assertEqual(health["observation_count"], 0)
        self.assertEqual(health["reference_count"], 0)
        self.assertEqual(self.store.checkpoints(), [])

    def test_public_market_api_is_bounded_and_exposes_no_league_context(self) -> None:
        from routes.intelligence_memory import create_intelligence_memory_router
        self.capture(league="private-league", event="private-trade")
        app = FastAPI()
        with patch(
            "routes.intelligence_memory.intelligence_checkpoint_store", self.store,
        ):
            app.include_router(create_intelligence_memory_router(default_league_id="public"))
            client = TestClient(app)
            health = client.get("/api/intelligence-memory/market/health")
            timeline = client.get(
                "/api/intelligence-memory/market/assets/player:10213/timeline?limit=1"
            )
            oversized = client.get("/api/intelligence-memory/market/observations?limit=501")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(timeline.status_code, 200)
        self.assertEqual(oversized.status_code, 422)
        self.assertNotIn("private-league", timeline.text)
        self.assertFalse(timeline.json()["league_context_exposed"])

    def test_storage_estimate_separates_global_states_from_league_references(self) -> None:
        self.capture(league="A", event="one")
        estimates = self.store.storage_estimates()
        sparse = estimates["global_sparse_market"]
        self.assertTrue(sparse["league_count_is_not_observation_growth_driver"])
        self.assertEqual(
            sparse["observation_growth_driver"],
            "meaningful_global_market_state_changes",
        )
        self.assertIn("100000_leagues", estimates)


if __name__ == "__main__":
    unittest.main()
