"""Step 5 shared Front Office evidence integration regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.brain import brain_service
from src.core.fois.facts import TradeFact
from src.core.fois.facts import FOISFacts
from src.core.fois.engine import FOISEngine
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.fois.history import load_results_history
from src.core.front_office_evidence import assemble_front_office_evidence
from src.core.front_office_intelligence import build_league_model
from src.core.intelligence.context import build_context
from tests.test_trade_intelligence import fixture_data
from tests.test_historical_franchise_state import FixtureStore


def trade(
    transaction_id: str, *, owner: str = "owner-1",
    process: str = "sound_process", outcome: str = "positive_outcome",
    confidence: str = "high", maturity: str = "mature",
) -> TradeFact:
    process_score = (
        None if process in {
            "insufficient_evidence", "evaluation_blocked_invalid_historical_state",
        } else 80
    )
    outcome_score = (
        None if outcome in {"insufficient_evidence", "outcome_not_yet_mature"}
        else 75
    )
    return TradeFact(
        transaction_id, 2025, None, process_score=process_score,
        outcome_score=outcome_score,
        partner_id="2", occurred_at="2025-10-01T00:00:00Z", owner_id=owner,
        process_classification=process, process_confidence=confidence,
        outcome_classification=outcome, outcome_confidence=confidence,
        outcome_maturity=maturity, history_generation="history-a",
        market_generation="market-a", evidence_references=(f"event:{transaction_id}",),
    )


class SharedEvidenceContractTests(unittest.TestCase):
    def test_step4_contract_reaches_fois_history_adapter(self) -> None:
        metrics = {}
        history = load_results_history(
            FixtureStore(), "league-a", metrics=metrics,
        )
        for roster_id in ("1", "2"):
            row = history[roster_id]["trades"][0]
            self.assertIsNotNone(row["process_classification"])
            self.assertIsNotNone(row["outcome_classification"])
            self.assertEqual(row["history_generation"], "history-generation-1:league-a")
            self.assertTrue(row["evidence_references"])
        self.assertEqual(metrics["step4_evaluations_loaded"], 1)
        self.assertEqual(metrics["step4_evaluations_recomputed"], 1)
        self.assertGreater(metrics["derived_cache_hits"], 0)
        self.assertEqual(metrics["provider_calls"], 0)
        self.assertEqual(metrics["raw_history_scans"], 0)

    def test_process_and_outcome_remain_separate_and_deterministic(self) -> None:
        first = assemble_front_office_evidence(
            league_id="league-a", franchise_id="league-a:franchise:1",
            gm_id="owner-1", trades=(trade("b"), trade("a", outcome="negative_outcome")),
        )
        repeated = assemble_front_office_evidence(
            league_id="league-a", franchise_id="league-a:franchise:1",
            gm_id="owner-1", trades=(trade("a", outcome="negative_outcome"), trade("b")),
        )
        self.assertEqual(first, repeated)
        self.assertEqual(first.process_distribution, {"sound_process": 2})
        self.assertEqual(
            first.outcome_distribution,
            {"negative_outcome": 1, "positive_outcome": 1},
        )
        self.assertNotEqual(first.process_score, first.outcome_score)

    def test_incomplete_and_blocked_evidence_never_becomes_zero(self) -> None:
        summary = assemble_front_office_evidence(
            league_id="league-a", franchise_id="league-a:franchise:1",
            gm_id="owner-1", trades=(trade(
                "a", process="evaluation_blocked_invalid_historical_state",
                outcome="outcome_not_yet_mature", confidence="low",
                maturity="not_yet_mature",
            ),),
        )
        self.assertEqual(summary.evaluated_transaction_count, 0)
        self.assertEqual(summary.evidence_completeness, 0)
        self.assertIsNone(summary.process_score)
        self.assertIn("evaluation_blocked_invalid_historical_state", summary.process_distribution)

    def test_league_identity_is_part_of_semantic_identity(self) -> None:
        one = assemble_front_office_evidence(
            league_id="one", franchise_id="one:franchise:1", gm_id="gm",
            trades=(trade("a"),),
        )
        two = assemble_front_office_evidence(
            league_id="two", franchise_id="two:franchise:1", gm_id="gm",
            trades=(trade("a"),),
        )
        self.assertNotEqual(one.semantic_identity, two.semantic_identity)

    def test_fois_confidence_respects_step4_evidence_confidence(self) -> None:
        high_trades = tuple(trade(f"high-{index}") for index in range(10))
        low_trades = tuple(
            trade(f"low-{index}", confidence="low") for index in range(10)
        )
        high_summary = assemble_front_office_evidence(
            league_id="league-a", franchise_id="league-a:franchise:1",
            gm_id="owner-1", trades=high_trades,
        ).contract()
        low_summary = assemble_front_office_evidence(
            league_id="league-a", franchise_id="league-a:franchise:1",
            gm_id="owner-1", trades=low_trades,
        ).contract()
        high = FOISEngine().evaluate(FOISFacts(
            "league-a", "league-a:franchise:1", "owner-1", (),
            trades=high_trades, front_office_evidence=high_summary,
        ))
        low = FOISEngine().evaluate(FOISFacts(
            "league-a", "league-a:franchise:1", "owner-1", (),
            trades=low_trades, front_office_evidence=low_summary,
        ))
        def process_confidence(score) -> float:
            category = next(row for row in score.category_scores if row.category_key == "trading_asset_management")
            metric = next(row for row in category.metric_scores if row.metric_key == "value_captured_at_transaction_time")
            return metric.confidence
        self.assertLess(process_confidence(low), process_confidence(high))

    def test_front_office_uses_shared_evidence_without_history_scan(self) -> None:
        data = fixture_data()
        summary = assemble_front_office_evidence(
            league_id=str(data["league"]["league_id"]),
            franchise_id=f'{data["league"]["league_id"]}:franchise:1',
            gm_id="owner-1", trades=(trade("a"),),
        ).contract()
        data["front_office_evidence"] = {"1": summary, "2": summary, "3": summary}
        with patch(
            "src.core.history_context.store.CanonicalHistoryStore.records",
            side_effect=AssertionError("request-time history scan"),
        ):
            model = build_league_model(data)
        self.assertEqual(model.reports[1].activity.trades, 1)
        self.assertEqual(model.reports[1].front_office_evidence, summary)

    def test_brain_transports_evidence_without_changing_confidence(self) -> None:
        data = fixture_data()
        brain = brain_service(data)
        baseline = brain.decision("Recommendation Engine", ("1",))
        evidence = {"semantic_identity": "evidence-a", "process_score": 80}
        enriched = brain.decision(
            "Recommendation Engine", ("1",), front_office_evidence=evidence,
        )
        self.assertEqual(enriched.confidence, baseline.confidence)
        self.assertEqual(enriched.front_office_evidence, evidence)

    def test_shared_evidence_generation_invalidates_derived_read_cache_key(self) -> None:
        data = fixture_data()
        baseline = build_context(data, 1).snapshot_key
        data["front_office_evidence"] = {
            "1": {
                "league_id": str(data["league"]["league_id"]),
                "semantic_identity": "generation-a",
            },
        }
        first = build_context(data, 1).snapshot_key
        data["front_office_evidence"]["1"]["semantic_identity"] = "generation-b"
        second = build_context(data, 1).snapshot_key
        self.assertNotEqual(baseline, first)
        self.assertNotEqual(first, second)


class SharedEvidenceFOISIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_gm_does_not_inherit_prior_owner_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(FOISRepository(Path(directory) / "fois.sqlite3"))
            data = {
                "league": {"league_id": "league-a", "season": "2026"},
                "teams": [{"roster_id": 1, "owner_id": "owner-1", "owner": "One"}],
                "fois_history": {"1": {
                    "seasons": [], "drafts": [], "waivers": [],
                    "trades": [
                        trade("current").__dict__,
                        trade("prior", owner="owner-0").__dict__,
                    ],
                }},
            }
            scores = await service.generate(data)
        evidence = scores[0].front_office_evidence
        self.assertEqual(evidence["transaction_count"], 1)
        self.assertEqual(evidence["evidence_references"], ["event:current"])
        self.assertEqual(scores[0].trade_partner_count, 1)


if __name__ == "__main__":
    unittest.main()
