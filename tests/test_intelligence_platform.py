"""Cross-engine contracts for the unified Intelligence Integration Platform."""
from __future__ import annotations

import time
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from src.platform.validation import HttpEndpoint, validate_routes
from tests.test_trade_intelligence import fixture_data


class IntelligencePlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60))

    def test_all_four_registered_providers_produce_one_recommendation(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        self.assertEqual(self.orchestrator.registry.names(), ("decision", "asset", "front_office", "trade", "market", "player_value", "roster"))
        self.assertEqual(set(result.recommendation.sources), {"Decision Engine", "Asset Intelligence", "Trade Intelligence", "Front Office Intelligence", "Market Intelligence"})
        self.assertTrue(result.recommendation.evidence)
        self.assertTrue(result.recommendation.why)
        self.assertTrue(result.recommendation.why_not)
        self.assertTrue(result.recommendation.assumptions)
        self.assertTrue(result.recommendation.change_conditions)

    def test_cross_engine_evidence_and_outputs_are_consistent(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        sources = {item.source for item in result.recommendation.evidence}
        self.assertIn("Decision Engine", sources)
        self.assertIn("Asset Intelligence", sources)
        self.assertIn("Front Office Intelligence", sources)
        self.assertIn("Trade Intelligence", sources)
        self.assertEqual(result.decision.profile.roster_id, result.context.active_roster_id)
        self.assertEqual(result.front_office_model.reports[1].decision, result.decision)
        self.assertTrue(all(item.proposal.active_roster_id == 1 for item in result.trades))

    def test_shared_cache_reuses_result_and_improves_latency(self) -> None:
        started = time.perf_counter()
        first = self.orchestrator.analyze(self.data, 1)
        first_elapsed = time.perf_counter() - started
        started = time.perf_counter()
        second = self.orchestrator.analyze(self.data, 1)
        second_elapsed = time.perf_counter() - started
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertLess(second_elapsed, first_elapsed)
        self.assertGreater(self.orchestrator.cache.health()["hit_rate"], 0)

    def test_refresh_invalidates_cached_orchestration(self) -> None:
        self.orchestrator.analyze(self.data, 1)
        refreshed = self.orchestrator.analyze(self.data, 1, refresh=True)
        self.assertFalse(refreshed.cache_hit)
        self.assertGreater(self.orchestrator.cache.health()["invalidations"], 0)

    def test_platform_health_and_unified_api_are_additive(self) -> None:
        async def noop() -> None:
            return None

        async def sync(**kwargs):
            return {}

        state = {"data": self.data, "last_sync": "2026-07-21T00:00:00+00:00", "last_error": None, "syncing": False}
        app = FastAPI()
        app.include_router(create_api_router(ensure_fresh=noop, require_data=lambda: self.data, sync_sleeper=sync, state=state, league_id="league-1"))
        client = TestClient(app)
        health = client.get("/api/platform/health")
        intelligence = client.get("/api/intelligence?front_office=1")
        legacy = client.get("/api/status")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(set(health.json()["engines"]), {"decision", "asset", "front_office", "trade", "market", "player_value", "roster"})
        self.assertEqual(intelligence.status_code, 200)
        self.assertEqual(intelligence.json()["active_front_office"], 1)
        self.assertIn("recommendation", intelligence.json())
        self.assertEqual(legacy.status_code, 200)

    def test_health_exposes_cache_namespaces_and_engine_timings(self) -> None:
        self.orchestrator.analyze(self.data, 1)
        health = self.orchestrator.health({"data": self.data, "last_sync": "now", "last_error": None})
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["sleeper"]["status"], "connected")
        self.assertTrue({"league", "assets", "front_offices", "trades", "market", "player_values", "roster", "result"}.issubset(health["cache"]["namespaces"]))
        self.assertTrue({"decision_engine", "asset_intelligence", "front_office_intelligence", "trade_intelligence", "market_intelligence", "player_value_projection", "roster_intelligence", "orchestration_total"}.issubset(health["orchestration"]["last_timings_ms"]))

    def test_application_services_use_orchestrator_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in ("services/trade_intelligence.py", "services/front_office_intelligence.py", "services/team_headquarters.py", "services/asset_intelligence.py", "services/commissioner.py"):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertIn("intelligence_orchestrator", source, relative)
        self.assertNotIn("src.core.trade_intelligence import", (root / "services/trade_intelligence.py").read_text(encoding="utf-8"))
        self.assertNotIn("src.core.front_office_intelligence import", (root / "services/front_office_intelligence.py").read_text(encoding="utf-8"))

    def test_validation_is_available_as_platform_component(self) -> None:
        app = FastAPI()

        @app.get("/platform-check")
        async def platform_check():
            return {}

        result = validate_routes(app.routes, (HttpEndpoint("GET", "/platform-check"),))
        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
