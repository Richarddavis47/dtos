from __future__ import annotations

import ast
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

    def test_capture_grace_keeps_normal_requests_ahead_of_browser_start(self):
        entered = threading.Event()

        def capture(_item, output):
            entered.set()
            Image.new("RGB", (10, 10), "navy").save(output, "PNG")
            return {}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(
                Path(folder), capture, start_grace_seconds=0.1,
            )
            self.assertEqual(service.schedule([request()]), 1)
            self.assertFalse(entered.wait(0.05))
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

    def test_capture_critical_pages_do_not_render_on_event_loop(self):
        root = Path(__file__).resolve().parents[1]
        for relative, function_name in (
            ("routes/market.py", "market_page"),
            ("routes/fois.py", "fois_page"),
        ):
            tree = ast.parse((root / relative).read_text(encoding="utf-8"))
            functions = [node for node in ast.walk(tree)
                         if getattr(node, "name", None) == function_name]
            self.assertEqual(len(functions), 1)
            self.assertIsInstance(functions[0], ast.FunctionDef)

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

    def test_matchups_mobile_transient_failure_retries_once_and_recovers(self):
        calls = 0

        def capture(_item, output):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("transient fixture timeout")
            Image.new("RGB", (390, 844), "navy").save(output, "PNG")
            return {
                "capture_process": {
                    "worker_rss_peak_bytes": 12_000,
                    "browser_rss_peak_bytes": 34_000,
                },
            }

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            self.assertEqual(service.schedule([request()]), 1)
            self.assertTrue(service.wait())
            health = service.health(1)
            self.assertEqual(calls, 2)
            self.assertEqual(health["current"], 1)
            self.assertEqual(health["stale"], 0)
            self.assertEqual(health["captures_retried"], 1)
            self.assertEqual(health["capture_attempt_failures"], 1)
            self.assertEqual(health["captures_failed"], 0)
            self.assertEqual(health["capture_worker_peak"], 1)
            self.assertEqual(health["browser_process_peak"], 1)
            self.assertEqual(health["capture_worker_rss_peak_bytes"], 12_000)
            self.assertEqual(health["browser_rss_peak_bytes"], 34_000)
            self.assertNotIn(
                "capture_process",
                service.capture("matchups-1", "mobile")["presentation"],
            )

    def test_production_shaped_flight_is_single_flight_and_complete(self):
        active = 0
        peak = 0
        lock = threading.Lock()

        def capture(_item, output):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                Image.new("RGB", (20, 10), "navy").save(output, "PNG")
                return {}
            finally:
                with lock:
                    active -= 1

        requests = [
            CaptureRequest(
                surface_id=f"surface-{index}", title=f"Surface {index}",
                human_url=f"/surface/{index}", semantic_url=f"/api/surface/{index}",
                viewport=viewport, fingerprint=f"{index}-{viewport}", canonical={},
            )
            for index in range(19) for viewport in ("mobile", "desktop")
        ]
        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            self.assertEqual(service.schedule(requests), 38)
            self.assertEqual(service.schedule(requests), 0)
            self.assertTrue(service.wait())
            health = service.health(38)
            self.assertEqual(peak, 1)
            self.assertEqual(health["required_captures"], 38)
            self.assertEqual(health["captures_started"], 38)
            self.assertEqual(health["captures_completed"], 38)
            self.assertEqual(health["captures_failed"], 0)
            self.assertEqual(health["current"], 38)
            self.assertEqual(health["stale"], 0)
            self.assertEqual(health["candidate_state"], "complete")

    def test_stale_mobile_capture_refreshes_through_registered_contract(self):
        calls = []

        def capture(item, output):
            calls.append((item.surface_id, item.viewport))
            Image.new("RGB", (10, 10), "navy" if len(calls) == 1 else "green").save(output, "PNG")
            return {"attempt": len(calls)}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            self.assertEqual(service.schedule([request()]), 1)
            self.assertTrue(service.wait())
            service._manifest["captures"]["matchups-1--mobile"]["status"] = "stale"
            prior = service.screenshot("matchups-1", "mobile").read_bytes()
            self.assertEqual(service.refresh("matchups-1", "mobile")["status"], "stale")
            self.assertTrue(service.wait())
            self.assertNotEqual(service.screenshot("matchups-1", "mobile").read_bytes(), prior)
            self.assertEqual(service.capture("matchups-1", "mobile")["status"], "current")
            health = service.health(1)
            self.assertEqual(health["stale"], 0)
            self.assertEqual(health["current"], 1)
            self.assertEqual(health["refresh_requested"], 1)
            self.assertEqual(health["refresh_started"], 1)
            self.assertEqual(health["refresh_succeeded"], 1)
            self.assertEqual(calls, [("matchups-1", "mobile"), ("matchups-1", "mobile")])

    def test_generic_desktop_stale_refresh_and_current_poll_dedupe(self):
        calls = []

        def capture(item, output):
            calls.append(item.viewport)
            Image.new("RGB", (10, 10), "black").save(output, "PNG")
            return {}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            desktop = request(viewport="desktop")
            service.schedule([desktop])
            service.wait()
            service._manifest["captures"]["matchups-1--desktop"]["status"] = "stale"
            service.refresh("matchups-1", "desktop")
            service.wait()
            self.assertEqual(service.refresh("matchups-1", "desktop")["status"], "current")
            self.assertEqual(calls, ["desktop", "desktop"])
            self.assertEqual(service.health(1)["refresh_deduped"], 1)

    def test_failed_manifest_publication_restores_prior_image_and_metadata(self):
        calls = 0

        def capture(_item, output):
            nonlocal calls
            calls += 1
            Image.new("RGB", (10, 10), "black" if calls == 1 else "white").save(output, "PNG")
            return {"attempt": calls}

        with tempfile.TemporaryDirectory() as folder:
            service = LiveVisualService(Path(folder), capture)
            service.schedule([request()])
            service.wait()
            old_image = service.screenshot("matchups-1", "mobile").read_bytes()
            old_row = service.capture("matchups-1", "mobile")
            service._manifest["captures"]["matchups-1--mobile"]["status"] = "stale"
            original_write = service._write_manifest
            failed = False

            def fail_once():
                nonlocal failed
                if not failed:
                    failed = True
                    raise OSError("fixture publication failure")
                original_write()

            service._write_manifest = fail_once
            service.refresh("matchups-1", "mobile")
            service.wait()
            self.assertEqual(service.screenshot("matchups-1", "mobile").read_bytes(), old_image)
            row = service.capture("matchups-1", "mobile")
            self.assertEqual(row["fingerprint"], old_row["fingerprint"])
            self.assertEqual(row["status"], "stale")
            self.assertEqual(service.health(1)["refresh_failed"], 1)

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
