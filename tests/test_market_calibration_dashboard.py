from __future__ import annotations

import unittest
from threading import get_ident
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.valuation import create_valuation_router
from src.core.provider_network import build_provider_network
from src.core.valuation.automation import audit_market_calibration, calibration_report
from src.core.valuation.universe import ValuationUniverse


def calibration_fixture(count: int = 60, *, healthy: bool = True) -> tuple[dict, dict]:
    now = datetime.now(timezone.utc).isoformat()
    players = {
        str(index): {"name": f"Player {index}", "position": "QB", "status": "Active", "dtos_value": 100}
        for index in range(1, count + 1)
    }
    fantasy_calc = {
        str(index): {"value": 1000 + index * 100, "confidence": 95, "updated_at": now}
        for index in range(1, count + 1)
    }
    dynasty_process = {
        str(index): {"value": 800 + index * 80, "confidence": 95, "updated_at": now}
        for index in range(1, count + 1)
    }
    status = "healthy" if healthy else "failed"
    data = {
        "normalized_players": players,
        "teams": [],
        "pick_ledger": [
            {"season": 2027, "round": round_number, "original_roster_id": roster_id, "current_owner_id": roster_id}
            for roster_id in range(1, 11) for round_number in range(1, 5)
        ],
        "market_data": {
            "providers": {"FantasyCalc": fantasy_calc, "DynastyProcess": dynasty_process},
            "provider_status": {
                "FantasyCalc": {"enabled": True, "status": status, "last_refresh": now},
                "DynastyProcess": {"enabled": True, "status": status, "last_refresh": now},
                "KeepTradeCut": {"enabled": False, "status": "unsupported", "reason": "No approved integration."},
            },
        },
        "players_fetched_at": now,
    }
    return data, {"data": data, "last_sync": now}


class MarketCalibrationDashboardTests(unittest.TestCase):
    def test_full_universe_is_audited_without_sampling(self) -> None:
        data, state = calibration_fixture()
        report = audit_market_calibration(data, state, apply=False)
        self.assertEqual(report["summary"]["total_assets_audited"], 100)
        self.assertEqual(report["integrity"]["duplicate_identities"], 0)
        self.assertEqual(report["summary"]["asset_integrity_score"], 100)
        self.assertEqual(next(row for row in report["category_health"] if row["category"] == "Quarterbacks")["assets_audited"], 60)

    def test_high_confidence_adjustment_is_model_level_bounded_and_explainable(self) -> None:
        data, state = calibration_fixture()
        build_provider_network(data, state)
        report = audit_market_calibration(data, state, apply=True)
        quarterback = next(row for row in report["recommendations"] if row["category"] == "Quarterbacks")
        self.assertTrue(quarterback["applied"])
        self.assertLessEqual(abs(quarterback["proposed_adjustment"]), .03)
        self.assertTrue(all(quarterback["safety_checks"].values()))
        self.assertTrue(quarterback["evidence"])
        self.assertIn("Quarterbacks", data["calibration_state"]["adjustments"])
        self.assertFalse(any("player:" in key for key in data["calibration_state"]["adjustments"]))

    def test_adjustment_changes_only_league_adjusted_layer(self) -> None:
        data, state = calibration_fixture()
        build_provider_network(data, state)
        before = ValuationUniverse(data, state).by_id["player:1"]["layers"]
        audit_market_calibration(data, state, apply=True)
        after = ValuationUniverse(data, state).by_id["player:1"]["layers"]
        # Regeneration intentionally refreshes generated_at. Calibration must preserve
        # the stable intrinsic contract while changing only the adjusted layer.
        for field in ("value", "source", "version", "confidence", "availability"):
            self.assertEqual(before["intrinsic_dtos_value"][field], after["intrinsic_dtos_value"][field])
        self.assertNotEqual(before["intrinsic_dtos_value"]["generated_at"], after["intrinsic_dtos_value"]["generated_at"])
        self.assertNotEqual(before["league_adjusted_value"]["value"], after["league_adjusted_value"]["value"])
        self.assertEqual(before["market_value"]["value"], after["market_value"]["value"])

    def test_failed_or_stale_provider_prevents_automatic_change(self) -> None:
        data, state = calibration_fixture(healthy=False)
        build_provider_network(data, state)
        report = audit_market_calibration(data, state, apply=True)
        self.assertFalse(any(row["applied"] for row in report["recommendations"]))
        self.assertEqual(report["summary"]["providers_available"], 0)

    def test_history_records_no_action_and_applied_runs(self) -> None:
        data, state = calibration_fixture()
        build_provider_network(data, state)
        first = audit_market_calibration(data, state, apply=True)
        self.assertEqual(len(data["calibration_history"]), 1)
        self.assertEqual(data["calibration_history"][0]["model_version"], "1.10.70")
        self.assertEqual(calibration_report(data, state)["generated_at"], first["generated_at"])

    def test_api_dashboard_categories_recommendations_and_history(self) -> None:
        data, state = calibration_fixture()
        audit_market_calibration(data, state, apply=False)

        async def ready() -> None:
            return None

        app = FastAPI()
        app.include_router(create_valuation_router(
            ensure_fresh=ready,
            require_data=lambda: data,
            state=state,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        client = TestClient(app)
        self.assertEqual(client.get("/api/valuation/calibration").status_code, 200)
        self.assertTrue(client.get("/api/valuation/calibration/categories").json()["categories"])
        self.assertTrue(client.get("/api/valuation/calibration/recommendations").json()["recommendations"])
        self.assertTrue(client.get("/api/valuation/calibration/history").json()["history"])
        dashboard = client.get("/valuation/calibration")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Automated Market Calibration", dashboard.text)

    def test_dashboard_runs_cpu_reports_off_the_event_loop(self) -> None:
        data, state = calibration_fixture()
        audit_market_calibration(data, state, apply=False)
        event_loop_threads: list[int] = []
        report_threads: list[int] = []

        async def ready() -> None:
            event_loop_threads.append(get_ident())

        def calibration_worker(input_data, input_state):
            report_threads.append(get_ident())
            return calibration_report(input_data, input_state)

        from src.core.provider_network import provider_network_report
        from src.core.valuation_intelligence import valuation_intelligence_report

        def network_worker(input_data):
            report_threads.append(get_ident())
            return provider_network_report(input_data)

        def intelligence_worker(input_data):
            report_threads.append(get_ident())
            return valuation_intelligence_report(input_data)

        app = FastAPI()
        app.include_router(create_valuation_router(
            ensure_fresh=ready, require_data=lambda: data, state=state,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        with (
            patch("routes.valuation.calibration_report", side_effect=calibration_worker),
            patch("routes.valuation.provider_network_report", side_effect=network_worker),
            patch(
                "routes.valuation.valuation_intelligence_report",
                side_effect=intelligence_worker,
            ),
        ):
            response = TestClient(app).get("/valuation/calibration")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(report_threads), 3)
        self.assertTrue(event_loop_threads)
        self.assertTrue(all(thread != event_loop_threads[0] for thread in report_threads))


if __name__ == "__main__":
    unittest.main()
