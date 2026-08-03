"""DINS 2.0 discovery, artifact, safety, and comparison regressions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from routes.inspect import create_inspection_router
from src.core.inspection import INSPECTION_SCHEMA_VERSION, InspectionArtifactStore, discover_pages
from src.core.inspection.comparison import compare_images


class VisualInspectionTests(unittest.TestCase):
    def state(self) -> dict:
        return {"last_sync": "2026-08-02T00:00:00Z", "data": {"league": {"league_id": "l1"}, "players": {"p1": {"full_name": "Player One", "position": "QB"}}, "teams": [{"roster_id": 1, "players": [{"id": "p1"}]}], "matchups": [{"matchup_id": 7}]}}

    def app(self, root: Path) -> FastAPI:
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

        app.include_router(create_inspection_router(state=self.state(), route_provider=lambda: app.routes, artifact_root=root))
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
        self.assertEqual(health["inspection_status"], "pending")
        self.assertFalse(health["production_inspection_matches_deployment"])

    def test_artifacts_are_namespaced_and_run_contract_is_retrievable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = InspectionArtifactStore(root, "https://example.test")
            page = store.current_root / "pages" / "home"
            page.mkdir(parents=True)
            payload = {"application_version": VERSION, "page_id": "home", "viewport": {"name": "desktop"}}
            (page / "desktop.json").write_text(json.dumps(payload), encoding="utf-8")
            (store.current_root / "manifest.json").write_text(json.dumps({"version": VERSION, "status": "complete", "total_pages_completed": 1}), encoding="utf-8")
            client = TestClient(self.app(root))
            response = client.get("/api/inspect/visual/pages/home/desktop")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_id"], "home")
        self.assertIn(f"v{VERSION}-b{BUILD_NUMBER}-s{INSPECTION_SCHEMA_VERSION}", store.artifact_url("pages/home/desktop.png"))

    def test_invalid_page_and_viewport_are_clean_json_errors(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            client = TestClient(self.app(Path(folder)))
            self.assertEqual(client.get("/api/inspect/pages/missing").status_code, 404)
            self.assertEqual(client.get("/api/inspect/visual/pages/home/watch").status_code, 404)

    def test_image_comparison_passes_identical_and_detects_change(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before, same, changed, diff = (root / name for name in ("before.png", "same.png", "changed.png", "diff.png"))
            Image.new("RGB", (20, 20), "white").save(before)
            Image.new("RGB", (20, 20), "white").save(same)
            Image.new("RGB", (20, 20), "black").save(changed)
            self.assertEqual(compare_images(before, same, diff).status, "pass")
            result = compare_images(before, changed, diff)
            self.assertEqual(result.status, "fail")
            self.assertEqual(result.changed_pixel_percentage, 100.0)
            self.assertTrue(diff.exists())

    def test_store_rejects_traversal_and_malformed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = InspectionArtifactStore(Path(folder))
            self.assertIsNone(store.read_json("../secret.json"))
            store.current_root.mkdir(parents=True)
            (store.current_root / "manifest.json").write_text("not-json", encoding="utf-8")
            self.assertIsNone(store.manifest())


if __name__ == "__main__":
    unittest.main()
