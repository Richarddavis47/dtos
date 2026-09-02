"""v1.12.2 sparse, event-relevant global player market-memory contracts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.historical_intelligence import (
    CheckpointDirection, HistoricalIntelligenceService,
)
from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, ProvenanceType, SourceObservation,
)
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore


class EmptyHistory:
    def dataset_version(self, _league_id: str) -> str:
        return "empty"

    def records(self, _league_id: str, _entity_type: str | None, **_kwargs):
        return 0, []


class EventRelevantGlobalMarketMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "memory.sqlite3"
        self.store = IntelligenceCheckpointStore(self.path)
        self.service = IntelligenceMemoryService(self.store)
        self.pipeline = CheckpointPipeline(self.service)
        self.data = {
            "league": {"league_id": "private-league-a", "season": "2026",
                       "status": "in_season", "settings": {"playoff_week_start": 15}},
            "week": 1,
            "players": {
                "1": {"team": "CIN", "position": "WR", "depth_chart_order": 1},
                "2": {"team": "CIN", "position": "QB", "depth_chart_order": 1},
                "3": {"team": "CIN", "position": "WR", "depth_chart_order": 2},
                "4": {"team": "DAL", "position": "QB", "depth_chart_order": 1},
                "5": {"team": "CIN", "position": "TE", "depth_chart_order": 1},
            },
            "relevant_player_universe": {"members": [
                {"player_id": "1", "reason_codes": ["current_roster"]},
                {"player_id": "2", "reason_codes": ["historical_traded"]},
                {"player_id": "4", "reason_codes": ["provider_only"]},
            ]},
            "valuation_intelligence": {"assets": {
                f"player:{player_id}": {"valuation_layers": {
                    "market_value": {"value": value},
                    "intrinsic_dtos_value": {"value": value + 10},
                }, "evidence_sources": [{
                    "provider_id": "canonical-market", "normalized_value": value,
                    "family": "observed_market", "category": "Market",
                    "weight": 90, "freshness_tier": "fresh", "reliability": 90,
                }]}
                for player_id, value in {"1": 9000, "2": 8200, "3": 5000,
                                         "4": 8000, "5": 4500}.items()
            }},
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _with_market_values(self, values: dict[str, int]) -> dict:
        data = {**self.data, "valuation_intelligence": {
            **self.data["valuation_intelligence"],
            "assets": {
                asset_id: {
                    **row,
                    "valuation_layers": {
                        **row["valuation_layers"],
                        "market_value": {
                            **row["valuation_layers"]["market_value"],
                            "value": values.get(asset_id, row["valuation_layers"]["market_value"]["value"]),
                        },
                    },
                    "evidence_sources": [{
                        **evidence,
                        "normalized_value": values.get(asset_id, evidence["normalized_value"]),
                    } for evidence in row["evidence_sources"]],
                }
                for asset_id, row in self.data["valuation_intelligence"]["assets"].items()
            },
        }}
        return data

    def test_milestone_uses_relevant_universe_not_all_valuation_assets(self) -> None:
        health = self.pipeline.ingest_scheduled(self.data, observed_at="ignored")
        self.assertEqual(
            {row.asset_id for row in self.store.checkpoints()},
            {"player:1", "player:2"},
        )
        self.assertEqual(health["milestone_assets_excluded"], 3)

    def test_targeted_ripple_persists_only_material_related_players(self) -> None:
        before = {"player:1": 9000, "player:2": 8200, "player:3": 5000,
                  "player:4": 8000, "player:5": 4500}
        after = {**before, "player:1": 8500, "player:2": 7800,
                 "player:3": 5000, "player:5": 4300}
        health = self.pipeline.ingest_market_event(
            self._with_market_values(after), event_id="injury-one",
            trigger=CheckpointTrigger.MAJOR_INJURY,
            primary_asset_ids=("player:1",), before_values=before,
            after_values=after, observed_at="2026-09-01T12:00:00Z",
        )
        self.assertEqual(
            {row.asset_id for row in self.store.checkpoints()},
            {"player:1", "player:2"},
        )
        self.assertEqual(health["primary_players_considered"], 1)
        self.assertLessEqual(health["related_players_considered"], 12)
        self.assertGreaterEqual(health["related_players_rejected_immaterial"], 2)
        self.assertEqual(self.store.checkpoints(asset_id="player:4"), [])
        self.assertEqual(
            self.store.observations(asset_id="player:1")[0].canonical_value, 8500,
        )

    def test_relationship_without_material_change_writes_nothing_related(self) -> None:
        values = {"player:1": 9000, "player:2": 8200, "player:3": 5000,
                  "player:4": 8000, "player:5": 4500}
        self.pipeline.ingest_market_event(
            self.data, event_id="status-one", trigger=CheckpointTrigger.NFL_TRADE,
            primary_asset_ids=("player:1",), before_values=values,
            after_values=values, observed_at="2026-09-02T12:00:00Z",
        )
        self.assertEqual(
            {row.asset_id for row in self.store.checkpoints()}, {"player:1"},
        )

    def test_detached_post_event_value_is_rejected(self) -> None:
        before = {"player:1": 9000}
        with self.assertRaisesRegex(ValueError, "attached canonical evidence"):
            self.pipeline.ingest_market_event(
                self.data, event_id="detached-value",
                trigger=CheckpointTrigger.NFL_TRADE,
                primary_asset_ids=("player:1",), before_values=before,
                after_values={"player:1": 8500},
                observed_at="2026-09-02T12:00:00Z",
            )

    def test_replay_is_idempotent_and_multi_league_state_is_shared(self) -> None:
        evidence = (SourceObservation(
            provider="canonical-market", raw_value=9000, normalized_value=9000,
            observed_at="2026-09-01T00:00:00Z", source_identity="market:9000",
            temporal_distance_seconds=0,
        ),)
        for league, event in (("private-a", "trade-a"), ("private-b", "trade-b")):
            self.service.capture(
                asset_id="player:1", asset_type="player",
                timestamp="2026-09-01T00:00:00Z", season=2026,
                trigger=CheckpointTrigger.TRADE_EXECUTION,
                provenance=ProvenanceType.LIVE_CAPTURED, league_id=league,
                event_id=event, market_value=9000, confidence=90,
                completeness=EvidenceCompleteness.COMPLETE,
                model_version="market-v1", market_observations=evidence,
            )
        health = self.store.market_memory_health()
        self.assertEqual(health["observation_count"], 1)
        self.assertEqual(health["reference_count"], 2)
        self.assertEqual(health["cross_league_reuse_count"], 1)

    def test_step_one_reader_is_durable_private_and_no_hindsight(self) -> None:
        for when, value, event in (
            ("2026-01-01T00:00:00Z", 8000, "early"),
            ("2026-06-01T00:00:00Z", 9000, "late"),
        ):
            self.service.capture(
                asset_id="player:1", asset_type="player", timestamp=when,
                season=2026, trigger=CheckpointTrigger.TRADE_EXECUTION,
                provenance=ProvenanceType.LIVE_CAPTURED,
                league_id="private-league", event_id=event,
                market_value=value, confidence=90,
                completeness=EvidenceCompleteness.COMPLETE,
                model_version="market-v1", market_observations=(SourceObservation(
                    provider="canonical-market", raw_value=value,
                    normalized_value=value, observed_at=when,
                    source_identity=f"market:{value}", temporal_distance_seconds=0,
                ),),
            )
        restarted = IntelligenceCheckpointStore(self.path)
        historical = HistoricalIntelligenceService(
            EmptyHistory(), checkpoint_reader=restarted,
        )
        selected = historical.nearest_market_checkpoint(
            "player:1", "2026-05-01T00:00:00Z",
            direction=CheckpointDirection.AT_OR_BEFORE,
        )
        self.assertEqual(selected.normalized_value, 8000)
        payload = selected.public_contract()
        self.assertTrue({
            "league_id", "manager", "roster_id", "transaction_package",
        }.isdisjoint(payload))
        self.assertEqual(payload["provider_observations"][0]["provider"],
                         "canonical-market")
        self.assertEqual(payload["normalization_version"], "1.0")

    def test_unavailable_evidence_does_not_create_fake_global_state(self) -> None:
        self.service.capture(
            asset_id="player:missing", asset_type="player",
            timestamp="2026-09-01T00:00:00Z", season=2026,
            trigger=CheckpointTrigger.WAIVER_ADD,
            provenance=ProvenanceType.LIVE_CAPTURED,
            league_id="private", event_id="waiver-missing",
            market_value=None, confidence=0,
            completeness=EvidenceCompleteness.UNAVAILABLE,
        )
        self.assertEqual(self.store.market_memory_health()["observation_count"], 0)
        self.assertEqual(self.store.market_memory_health()["unavailable_references"], 1)


if __name__ == "__main__":
    unittest.main()
