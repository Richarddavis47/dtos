"""Public crawl API discovery, cache, safety, and serialization contracts."""
from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.crawl import create_crawl_router
from src.core.intelligence.cache import intelligence_cache
from tests.test_player_api import fixture_data


LEAGUE_ID = "league-1"


class CrawlApiTests(unittest.TestCase):
    def setUp(self) -> None:
        intelligence_cache.invalidate("crawl:")
        self.data = fixture_data()
        self.data["league"]["league_id"] = LEAGUE_ID
        self.data.update({"week": 1, "matchups": {}, "pick_ledger": [], "owners": [], "scoring_settings": {}, "league_settings": {}, "roster_positions": ["QB", "RB", "WR", "TE", "SUPER_FLEX"]})
        self.state = {"data": self.data, "last_sync": "2026-07-22T12:00:00+00:00", "last_error": None, "syncing": False}
        app = FastAPI()
        app.include_router(create_crawl_router(get_data=lambda: self.state["data"], state=self.state, league_id=LEAGUE_ID))
        self.client = TestClient(app)

    def test_index_discovers_public_pages_endpoints_and_sync(self) -> None:
        response = self.client.get("/api/crawl")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["valuation_schema_version"], "1.0")
        self.assertEqual(payload["default_league_id"], LEAGUE_ID)
        self.assertIn("/api/crawl/snapshot", payload["endpoints"].values())
        self.assertIn("/api/crawl/history", payload["endpoints"].values())
        self.assertIn("/teams", payload["pages"])
        self.assertEqual(response.headers["access-control-allow-origin"], "*")

    def test_snapshot_and_every_section_endpoint_are_json(self) -> None:
        endpoints = ("snapshot", "teams", "front-offices", "trades", "transactions", "matchups", "picks", "standings")
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/api/crawl/{endpoint}?league={LEAGUE_ID}")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.headers["content-type"].startswith("application/json"))
                self.assertTrue(response.json()["ok"])

    def test_history_endpoints_are_paginated_and_backwards_compatible(self) -> None:
        endpoints = (
            "history", "history/seasons", "history/matchups", "history/standings",
            "history/playoffs", "history/transactions", "history/trades",
            "history/drafts", "history/players", "history/teams",
            "history/import-status", "history/data-quality",
        )
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/api/crawl/{endpoint}?league={LEAGUE_ID}&limit=2")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["ok"])
        history = self.client.get(f"/api/crawl/history?league={LEAGUE_ID}&limit=2").json()
        self.assertEqual(history["schema_version"], "1.0")
        self.assertEqual(history["limit"], 2)

    def test_missing_usage_has_explicit_provider_reason(self) -> None:
        payload = self.client.get(
            f"/api/crawl/history/player/player-one/usage?league={LEAGUE_ID}",
        ).json()
        self.assertEqual(payload["availability"], "provider_not_supported")
        self.assertIn("provider", payload["reason"].casefold())

    def test_snapshot_uses_public_allowlist_and_contains_required_sections(self) -> None:
        payload = self.client.get("/api/crawl/snapshot").json()["data"]
        self.assertEqual(payload["valuation_schema_version"], "1.0")
        self.assertTrue({"league", "owners", "teams", "standings", "draft_picks", "matchups", "transactions", "trades", "front_offices", "rankings", "recommendations", "alerts", "sync"}.issubset(payload))
        serialized = str(payload).casefold()
        for secret in ("database_url", "password", "token", "secret", "c:\\users", "/tmp/"):
            self.assertNotIn(secret, serialized)

    def test_team_valuation_summaries_are_concise_and_canonical(self) -> None:
        self.data["market_data"] = {"providers": {"FantasyCalc": {"player one": {"value": 7200, "confidence": 85}}, "DynastyProcess": {"player one": {"value": 6500, "confidence": 75}}}}
        intelligence_cache.invalidate("crawl:")
        payload = self.client.get("/api/crawl/teams").json()
        self.assertEqual(payload["valuation_schema_version"], "1.0")
        valuation = payload["data"]["teams"][0]["roster"][0]["valuation"]
        self.assertTrue(0 <= valuation["market_value"] <= 1000)
        self.assertIn(valuation["calibration_status"], {"calibrated", "partially_calibrated", "stale"})
        self.assertNotIn("raw_value", valuation)

    def test_team_intelligence_is_shared_across_crawl_contracts(self) -> None:
        teams = self.client.get("/api/crawl/teams").json()
        front_offices = self.client.get("/api/crawl/front-offices").json()
        snapshot = self.client.get("/api/crawl/snapshot").json()
        self.assertEqual(teams["team_intelligence_schema_version"], "1.0")
        self.assertEqual(front_offices["data"]["team_intelligence_schema_version"], "1.0")
        self.assertEqual(snapshot["data"]["team_intelligence_schema_version"], "1.0")
        card = teams["data"]["teams"][0]["team_intelligence"]
        self.assertTrue({"overall", "current_contending", "dynasty", "positions", "confidence", "current_window", "explanation"}.issubset(card))
        self.assertEqual(card["current_window"], front_offices["data"]["team_intelligence"]["1"]["current_window"])

    def test_preseason_standings_are_projection_labeled(self) -> None:
        for team in self.data["teams"]:
            team.update({"wins": 0, "losses": 0, "ties": 0})
        intelligence_cache.invalidate()
        rows = self.client.get("/api/crawl/standings").json()["data"]["standings"]
        self.assertTrue(all(row["ranking_type"] == "Preseason Projection" for row in rows))

    def test_default_explicit_and_invalid_league_selection(self) -> None:
        self.assertEqual(self.client.get("/api/crawl/teams").json()["league_id"], LEAGUE_ID)
        self.assertEqual(self.client.get(f"/api/crawl/teams?league={LEAGUE_ID}").status_code, 200)
        invalid = self.client.get("/api/crawl/teams?league=not-real")
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(invalid.json()["error"], "invalid_league")

    def test_empty_data_is_valid_and_does_not_trigger_sync(self) -> None:
        self.state["data"] = {}
        self.state["last_sync"] = None
        response = self.client.get("/api/crawl/teams")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"count": 0, "teams": []})

    def test_cache_reuse_and_sync_marker_invalidation(self) -> None:
        first = self.client.get("/api/crawl/teams").json()
        second = self.client.get("/api/crawl/teams").json()
        self.assertFalse(first["cache"]["cached"])
        self.assertTrue(second["cache"]["cached"])
        self.assertEqual(first["cache"]["generated_at"], second["cache"]["generated_at"])
        self.state["last_sync"] = "2026-07-22T12:01:00+00:00"
        refreshed = self.client.get("/api/crawl/teams").json()
        self.assertFalse(refreshed["cache"]["cached"])

    def test_safe_filters_and_pagination_have_isolated_cache_keys(self) -> None:
        all_teams = self.client.get("/api/crawl/teams?limit=2").json()["data"]
        selected = self.client.get("/api/crawl/teams?team=1").json()["data"]
        self.assertEqual(len(all_teams["teams"]), 2)
        self.assertEqual(selected["teams"][0]["roster_id"], 1)

    def test_robots_and_sitemap_expose_only_public_discovery(self) -> None:
        robots = self.client.get("/robots.txt")
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("Allow: /api/crawl", robots.text)
        self.assertIn("Disallow: /sync", robots.text)
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("https://dtos.onrender.com/teams", sitemap.text)
        self.assertNotIn("/api/", sitemap.text)


if __name__ == "__main__":
    unittest.main()
