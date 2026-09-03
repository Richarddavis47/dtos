"""Step 6 canonical GM Behavioral Intelligence regressions."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from src.core.fois.facts import TradeFact
from src.core.front_office_evidence import assemble_front_office_evidence
from src.core.gm_behavioral_intelligence import GMBehavioralIntelligenceService


def trade(
    identity: str, *, league: str = "league-a", owner: str = "gm-1",
    incoming: tuple[str, ...] = ("player:b",),
    outgoing: tuple[str, ...] = ("player:a", "player:c"),
    incoming_types: tuple[str, ...] = ("player",),
    outgoing_types: tuple[str, ...] = ("player", "player"),
    incoming_positions: tuple[str, ...] = ("QB",),
    outgoing_positions: tuple[str, ...] = ("RB", "WR"),
    value_in: float | None = 110.0, value_out: float | None = 100.0,
    window: str = "contending", partner: str = "gm-2",
    phase: str = "midseason", process: str = "sound_process",
    outcome: str = "positive_outcome", season: int = 2025,
) -> TradeFact:
    return TradeFact(
        identity, season, None, process_score=80, outcome_score=75,
        partner_id=partner, occurred_at=f"{season}-10-01T00:00:00Z",
        owner_id=owner, process_classification=process,
        process_confidence="high", outcome_classification=outcome,
        outcome_confidence="medium", outcome_maturity="mature",
        history_generation=f"{league}-history", market_generation="market-a",
        evidence_references=(f"event:{identity}",),
        incoming_asset_ids=incoming, outgoing_asset_ids=outgoing,
        incoming_asset_types=incoming_types, outgoing_asset_types=outgoing_types,
        incoming_positions=incoming_positions, outgoing_positions=outgoing_positions,
        known_incoming_value=value_in, known_outgoing_value=value_out,
        market_coverage_ratio=(1.0 if value_in is not None and value_out is not None else 0.0),
        competitive_window_at_trade=window, season_phase=phase,
    )


def profile(rows: tuple[TradeFact, ...], *, league: str = "league-a", gm: str = "gm-1"):
    evidence = assemble_front_office_evidence(
        league_id=league, franchise_id=f"{league}:franchise:1",
        gm_id=gm, trades=rows,
    )
    return GMBehavioralIntelligenceService().build_profile(
        evidence=evidence, trades=rows,
    )


def dimension(result, key: str):
    return next(row for row in result.dimensions if row.key == key)


class GMBehavioralIntelligenceTests(unittest.TestCase):
    def test_repeated_multi_asset_sales_support_consolidation(self) -> None:
        result = profile(tuple(trade(str(index)) for index in range(7)))
        self.assertEqual(dimension(result, "package_style").tendency, "consolidation")
        self.assertEqual(dimension(result, "package_style").sample_count, 7)

    def test_false_consolidator_stays_mixed(self) -> None:
        rows = tuple(trade(f"c-{i}") for i in range(3)) + tuple(trade(
            f"d-{i}", incoming=("a", "b"), outgoing=("c",),
            incoming_types=("player", "player"), outgoing_types=("player",),
        ) for i in range(3))
        self.assertEqual(dimension(profile(rows), "package_style").tendency, "mixed")

    def test_window_shift_is_preserved_not_flattened(self) -> None:
        rows = tuple(trade(
            f"r-{i}", window="rebuilding", incoming=("pick:a",), outgoing=("player:a",),
            incoming_types=("pick",), outgoing_types=("player",),
        ) for i in range(4)) + tuple(trade(
            f"c-{i}", window="contending", incoming=("player:b",), outgoing=("pick:b",),
            incoming_types=("player",), outgoing_types=("pick",),
        ) for i in range(4))
        counts = dimension(profile(rows), "window_dependent_behavior").supporting_counts
        self.assertEqual(counts["rebuilding:acquire_picks"], 4)
        self.assertEqual(counts["contending:acquire_players"], 4)

    def test_price_behavior_uses_only_priced_sample(self) -> None:
        rows = tuple(trade(f"p-{i}") for i in range(4)) + tuple(
            trade(f"u-{i}", value_in=None, value_out=None) for i in range(16)
        )
        price = dimension(profile(rows), "price_behavior")
        self.assertEqual(price.sample_count, 4)
        self.assertEqual(price.opportunity_count, 20)
        self.assertEqual(price.coverage, .2)
        self.assertEqual(price.confidence, "low")

    def test_process_and_outcome_remain_distinct(self) -> None:
        rows = tuple(trade(str(i), process="sound_process", outcome="negative_outcome") for i in range(6))
        result = profile(rows)
        self.assertEqual(result.process_distribution, {"sound_process": 6})
        self.assertEqual(result.outcome_distribution, {"negative_outcome": 6})

    def test_bilateral_frequency_is_traceable(self) -> None:
        result = profile(tuple(trade(str(i), partner="gm-9") for i in range(5)))
        bilateral = dimension(result, "bilateral_relationships")
        self.assertEqual(bilateral.supporting_counts, {"gm-9": 5})
        self.assertEqual(len(bilateral.evidence_references), 5)

    def test_manager_change_excludes_previous_owner(self) -> None:
        current = tuple(trade(f"new-{i}") for i in range(5))
        prior = tuple(trade(f"old-{i}", owner="gm-old") for i in range(8))
        result = profile(tuple(row for row in current + prior if row.owner_id == "gm-1"))
        self.assertEqual(result.transaction_count, 5)
        self.assertTrue(all("old-" not in ref for ref in result.evidence_references))

    def test_leagues_never_share_identity_or_cache(self) -> None:
        service = GMBehavioralIntelligenceService()
        rows = tuple(trade(str(i)) for i in range(5))
        one = assemble_front_office_evidence(league_id="one", franchise_id="one:franchise:1", gm_id="gm", trades=rows)
        two = assemble_front_office_evidence(league_id="two", franchise_id="two:franchise:1", gm_id="gm", trades=rows)
        self.assertNotEqual(service.build_profile(evidence=one, trades=rows).semantic_identity,
                            service.build_profile(evidence=two, trades=rows).semantic_identity)

    def test_no_evidence_produces_no_tendency(self) -> None:
        result = profile(())
        self.assertEqual(result.overall_confidence, "low")
        self.assertTrue(all(row.tendency == "insufficient_evidence" for row in result.dimensions))

    def test_deterministic_under_input_order(self) -> None:
        rows = tuple(trade(str(i)) for i in range(6))
        self.assertEqual(profile(rows), profile(tuple(reversed(rows))))

    def test_cache_reuses_same_generation_and_invalidates_changed_behavior(self) -> None:
        service = GMBehavioralIntelligenceService()
        rows = tuple(trade(str(i)) for i in range(5))
        first_evidence = assemble_front_office_evidence(league_id="l", franchise_id="l:franchise:1", gm_id="g", trades=rows)
        first = service.build_profile(evidence=first_evidence, trades=rows)
        self.assertIs(first, service.build_profile(evidence=first_evidence, trades=rows))
        changed = rows[:-1] + (trade("4", incoming=("a", "b"), outgoing=("c",), incoming_types=("player", "pick"), outgoing_types=("player",)),)
        changed_evidence = assemble_front_office_evidence(league_id="l", franchise_id="l:franchise:1", gm_id="g", trades=changed)
        second = service.build_profile(evidence=changed_evidence, trades=changed)
        self.assertNotEqual(first.semantic_identity, second.semantic_identity)
        self.assertEqual(service.health()["profiles_built"], 2)
        self.assertEqual(service.health()["cache_hits"], 1)

    def test_builder_never_calls_provider_or_history_store(self) -> None:
        rows = tuple(trade(str(i)) for i in range(5))
        with patch("src.core.history_context.store.CanonicalHistoryStore.records", side_effect=AssertionError("raw scan")):
            result = profile(rows)
        self.assertEqual(result.transaction_count, 5)

    def test_large_fixture_is_one_pass_and_bounded(self) -> None:
        service = GMBehavioralIntelligenceService()
        rows = tuple(trade(str(i), season=2020 + i % 6) for i in range(500))
        evidence = assemble_front_office_evidence(league_id="l", franchise_id="l:franchise:1", gm_id="g", trades=rows)
        result = service.build_profile(evidence=evidence, trades=rows)
        health = service.health()
        self.assertEqual(result.transaction_count, 500)
        self.assertEqual(health["aggregation_passes"], 1)
        self.assertEqual(health["evaluations_consumed"], 500)
        self.assertLess(len(str(result.contract())), 40_000)

    def test_contract_survives_json_persistence_without_shape_change(self) -> None:
        import json

        result = profile(tuple(trade(str(i)) for i in range(5)))
        contract = result.contract()
        self.assertEqual(contract, json.loads(json.dumps(contract)))
        self.assertIsInstance(contract["dimensions"], list)
        self.assertIsInstance(contract["evidence_references"], list)


if __name__ == "__main__":
    unittest.main()
