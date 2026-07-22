"""Live Data Platform provider, refresh, history, fallback, and boundary contracts."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from src.core.data_platform import DataEnvelope, DataPlatform, DataProvider, DataQuality, LicensingTier, ProviderMetadata, ProviderRegistry, ProviderStatus, SnapshotWarehouse, consensus, interpret_news, trend


def meta(name: str = "Fixture", category: str = "market", *, enabled: bool = True, live: bool = True, scheduled: bool = True) -> ProviderMetadata:
    return ProviderMetadata(name, category, "1", LicensingTier.PUBLIC_API, enabled, live, scheduled, 900, 3600)


class FixtureProvider(DataProvider):
    def __init__(self, name: str = "Fixture", value: float | None = 100, *, failure: str | None = None, enabled: bool = True) -> None:
        self.metadata = meta(name, enabled=enabled)
        self.value = value
        self.failure = failure

    def fetch(self, key: str, context: dict[str, object]) -> DataEnvelope:
        if self.failure:
            raise RuntimeError(self.failure)
        stamp = str(context.get("timestamp") or "2026-07-22T12:00:00+00:00")
        quality = DataQuality("good" if self.value is not None else "blocked", () if self.value is not None else ("Missing value",), 100 if self.value is not None else 0)
        return DataEnvelope(key, "market", self.value, self.metadata.name, self.metadata.name, stamp, "fresh", 90, "miss", "live", quality, ())


class DataPlatformTests(unittest.TestCase):
    def test_registry_supports_dynamic_registration_and_duplicate_protection(self) -> None:
        registry = ProviderRegistry()
        registry.register(FixtureProvider())
        self.assertEqual(registry.names(), ("Fixture",))
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(FixtureProvider())

    def test_provider_metadata_and_health_are_complete(self) -> None:
        platform = DataPlatform()
        platform.register(FixtureProvider())
        platform.fetch("Fixture", "p1", {"namespace": "league:1"})
        row = platform.health()["providers"]["Fixture"]
        self.assertEqual(row["status"], ProviderStatus.HEALTHY)
        self.assertEqual(row["licensing_tier"], LicensingTier.PUBLIC_API)
        self.assertIsNotNone(row["next_refresh"])
        self.assertGreaterEqual(row["confidence"], 1)

    def test_disabled_provider_is_explicit_and_independent(self) -> None:
        platform = DataPlatform()
        platform.register(FixtureProvider(enabled=False))
        result = platform.fetch("Fixture", "p1", {})
        self.assertEqual(result.retrieval_mode, "unavailable")
        self.assertIn("licensing", result.limitations[0])

    def test_scheduled_and_on_demand_refresh_are_independent(self) -> None:
        platform = DataPlatform()
        platform.register(FixtureProvider())
        schedules = platform.scheduled(in_season=True)
        refreshed = platform.refresh("market", {"namespace": "league:1"}, ("p1", "p2"))
        self.assertTrue(schedules[0]["due"])
        self.assertEqual(refreshed[0].records, 2)
        self.assertEqual(refreshed[0].status, "success")

    def test_cache_invalidation_is_namespaced_and_counted(self) -> None:
        platform = DataPlatform()
        platform.register(FixtureProvider())
        platform.fetch("Fixture", "p1", {"namespace": "league:1"})
        cached = platform.fetch("Fixture", "p1", {"namespace": "league:1"})
        platform.fetch("Fixture", "p1", {"namespace": "league:2"})
        self.assertEqual(cached.retrieval_mode, "cache_hit")
        self.assertEqual(platform.invalidate("Fixture"), 2)
        self.assertEqual(platform.health()["cache"]["entries"], 0)

    def test_snapshot_warehouse_persists_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            platform = DataPlatform(warehouse=SnapshotWarehouse(path))
            platform.register(FixtureProvider())
            platform.fetch("Fixture", "p1", {"namespace": "league:1"})
            restored = SnapshotWarehouse(path).history("p1", "market")
            self.assertEqual(len(restored), 1)
            self.assertEqual(restored[0].provider, "Fixture")

    def test_consensus_preserves_sources_and_limits_outlier_influence(self) -> None:
        rows = tuple(FixtureProvider(name, value).fetch("p1", {}) for name, value in (("A", 100), ("B", 105), ("C", 1000)))
        result = consensus("p1", rows, ("A", "B", "C", "D"))
        self.assertLess(result.value or 1000, 500)
        self.assertEqual(result.missing_providers, ("D",))
        self.assertIn("C", result.bullish_sources)
        self.assertEqual(len(result.sources), 3)

    def test_historical_trends_cover_all_required_windows(self) -> None:
        now = datetime.now(timezone.utc)
        provider = FixtureProvider()
        first = provider.fetch("p1", {"timestamp": (now - timedelta(days=100)).isoformat()})
        second = replace(provider.fetch("p1", {"timestamp": now.isoformat()}), value=125)
        result = trend("p1", (first, second), now)
        self.assertEqual(result.percentage_change, 25)
        self.assertEqual(set(result.periods), {"7 days", "30 days", "90 days", "1 year", "lifetime"})
        self.assertEqual(result.direction, "Rising")

    def test_fallback_chain_discloses_cache_history_estimate_and_unavailable(self) -> None:
        provider = FixtureProvider()
        platform = DataPlatform()
        platform.register(provider)
        live = platform.fetch("Fixture", "p1", {"namespace": "one"})
        provider.failure = "outage"
        cached = platform.fetch("Fixture", "p1", {"namespace": "one", "force_refresh": True})
        historical = platform.fetch("Fixture", "p1", {"namespace": "two", "force_refresh": True})
        estimate = platform.fetch("Fixture", "p2", {"namespace": "two", "dtos_estimate": 77})
        unavailable = platform.fetch("Fixture", "p3", {"namespace": "two"})
        self.assertEqual(live.retrieval_mode, "live")
        self.assertEqual(cached.retrieval_mode, "cached_fallback")
        self.assertEqual(historical.retrieval_mode, "historical_snapshot")
        self.assertEqual(estimate.retrieval_mode, "dtos_estimate")
        self.assertEqual(unavailable.retrieval_mode, "unavailable")

    def test_partial_complete_outages_and_rate_limits_are_non_blocking(self) -> None:
        platform = DataPlatform()
        platform.register(FixtureProvider("Good", 100))
        platform.register(FixtureProvider("Limited", failure="rate limit exceeded"))
        result = platform.aggregate("market", "p1", {"namespace": "league"})
        self.assertEqual(result.value, 100)
        self.assertEqual(result.missing_providers, ("Limited",))
        self.assertEqual(platform.health()["providers"]["Limited"]["status"], ProviderStatus.RATE_LIMITED)

    def test_news_intelligence_is_structured_and_does_not_fabricate(self) -> None:
        result = interpret_news("Player limited and questionable", source_confidence=80, verified=False)
        self.assertEqual(result.category, "Injury")
        self.assertEqual(result.confidence, 55)
        self.assertTrue(result.reasoning)

    def test_outputs_are_deterministic_for_identical_inputs(self) -> None:
        rows = tuple(FixtureProvider(name, value).fetch("p1", {}) for name, value in (("A", 100), ("B", 105)))
        self.assertEqual(consensus("p1", rows, ("A", "B")), consensus("p1", rows, ("A", "B")))

    def test_intelligence_engines_use_data_platform_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        market = (root / "src/core/market_intelligence/engine.py").read_text(encoding="utf-8")
        sleeper = (root / "services/sleeper.py").read_text(encoding="utf-8")
        orchestrator = (root / "src/core/intelligence/orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("src.core.data_platform", market)
        self.assertNotIn("market_intelligence.providers", market)
        self.assertIn("data_platform.get_json", sleeper)
        self.assertNotIn("httpx", orchestrator)

    def test_unified_data_api_exposes_standardized_contracts(self) -> None:
        async def ensure() -> None:
            return None

        async def sync_sleeper(**kwargs: object) -> dict[str, object]:
            return state

        state: dict[str, object] = {"data": {"players": {"p1": {"player_id": "p1", "fantasycalc_value": 100}}, "market_data": {"providers": {}}}}
        app = FastAPI()
        app.include_router(create_api_router(ensure_fresh=ensure, require_data=lambda: state["data"], sync_sleeper=sync_sleeper, state=state, league_id="league-test"))
        client = TestClient(app)
        providers = client.get("/api/data/providers")
        health = client.get("/api/data/health")
        sources = client.get("/api/data/market/p1")
        history = client.get("/api/data/history/market/p1")
        trend_response = client.get("/api/data/trend/market/p1")
        self.assertEqual({providers.status_code, health.status_code, sources.status_code, history.status_code, trend_response.status_code}, {200})
        self.assertTrue(providers.json()["providers"])
        self.assertIn("source", sources.json()["sources"][0])
        self.assertIn("quality", sources.json()["sources"][0])
        self.assertIn("periods", trend_response.json())


if __name__ == "__main__":
    unittest.main()
