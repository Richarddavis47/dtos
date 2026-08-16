"""FOIS integration coverage for canonical historical trade occurrence time."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from src.core.fois.facts import TradeFact
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


PROCESS_EVIDENCE = {
    "status": "available",
    "definitive_checkpoint_ids": ["checkpoint-1"],
    "excluded_checkpoint_ids": [],
    "confidence_multiplier": 1.0,
    "completeness": 100.0,
    "unavailable_values": 0,
    "reconstructed_is_definitive": False,
}


class FOISTradeFactTimestampTests(unittest.IsolatedAsyncioTestCase):
    def test_constructor_accepts_and_normalizes_canonical_occurrence_time(self) -> None:
        fact = TradeFact(
            "trade-1", 2025, None,
            occurred_at="2025-08-24T22:00:45.048-04:00",
            process_evidence=PROCESS_EVIDENCE,
        )

        self.assertEqual(fact.occurred_at, "2025-08-25T02:00:45.048000Z")
        self.assertEqual(fact.process_evidence, PROCESS_EVIDENCE)

    def test_missing_or_invalid_time_remains_unavailable(self) -> None:
        missing = TradeFact("trade-1", 2025, None, occurred_at=None)
        invalid = TradeFact("trade-2", 2025, None, occurred_at="not-a-time")
        naive = TradeFact("trade-3", 2025, None, occurred_at="2025-08-25T02:00:45")

        self.assertIsNone(missing.occurred_at)
        self.assertIsNone(invalid.occurred_at)
        self.assertIsNone(naive.occurred_at)

    def test_serialization_round_trip_preserves_time_identity_and_evidence(self) -> None:
        original = TradeFact(
            "trade-1", 2025, None,
            occurred_at="2025-08-25T02:00:45Z",
            process_evidence=PROCESS_EVIDENCE,
        )

        restored = TradeFact(**asdict(original))

        self.assertEqual(restored, original)
        self.assertEqual(restored.transaction_id, "trade-1")
        self.assertEqual(restored.occurred_at, "2025-08-25T02:00:45Z")

    async def test_exact_production_generation_path_accepts_historical_trade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(
                FOISRepository(Path(directory) / "fois.sqlite3"),
            )
            data = {
                "league": {"league_id": "league", "season": "2026"},
                "teams": [{
                    "roster_id": 1, "owner_id": "owner", "owner": "GM",
                    "players": [],
                }],
                "fois_history": {
                    "1": {
                        "seasons": [],
                        "trades": [{
                            "transaction_id": "trade-1",
                            "season": 2025,
                            "occurred_at": "2025-08-25T02:00:45Z",
                            "strategically_productive": None,
                            "market_overpay_percent": None,
                            "championship_outlook_delta": None,
                            "partner_id": "2",
                            "process_evidence": PROCESS_EVIDENCE,
                        }],
                    },
                },
            }

            scores = await service.generate(data)

            self.assertEqual(service.status()["state"], "complete")
            self.assertEqual(len(scores), 1)
            trading = next(
                row for row in scores[0].category_scores
                if row.category_key == "trading_asset_management"
            )
            transaction_time = next(
                row for row in trading.metric_scores
                if row.metric_key == "value_captured_at_transaction_time"
            )
            self.assertIsNone(transaction_time.raw_value)
            self.assertEqual(transaction_time.sample_size, 0)

    async def test_replay_is_idempotent_and_does_not_change_trade_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            service = FOISService(repository)
            trade = {
                "transaction_id": "trade-1", "season": 2025,
                "occurred_at": "2025-08-25T02:00:45Z",
                "strategically_productive": None,
                "process_evidence": PROCESS_EVIDENCE,
            }
            data = {
                "league": {"league_id": "league", "season": "2026"},
                "teams": [{"roster_id": 1, "owner_id": "owner", "players": []}],
                "fois_history": {"1": {"seasons": [], "trades": [trade]}},
            }

            first = await service.generate(data)
            replay = await service.generate(data)

            self.assertEqual(first[0].score_key, replay[0].score_key)
            self.assertEqual(repository.count(), 1)


if __name__ == "__main__":
    unittest.main()
