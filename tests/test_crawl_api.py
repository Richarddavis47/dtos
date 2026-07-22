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
        self.assertEqual(payload["default_league_id"], LEAGUE_ID)
        self.assertIn("/api/crawl/snapshot", payload["endpoints"].values())
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

    def test_snapshot_uses_public_allowlist_and_contains_required_sections(self) -> None:
        payload = self.client.get("/api/crawl/snapshot").json()["data"]
        self.assertTrue({"league", "owners", "teams", "standings", "draft_picks", "matchups", "transactions", "trades", "front_offices", "rankings", "recommendations", "alerts", "sync"}.issubset(payload))
        serialized = str(payload).casefold()
        for secret in ("database_url", "password", "token", "secret", "c:\\users", "/tmp/"):
            self.assertNotIn(secret, serialized)

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
