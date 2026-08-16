"""v1.10.20 canonical checkpoint runtime integration regressions."""
from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from src.core.intelligence_memory.models import CheckpointTrigger, ProvenanceType
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore


class RuntimeCheckpointPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = IntelligenceCheckpointStore(Path(self.temporary.name) / "memory.sqlite3")
        self.pipeline = CheckpointPipeline(IntelligenceMemoryService(self.store))
        self.data = {
            "league": {"league_id": "L1", "season": "2026", "status": "in_season",
                       "settings": {"playoff_week_start": 15}},
            "week": 1, "scoring_settings": {"rec": 1}, "roster_positions": ["QB", "BN"],
            "valuation_intelligence": {"assets": {
                "player:1": {"valuation_layers": {
                    "market_value": {"value": 7000}, "intrinsic_dtos_value": {"value": 7100},
                    "league_adjusted_value": {"value": 7200}, "contender_value": {"value": 7300},
                    "rebuilder_value": {"value": 7050},
                }, "evidence_sources": [{
                    "provider_id": "fantasycalc", "normalized_value": 7000,
                    "family": "fantasycalc_observed_market", "category": "Market",
                    "weight": 82.5, "freshness_tier": "fresh", "reliability": 80,
                }]}
            }},
            "projection_intelligence": {"players": {"1": {
                "canonical_projection": 18.25, "provider": "Sleeper",
                "season": 2026, "week": 1, "scoring_profile_id": "profile-one",
                "source_timestamp": "2026-09-01T00:00:00+00:00",
                "source_freshness": "Fresh", "availability": "active",
                "availability_state": "projected", "projection_confidence": 90,
                "sleeper_evidence_fingerprint": "sleeper-week-one",
            }}},
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_trade_sync_writes_once_and_preserves_values(self) -> None:
        trade = {"transaction_id": "T1", "type": "trade", "created": 1_750_000_000_000,
                 "adds": {"1": 2}, "drops": {}, "draft_picks": []}
        self.pipeline.ingest_transactions(self.data, [trade])
        self.pipeline.ingest_transactions(self.data, [trade])
        rows = self.store.checkpoints(league_id="L1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].trigger_type, CheckpointTrigger.TRADE_EXECUTION)
        self.assertEqual(rows[0].dtos_value, 7200)
        self.assertEqual(self.pipeline.health()["duplicates_skipped"], 1)
        self.assertEqual(rows[0].roster_id, "2")

    def test_material_player_event_keeps_only_compact_projection_evidence(self) -> None:
        trade = {"transaction_id": "projection-T1", "type": "trade",
                 "created": 1_750_000_000_000, "adds": {"1": 2}}
        self.pipeline.ingest_transactions(self.data, [trade])
        observation = self.store.checkpoints()[0].observations[0]
        self.assertEqual(observation.provider, "Sleeper")
        self.assertEqual(observation.normalized_value, 18.25)
        self.assertEqual(observation.metadata["scoring_profile_id"], "profile-one")
        self.assertNotIn("players", observation.metadata)
        self.assertNotIn("payload", observation.metadata)
        global_observation = self.store.observations()[0]
        self.assertEqual(global_observation.provider_evidence[0].provider, "fantasycalc")
        self.assertEqual(global_observation.provider_evidence[0].normalized_value, 7000)

    def test_event_replay_after_model_change_remains_idempotent(self) -> None:
        trade = {"transaction_id": "T-model", "type": "trade", "created": 1_750_000_000_000,
                 "adds": {"1": 2}}
        self.pipeline.ingest_transactions(self.data, [trade])
        changed = {**self.data, "valuation_intelligence": {
            **self.data["valuation_intelligence"], "brain_snapshot_id": "new-model"}}
        self.pipeline.ingest_transactions(changed, [trade])
        self.assertEqual(len(self.store.checkpoints()), 1)

    def test_waiver_add_and_drop_write_distinct_checkpoints(self) -> None:
        transaction = {"transaction_id": "W1", "type": "waiver", "created": 1_750_000_000_000,
                       "adds": {"1": 2}, "drops": {"2": 2}, "settings": {"waiver_bid": 12}}
        self.pipeline.ingest_transactions(self.data, [transaction])
        self.assertEqual(
            {row.trigger_type for row in self.store.checkpoints()},
            {CheckpointTrigger.WAIVER_ADD, CheckpointTrigger.DROP},
        )

    def test_draft_selection_and_lineage_are_idempotent(self) -> None:
        pick = {"draft_id": "D1", "player_id": "1", "pick_no": 1.04,
                "round": 1, "roster_id": 3}
        self.pipeline.ingest_drafts(self.data, [pick], observed_at="2026-05-01T00:00:00+00:00")
        self.pipeline.ingest_drafts(self.data, [pick], observed_at="2026-05-01T00:00:00+00:00")
        rows = self.store.checkpoints()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].trigger_type, CheckpointTrigger.FANTASY_DRAFT_PICK)
        self.assertEqual(self.store.health()["pick_lineage_count"], 1)

    def test_scheduled_checkpoint_is_once_and_not_hardcoded_to_league(self) -> None:
        self.pipeline.ingest_scheduled(self.data, observed_at="ignored")
        self.pipeline.ingest_scheduled(self.data, observed_at="ignored")
        rows = self.store.checkpoints()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].league_id)
        self.assertEqual(rows[0].trigger_type, CheckpointTrigger.SEASON_START)
        self.assertEqual(rows[0].knowledge_state, "scheduled_global_market_benchmark")

    def test_historical_backfill_is_explicit_not_live(self) -> None:
        trade = {"transaction_id": "old", "type": "trade", "adds": {"1": 2}}
        self.pipeline.ingest_transactions(
            self.data, [trade], provenance=ProvenanceType.HISTORICAL_SOURCE_BACKFILL,
            observed_at="2022-09-01T00:00:00+00:00",
        )
        self.assertEqual(self.store.checkpoints()[0].provenance_type,
                         ProvenanceType.HISTORICAL_SOURCE_BACKFILL)

    def test_leagues_are_isolated(self) -> None:
        trade = {"transaction_id": "same", "type": "trade", "adds": {"1": 2}}
        self.pipeline.ingest_transactions(self.data, [trade])
        other = {**self.data, "league": {**self.data["league"], "league_id": "L2"}}
        self.pipeline.ingest_transactions(other, [trade])
        self.assertEqual(len(self.store.checkpoints()), 2)

    def test_missing_current_market_is_unavailable_not_historical_fallback(self) -> None:
        trade = {"transaction_id": "T2", "type": "trade", "adds": {"99": 2}}
        self.pipeline.ingest_transactions(self.data, [trade])
        row = self.store.checkpoints()[0]
        self.assertIsNone(row.market_value)
        self.assertEqual(row.knowledge_state, "current_market_unavailable")

    def test_reads_do_not_invoke_pipeline(self) -> None:
        with patch.object(self.pipeline, "ingest_runtime") as writer:
            self.pipeline.health()
        writer.assert_not_called()

    def test_schema_two_migrates_existing_checkpoint_store_without_rewrite(self) -> None:
        path = Path(self.temporary.name) / "legacy.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript("""
        CREATE TABLE intelligence_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT INTO intelligence_metadata VALUES('schema_version','1');
        CREATE TABLE intelligence_checkpoints(
          checkpoint_id TEXT PRIMARY KEY, semantic_key TEXT NOT NULL UNIQUE,
          asset_id TEXT NOT NULL, asset_type TEXT NOT NULL, league_id TEXT,
          scoring_profile_id TEXT, observed_at TEXT NOT NULL, season INTEGER NOT NULL,
          week INTEGER, trigger_type TEXT NOT NULL, provenance_type TEXT NOT NULL,
          dtos_value REAL, intrinsic_value REAL, contender_value REAL,
          rebuilder_value REAL, market_value REAL, confidence INTEGER NOT NULL,
          evidence_completeness TEXT NOT NULL, model_version TEXT NOT NULL,
          normalization_version TEXT NOT NULL, brain_identity TEXT,
          related_event_id TEXT, knowledge_state TEXT, schema_version TEXT NOT NULL,
          observations_json TEXT NOT NULL);
        """)
        connection.commit()
        connection.close()
        migrated = IntelligenceCheckpointStore(path)
        verification = sqlite3.connect(path)
        try:
            columns = verification.execute(
                "PRAGMA table_info(intelligence_checkpoints)"
            ).fetchall()
        finally:
            verification.close()
        self.assertIn("roster_id", {row[1] for row in columns})
        self.assertEqual(migrated.health()["schema_version"], 3)


if __name__ == "__main__":
    unittest.main()
