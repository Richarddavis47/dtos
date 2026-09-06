"""The retired archive is absent; independent product protections remain."""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.inspect import create_inspection_router


class VisualRetirementTests(unittest.TestCase):
    def test_semantic_health_needs_no_artifacts_or_publication(self):
        app = FastAPI()
        app.include_router(create_inspection_router(state={}))
        with TestClient(app) as client:
            health = client.get("/api/inspect/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["mode"], "semantic_read_only")
            self.assertNotIn("publication_status", health.json())
            for path in (
                "/api/inspect/visual", "/api/inspect/releases/current",
                "/api/inspect/current-visual/manifest", "/api/inspect/live/visual",
            ):
                self.assertEqual(client.get(path).status_code, 404)

    def test_application_has_no_capture_stack_or_public_download_routes(self):
        script = (
            "import sys; import dtos_app; "
            "assert 'playwright.sync_api' not in sys.modules; "
            "assert not hasattr(dtos_app, 'live_visual_service'); "
            "assert not hasattr(dtos_app, 'current_visual_mirror'); "
            "assert not any(r.path.startswith(('/current-visual', '/inspection-artifacts')) "
            "for r in dtos_app.app.routes if hasattr(r, 'path'))"
        )
        result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manager_pages_remain_off_the_event_loop(self):
        root = Path(__file__).resolve().parents[1]
        for relative, name in (("routes/market.py", "market_page"),
                               ("routes/fois.py", "fois_page")):
            tree = ast.parse((root / relative).read_text(encoding="utf-8"))
            functions = [node for node in ast.walk(tree) if getattr(node, "name", None) == name]
            self.assertEqual(len(functions), 1)
            self.assertIsInstance(functions[0], ast.FunctionDef)
