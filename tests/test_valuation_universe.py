from __future__ import annotations

import csv
import io
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.valuation import create_valuation_router
from src.core.valuation.universe import LAYER_NAMES, PROVIDER_NAMES, ValuationUniverse


def fixture() -> tuple[dict, dict]:
    data = {
        "normalized_players": {
            "1": {"name": "Rostered QB", "position": "QB", "nfl_team": "BUF", "status": "Active", "dtos_value": 80},
            "2": {"name": "Free Agent", "position": "WR", "nfl_team": "FA", "status": "Inactive"},
        },
        "teams": [{"roster_id": 4, "team_name": "Front Office", "owner": "GM", "players": [{"id": "1", "roster_slot": "Starter"}]}],
        "pick_ledger": [{"season": 2027, "round": 1, "original_roster_id": 4, "original_team": "Front Office", "current_owner_id": 4, "current_owner": "Front Office"}],
        "market_data": {
            "providers": {
                "FantasyCalc": {"1": {"value": 9000, "rank": 2, "confidence": 90, "updated_at": "2026-08-03T06:00:00+00:00"}},
                "DynastyProcess": {"1": {"value": 8000, "rank": 3, "confidence": 80, "updated_at": "2026-08-03T06:00:00+00:00"}},
            },
            "provider_status": {
                "FantasyCalc": {"enabled": True, "status": "healthy", "last_refresh": "2026-08-03T06:00:00+00:00"},
                "DynastyProcess": {"enabled": True, "status": "healthy", "last_refresh": "2026-08-03T06:00:00+00:00"},
                "KeepTradeCut": {"enabled": False, "status": "unsupported", "reason": "No approved integration."},
            },
        },
    }
    return data, {"data": data, "last_sync": "2026-08-03T06:00:00+00:00"}


class ValuationUniverseTests(unittest.TestCase):
    def setUp(self) -> None:
        data, state = fixture()
        self.data, self.state = data, state
        self.universe = ValuationUniverse(data, state)

    def test_every_player_and_pick_has_one_canonical_identity(self) -> None:
        self.assertEqual(self.universe.status()["counts"], {"players": 2, "picks": 1, "total": 3})
        self.assertEqual(self.universe.status()["duplicate_identities"], 0)
        self.assertEqual(len({row["asset_id"] for row in self.universe.assets}), 3)

    def test_rostered_and_free_agent_identity_is_explicit(self) -> None:
        rostered = self.universe.by_id["player:1"]["identity"]
        free_agent = self.universe.by_id["player:2"]["identity"]
        self.assertFalse(rostered["free_agent"])
        self.assertEqual(rostered["current_owner"]["roster_id"], 4)
        self.assertTrue(free_agent["free_agent"])
        self.assertIsNone(free_agent["current_owner"])

    def test_all_layers_remain_separate_and_traceable(self) -> None:
        layers = self.universe.by_id["player:1"]["layers"]
        self.assertEqual(tuple(layers), LAYER_NAMES)
        for layer in layers.values():
            self.assertEqual(set(layer), {"value", "source", "version", "generated_at", "confidence", "availability"})
        self.assertNotEqual(layers["market_value"]["source"], layers["intrinsic_dtos_value"]["source"])

    def test_provider_abstraction_includes_available_and_unavailable_sources(self) -> None:
        rows = self.universe.by_id["player:1"]["providers"]
        self.assertEqual(tuple(row["provider"] for row in rows), PROVIDER_NAMES)
        self.assertEqual(next(row for row in rows if row["provider"] == "FantasyCalc")["availability"], "available")
        self.assertEqual(next(row for row in rows if row["provider"] == "KTC")["availability"], "unsupported")
        self.assertEqual(next(row for row in rows if row["provider"] == "DTOS")["normalized_value"], 800)
        summary = self.universe.providers()["providers"]
        self.assertEqual(next(row for row in summary if row["provider"] == "KTC")["status"], "unsupported")

    def test_freshness_contract_exposes_release_and_sync_identity(self) -> None:
        freshness = self.universe.freshness
        for key in ("dtos_version", "build", "commit", "sleeper_sync_timestamp", "valuation_timestamp", "provider_refresh_timestamp", "generation_timestamp", "current_status"):
            self.assertIn(key, freshness)

    def test_csv_export_contains_every_asset_once(self) -> None:
        rows = list(csv.DictReader(io.StringIO(self.universe.csv_bytes().decode())))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row["asset_id"] for row in rows}), 3)
        self.assertEqual(rows[0]["asset_type"], "player")

    def test_api_contract_supports_listing_lookup_status_and_exports(self) -> None:
        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(ensure_fresh=ready, require_data=lambda: self.data, state=self.state))
        client = TestClient(app)
        self.assertEqual(client.get("/api/valuation").status_code, 200)
        self.assertEqual(client.get("/api/valuation/assets?limit=1").json()["total"], 3)
        self.assertEqual(client.get("/api/valuation/assets/player:1").json()["identity"]["player_name"], "Rostered QB")
        self.assertEqual(client.get("/api/valuation/assets/missing").status_code, 404)
        self.assertEqual(client.get("/api/valuation/status").json()["duplicate_identities"], 0)
        self.assertEqual(len(client.get("/api/valuation/export.json").json()["assets"]), 3)
        self.assertIn("text/csv", client.get("/api/valuation/export.csv").headers["content-type"])

    def test_no_existing_value_is_recalibrated(self) -> None:
        layers = self.universe.by_id["player:1"]["layers"]
        self.assertEqual(layers["intrinsic_dtos_value"]["value"], 800)
        self.assertEqual(layers["league_adjusted_value"]["value"], 800)
        self.assertNotEqual(layers["market_value"]["value"], layers["intrinsic_dtos_value"]["value"])


if __name__ == "__main__":
    unittest.main()
