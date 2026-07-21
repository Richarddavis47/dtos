"""Front Office Intelligence behavioral and integration contracts."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.front_offices import create_front_offices_router
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
        with patch("src.core.trade_intelligence.gm.partner_selection.build_league_model", wraps=build_league_model) as shared:
            trade_intelligence.opportunities(self.data, 1)
        self.assertGreater(shared.call_count, 0)

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
        self.assertEqual(page.status_code, 200)
        self.assertIn("Front Office Intelligence v1", page.text)
        self.assertNotIn("<details open", page.text)


if __name__ == "__main__":
    unittest.main()
