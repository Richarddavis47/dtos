from contextvars import ContextVar
import unittest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from routes.valuation import create_valuation_router


class NormalizationInputsRouteTests(unittest.TestCase):
    def test_selected_context_and_bounded_pagination_without_provider_work(self):
        selected = ContextVar("selected", default="A")
        states = {
            league: {"league": {"league_id": league}, "market_data": {
                "providers": {"FantasyCalc": {"1": {"value": value, "confidence": 85,
                    "updated_at": "2026-09-04T17:30:00Z", "private_unused": "must-not-serialize"}}}}}
            for league, value in (("A", 6000), ("B", 7000))
        }
        app = FastAPI()
        fresh = AsyncMock()
        app.include_router(create_valuation_router(
            ensure_fresh=fresh, require_data=lambda: states[selected.get()], state={"last_sync": "same"},
        ))
        import asyncio
        async def run(league):
            token = selected.set(league)
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                    response = await client.get("/api/valuation/normalization-inputs?limit=1")
                    self.assertEqual(response.status_code, 200)
                    return response.json()
            finally:
                selected.reset(token)
        async def concurrent():
            return await asyncio.gather(run("A"), run("B"), run("A"))
        result = asyncio.run(concurrent())
        self.assertEqual([r["league_id"] for r in result], ["A", "B", "A"])
        self.assertEqual([r["records"][0]["raw_value"] for r in result], [6000, 7000, 6000])
        self.assertNotIn("private_unused", str(result))
        self.assertEqual(result[0]["records"][0]["scale"]["reliability"], 0.90)
        self.assertEqual(result[0]["records"][0]["normalization_version"], "1.1")
        client = TestClient(app)
        self.assertEqual(client.get("/api/valuation/normalization-inputs?limit=251").status_code, 422)
        self.assertEqual(client.get("/api/valuation/normalization-inputs?offset=1").json()["records"], [])
