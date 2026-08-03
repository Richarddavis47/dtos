from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.valuation import create_valuation_router
from src.core.intelligence.serialization import recommendation_contract
from src.core.brain import brain_service
from src.core.provider_network import build_provider_network
from src.core.valuation_intelligence import build_valuation_intelligence
from tests.test_provider_network import fixture


class BrainIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data, self.state = fixture()
        build_provider_network(self.data, self.state)
        build_valuation_intelligence(self.data, self.state)

    def test_all_consumers_receive_the_identical_canonical_asset(self) -> None:
        brain = brain_service(self.data)
        expected = brain.asset("player:1")
        for consumer in ("Team Headquarters", "FOIS", "Trade Intelligence", "Player Dossier"):
            decision = brain.decision(consumer, ("1",))
            self.assertIs(decision.assets[0], expected)
            self.assertEqual(decision.assets[0]["valuation_layers"], expected["valuation_layers"])
            self.assertEqual(decision.assets[0]["scores"], expected["scores"])
            self.assertEqual(decision.assets[0]["explanation"], expected["explanation"])

    def test_brain_reads_cache_without_network_or_recalculation(self) -> None:
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            first = brain_service(self.data).asset("1")
            second = brain_service(self.data).asset("player:1")
        self.assertEqual(first, second)
        self.assertEqual(self.data["valuation_intelligence"]["safety"]["external_requests_during_build"], 0)

    def test_decision_confidence_is_distinct_and_explainable(self) -> None:
        brain = brain_service(self.data)
        decision = brain.decision("Trade Intelligence", ("1", "2"), trade_complexity=5)
        self.assertNotEqual(decision.confidence.value, decision.confidence.evidence_confidence)
        self.assertEqual(len(decision.confidence.rationale), 4)
        self.assertGreater(decision.confidence.complexity_penalty, 0)

    def test_migration_and_health_have_no_legacy_or_duplicate_consumers(self) -> None:
        brain = brain_service(self.data)
        self.assertEqual(brain.migration()["legacy_consumer_count"], 0)
        self.assertEqual(brain.migration()["duplicate_calculation_count"], 0)
        self.assertFalse(brain.health()["synchronization"]["request_time_recalculation"])

    def test_public_contracts_are_stable_and_missing_assets_are_explicit(self) -> None:
        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(ensure_fresh=ready, require_data=lambda: self.data, state=self.state))
        client = TestClient(app)
        for route in ("/api/brain", "/api/brain/health", "/api/brain/migration", "/api/brain/assets/player:1", "/api/brain/timeline/player:1"):
            self.assertEqual(client.get(route).status_code, 200, route)
        self.assertEqual(client.get("/api/brain/assets/not-real").status_code, 404)

    def test_missing_brain_recommendation_is_explicit_not_silently_omitted(self) -> None:
        contract = recommendation_contract(None, None)
        self.assertEqual(contract["availability"], "unavailable")
        self.assertIn("decision_confidence", contract)
        self.assertIn("brain_snapshot_id", contract)
        self.assertTrue(contract["decision_provenance"])


if __name__ == "__main__":
    unittest.main()
