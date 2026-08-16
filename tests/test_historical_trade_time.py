from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore
from src.core.history_context.timestamps import canonical_transaction_timestamp


class HistoricalTradeTimeTests(unittest.TestCase):
    def test_sleeper_created_is_canonical_utc_and_precedes_status_updated(self) -> None:
        occurred, provenance = canonical_transaction_timestamp({
            "created": 1756087245048, "status_updated": 1756087302476,
        })
        self.assertEqual(occurred, "2025-08-25T02:00:45.048000Z")
        self.assertEqual(provenance["field"], "created")

    def test_status_updated_is_fallback_and_missing_is_not_fabricated(self) -> None:
        occurred, provenance = canonical_transaction_timestamp({"status_updated": 1701058277465})
        self.assertEqual(occurred, "2023-11-27T04:11:17.465000Z")
        self.assertEqual(provenance["field"], "status_updated")
        self.assertEqual(canonical_transaction_timestamp({})[0], None)
        self.assertEqual(canonical_transaction_timestamp({"created": "not-a-time"})[0], None)

    def test_naive_iso_is_rejected_and_aware_iso_is_utc(self) -> None:
        self.assertIsNone(canonical_transaction_timestamp({"created": "2025-01-01T12:00:00"})[0])
        occurred, _ = canonical_transaction_timestamp({"created": "2025-01-01T07:00:00-05:00"})
        self.assertEqual(occurred, "2025-01-01T12:00:00Z")

    def test_trade_and_asset_events_share_timestamp_without_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cached = cache.normalize("L", 2025, {
                "transactions": {"1": [{
                    "transaction_id": "T1", "type": "trade", "status": "complete",
                    "created": 1756087245048, "status_updated": 1756087302476,
                    "roster_ids": [1, 2], "adds": {"100": 1}, "drops": {"100": 2},
                    "draft_picks": [{"season": "2027", "round": 1, "roster_id": 2,
                                     "owner_id": 1, "previous_owner_id": 2}],
                }]},
            })
            cache.write(cached)
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                graph = HistoricalAssetGraph(store, "L", {})
                dossier = graph.trade_dossier("T1")
            self.assertIsNotNone(dossier)
            assert dossier is not None
            self.assertEqual(dossier["trade_id"], "TRADE-L-T1")
            self.assertEqual(dossier["occurred_at"], "2025-08-25T02:00:45.048000Z")
            self.assertTrue(dossier["asset_events"])
            self.assertTrue(all(
                row["occurred_at"] == dossier["occurred_at"]
                for row in dossier["asset_events"]
            ))
            self.assertTrue(all(row["completeness"] == "complete" for row in dossier["asset_events"]))

    def test_waiver_and_drop_events_inherit_transaction_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2024, {
                "transactions": {"2": [{
                    "transaction_id": "W1", "type": "waiver", "status": "complete",
                    "created": 1700000000000, "roster_ids": [3],
                    "adds": {"200": 3}, "drops": {"201": 3},
                }]},
            }))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                graph = HistoricalAssetGraph(store, "L", {})
                added = graph.events(asset_id="DTOS-P-200")
                dropped = graph.events(asset_id="DTOS-P-201")
            self.assertEqual(added[0]["occurred_at"], "2023-11-14T22:13:20Z")
            self.assertEqual(dropped[0]["occurred_at"], "2023-11-14T22:13:20Z")

    def test_trade_time_matching_uses_pre_event_observation_and_partial_coverage(self) -> None:
        class Memory:
            calls = []

            def observation_at_or_before(self, **query):
                self.calls.append(query)
                if query["asset_id"] != "player:100":
                    return None
                return SimpleNamespace(
                    observation_id="OBS-1", observed_at="2025-08-24T12:00:00Z",
                    canonical_value=700, provenance_type=SimpleNamespace(
                        value="historical_source_backfill",
                    ),
                )

        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2025, {
                "transactions": {"1": [{
                    "transaction_id": "T1", "type": "trade", "status": "complete",
                    "created": 1756087245048, "roster_ids": [1, 2],
                    "adds": {"100": 1, "101": 2}, "drops": {"100": 2, "101": 1},
                }]},
            }))
            memory = Memory()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                dossier = HistoricalAssetGraph(
                    CanonicalHistoryStore(), "L", {}, intelligence_store=memory,
                ).trade_dossier("T1")
            assert dossier is not None
            intelligence = dossier["trade_time_intelligence"]
            self.assertEqual(intelligence["coverage_state"], "partial")
            self.assertEqual(intelligence["valued_assets"], 1)
            self.assertEqual(intelligence["total_assets"], 2)
            self.assertEqual(intelligence["process_state"], "not_gradable")
            self.assertFalse(intelligence["unavailable_assets_are_zero"])
            self.assertTrue(all(
                call["event_at"] == dossier["occurred_at"] for call in memory.calls
            ))

    def test_matching_never_requests_or_substitutes_a_later_observation(self) -> None:
        class Memory:
            def observation_at_or_before(self, **query):
                self.event_at = query["event_at"]
                return None

        memory = Memory()
        row = {"occurred_at": "2022-01-01T00:00:00Z"}
        event = {"asset_id": "DTOS-P-100", "to_franchise_id": "L:franchise:1"}
        graph = HistoricalAssetGraph(
            CanonicalHistoryStore(), "L", {}, intelligence_store=memory,
        )
        result = graph._trade_time_intelligence(row, [event])
        self.assertEqual(memory.event_at, row["occurred_at"])
        self.assertEqual(result["coverage_state"], "unavailable")
        self.assertFalse(result["later_observation_substitution"])


if __name__ == "__main__":
    unittest.main()
