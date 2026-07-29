"""Regression coverage for the single competitive-window contract."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from src.core.competitive_window import (
    COMPETITIVE_WINDOW_CONTRACT_VERSION,
    CompetitiveWindowClassification,
    build_competitive_window,
)
from src.core.intelligence import (
    IntelligenceCache,
    IntelligenceOrchestrator,
    IntelligenceRegistry,
)
from tests.test_trade_intelligence import fixture_data


class CompetitiveWindowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.orchestrator = IntelligenceOrchestrator(
            IntelligenceRegistry(),
            IntelligenceCache(default_ttl=60),
        )

    def test_contract_is_complete_and_explainable(self) -> None:
        contract = build_competitive_window(
            current_strength=90,
            overall_strength=85,
            future_strength=70,
            depth=65,
            youth=55,
            draft_capital=60,
            risk=20,
            confidence=88,
            elite_assets=3,
            starter_strength=92,
        )
        self.assertEqual(
            contract.classification,
            CompetitiveWindowClassification.ELITE_CONTENDER,
        )
        self.assertEqual(contract.version, COMPETITIVE_WINDOW_CONTRACT_VERSION)
        self.assertTrue(contract.generated_at)
        self.assertTrue(contract.reasons)
        self.assertTrue(contract.strengths)
        self.assertTrue(contract.weaknesses)
        for score in (
            contract.championship_score,
            contract.playoff_score,
            contract.rebuild_score,
            contract.confidence,
        ):
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_every_consumer_shares_the_exact_contract(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        contract = result.decision.competitive_window
        self.assertIs(contract, result.roster.team_intelligence[1].competitive_window)
        self.assertIs(
            contract,
            result.front_office_model.reports[1].competitive_window,
        )
        self.assertIs(contract, result.recommendation.competitive_window)
        self.assertTrue(
            all(dossier.competitive_window is contract for dossier in result.trades)
        )

    def test_all_rosters_have_no_contradictory_classification(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        for roster_id, decision in result.decisions.items():
            expected = result.roster.team_intelligence[
                roster_id
            ].competitive_window.classification
            self.assertEqual(decision.competitive_window.classification, expected)
            self.assertEqual(
                result.front_office_model.reports[
                    roster_id
                ].competitive_window.classification,
                expected,
            )

    def test_canonical_computation_runs_once_per_roster(self) -> None:
        import src.core.team_intelligence.engine as engine

        with patch.object(
            engine,
            "build_competitive_window",
            wraps=engine.build_competitive_window,
        ) as canonical:
            result = self.orchestrator.analyze(self.data, 1)
        self.assertEqual(canonical.call_count, len(result.decisions))

    def test_execution_order_precedes_trade_and_recommendation(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        order = tuple(result.timings_ms)
        self.assertLess(order.index("player_value_projection"), order.index("roster_intelligence"))
        self.assertLess(order.index("roster_intelligence"), order.index("trade_intelligence"))

    def test_api_serializes_the_same_contract(self) -> None:
        async def noop() -> None:
            return None

        async def sync(**kwargs):
            return {}

        state = {"data": self.data}
        app = FastAPI()
        app.include_router(
            create_api_router(
                ensure_fresh=noop,
                require_data=lambda: self.data,
                sync_sleeper=sync,
                state=state,
                league_id="league-1",
            )
        )
        response = TestClient(app).get("/api/intelligence?front_office=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["competitive_window"]["classification"],
            payload["roster"]["team_intelligence"]["1"]["competitive_window"][
                "classification"
            ],
        )

    def test_golden_classification_boundaries_remain_stable(self) -> None:
        cases = (
            (95, 90, 80, "Elite Contender"),
            (75, 70, 60, "Contender"),
            (60, 55, 55, "Playoff Team"),
            (45, 45, 55, "Re-tooling"),
            (35, 35, 60, "Rebuilding"),
            (20, 20, 25, "Full Rebuild"),
        )
        for current, overall, future, expected in cases:
            with self.subTest(expected=expected):
                contract = build_competitive_window(
                    current_strength=current,
                    overall_strength=overall,
                    future_strength=future,
                    depth=50,
                    youth=50,
                    draft_capital=50,
                    risk=50,
                    confidence=75,
                )
                self.assertEqual(contract.classification.value, expected)


if __name__ == "__main__":
    unittest.main()
