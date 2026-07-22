"""Market Intelligence provider, consensus, history, fallback, and integration contracts."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from src.core.market_intelligence import MarketHistoryStore, MarketProvider, MarketProviderRegistry, MarketQuoteCache, MarketSnapshot, ProviderQuote, ValueGapLabel, value_gap
from src.core.market_intelligence.aggregation import build_consensus
from src.core.market_intelligence.trends import calculate_trend
from tests.test_trade_intelligence import fixture_data


class StaticProvider(MarketProvider):
    def __init__(self, name: str, value: float | None, *, fail: bool = False) -> None:
        self.name = name
        self.field = name.casefold()
        self.value = value
        self.fail = fail

    def _extract(self, asset, market_data):
        if self.fail:
            raise ValueError("offline")
        return self.value, 80, "2026-07-21T12:00:00+00:00", "Documented test provider"


def market_data() -> dict:
    data = fixture_data()
    data["market_data"] = {"context_mode": "online"}
    for index, player in enumerate(data["players"].values()):
        base = 48 + index % 20
        player.update({"fantasycalc_value": base, "keeptradecut_value": base + 2, "sleeper_adp_value": base - 1, "dynastyprocess_value": base + 1})
    return data


class ConsensusTests(unittest.TestCase):
    def test_consensus_limits_outlier_and_reports_agreement(self) -> None:
        quotes = tuple(ProviderQuote(name, "p1", value, 80, "now", name, True, "test") for name, value in (("A", 50), ("B", 52), ("C", 51), ("D", 100)))
        result = build_consensus("p1", quotes, ("A", "B", "C", "D"))
        self.assertLess(result.value, 65)
        self.assertGreater(result.value, 49)
        self.assertLess(result.agreement, 100)
        self.assertEqual(result.missing_providers, ())

    def test_missing_and_failed_providers_do_not_create_values(self) -> None:
        registry = MarketProviderRegistry()
        registry.register(StaticProvider("Available", 60))
        registry.register(StaticProvider("Offline", None, fail=True))
        quotes = tuple(provider.quote("p1", {"id": "p1"}, {}) for provider in registry.providers())
        result = build_consensus("p1", quotes, registry.names())
        self.assertEqual(result.value, 60)
        self.assertEqual(result.missing_providers, ("Offline",))

    def test_mixed_provider_availability_reduces_confidence(self) -> None:
        all_quotes = tuple(ProviderQuote(name, "p1", value, 80, "now", name, True, "test") for name, value in (("A", 50), ("B", 51), ("C", 52), ("D", 50)))
        partial = all_quotes[:2] + tuple(ProviderQuote(name, "p1", None, 0, None, name, False, "offline") for name in ("C", "D"))
        complete = build_consensus("p1", all_quotes, ("A", "B", "C", "D"))
        degraded = build_consensus("p1", partial, ("A", "B", "C", "D"))
        self.assertLess(degraded.confidence, complete.confidence)
        self.assertEqual(degraded.missing_providers, ("C", "D"))

    def test_value_gap_keeps_intrinsic_and_market_values_separate(self) -> None:
        self.assertEqual(value_gap(75, 50, 80).label, ValueGapLabel.UNDERVALUED)
        self.assertEqual(value_gap(40, 70, 80).label, ValueGapLabel.OVERVALUED)
        self.assertEqual(value_gap(52, 50, 80).label, ValueGapLabel.FAIR)
        self.assertEqual(value_gap(80, None, 0).label, ValueGapLabel.UNCERTAIN)


class HistoryAndCacheTests(unittest.TestCase):
    def test_history_persists_and_trends_cover_supported_horizons(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market.json"
            now = datetime.now(timezone.utc)
            rows = (
                MarketSnapshot("p1", (now - timedelta(days=6)).isoformat(), "A", 50, 60),
                MarketSnapshot("p1", now.isoformat(), "A", 60, 75),
            )
            MarketHistoryStore(path).append(rows)
            loaded = MarketHistoryStore(path).for_asset("p1")
            trend = calculate_trend(loaded, now)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(trend.direction, "Rising")
            self.assertEqual(trend.periods["7 day"], 20.0)
            self.assertGreater(trend.confidence_drift, 0)

    def test_expired_cache_uses_stale_quote_when_provider_fails(self) -> None:
        cache = MarketQuoteCache(ttl_seconds=-1)
        fresh = ProviderQuote("A", "p1", 55, 80, "now", "A", True, "fresh")
        failed = ProviderQuote("A", "p1", None, 0, None, "A", False, "offline")
        self.assertEqual(cache.quote("A", "p1", lambda: fresh, namespace="league:1", context_mode="online").value, 55)
        fallback = cache.quote("A", "p1", lambda: failed, namespace="league:1", context_mode="offline", allow_cached_fallback=True, maximum_stale_seconds=60)
        self.assertTrue(fallback.cached)
        self.assertEqual(fallback.value, 55)
        self.assertEqual(cache.health()["offline_fallbacks"], 1)

    def test_online_offline_and_recovery_modes_are_isolated(self) -> None:
        cache = MarketQuoteCache(ttl_seconds=60)
        fresh = ProviderQuote("A", "p1", 55, 80, "now", "A", True, "fresh", retrieval_mode="live")
        unavailable = ProviderQuote("A", "p1", None, 0, None, "A", False, "offline")
        online = cache.quote("A", "p1", lambda: fresh, namespace="league:1", context_mode="online")
        offline = cache.quote("A", "p1", lambda: unavailable, namespace="league:1", context_mode="offline")
        recovered = cache.quote("A", "p1", lambda: fresh, namespace="league:2", context_mode="online")
        self.assertEqual(online.retrieval_mode, "live")
        self.assertFalse(offline.available)
        self.assertEqual(offline.retrieval_mode, "unavailable")
        self.assertTrue(recovered.available)

    def test_cached_fallback_is_explicit_and_reduces_confidence(self) -> None:
        cache = MarketQuoteCache(ttl_seconds=60)
        fresh = ProviderQuote("A", "p1", 55, 80, "now", "A", True, "fresh", retrieval_mode="live")
        cache.quote("A", "p1", lambda: fresh, namespace="league:1", context_mode="online")
        fallback = cache.quote("A", "p1", lambda: fresh, namespace="league:1", context_mode="offline", allow_cached_fallback=True)
        self.assertEqual(fallback.retrieval_mode, "cached_fallback")
        self.assertEqual(fallback.freshness, "stale")
        self.assertLess(fallback.confidence, fresh.confidence)
        self.assertLess(fallback.confidence_impact, 0)

    def test_provider_invalidation_and_namespace_isolation(self) -> None:
        cache = MarketQuoteCache(ttl_seconds=60)
        quote = ProviderQuote("A", "p1", 55, 80, "now", "A", True, "fresh", retrieval_mode="live")
        cache.quote("A", "p1", lambda: quote, namespace="league:1", context_mode="online")
        cache.quote("A", "p1", lambda: quote, namespace="league:2", context_mode="online")
        self.assertEqual(cache.invalidate_provider("A"), 2)
        self.assertEqual(cache.health()["entries"], 0)

    def test_stale_cache_is_rejected_beyond_maximum_age(self) -> None:
        cache = MarketQuoteCache(ttl_seconds=-1)
        quote = ProviderQuote("A", "p1", 55, 80, "now", "A", True, "fresh", retrieval_mode="live")
        cache.quote("A", "p1", lambda: quote, namespace="league:1", context_mode="online")
        rejected = cache.quote("A", "p1", lambda: quote, namespace="league:1", context_mode="offline", allow_cached_fallback=True, maximum_stale_seconds=-1)
        self.assertFalse(rejected.available)
        self.assertEqual(rejected.retrieval_mode, "unavailable")


class MarketIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = market_data()
        self.orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache())

    def test_orchestrator_registers_market_and_enriches_assets_and_trades(self) -> None:
        result = self.orchestrator.analyze(self.data, 1)
        self.assertEqual(self.orchestrator.registry.names(), ("decision", "asset", "front_office", "trade", "market", "player_value", "roster"))
        self.assertTrue(result.market.assets)
        self.assertTrue(any(report.consensus.value is not None for report in result.market.assets.values()))
        self.assertTrue(all(dossier.market is not None for dossier in result.trades))
        self.assertIn("Market Intelligence", result.recommendation.sources)
        self.assertIn("market_intelligence", result.timings_ms)

    def test_player_dossier_uses_consensus_without_replacing_intrinsic_value(self) -> None:
        player_id, player = next(iter(self.data["players"].items()))
        report = self.orchestrator.player_report(self.data, {**player, "id": player_id}, 1)
        self.assertNotEqual(report.core_values.market.summary, "Neutral placeholder until a traceable market-consensus provider is connected.")
        self.assertIn("independent", report.core_values.market.summary.casefold())
        self.assertEqual(report.core_values.dynasty.name, "Dynasty Value")

    def test_offline_provider_state_is_explicit_and_non_blocking(self) -> None:
        data = fixture_data()
        result = self.orchestrator.analyze(data, 1)
        self.assertTrue(result.market.offline)
        self.assertTrue(all(report.consensus.value is None for report in result.market.assets.values()))
        self.assertTrue(result.recommendation)

    def test_health_endpoint_reports_all_market_providers_and_cache(self) -> None:
        self.orchestrator.analyze(self.data, 1)
        health = self.orchestrator.health({"data": self.data, "last_sync": "now", "last_error": None})
        self.assertEqual(set(health["market"]["providers"]), {"FantasyCalc", "KeepTradeCut", "Sleeper ADP", "DynastyProcess"})
        self.assertIn("ttl_seconds", health["market"]["cache"])

        async def noop():
            return None

        async def sync(**kwargs):
            return {}

        app = FastAPI()
        app.include_router(create_api_router(ensure_fresh=noop, require_data=lambda: self.data, sync_sleeper=sync, state={"data": self.data}, league_id="league-1"))
        payload = TestClient(app).get("/api/platform/health").json()
        self.assertIn("market", payload)


if __name__ == "__main__":
    unittest.main()
