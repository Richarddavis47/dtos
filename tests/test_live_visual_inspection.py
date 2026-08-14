from __future__ import annotations

import tempfile
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from routes.inspect import create_inspection_router
from src.core.inspection.live_visual import CaptureRequest, LiveVisualService
from src.platform.lifecycle import lifecycle_coordinator


def request(fingerprint: str = "one", viewport: str = "mobile") -> CaptureRequest:
    return CaptureRequest(
        surface_id="matchups-1", title="Alpha vs Beta", human_url="/matchups/1",
        semantic_url="/api/inspect/live/matchups/1", viewport=viewport,
        fingerprint=fingerprint,
        canonical={"projection_snapshot_id": "projection", "brain_snapshot_id": "brain"},
    )


class LiveVisualInspectionTests(unittest.TestCase):
    def tearDown(self):
        lifecycle_coordinator.reset()

    def test_browser_capture_waits_for_market_semantic_phase(self):
        entered = threading.Event()

        def capture(_item, output):
            entered.set()
            Image.new("RGB", (10, 10), "navy").save(output, "PNG")
            return {}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            with lifecycle_coordinator.phase("asset_market_build"):
                self.assertEqual(service.schedule([request()]), 1)
                self.assertFalse(entered.wait(0.05))
                self.assertEqual(service.health(1)["browser_processes"], 0)
            self.assertTrue(service.wait())
            self.assertTrue(entered.is_set())

    def test_first_generation_reservation_defers_browser_until_market_ready(self):
        entered = threading.Event()

        def capture(_item, output):
            entered.set()
            Image.new("RGB", (10, 10), "navy").save(output, "PNG")
            return {}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            lifecycle_coordinator.reserve_market_critical("No compatible market.")
            self.assertEqual(service.schedule([request()]), 1)
            self.assertFalse(entered.wait(0.1))
            health = service.health(1)
            self.assertEqual(health["browser_processes"], 0)
            self.assertGreater(health["deferred_captures"], 0)
            self.assertEqual(health["defer_reason"], "market_critical")
            lifecycle_coordinator.release_market_critical()
            self.assertTrue(service.wait())
            self.assertTrue(entered.is_set())

    def test_application_import_does_not_load_browser_capture_stack(self):
        script = (
            "import sys; import dtos_app; "
            "assert 'src.core.inspection.live_browser' not in sys.modules; "
            "assert 'playwright.sync_api' not in sys.modules; "
            "assert 'tools.inspection.capture' not in sys.modules"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_capture_is_deduplicated_and_public_png_is_valid(self):
        calls = []

        def capture(item, output):
            calls.append(item.fingerprint)
            Image.new("RGB", (390, 844), "navy").save(output, "PNG")
            return {"presentation_contract": {"starter_count": 22}}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            self.assertEqual(service.schedule([request(), request()]), 1)
            self.assertTrue(service.wait())
            self.assertEqual(service.schedule([request()]), 0)
            self.assertEqual(calls, ["one"])
            with Image.open(service.screenshot("matchups-1", "mobile")) as image:
                self.assertEqual(image.size, (390, 844))

    def test_failure_preserves_last_valid_capture(self):
        fail = False

        def capture(_item, output):
            if fail:
                raise RuntimeError("private fixture detail")
            Image.new("RGB", (10, 10), "black").save(output, "PNG")
            return {}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            service.schedule([request()])
            service.wait()
            original = service.screenshot("matchups-1", "mobile").read_bytes()
            fail = True
            service.schedule([request("two")])
            service.wait()
            self.assertEqual(service.screenshot("matchups-1", "mobile").read_bytes(), original)
            self.assertEqual(service.capture("matchups-1", "mobile")["status"], "stale")
            self.assertNotIn("private fixture detail", service.health(1)["last_error"])

    def test_public_routes_are_read_only_and_pending_is_bounded(self):
        state = {"data": {"league": {"league_id": "league"}, "matchups": {"1": []}}}
        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder))
            app = FastAPI()
            app.include_router(create_inspection_router(
                state=state, route_provider=lambda: app.routes,
                live_visual_service=service, league_id="league",
            ))
            client = TestClient(app)
            root = client.get("/api/inspect/live").json()
            health = client.get("/api/inspect/live/visual/health").json()
            pending = client.get("/api/inspect/live/visual/metadata/matchups-1/mobile").json()
            self.assertEqual(root["visual_inspection"], "/api/inspect/live/visual")
            self.assertIn("current_manifest", root["external_visual_mirror"])
            self.assertEqual(health["status"], "pending")
            self.assertEqual(health["browser_processes"], 0)
            self.assertEqual(pending["status"], "pending")

    def test_atomic_publication_failure_does_not_expose_partial_file(self):
        def broken(_item, output):
            output.write_bytes(b"partial")
            raise RuntimeError("capture")

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), broken)
            service.schedule([request()])
            service.wait()
            self.assertIsNone(service.screenshot("matchups-1", "mobile"))
            self.assertFalse(any(Path(folder).rglob("*.partial.png")))


if __name__ == "__main__":
    unittest.main()
