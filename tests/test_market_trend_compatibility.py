"""Active sparse store/service contract, including the production mixed-scale case."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint,
    ProvenanceType, SourceObservation,
)
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.market_trends import MarketTrendService
from tests.test_market_trends_step7 import _Reader, _row


class SparseComparisonTests(unittest.TestCase):
    def rows(self):
        return [_row("a", "2026-01-01T00:00:00Z", 100),
                _row("b", "2026-02-01T00:00:00Z", 200)]

    def assert_unavailable(self, result):
        self.assertEqual(result["direction"], "not_comparable")
        for name in ("magnitude", "volatility", "observed_high", "observed_low"):
            self.assertIsNone(result[name], name)
        self.assertEqual(result["milestones"], {})
        self.assertEqual(result["confidence"], "unavailable")

    def test_each_required_semantic_boundary_fails_closed(self):
        for field in ("value_concept", "value_scale", "format_key", "methodology"):
            with self.subTest(field=field):
                rows = self.rows()
                rows[1]["comparison_semantics"][field] = "different"
                result = MarketTrendService(_Reader(rows)).trend_for_asset("player:1", None)
                self.assert_unavailable(result)
                self.assertTrue(result["comparison_reasons"])

    def test_unknown_is_not_matching_semantics(self):
        rows = self.rows()
        for row in rows:
            row.pop("comparison_semantics")
        self.assert_unavailable(MarketTrendService(_Reader(rows)).trend_for_asset("player:1", None))

    def test_current_number_without_identity_cannot_contaminate_history(self):
        result = MarketTrendService(_Reader(self.rows())).trend_for_asset("player:1", 9999)
        self.assertEqual(result["magnitude"], 100)
        self.assertEqual(result["direction"], "rising")
        self.assertFalse(result["provenance"]["current_endpoint_comparable"])

    def test_compatible_history_without_current_quote_remains_supported(self):
        result = MarketTrendService(_Reader(self.rows())).trend_for_asset("player:1", None)
        self.assertEqual(result["direction"], "rising")
        self.assertEqual(result["comparison_reasons"], ())

    def test_same_time_conflicting_prices_have_no_order(self):
        rows = self.rows()
        rows[1]["observed_at"] = rows[0]["observed_at"]
        self.assert_unavailable(MarketTrendService(_Reader(rows)).trend_for_asset("player:1", None))

    def test_as_of_respects_knowledge_not_only_source_date(self):
        rows = self.rows()
        rows[1]["known_at"] = "2026-08-01T00:00:00Z"
        result = MarketTrendService(_Reader(rows)).trend_for_asset(
            "player:1", None, as_of="2026-04-01T00:00:00Z")
        self.assertEqual(result["checkpoint_count"], 1)
        self.assertEqual(result["direction"], "insufficient_evidence")

    def test_provider_change_is_not_independent_price_movement(self):
        rows = self.rows()
        rows[1]["providers"] = ("Different",)
        self.assert_unavailable(MarketTrendService(_Reader(rows)).trend_for_asset("player:1", None))

    def test_week_label_is_not_an_observed_instant(self):
        rows = self.rows()
        rows[1]["observed_at"] = "2026-W01"
        result = MarketTrendService(_Reader(rows)).trend_for_asset("player:1", None)
        self.assertEqual(result["checkpoint_count"], 1)
        self.assertEqual(result["provenance"]["invalid_temporal_evidence_count"], 1)

    def test_store_retains_explicit_compatible_contract_for_valid_trend(self):
        with TemporaryDirectory() as directory:
            store = IntelligenceCheckpointStore(Path(directory) / "memory.sqlite3")
            for index, row in enumerate(self.rows()):
                checkpoint = IntelligenceCheckpoint(
                    checkpoint_id=f"explicit-{index}", asset_id="player:1", asset_type="player",
                    timestamp=row["observed_at"], season=2026,
                    trigger_type=CheckpointTrigger.SEASON_START,
                    provenance_type=ProvenanceType.LIVE_CAPTURED,
                    market_value=row["value"], confidence=80,
                    evidence_completeness=EvidenceCompleteness.COMPLETE, model_version="fixture-v1",
                )
                store.put_sparse(checkpoint, market_context_id="explicit-global", provider_evidence=(
                    SourceObservation(provider="A", raw_value=row["value"], normalized_value=row["value"],
                                      observed_at=row["observed_at"], source_identity=str(index),
                                      temporal_distance_seconds=0,
                                      metadata={"comparison_semantics": row["comparison_semantics"]}),))
            result = MarketTrendService(store).trend_for_asset("player:1", None)
            self.assertEqual(result["direction"], "rising")
            self.assertEqual(result["magnitude"], 100)

    def test_live_store_preserves_legacy_records_and_exposes_boundary(self):
        from routes.market import _trend_boundary_notice
        with TemporaryDirectory() as directory:
            store = IntelligenceCheckpointStore(Path(directory) / "memory.sqlite3")
            for index, (value, method) in enumerate(((5237, "1.10.31"), (752, "1.10.59"), (757, "1.10.28"))):
                checkpoint = IntelligenceCheckpoint(
                    checkpoint_id=f"legacy-{index}", asset_id="player:1", asset_type="player",
                    timestamp=f"2026-0{index + 1}-01T00:00:00Z", season=2026,
                    trigger_type=CheckpointTrigger.SEASON_START,
                    provenance_type=ProvenanceType.HISTORICAL_SOURCE_BACKFILL,
                    market_value=value, confidence=80 - index * 10,
                    evidence_completeness=EvidenceCompleteness.COMPLETE, model_version=method,
                )
                store.put_sparse(checkpoint, market_context_id="legacy-global", provider_evidence=(
                    SourceObservation(provider="dynastyprocess", raw_value=value,
                                      normalized_value=value, observed_at=checkpoint.timestamp,
                                      source_identity=str(index), temporal_distance_seconds=0),))
            def records():
                with store._connect() as connection:
                    return [tuple(row) for row in connection.execute(
                        "SELECT * FROM global_market_observations ORDER BY observation_id")]
            before = records()
            result = MarketTrendService(store).trend_for_asset("player:1", None)
            self.assert_unavailable(result)
            self.assertIn("METHODOLOGY_VERSION_CHANGED", result["comparison_reasons"])
            self.assertIn("Methodology / semantic boundary", _trend_boundary_notice(result))
            self.assertEqual(records(), before)
            self.assertEqual(sorted(row["value"] for row in result["checkpoints"]), [752, 757, 5237])

    def test_current_contract_is_part_of_cache_identity(self):
        service = MarketTrendService(_Reader(self.rows()))
        current = deepcopy(self.rows()[1])
        args = dict(as_of="2026-03-01T00:00:00Z", current_evidence_at="2026-03-01T00:00:00Z")
        valid = service.trend_for_asset("player:1", 300, current_semantics=current, **args)
        current["comparison_semantics"]["value_scale"] = "other"
        invalid = service.trend_for_asset("player:1", 300, current_semantics=current, **args)
        self.assertEqual(valid["magnitude"], 200)
        self.assertEqual(invalid["magnitude"], 100)


if __name__ == "__main__":
    unittest.main()
