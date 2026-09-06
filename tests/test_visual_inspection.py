"""Semantic discovery and deployment identity regressions (no visual archive)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from routes.inspect import create_inspection_router
from src.core.inspection import discover_pages


class VisualInspectionTests(unittest.TestCase):
    def state(self) -> dict:
        return {"last_sync": "2026-08-02T00:00:00Z", "data": {"league": {"league_id": "l1"}, "players": {"p1": {"full_name": "Player One", "position": "QB"}}, "teams": [{"roster_id": 1, "team_name": "Team 1", "owner": "Owner 1", "players": [{"id": "p1"}]}], "matchups": [{"matchup_id": 7}]}}

    def app(self, root: Path, publication_payload: dict | None = None) -> FastAPI:
        app = FastAPI()

        @app.get("/", response_class=HTMLResponse)
        async def home() -> HTMLResponse:
            return HTMLResponse("<h1>Home</h1>")

        @app.get("/teams/{roster_id}", response_class=HTMLResponse)
        async def team(roster_id: int) -> HTMLResponse:
            return HTMLResponse(f"<h1>Team {roster_id}</h1>")

        @app.get("/players/{player_id}", response_class=HTMLResponse)
        async def player(player_id: str) -> HTMLResponse:
            return HTMLResponse(f"<h1>{player_id}</h1>")

        app.include_router(create_inspection_router(state=self.state(), route_provider=lambda: app.routes))
        return app

    def test_discovery_resolves_dynamic_routes_and_excludes_api(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            app = self.app(Path(folder))
            pages = discover_pages(app.routes, self.state())
        routes = {page.route for page in pages}
        self.assertIn("/", routes)
        self.assertIn("/teams/1", routes)
        self.assertIn("/players/p1", routes)
        self.assertNotIn("/api/inspect", routes)

    def test_discovery_uses_meaningful_dynamic_page_names(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            pages = discover_pages(self.app(Path(folder)).routes, self.state())
        names = {page.route: page.page_name for page in pages}
        self.assertEqual(names["/teams/1"], "Team 1 Headquarters")
        self.assertEqual(names["/players/p1"], "Player One — Player Intelligence")

    def test_public_contract_exposes_schema_site_map_and_pending_health(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            client = TestClient(self.app(Path(folder)))
            schema = client.get("/api/inspect/schema").json()
            site_map = client.get("/api/inspect/site-map").json()
            health = client.get("/api/inspect/health").json()
        self.assertEqual(schema["inspection_schema_version"], "2.0")
        self.assertEqual(schema["application_version"], VERSION)
        self.assertEqual(schema["application_build"], BUILD_NUMBER)
        self.assertGreaterEqual(site_map["metrics"]["inspectable"], 3)
        self.assertEqual(health["mode"], "semantic_read_only")
        self.assertNotIn("publication_status", health)

    def test_invalid_page_and_viewport_are_clean_json_errors(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            client = TestClient(self.app(Path(folder)))
            self.assertEqual(client.get("/api/inspect/pages/missing").status_code, 404)
            self.assertEqual(client.get("/api/inspect/visual/pages/home/watch").status_code, 404)

    def test_deployment_provenance_contract_is_complete(self) -> None:
        deployment = deployment_metadata()
        self.assertEqual(set(deployment), {"branch", "commit", "deployed_at"})
        self.assertTrue(all(deployment.values()))


if __name__ == "__main__":
    unittest.main()
