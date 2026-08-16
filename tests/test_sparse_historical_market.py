"""v1.10.31 sparse historical trade market matching regressions."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from threading import Thread

from src.core.intelligence_memory.historical_resolver import (
    HistoricalMarketResolver, HistoricalProviderCache, PersistenceContext,
    persistence_decision,
)
from src.core.intelligence_memory.historical_providers import DynastyProcessHistoricalProvider
from src.core.intelligence_memory.trade_resolution import HistoricalTradeResolutionService
from src.core.intelligence_memory.market import select_historical_market
from src.core.intelligence_memory.market_memory import market_context_id
from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, EvidencePersistenceDecision,
    IntelligenceCheckpoint, ProvenanceType, SourceObservation,
)
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.triggers import trade_assessment


class Provider:
    provider_id = "dynastyprocess"

    def __init__(self, observations=()):
        self.rows = tuple(observations)
        self.calls = 0

    def observations(self, **_context):
        self.calls += 1
        return self.rows


def source(value=7000, observed_at="2023-10-01T00:00:00+00:00"):
    return SourceObservation(
        provider="dynastyprocess", raw_value=value, normalized_value=value,
        observed_at=observed_at, source_identity=f"snapshot:{observed_at}:{value}",
        temporal_distance_seconds=None,
    )


def checkpoint(asset_id="player:10213", league_id="A", event_id="trade-1"):
    return IntelligenceCheckpoint(
        checkpoint_id=f"cp:{league_id}:{asset_id}:{event_id}", asset_id=asset_id,
        asset_type="player", timestamp="2023-10-03T00:00:00+00:00", season=2023,
        trigger_type=CheckpointTrigger.TRADE_EXECUTION,
        provenance_type=ProvenanceType.UNAVAILABLE, league_id=league_id,
        market_value=None, confidence=0,
        evidence_completeness=EvidenceCompleteness.UNAVAILABLE,
        model_version="1.10.31", related_event_id=event_id,
    )


class SparseHistoricalResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = IntelligenceCheckpointStore(Path(self.temp.name) / "memory.sqlite3")
        self.context = market_context_id(asset_type="player", scoring_profile_id="ignored")

    def tearDown(self):
        self.temp.cleanup()

    def test_ephemeral_evidence_is_not_persisted(self):
        provider = Provider((source(),))
        resolver = HistoricalMarketResolver(self.store, (provider,))
        result = resolver.resolve(
            asset_id="player:10213", asset_type="player", market_context_id=self.context,
            occurred_at="2023-10-03T00:00:00+00:00",
            persistence=PersistenceContext("inspection", future_access_guaranteed=True),
        )
        self.assertEqual(result.persistence, EvidencePersistenceDecision.EPHEMERAL_ONLY)
        self.assertEqual(self.store.market_memory_health()["observation_count"], 0)

    def test_trade_evidence_is_preserved_once_and_reused_across_leagues(self):
        provider = Provider((source(),))
        resolver = HistoricalMarketResolver(self.store, (provider,))
        policy = PersistenceContext("trade_execution")
        first, _, created, reference = resolver.resolve_checkpoint(
            checkpoint(), market_context_id=self.context, persistence=policy,
        )
        self.assertTrue(created)
        self.assertTrue(reference)
        second, _, created_again, second_reference = resolver.resolve_checkpoint(
            checkpoint(league_id="B", event_id="trade-2"),
            market_context_id=self.context, persistence=policy,
        )
        self.assertEqual(second.persistence, EvidencePersistenceDecision.ALREADY_PRESERVED)
        self.assertFalse(created_again)
        self.assertTrue(second_reference)
        self.assertEqual(first.observation_id, second.observation_id)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(self.store.market_memory_health()["observation_count"], 1)

    def test_cache_is_global_bounded_disposable_and_omits_league(self):
        provider = Provider((source(),))
        cache = HistoricalProviderCache(ttl_seconds=60, maximum_entries=1)
        resolver = HistoricalMarketResolver(self.store, (provider,), cache=cache)
        args = dict(asset_id="player:1", asset_type="player", market_context_id=self.context,
                    occurred_at="2023-10-03T00:00:00+00:00",
                    persistence=PersistenceContext("inspection", True))
        resolver.resolve(**args)
        resolver.resolve(**args)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(cache.health()["ownership"], "disposable_global_provider_cache")
        cache.clear()
        self.assertEqual(cache.health()["entries"], 0)

    def test_later_evidence_and_current_values_are_unavailable(self):
        provider = Provider((source(observed_at="2023-10-04T00:00:00+00:00"),))
        result = HistoricalMarketResolver(self.store, (provider,)).resolve(
            asset_id="player:1", asset_type="player", market_context_id=self.context,
            occurred_at="2023-10-03T00:00:00+00:00",
            persistence=PersistenceContext("trade_execution"),
        )
        self.assertFalse(result.available)
        self.assertEqual(result.persistence, EvidencePersistenceDecision.UNAVAILABLE)

    def test_pick_requires_legitimate_generic_pick_evidence(self):
        selected = select_historical_market(
            [source(value=2500)], "2023-10-03T00:00:00+00:00",
        )
        self.assertIsNotNone(selected.value)
        missing = HistoricalMarketResolver(self.store).resolve(
            asset_id="pick:2025:1:R1", asset_type="future_pick",
            market_context_id=market_context_id(
                asset_type="future_pick", scoring_profile_id=None,
            ), occurred_at="2023-10-03T00:00:00+00:00",
            persistence=PersistenceContext("trade_execution"),
        )
        self.assertFalse(missing.available)

    def test_partial_trade_never_counts_missing_asset_as_zero(self):
        valued = replace(
            checkpoint(), market_value=7000, confidence=70,
            provenance_type=ProvenanceType.HISTORICAL_SOURCE_BACKFILL,
            evidence_completeness=EvidenceCompleteness.COMPLETE,
        )
        result = trade_assessment({"one": (valued, checkpoint(asset_id="pick:2025:1:R1")), "two": (valued,)})
        self.assertEqual(result.status, EvidenceCompleteness.PARTIAL)
        self.assertIsNone(result.side_totals["one"])
        self.assertFalse(result.process_grade_eligible)
        self.assertEqual(result.coverage_ratio, 2 / 3)
        self.assertEqual(result.missing_asset_ids, ("pick:2025:1:R1",))
        self.assertGreater(result.confidence, 0)

    def test_concurrent_preservation_creates_one_observation(self):
        provider = Provider((source(),))
        results = []
        def run(index):
            resolver = HistoricalMarketResolver(self.store, (provider,))
            results.append(resolver.resolve_checkpoint(
                checkpoint(league_id=f"L{index}", event_id=f"T{index}"),
                market_context_id=self.context,
                persistence=PersistenceContext("trade_execution"),
            ))
        threads = [Thread(target=run, args=(index,)) for index in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(self.store.market_memory_health()["observation_count"], 1)
        self.assertEqual(sum(int(row[2]) for row in results), 1)

    def test_persistence_policy_is_central_and_auditable(self):
        available = select_historical_market((source(),), "2023-10-03T00:00:00+00:00")
        self.assertEqual(
            persistence_decision(available, PersistenceContext("trade_execution")),
            EvidencePersistenceDecision.PRESERVE_GLOBAL,
        )
        self.assertEqual(
            persistence_decision(available, PersistenceContext("inspection", True)),
            EvidencePersistenceDecision.EPHEMERAL_ONLY,
        )

    def test_dynastyprocess_snapshot_matches_player_and_generic_pick_without_disk_archive(self):
        values = (
            '"player","value_2qb","fp_id"\n'
            '"Alpha Player",7000,"10"\n'
            '"2027 Early 1st",3000,NA\n'
            '"2027 Mid 1st",2500,NA\n'
            '"2027 Late 1st",2000,NA\n'
        )
        ids = '"fantasypros_id","sleeper_id"\n"10","100"\n'
        provider = DynastyProcessHistoricalProvider(
            get_json=lambda _url, _params: [{
                "sha": "a" * 40,
                "commit": {"committer": {"date": "2023-10-01T00:00:00Z"}},
            }],
            get_text=lambda url: ids if url.endswith("db_playerids.csv") else values,
        )
        player = provider.observations(
            asset_id="player:100", asset_type="player", market_context_id=self.context,
            at_or_before="2023-10-03T00:00:00Z",
        )
        pick = provider.observations(
            asset_id="pick:2027:1:R1", asset_type="future_pick", market_context_id=self.context,
            at_or_before="2023-10-03T00:00:00Z",
        )
        self.assertEqual(player[0].normalized_value, 7000)
        self.assertEqual(pick[0].normalized_value, 2500)
        self.assertEqual(provider.health()["permanent_snapshot_bytes"], 0)

    def test_trade_service_reads_canonical_facts_and_persists_no_league_snapshot(self):
        provider = Provider((source(),))
        resolver = HistoricalMarketResolver(self.store, (provider,))
        service = HistoricalTradeResolutionService(resolver)
        class History:
            def records(self, league_id, entity_type, limit):
                self.query = (league_id, entity_type, limit)
                return 1, [{
                    "source_record_id": "T1", "season": 2023,
                    "occurred_at": "2023-10-03T00:00:00+00:00",
                    "payload": {"adds": {"10213": 1}, "drops": {"10213": 2}},
                }]
        history = History()
        summary = service.run(history, "L")
        self.assertEqual(summary.completed_trades, 1)
        self.assertEqual(summary.fully_valued, 1)
        self.assertEqual(resolver.health()["per_league_permanent_historical_market_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
