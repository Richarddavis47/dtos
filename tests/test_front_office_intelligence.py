"""Front Office Intelligence behavioral and integration contracts."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.front_offices import create_front_offices_router
from routes.trades import create_trades_router
from src.core.front_office_intelligence import build_league_model
from src.core.trade_intelligence import trade_intelligence
from tests.test_trade_intelligence import fixture_data


class FrontOfficeIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()

    def test_every_organization_has_explainable_neutral_profile(self) -> None:
        model = build_league_model(self.data)
        self.assertEqual(set(model.reports), {1, 2, 3})
        self.assertEqual(len(model.relationships), 3)
        for report in model.reports.values():
            self.assertTrue(report.evidence)
            self.assertTrue(report.philosophies)
            self.assertGreater(report.confidence, 0)
            text = f"{report.executive_summary} {report.negotiation_style}".lower()
            self.assertNotIn("good manager", text)
            self.assertNotIn("bad manager", text)

    def test_sparse_history_keeps_acceptance_probability_unavailable(self) -> None:
        report = build_league_model(self.data).compatibility(1, 2)
        self.assertIsNone(report.forecast.acceptance_probability)
        self.assertTrue(report.forecast.evidence)
        self.assertIn("insufficient", " ".join(report.forecast.notes).lower())

    def test_sufficient_observed_history_enables_conservative_probability(self) -> None:
        self.data["transactions"] = [{"type": "trade", "roster_ids": [1, 2]} for _ in range(5)]
        report = build_league_model(self.data).compatibility(1, 2)
        self.assertIsNotNone(report.forecast.acceptance_probability)
        self.assertLessEqual(report.forecast.acceptance_probability, 65)

    def test_trade_intelligence_consumes_front_office_model(self) -> None:
        with patch("src.core.trade_intelligence.engine.trade_engine.build_asset_pool") as assets:
            assets.return_value = ()
            trade_intelligence.opportunities(self.data, 1)
        self.assertGreater(assets.call_count, 0)

    def test_page_and_api_share_the_same_dossiers(self) -> None:
        async def noop() -> None:
            return None

        app = FastAPI()
        app.include_router(create_front_offices_router(ensure_fresh=noop, require_data=lambda: self.data, page=lambda _, body: HTMLResponse(body)))
        client = TestClient(app)
        api = client.get("/api/front-offices?front_office=2")
        page = client.get("/front-offices?front_office=2")
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.json()["active_front_office"], 2)
        self.assertEqual(len(api.json()["organizations"]), 3)
        self.assertIsNotNone(api.json()["decision_confidence"])
        self.assertEqual(api.json()["availability"], "available")
        self.assertTrue(api.json()["brain_snapshot_id"])
        self.assertTrue(api.json()["decision_provenance"])
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-dtos-component="recommendation"', page.text)
        self.assertIn("Franchise Management Profile", page.text)
        self.assertNotIn("<details open", page.text)

    def test_trade_and_front_office_serialize_identical_brain_decision_contracts(self) -> None:
        async def noop() -> None:
            return None

        app = FastAPI()
        def page(_: str, body: str) -> HTMLResponse:
            return HTMLResponse(body)
        app.include_router(create_front_offices_router(ensure_fresh=noop, require_data=lambda: self.data, page=page))
        app.include_router(create_trades_router(ensure_fresh=noop, require_data=lambda: self.data, page=page))
        client = TestClient(app)
        office = client.get("/api/front-offices?front_office=1").json()
        trade = client.get("/api/trades?front_office=1").json()
        for key in (
            "decision_confidence", "decision_confidence_version", "brain_snapshot_id",
            "recommendation_timestamp", "decision_provenance", "recommendation_explanation",
        ):
            self.assertEqual(office[key], trade[key], key)


if __name__ == "__main__":
    unittest.main()
