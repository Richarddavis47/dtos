from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.valuation import create_valuation_router
from src.core.provider_network import EVIDENCE_CONTRACT_VERSION, PROVIDER_REGISTRY_VERSION, build_provider_network, provider_registry
from src.core.provider_network.contracts import EvidenceObservation
from src.core.provider_network.trades import observed_trades
from src.core.valuation.automation import audit_market_calibration


def fixture() -> tuple[dict, dict]:
    now = datetime.now(timezone.utc).isoformat()
    players = {str(index): {"name": f"Player {index}", "position": ("QB", "RB", "WR", "TE")[index % 4], "status": "Active", "dtos_value": 60 + index % 20} for index in range(1, 81)}
    providers = {
        "FantasyCalc": {key: {"value": 1000 + int(key) * 10, "confidence": 90, "updated_at": now, "rank": int(key)} for key in players},
        "DynastyProcess": {key: {"value": 800 + int(key) * 8, "confidence": 85, "updated_at": now, "rank": int(key)} for key in players},
    }
    transactions = [
        {"transaction_id": "trade-1", "type": "trade", "status": "complete", "roster_ids": [1, 2], "adds": {"1": 1, "2": 2}, "drops": {"1": 2, "2": 1}, "created": 1},
        {"transaction_id": "trade-1", "type": "trade", "status": "complete", "roster_ids": [1, 2], "adds": {"1": 1, "2": 2}},
        {"transaction_id": "waiver-1", "type": "waiver", "status": "complete", "roster_ids": [1], "adds": {"3": 1}},
        {"transaction_id": "broken", "type": "trade", "status": "complete", "roster_ids": [1, 2], "adds": {"4": 1}},
    ]
    data = {
        "league": {"league_id": "league-one"}, "normalized_players": players, "teams": [],
        "pick_ledger": [{"season": 2027, "round": round_number, "original_roster_id": roster_id, "current_owner_id": roster_id} for roster_id in range(1, 11) for round_number in range(1, 5)],
        "transactions": transactions, "players_fetched_at": now,
        "market_data": {"providers": providers, "provider_status": {
            "FantasyCalc": {"status": "healthy", "last_refresh": now, "records_retrieved": 80},
            "DynastyProcess": {"status": "healthy", "last_refresh": now, "records_retrieved": 80},
            "KeepTradeCut": {"status": "unsupported", "reason": "No approved integration."},
        }},
    }
    return data, {"data": data, "last_sync": now}


class ProviderNetworkTests(unittest.TestCase):
    def test_registry_is_versioned_and_every_provider_has_compliance(self) -> None:
        rows = provider_registry()
        self.assertEqual(PROVIDER_REGISTRY_VERSION, "1.0")
        self.assertEqual(EVIDENCE_CONTRACT_VERSION, "1.0")
        self.assertTrue(all(row["compliance_status"] and row["evidence_family"] and row["license_or_usage_right_status"] and row["rate_limits"] for row in rows))
        ktc = next(row for row in rows if row["provider_id"] == "keeptradecut")
        self.assertEqual(ktc["compliance_status"], "unsupported_no_public_interface")
        self.assertIn("no approved provider integration", ktc["status_explanation"])

    def test_fantasypros_credential_state_exposes_no_secret(self) -> None:
        with patch.dict(os.environ, {"FANTASYPROS_API_KEY": "top-secret-value"}):
            row = next(item for item in provider_registry() if item["provider_id"] == "fantasypros")
        self.assertTrue(row["credentials_configured"])
        self.assertNotIn("top-secret-value", json.dumps(row))
        self.assertEqual(row["compliance_status"], "approved_credentials_required")

    def test_restricted_observation_redacts_raw_fields(self) -> None:
        row = EvidenceObservation("player:1", "restricted", "expert_consensus", 900.0, 800, 1, 1, "A", "PPR", "SF", 12, False, None, None, "now", None, 1, 80, "available", 100, "exact", "1", "private", "family", False).public_dict()
        self.assertIsNone(row["raw_value"])
        self.assertIsNone(row["normalized_value"])
        self.assertNotIn("private", json.dumps(row))

    def test_network_maps_exact_ids_and_reduces_correlated_families(self) -> None:
        data, state = fixture()
        report = build_provider_network(data, state)
        self.assertEqual(report["evidence_summary"]["observations"], 160)
        self.assertEqual(report["evidence_summary"]["unmatched"], 0)
        self.assertEqual(report["evidence_summary"]["conflicting"], 0)
        self.assertEqual(report["consensus"]["assets_with_evidence"], 80)
        self.assertEqual(report["consensus"]["assets_with_multiple_independent_families"], 80)
        self.assertEqual(report["evidence_summary"]["exact"], 160)
        self.assertTrue(all(key in report["performance"] for key in ("universe_ms", "normalization_ms", "identity_resolution_ms", "trade_inference_ms", "reliability_ms", "consensus_ms", "total_ms")))
        sample = report["consensus"]["sample"][0]
        self.assertEqual(sample["raw_provider_count"], 2)
        self.assertEqual(sample["independent_evidence_family_count"], 2)

    def test_missing_provider_record_is_reported_not_zero(self) -> None:
        data, state = fixture()
        del data["market_data"]["providers"]["FantasyCalc"]["1"]
        report = build_provider_network(data, state)
        fantasycalc = next(row for row in report["providers"] if row["provider_id"] == "fantasycalc")
        self.assertEqual(fantasycalc["record_count"], 79)
        self.assertLess(fantasycalc["coverage_percentage"], 80 * 100 / 120)

    def test_trade_evidence_is_deduplicated_isolated_and_quality_filtered(self) -> None:
        data, _ = fixture()
        trades, excluded = observed_trades(data)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].league_id, "league-one")
        self.assertEqual(excluded["duplicate"], 1)
        self.assertEqual(excluded["not_completed_trade"], 1)
        self.assertEqual(excluded["incomplete"], 1)

    def test_reliability_is_dynamic_bounded_and_category_specific(self) -> None:
        data, state = fixture()
        report = build_provider_network(data, state)
        fantasycalc = next(row for row in report["providers"] if row["provider_id"] == "fantasycalc")
        self.assertGreater(fantasycalc["reliability_score"], 0)
        self.assertLessEqual(fantasycalc["reliability_score"], 100)
        self.assertNotEqual(fantasycalc["reliability_dimensions"]["pick"], fantasycalc["reliability_dimensions"]["QB"])

    def test_calibration_requires_independent_family_coverage(self) -> None:
        data, state = fixture()
        build_provider_network(data, state)
        report = audit_market_calibration(data, state, apply=True)
        self.assertEqual(report["integrity"]["duplicate_identities"], 0)
        self.assertEqual(sum(row["applied"] for row in report["recommendations"]), 0)
        self.assertTrue(all("independent_evidence_families" in row["safety_checks"] for row in report["recommendations"]))

    def test_public_api_uses_cached_network_and_versioned_envelopes(self) -> None:
        data, state = fixture()
        build_provider_network(data, state)

        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(ensure_fresh=ready, require_data=lambda: data, state=state))
        client = TestClient(app)
        for route in ("/api/valuation/providers", "/api/valuation/providers/fantasycalc", "/api/valuation/providers/fantasycalc/status", "/api/valuation/providers/fantasycalc/coverage", "/api/valuation/providers/fantasycalc/reliability", "/api/valuation/providers/fantasycalc/history", "/api/valuation/provider-consensus", "/api/valuation/provider-agreement", "/api/valuation/observed-market", "/api/valuation/league-market"):
            response = client.get(route)
            self.assertEqual(response.status_code, 200, route)
            payload = response.json()
            self.assertEqual(payload["provider_registry_version"], PROVIDER_REGISTRY_VERSION)
            self.assertEqual(payload["evidence_contract_version"], EVIDENCE_CONTRACT_VERSION)
        self.assertNotIn("evidence", client.get("/api/valuation/providers").json())
        self.assertEqual(client.get("/api/valuation/providers/not-real").status_code, 404)

    def test_pending_provider_runtime_metrics_are_explicit(self) -> None:
        data, state = fixture()
        data.pop("provider_network", None)

        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(ensure_fresh=ready, require_data=lambda: data, state=state))
        client = TestClient(app)
        coverage = client.get("/api/valuation/providers/fantasycalc/coverage")
        reliability = client.get("/api/valuation/providers/fantasycalc/reliability")
        self.assertEqual(coverage.status_code, 200)
        self.assertEqual(coverage.json()["runtime_metrics_status"], "pending")
        self.assertIsNone(coverage.json()["identity_match_rate"])
        self.assertEqual(reliability.status_code, 200)
        self.assertEqual(reliability.json()["runtime_metrics_status"], "pending")
        self.assertIsNone(reliability.json()["reliability_score"])

    def test_build_is_deterministic_except_documented_timestamps(self) -> None:
        data, state = fixture()
        first = build_provider_network(data, state)
        second = build_provider_network(data, state)
        self.assertEqual(first["consensus"], second["consensus"])
        self.assertEqual(first["observed_market"], second["observed_market"])
        self.assertEqual(first["evidence_summary"], second["evidence_summary"])


if __name__ == "__main__":
    unittest.main()
