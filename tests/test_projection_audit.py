from __future__ import annotations

import copy
import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.audit import create_audit_router
from services.projection_audit import build_projection_audit


class FakeMarket:
    league_id = "league-1"
    brain_generation = "brain-1"
    assets = [{
        "asset_id": "player:10", "position": "QB", "owner": "Alpha",
        "availability": "rostered", "confidence": 88,
        "values": {"market_value": 7000, "intrinsic_dtos_value": 7100,
                   "contender_value": 7400, "rebuilder_value": 6800,
                   "liquidity_score": 75},
    }]
    by_id = {row["asset_id"]: row for row in assets}

    def identity(self):
        return {"market_generation": "market-1"}

    def audit_identity(self):
        return {"market_generation": "market-1", "brain_snapshot_id": "1.10.11:brain-1"}

    def directory(self, *, limit, sort):
        return {"assets": [{**self.assets[0], "rank": 1}]}


@dataclass(frozen=True)
class Category:
    category_key: str
    normalized_score: float


@dataclass(frozen=True)
class Score:
    gm_id: str = "gm-1"
    gm_name: str = "General Manager"
    franchise_id: str = "1"
    overall_score: float = 82.0
    overall_letter_grade: str = "B"
    category_scores: tuple[Category, ...] = (
        Category("results", 80), Category("trading_asset_management", 81),
        Category("roster_construction", 82), Category("drafting_talent_evaluation", 83),
    )
    confidence: float = 90
    completeness: float = 95
    brain_snapshot_id: str = "brain-1"
    evidence_references: tuple[str, ...] = ("projection_snapshot:projection-1",)


def fixture():
    data = {
        "league": {"league_id": "league-1", "name": "Day Traders"},
        "nfl_state": {"season_type": "regular"},
        "matchups": {"1": [{
            "team": "Alpha", "owner": "GM A", "roster_id": 1, "points": 12,
            "lineup": [{"id": "10", "name": "J. Daniels", "position": "QB",
                        "nfl_team": "WAS", "slot": "QB", "points": 12}],
        }, {
            "team": "Beta", "owner": "GM B", "roster_id": 2, "points": 0,
            "lineup": [{"id": "11", "name": "Missing Player", "position": "RB",
                        "nfl_team": None, "slot": "RB", "points": 0}],
        }]},
    }
    snapshot = {
        "season": "2026", "week": 1, "projection_snapshot_id": "projection-1",
        "players": {"10": {"sleeper_projection": 17.91, "dtos_projection": 20.0,
                            "canonical_projection": 19.27, "weekly_floor": 14,
                            "weekly_median": 19.27, "weekly_ceiling": 25,
                            "projection_confidence": 84, "projection_agreement": "High",
                            "sleeper_freshness": "Fresh"}},
    }
    return data, snapshot


class ProjectionAuditTests(unittest.TestCase):
    def test_export_is_read_only_complete_and_reconciled(self):
        data, snapshot = fixture()
        original_data, original_snapshot = copy.deepcopy(data), copy.deepcopy(snapshot)
        result = build_projection_audit(
            data=data, projection_snapshot=snapshot, projection_health={"status": "ready"},
            market=FakeMarket(), fois_scores=(Score(),), now="2026-08-11T00:00:00+00:00",
        )
        self.assertEqual(result["audit_summary"]["total_starters"], 2)
        self.assertEqual(result["audit_summary"]["starters_with_both"], 1)
        self.assertEqual(result["players"][0]["dtos_minus_sleeper"], 2.09)
        self.assertIsNone(result["players"][1]["canonical_projection"])
        self.assertEqual(result["teams"][0]["sleeper_projected_total"], 17.91)
        self.assertEqual(result["players"][0]["brain_snapshot_id"], "1.10.11:brain-1")
        self.assertEqual(result["fois"][0]["projection_snapshot_id"], "projection-1")
        self.assertEqual(data, original_data)
        self.assertEqual(snapshot, original_snapshot)

    def test_routes_never_build_market_and_csv_is_bounded(self):
        data, snapshot = fixture()

        class Projection:
            def snapshot(self): return snapshot
            def health(self, *, include_accuracy=True):
                return {"status": "ready", "external_requests": 0,
                        "accuracy_included": include_accuracy}

        class Cache:
            calls = 0
            def current(self):
                self.calls += 1
                return FakeMarket()

        class Repository:
            def league(self, league_id, model): return (Score(),)

        class FOIS:
            repository = Repository()

        cache = Cache()
        app = FastAPI()
        app.include_router(create_audit_router(
            require_data=lambda: data, projection_service=Projection(),
            market_cache=cache, fois_service=FOIS(),
        ))
        client = TestClient(app)
        response = client.get("/api/audit/projections/current")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["audit_summary"]["external_provider_calls"], 0)
        csv_response = client.get("/api/audit/projections/current.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("J. Daniels", csv_response.text)
        self.assertEqual(cache.calls, 2)

    def test_missing_retained_market_fails_without_starting_one(self):
        data, snapshot = fixture()

        class Projection:
            def snapshot(self): return snapshot
            def health(self, *, include_accuracy=True): return {}

        class Cache:
            def current(self): return None

        app = FastAPI()
        app.include_router(create_audit_router(
            require_data=lambda: data, projection_service=Projection(),
            market_cache=Cache(), fois_service=object(),
        ))
        self.assertEqual(TestClient(app).get("/api/audit/projections/current").status_code, 503)


if __name__ == "__main__":
    unittest.main()
