from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint,
    ProvenanceType, SourceObservation,
)
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.market_trends import MarketTrendService


class _Reader:
    def __init__(self, rows=None, liquidity=None):
        self.rows = rows or []
        self.liquidity = liquidity
        self.calls = 0

    def market_trend_evidence(self, *, asset_ids, league_id, as_of):
        self.calls += 1
        eligible = [row for row in self.rows if row["observed_at"] <= as_of]
        return {asset_id: {
            "observations": eligible if asset_id == "player:1" else [],
            **({"liquidity": self.liquidity} if asset_id == "player:1" and self.liquidity else {}),
        } for asset_id in asset_ids}


def _row(identity, stamp, value, reasons=(), providers=("A", "B")):
    return {
        "observation_id": identity, "observed_at": stamp, "value": value,
        "confidence": 80, "reason_codes": reasons, "providers": providers,
        "related_asset_ids": (),
    }


class Step7MarketTrendTests(unittest.TestCase):
    def trend(self, values, *, current=None, as_of="2026-09-01T00:00:00+00:00"):
        rows = [_row(str(i), f"2026-0{i + 1}-01T00:00:00+00:00", value) for i, value in enumerate(values)]
        service = MarketTrendService(_Reader(rows))
        return service.trend_for_asset("player:1", current, as_of=as_of)

    def test_rising_falling_stable_volatile_and_insufficient(self):
        self.assertEqual(self.trend([100, 120, 145], current=170)["direction"], "rising")
        self.assertEqual(self.trend([170, 145, 120], current=90)["direction"], "falling")
        self.assertEqual(self.trend([1000, 1005, 995], current=1001)["direction"], "stable")
        self.assertEqual(self.trend([100, 500, 110], current=450)["direction"], "volatile")
        self.assertEqual(self.trend([], current=100)["direction"], "insufficient_evidence")

    def test_as_of_excludes_future_and_never_fabricates_history(self):
        reader = _Reader([
            _row("a", "2026-01-01T00:00:00+00:00", 100),
            _row("future", "2027-01-01T00:00:00+00:00", 900),
        ])
        result = MarketTrendService(reader).trend_for_asset(
            "player:1", 150, as_of="2026-06-01T00:00:00+00:00",
        )
        self.assertEqual(result["checkpoint_count"], 1)
        self.assertEqual(result["observed_high"], 100)
        self.assertNotEqual(result["direction"], "stable")

    def test_milestones_range_event_provenance_and_related_player(self):
        reader = _Reader([
            _row("a", "2026-01-01T00:00:00+00:00", 100, ("season_start",)),
            {**_row("b", "2026-04-01T00:00:00+00:00", 180, ("nfl_draft",)),
             "related_asset_ids": ("player:2",)},
            _row("c", "2026-07-01T00:00:00+00:00", 140, ("material_market_state",)),
        ])
        result = MarketTrendService(reader).trend_for_asset(
            "player:1", 200, as_of="2026-09-01T00:00:00+00:00",
        )
        self.assertEqual((result["observed_low"], result["observed_high"]), (100, 180))
        self.assertEqual(result["milestones"]["season_start"]["change"], 100)
        self.assertEqual(result["checkpoints"][1]["related_asset_ids"], ("player:2",))
        self.assertTrue(result["provenance"]["sparse_observations"])
        self.assertEqual(result["provenance"]["provider_calls"], 0)

    def test_global_trend_is_independent_of_league_liquidity(self):
        rows = [_row("a", "2026-01-01T00:00:00+00:00", 100), _row("b", "2026-04-01T00:00:00+00:00", 140)]
        low = {"league_id": "L1", "transaction_count": 1, "recent_transaction_count": 0,
               "ownership_turnover_count": 1, "distinct_franchises": 1,
               "last_transaction_at": "2026-02-01T00:00:00+00:00", "confidence": "low", "availability": "available"}
        a = MarketTrendService(_Reader(rows, low)).trend_for_asset("player:1", 180, league_id="L1", as_of="2026-09-01T00:00:00+00:00")
        b = MarketTrendService(_Reader(rows)).trend_for_asset("player:1", 180, league_id="L2", as_of="2026-09-01T00:00:00+00:00")
        self.assertEqual((a["direction"], a["magnitude"]), (b["direction"], b["magnitude"]))
        self.assertEqual(a["league_liquidity"]["confidence"], "low")
        self.assertIsNone(b["league_liquidity"])

    def test_generation_aware_cache_is_deterministic_and_bounded(self):
        reader = _Reader([_row("a", "2026-01-01T00:00:00+00:00", 100), _row("b", "2026-02-01T00:00:00+00:00", 200)])
        service = MarketTrendService(reader, cache_limit=2)
        first = service.trend_for_asset("player:1", 250, generation="g1", as_of="2026-09-01T00:00:00+00:00")
        second = service.trend_for_asset("player:1", 250, generation="g1", as_of="2026-09-01T00:00:00+00:00")
        self.assertEqual(first, second)
        self.assertEqual(reader.calls, 1)
        service.trend_for_asset("player:1", 250, generation="g2", as_of="2026-09-01T00:00:00+00:00")
        self.assertEqual(reader.calls, 2)

    def test_default_current_boundary_is_stable_and_evidence_driven(self):
        rows = [
            _row("a", "2026-01-01T00:00:00+00:00", 100),
            _row("b", "2026-02-01T00:00:00+00:00", 120),
        ]
        service = MarketTrendService(_Reader(rows))
        first = service.trend_for_asset(
            "player:1", 140, current_evidence_at="2026-03-01T00:00:00+00:00",
        )
        second = service.trend_for_asset(
            "player:1", 140, current_evidence_at="2026-03-01T00:00:00+00:00",
        )
        self.assertEqual(first, second)
        self.assertEqual(first["as_of"], "2026-03-01T00:00:00+00:00")

    def test_current_boundary_advances_only_with_asset_evidence(self):
        reader = _Reader([
            _row("a", "2026-01-01T00:00:00+00:00", 100),
            _row("b", "2026-02-01T00:00:00+00:00", 120),
        ])
        service = MarketTrendService(reader)
        first = service.trend_for_asset(
            "player:1", 140, generation="g1",
            current_evidence_at="2026-03-01T00:00:00+00:00",
        )
        unrelated_generation = service.trend_for_asset(
            "player:1", 140, generation="g2",
            current_evidence_at="2026-03-01T00:00:00+00:00",
        )
        advanced = service.trend_for_asset(
            "player:1", 150, generation="g3",
            current_evidence_at="2026-04-01T00:00:00+00:00",
        )
        self.assertEqual(first["as_of"], unrelated_generation["as_of"])
        self.assertEqual(advanced["as_of"], "2026-04-01T00:00:00+00:00")
        self.assertNotEqual(first["magnitude"], advanced["magnitude"])

    def test_default_without_current_or_historical_evidence_is_stable(self):
        service = MarketTrendService(_Reader())
        first = service.trend_for_asset("pick:2028:1:1", None)
        second = service.trend_for_asset("pick:2028:1:1", None)
        self.assertEqual(first, second)
        self.assertEqual(first["as_of"], "1970-01-01T00:00:00+00:00")

    def test_compact_summary_omits_deep_private_and_checkpoint_data(self):
        reader = _Reader([_row("a", "2026-01-01T00:00:00+00:00", 100), _row("b", "2026-02-01T00:00:00+00:00", 120)])
        result = MarketTrendService(reader).trend_for_asset(
            "player:1", 140, compact=True, as_of="2026-09-01T00:00:00+00:00",
        )
        self.assertNotIn("checkpoints", result)
        self.assertNotIn("league_liquidity", result)
        self.assertEqual(result["direction"], "rising")

    def test_compact_serialization_is_byte_identical_across_processes(self):
        script = """
import json
from src.core.market_trends.models import MarketTrend, TrendDirection
trend = MarketTrend(
    asset_id='player:1', current_value=140.0,
    as_of='2026-03-01T00:00:00+00:00', direction=TrendDirection.RISING,
    magnitude=40.0, magnitude_band='moderate', horizon='59_days',
    confidence='medium', confidence_score=65, evidence_coverage='partial',
    checkpoint_count=2, latest_checkpoint_age_days=29,
    observed_high=120.0, observed_low=100.0, volatility=0.0,
    volatility_band='stable',
)
print(json.dumps(trend.public(compact=True), separators=(',', ':')))
"""
        outputs = [
            subprocess.check_output(
                [sys.executable, "-c", script], text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            ).strip()
            for seed in ("1", "987654")
        ]
        self.assertEqual(outputs[0].encode(), outputs[1].encode())
        self.assertEqual(
            tuple(json.loads(outputs[0])),
            (
                "asset_id", "direction", "magnitude", "magnitude_band",
                "horizon", "confidence", "checkpoint_count", "as_of",
                "schema_version", "method_version",
            ),
        )

    def test_canonical_store_read_is_bounded_private_and_non_writing(self):
        with TemporaryDirectory() as temporary:
            store = IntelligenceCheckpointStore(Path(temporary) / "memory.sqlite3")
            for index, (stamp, value, roster) in enumerate((
                ("2026-01-01T00:00:00+00:00", 100, "1"),
                ("2026-06-01T00:00:00+00:00", 180, "2"),
            )):
                checkpoint = IntelligenceCheckpoint(
                    checkpoint_id=f"cp-{index}", asset_id="player:1", asset_type="player",
                    timestamp=stamp, season=2026, trigger_type=CheckpointTrigger.TRADE_EXECUTION,
                    provenance_type=ProvenanceType.LIVE_CAPTURED, league_id="league-a",
                    roster_id=roster, market_value=value, confidence=80,
                    evidence_completeness=EvidenceCompleteness.COMPLETE,
                    model_version="test", related_event_id=f"trade-{index}",
                )
                store.put_sparse(
                    checkpoint, market_context_id="player:global",
                    provider_evidence=(SourceObservation(
                        provider="ProviderA", raw_value=value, normalized_value=value,
                        observed_at=stamp, source_identity=f"source-{index}",
                        temporal_distance_seconds=0,
                    ),),
                )
            before = store.market_memory_health()
            evidence = store.market_trend_evidence(
                asset_ids=("player:1",), league_id="league-a",
                as_of="2026-09-01T00:00:00+00:00",
            )["player:1"]
            after = store.market_memory_health()
            self.assertEqual(len(evidence["observations"]), 2)
            self.assertEqual(evidence["liquidity"]["transaction_count"], 2)
            self.assertEqual(evidence["liquidity"]["distinct_franchises"], 2)
            self.assertNotIn("trade_execution", evidence["observations"][0]["reason_codes"])
            self.assertEqual(before["observation_count"], after["observation_count"])
            self.assertEqual(before["reference_count"], after["reference_count"])


if __name__ == "__main__":
    unittest.main()
