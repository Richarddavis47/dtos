"""Provider normalization, identity resolution, reliability, and player API regressions."""
from __future__ import annotations

import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from src.core.data_platform import DataEnvelope, DataQuality, PlayerIdentityResolver, ProviderNormalizer, ReliabilityTracker, consensus, data_platform
from src.core.data_platform.normalization import normalize_confidence, normalize_name, normalize_position, normalize_team, normalize_timestamp
from tests.test_trade_intelligence import fixture_data


class NormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.players = {
            "s1": {"player_id": "s1", "full_name": "Marvin Harrison Jr.", "position": "WR/PR", "team": "JAC", "age": 23, "years_exp": 1, "status": "Active", "fantasycalc_id": 99, "ktc_id": "mhj"},
            "rookie": {"player_id": "rookie", "full_name": "Rookie Prospect", "position": "RB", "team": None, "years_exp": 0},
        }
        self.resolver = PlayerIdentityResolver(self.players)

    def test_identity_resolves_all_registered_provider_ids_and_name_variations(self) -> None:
        self.assertEqual(self.resolver.resolve("99", "FantasyCalc").dtos_id, "s1")
        self.assertEqual(self.resolver.resolve("mhj", "KeepTradeCut").dtos_id, "s1")
        self.assertEqual(self.resolver.resolve("marvinharrison", name="Marvin Harrison Jr.").dtos_id, "s1")
        self.assertEqual(normalize_name("Marvin Harrison Jr."), "marvinharrison")

    def test_team_position_free_agent_and_rookie_normalization(self) -> None:
        player = self.resolver.resolve("s1")
        rookie = self.resolver.resolve("rookie")
        self.assertEqual((player.position, player.nfl_team), ("WR", "JAX"))
        self.assertEqual((rookie.nfl_team, rookie.experience), ("FA", 0))
        self.assertEqual(normalize_team("WSH"), "WAS")
        self.assertEqual(normalize_position("D/ST"), "DST")

    def test_sleeper_metadata_is_always_normalized_to_a_dictionary(self) -> None:
        cases = (
            ("null", {"player_id": "null", "full_name": "Null Metadata", "metadata": None}, {}),
            ("empty", {"player_id": "empty", "full_name": "Empty Metadata", "metadata": {}}, {}),
            ("missing", {"player_id": "missing", "full_name": "Missing Metadata"}, {}),
            ("valid", {"player_id": "valid", "full_name": "Current Name", "metadata": {"previous_name": "Former Name", "number": 12, "ignored": None}}, {"previous_name": "Former Name", "number": "12"}),
        )
        resolver = PlayerIdentityResolver()
        for key, payload, expected in cases:
            with self.subTest(key=key):
                player = resolver.register(key, payload)
                self.assertIsInstance(player.metadata, dict)
                self.assertEqual(player.metadata, expected)
                self.assertEqual(resolver.resolve(key), player)
        self.assertIn("Former Name", resolver.resolve("valid").aliases)

    def test_value_rank_adp_timestamp_and_confidence_are_normalized(self) -> None:
        value = ProviderNormalizer(self.resolver).value("FantasyCalc", "99", {"value": "9150", "rank": "8", "position_rank": 3, "tier": 1, "adp": "10.5", "confidence": .92, "updated_at": "2026-07-22T10:00:00Z"})
        self.assertEqual((value.dtos_id, value.value, value.rank, value.position_rank, value.adp, value.confidence), ("s1", 9150, 8, 3, 10.5, 92))
        self.assertTrue(value.timestamp.endswith("+00:00"))
        self.assertEqual(normalize_confidence(1.5), 2)
        self.assertTrue(normalize_timestamp("bad timestamp").endswith("+00:00"))

    def test_invalid_values_and_broken_ids_are_blocked_with_reasons(self) -> None:
        invalid = ProviderNormalizer(self.resolver).value("FantasyCalc", "missing", {"value": -10})
        self.assertIsNone(invalid.value)
        self.assertGreaterEqual(len(invalid.warnings), 2)

    def test_reliability_declines_after_failures_and_schema_changes(self) -> None:
        tracker = ReliabilityTracker()
        healthy = tracker.record("A", success=True, latency_ms=10)
        tracker.record("B", success=False, latency_ms=1500, schema_failure=True)
        degraded = tracker.record("B", success=False, latency_ms=1500, schema_failure=True)
        self.assertGreater(healthy, degraded)
        self.assertEqual(tracker.health()["B"]["schema_failures"], 2)

    def test_consensus_weights_reliability_freshness_and_coverage(self) -> None:
        quality = DataQuality("good", (), 100)
        strong = DataEnvelope("p", "market", 100, "A", "A", "2026-07-22T10:00:00+00:00", "fresh", 90, "fresh", "live", quality, (), "Live", 100, {"contract": "NormalizedValue"})
        weak = DataEnvelope("p", "market", 300, "B", "B", "2026-07-21T10:00:00+00:00", "stale", 90, "historical_snapshot", "historical_snapshot", quality, (), "Historical", 10, {"contract": "NormalizedValue"})
        result = consensus("p", (strong, weak), ("A", "B", "C"))
        self.assertLess(result.value or 300, 200)
        self.assertEqual(result.missing_providers, ("C",))
        self.assertLess(result.confidence, 90)

    def test_player_report_has_normalized_identity_availability_and_reasons(self) -> None:
        data = fixture_data()
        player_id = next(iter(data["players"]))
        report = data_platform.player_report(player_id, data)
        self.assertEqual(report["normalized_player"]["dtos_id"], player_id)
        self.assertTrue(report["provider_values"])
        self.assertTrue(report["provider_availability"])
        self.assertIn("contract", report["normalization"])
        self.assertTrue(report["unavailable_reasons"])

    def test_player_intelligence_api_and_missing_player_contract(self) -> None:
        data = fixture_data()
        player_id = next(iter(data["players"]))
        state = {"data": data}

        async def ensure() -> None:
            return None

        async def sync_sleeper(**kwargs: object) -> dict[str, object]:
            return state

        app = FastAPI()
        app.include_router(create_api_router(ensure_fresh=ensure, require_data=lambda: data, sync_sleeper=sync_sleeper, state=state, league_id="test"))
        client = TestClient(app)
        found = client.get(f"/api/players/{player_id}/intelligence")
        missing = client.get("/api/players/not-real/intelligence")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(missing.status_code, 404)
        self.assertIn("provider_availability", found.json())
        self.assertIn("unavailable_reasons", found.json())

    def test_normalization_and_consensus_are_deterministic(self) -> None:
        normalizer = ProviderNormalizer(self.resolver)
        row = {"value": 100, "confidence": 80, "updated_at": "2026-07-22T10:00:00Z"}
        self.assertEqual(normalizer.value("FantasyCalc", "99", row), normalizer.value("FantasyCalc", "99", row))

    def test_provider_formats_do_not_cross_intelligence_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in ("src/core/market_intelligence/engine.py", "src/core/league_intelligence/engine.py", "src/core/roster_intelligence/engine.py", "src/core/trade_intelligence/engine/trade_engine.py"):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("market_intelligence.providers", source)
            self.assertNotIn("fantasycalc_id", source)
            self.assertNotIn("ktc_id", source)


if __name__ == "__main__":
    unittest.main()
