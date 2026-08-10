from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.valuation import create_valuation_router
from src.core.provider_network import build_provider_network
from src.core.valuation_intelligence import build_valuation_intelligence
from src.core.valuation_intelligence.engine import resolve_asset_name
from tests.test_provider_network import fixture


class ValuationIntelligenceTests(unittest.TestCase):
    def build(self) -> tuple[dict, dict, dict]:
        data, state = fixture()
        build_provider_network(data, state)
        return data, state, build_valuation_intelligence(data, state)

    def test_every_canonical_asset_receives_reproducible_scores(self) -> None:
        data, state, report = self.build()
        self.assertEqual(report["asset_count"], 120)
        self.assertEqual(report["safety"]["asset_integrity_score"], 100)
        self.assertTrue(all(0 <= score <= 100 for row in report["assets"].values() for score in row["scores"].values()))
        self.assertEqual(report["assets"]["player:1"]["scores"], build_valuation_intelligence(data, state)["assets"]["player:1"]["scores"])

    def test_coverage_is_not_confidence_and_categories_are_explicit(self) -> None:
        _, _, report = self.build()
        row = report["assets"]["player:1"]
        self.assertNotEqual(row["scores"]["coverage"], row["scores"]["confidence"])
        self.assertEqual(len(row["categories"]), 8)
        self.assertIn("Market", [item["name"] for item in row["categories"] if item["available"]])

    def test_canonical_player_and_pick_names_are_resolved_without_aliases(self) -> None:
        _, _, report = self.build()
        self.assertEqual(report["assets"]["player:1"]["display_name"], "Player 1")
        self.assertEqual(report["assets"]["pick:2027:1:1"]["display_name"], "2027 Round 1 (Roster 1)")
        self.assertNotEqual(report["assets"]["player:1"]["display_name"], "player:1")

    def test_missing_optional_name_uses_deterministic_diagnostic_fallback(self) -> None:
        asset = {"asset_id": "player:missing", "asset_type": "player", "identity": {}}
        self.assertEqual(resolve_asset_name(asset), "Unknown asset (player:missing)")
        self.assertEqual(resolve_asset_name({"asset_id": "pick:missing"}), "Unknown asset (pick:missing)")

    def test_name_resolution_does_not_change_scores(self) -> None:
        data, state, report = self.build()
        scores = report["assets"]["player:1"]["scores"]
        data["normalized_players"]["1"]["name"] = "Renamed Canonical Player"
        build_provider_network(data, state)
        changed = build_valuation_intelligence(data, state)
        self.assertEqual(changed["assets"]["player:1"]["display_name"], "Renamed Canonical Player")
        self.assertEqual(changed["assets"]["player:1"]["scores"], scores)

    def test_agreement_responds_to_conflicting_provider_evidence(self) -> None:
        data, state = fixture()
        data["market_data"]["providers"]["FantasyCalc"]["1"]["value"] = 1
        data["market_data"]["providers"]["DynastyProcess"]["1"]["value"] = 100000
        build_provider_network(data, state)
        report = build_valuation_intelligence(data, state)
        self.assertLess(report["assets"]["player:1"]["scores"]["agreement"], 100)

    def test_dynamic_provider_contributions_are_measurable(self) -> None:
        _, _, report = self.build()
        sources = report["assets"]["player:1"]["evidence_sources"]
        self.assertEqual(len(sources), 2)
        self.assertTrue(all(source["weight"] > 0 and source["reliability"] > 0 for source in sources))

    def test_missing_provider_evidence_is_explained_without_inventing_values(self) -> None:
        data, state = fixture()
        data["market_data"]["providers"] = {}
        build_provider_network(data, state)
        report = build_valuation_intelligence(data, state)
        row = report["assets"]["player:1"]
        self.assertEqual(row["provider_count"], 0)
        self.assertIn("No supported market-provider observation", row["explanation"])
        self.assertIn("Missing market support", row["diagnostics"])

    def test_timeline_is_idempotent_and_records_semantic_changes(self) -> None:
        data, state, first = self.build()
        self.assertEqual(len(first["timeline"]["player:1"]), 1)
        self.assertEqual(len(build_valuation_intelligence(data, state)["timeline"]["player:1"]), 1)
        data["provider_network"]["evidence"] = [row for row in data["provider_network"]["evidence"] if row["canonical_asset_id"] != "player:1"]
        changed = build_valuation_intelligence(data, state)
        self.assertEqual(len(changed["timeline"]["player:1"]), 2)

    def test_diagnostics_identify_missing_evidence(self) -> None:
        _, _, report = self.build()
        self.assertTrue(report["diagnostics"]["Missing evidence"])

    def test_valuation_layers_remain_independent(self) -> None:
        _, _, report = self.build()
        layers = report["assets"]["player:1"]["valuation_layers"]
        self.assertEqual(set(layers), {"market_value", "intrinsic_dtos_value", "league_adjusted_value", "contender_value", "rebuilder_value"})
        self.assertTrue(report["safety"]["independent_layers_preserved"])

    def test_build_performs_no_external_requests(self) -> None:
        data, state = fixture()
        build_provider_network(data, state)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            report = build_valuation_intelligence(data, state)
        self.assertEqual(report["safety"]["external_requests_during_build"], 0)

    def test_api_contracts_dashboard_and_asset_integration(self) -> None:
        data, state, _ = self.build()

        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(ensure_fresh=ready, require_data=lambda: data, state=state, page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}")))
        client = TestClient(app)
        routes = ("/api/valuation/evidence", "/api/valuation/evidence/player:1", "/api/valuation/confidence", "/api/valuation/coverage", "/api/valuation/agreement", "/api/valuation/explanation?asset_id=player:1", "/api/valuation/timeline?asset_id=player:1", "/api/valuation/diagnostics")
        for route in routes:
            response = client.get(route)
            self.assertEqual(response.status_code, 200, route)
        self.assertEqual(response.json()["application_version"], "1.10.0")
        self.assertEqual(response.json()["application_build"], 1100)
        self.assertIsNotNone(client.get("/api/valuation/assets/player:1").json()["valuation_intelligence"])
        dashboard = client.get("/valuation/calibration")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Evidence Intelligence Dashboard", dashboard.text)

    def test_missing_asset_contract_is_explicit(self) -> None:
        data, state, _ = self.build()

        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(ensure_fresh=ready, require_data=lambda: data, state=state))
        client = TestClient(app)
        self.assertEqual(client.get("/api/valuation/evidence/not-real").status_code, 404)
        self.assertEqual(client.get("/api/valuation/explanation?asset_id=not-real").status_code, 404)


if __name__ == "__main__":
    unittest.main()
