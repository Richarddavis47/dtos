"""v1.12.4 historical transaction intelligence regressions."""
from __future__ import annotations

import asyncio
import copy
import unittest
from dataclasses import replace

from src.core.historical_franchise_state import HistoricalFranchiseStateService
from src.core.historical_intelligence import (
    GlobalMarketCheckpoint, HistoricalIntelligenceService,
)
from src.core.historical_transaction_intelligence import (
    HistoricalTransactionIntelligenceService, OutcomeClassification,
    ProcessClassification,
)
from tests.test_historical_franchise_state import FixtureStore


def checkpoint(asset: str, when: str, value: float) -> GlobalMarketCheckpoint:
    return GlobalMarketCheckpoint.create(
        asset_id=asset, occurred_at=when, provider="market",
        normalized_value=value, confidence=90, classification="event_relevant",
        reason_codes=("trade",),
    )


class HistoricalTransactionIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FixtureStore()
        self.history = HistoricalIntelligenceService(self.store, (
            checkpoint("player-old", "2025-09-20T00:00:00Z", 5000),
            checkpoint("player-new", "2025-09-20T00:00:00Z", 6000),
            checkpoint("player-stay", "2025-09-20T00:00:00Z", 2000),
        ))
        self.states = HistoricalFranchiseStateService(self.history)
        self.service = HistoricalTransactionIntelligenceService(self.history, self.states)
        self.event = self.history.transaction_history("league-a")[0]
        self.as_of = "2025-12-31T00:00:00Z"

    def evaluate(self):
        return self.service.evaluate_trade("league-a", self.event.event_id, as_of=self.as_of)

    def test_bilateral_process_uses_canonical_event_and_step3_states(self) -> None:
        result = self.evaluate()
        self.assertEqual(result.event_id, self.event.event_id)
        self.assertEqual(len(result.sides), 2)
        self.assertEqual({side.franchise_id for side in result.sides}, set(self.event.franchise_ids))
        self.assertTrue(all(side.pre_state_id != side.post_state_id for side in result.sides))
        self.assertEqual(self.service.health()["raw_history_scans"], 0)
        self.assertEqual(self.service.health()["provider_calls"], 0)

    def test_explicit_trade_participants_exclude_unrelated_asset_destinations(self) -> None:
        store = FixtureStore()
        trade = next(row for row in store.rows if row["entity_type"] == "trade")
        trade["payload"]["adds"]["unrelated-player"] = 3
        history = HistoricalIntelligenceService(store)
        service = HistoricalTransactionIntelligenceService(
            history, HistoricalFranchiseStateService(history),
        )
        event = history.transaction_history("league-a")[0]
        result = service.evaluate_trade("league-a", event.event_id, as_of=self.as_of)
        self.assertEqual(
            {side.franchise_id for side in result.sides},
            {"league-a:franchise:1", "league-a:franchise:2"},
        )

    def test_backlog_reuses_one_season_index_instead_of_rescanning_per_trade(self) -> None:
        store = FixtureStore()
        template = next(row for row in store.rows if row["entity_type"] == "trade")
        for index in range(2, 22):
            row = copy.deepcopy(template)
            row["source_record_id"] = f"trade-{index}"
            row["record_key"] = f"cache:league-a:2025:trade:trade-{index}"
            row["occurred_at"] = f"2025-10-{index:02d}T12:00:00Z"
            store.rows.append(row)
        history = HistoricalIntelligenceService(store)
        states = HistoricalFranchiseStateService(history)
        service = HistoricalTransactionIntelligenceService(history, states)
        evaluations, metrics = service.evaluate_backlog(
            "league-a", limit=100, as_of=self.as_of,
        )
        self.assertEqual(len(evaluations), 21)
        self.assertTrue(all(len(row.sides) == 2 for row in evaluations))
        self.assertLessEqual(states.metrics()["source_record_queries"], 5)
        self.assertGreater(states.metrics()["cache_hits"], 0)
        self.assertEqual(metrics.provider_calls, 0)
        self.assertEqual(metrics.raw_history_scans, 0)

    def test_unknown_market_asset_is_not_zero_and_reduces_confidence(self) -> None:
        result = self.evaluate()
        side = next(row for row in result.sides if row.process.missing_asset_ids)
        self.assertIn("PICK-2027-R1-ORIG2", side.process.missing_asset_ids)
        self.assertGreater(side.process.known_incoming_value + side.process.known_outgoing_value, 0)
        self.assertLess(side.process.market_coverage_ratio, 1)
        self.assertNotEqual(side.process.confidence.value, "high")

    def test_future_market_evidence_cannot_change_process(self) -> None:
        first = self.evaluate()
        future_history = HistoricalIntelligenceService(self.store, (
            checkpoint("player-old", "2025-09-20T00:00:00Z", 5000),
            checkpoint("player-new", "2025-09-20T00:00:00Z", 6000),
            checkpoint("player-new", "2025-11-20T00:00:00Z", 50),
            checkpoint("player-stay", "2025-09-20T00:00:00Z", 2000),
        ))
        future = HistoricalTransactionIntelligenceService(
            future_history, HistoricalFranchiseStateService(future_history),
        ).evaluate_trade("league-a", future_history.transaction_history("league-a")[0].event_id, as_of=self.as_of)
        self.assertEqual(
            [(side.process.classification, side.process.known_incoming_value, side.process.known_outgoing_value) for side in first.sides],
            [(side.process.classification, side.process.known_incoming_value, side.process.known_outgoing_value) for side in future.sides],
        )

    def test_process_and_outcome_can_disagree_in_both_directions(self) -> None:
        result = self.evaluate()
        before, after = self.states.around_event("league-a", "1", self.event.event_id)
        sound = replace(
            result.sides[0].process, classification=ProcessClassification.SOUND,
        )
        poor = replace(
            result.sides[0].process, classification=ProcessClassification.POOR,
        )
        later_bad = replace(after, state_id="later-bad", roster_market_value=1, known_market_value=1)
        later_good = replace(after, state_id="later-good", roster_market_value=100_000, known_market_value=100_000)
        bad_outcome = self.service._outcome(replace(after, roster_market_value=10_000), later_bad, self.as_of)
        good_outcome = self.service._outcome(replace(after, roster_market_value=10_000), later_good, self.as_of)
        self.assertEqual((sound.classification, bad_outcome.classification), (ProcessClassification.SOUND, OutcomeClassification.NEGATIVE))
        self.assertEqual((poor.classification, good_outcome.classification), (ProcessClassification.POOR, OutcomeClassification.POSITIVE))
        self.assertEqual(before.league_id, after.league_id)

    def test_both_sides_are_not_forced_into_winner_loser_pair(self) -> None:
        result = self.evaluate()
        classifications = [side.process.classification for side in result.sides]
        self.assertFalse(
            ProcessClassification.STRONG in classifications
            and ProcessClassification.POOR in classifications,
        )

    def test_missing_projection_does_not_fabricate_lineup_delta(self) -> None:
        result = self.evaluate()
        dimensions = [dimension for side in result.sides for dimension in side.process.dimensions if dimension.name == "lineup_impact"]
        self.assertTrue(dimensions)
        self.assertTrue(any(not dimension.evidence_available for dimension in dimensions))
        self.assertTrue(any("fabricated" in dimension.explanation for dimension in dimensions if not dimension.evidence_available))

    def test_determinism_and_idempotent_backlog_reuse(self) -> None:
        first, metrics = self.service.evaluate_backlog("league-a", limit=10, as_of=self.as_of)
        second, replay = self.service.evaluate_backlog("league-a", limit=10, as_of=self.as_of)
        self.assertEqual(first, second)
        self.assertEqual(metrics.trades_discovered, 1)
        self.assertEqual(replay.reused, 1)
        self.assertEqual(self.service.health()["evaluations"], 1)

    def test_backlog_limit_is_bounded_and_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self.service.evaluate_backlog("league-a", limit=0)
        with self.assertRaises(ValueError):
            self.service.evaluate_backlog("league-a", limit=1001)

    def test_invalid_step3_state_blocks_grade(self) -> None:
        self.store.rows = [row for row in self.store.rows if row["entity_type"] not in {"league_season", "roster_snapshot"}]
        history = HistoricalIntelligenceService(self.store)
        service = HistoricalTransactionIntelligenceService(history, HistoricalFranchiseStateService(history))
        event = history.transaction_history("league-a")[0]
        result = service.evaluate_trade("league-a", event.event_id, as_of=self.as_of)
        self.assertTrue(all(side.process.classification is ProcessClassification.BLOCKED for side in result.sides))

    def test_multi_league_evaluations_remain_isolated(self) -> None:
        league_b = FixtureStore("league-b")
        combined = FixtureStore()
        combined.rows.extend(league_b.rows)
        history = HistoricalIntelligenceService(combined, (
            checkpoint("player-old", "2025-09-20T00:00:00Z", 5000),
            checkpoint("player-new", "2025-09-20T00:00:00Z", 6000),
        ))
        service = HistoricalTransactionIntelligenceService(history, HistoricalFranchiseStateService(history))
        a = service.evaluate_backlog("league-a", as_of=self.as_of)[0][0]
        b = service.evaluate_backlog("league-b", as_of=self.as_of)[0][0]
        self.assertNotEqual(a.evaluation_id, b.evaluation_id)
        self.assertTrue(all(side.franchise_id.startswith("league-a:") for side in a.sides))
        self.assertTrue(all(side.franchise_id.startswith("league-b:") for side in b.sides))

    def test_async_backlog_runs_off_event_loop(self) -> None:
        async def exercise() -> None:
            task = asyncio.create_task(self.service.evaluate_backlog_async("league-a", as_of=self.as_of))
            await asyncio.sleep(0)
            rows, metrics = await task
            self.assertEqual(len(rows), 1)
            self.assertEqual(metrics.provider_calls, 0)
        asyncio.run(exercise())

    def test_current_bilateral_engine_is_not_called_or_modified(self) -> None:
        result = self.evaluate()
        self.assertEqual(result.method_version, "historical-trade-process-outcome-1")
        self.assertNotIn("SMASH ACCEPT", str(result.private_contract()))


if __name__ == "__main__":
    unittest.main()
