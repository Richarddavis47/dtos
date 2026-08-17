from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from routes.inspect import create_inspection_router
from src.core.inspection.current_visual import CurrentVisualMirror
from src.core.inspection.live_visual import CaptureRequest, LiveVisualService
from tools.inspection.verify_current_visual import verify_current


def capture_request(surface: str, viewport: str, fingerprint: str) -> CaptureRequest:
    return CaptureRequest(
        surface_id=surface, title=surface.title(), human_url=f"/{surface}",
        semantic_url=f"/api/{surface}", viewport=viewport, fingerprint=fingerprint,
        canonical={"data_as_of": "now"},
    )


class CurrentVisualMirrorTests(unittest.TestCase):
    def service(self, root: Path, color: list[str]) -> LiveVisualService:
        def capture(_request, output):
            Image.new("RGB", (20, 10), color[-1]).save(output, "PNG")
            return {}

        return LiveVisualService(root / "live", capture)

    def publish(self, service: LiveVisualService, fingerprint: str) -> None:
        service.schedule([
            capture_request("fois", "desktop", fingerprint),
            capture_request("fois", "mobile", fingerprint),
        ])
        self.assertTrue(service.wait())

    def test_candidate_promotes_atomically_and_retires_prior_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            colors = ["navy"]
            service = self.service(root, colors)
            mirror = CurrentVisualMirror(root / "rolling", service, "https://dtos.example")
            service.on_complete(mirror.promote)
            self.publish(service, "one")
            first = mirror.manifest()
            self.assertEqual(first["status"], "complete")
            self.assertEqual(first["image_count"], 2)
            self.assertEqual(first["desktop_count"], 1)
            self.assertEqual(first["mobile_count"], 1)
            self.assertEqual(first["stale_count"], 0)
            self.assertEqual(first["failed_count"], 0)
            self.assertGreater(first["current_visual_bytes"], 0)
            self.assertTrue(all(row["image_url"].startswith("https://dtos.example/") for row in first["captures"]))
            old = first["current_generation"]

            colors.append("green")
            self.publish(service, "two")
            second = mirror.manifest()
            self.assertNotEqual(second["current_generation"], old)
            self.assertEqual(second["retired_generation_count"], 1)
            self.assertEqual(second["retired_bytes_deleted"], first["current_visual_bytes"])
            generations = list((root / "rolling" / "generations").iterdir())
            self.assertEqual([path.name for path in generations], [second["current_generation"]])
            self.assertFalse(any(root.glob("rolling/.candidate-*")))

    def test_failed_or_stale_candidate_preserves_current(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service, "https://dtos.example")
            self.publish(service, "one")
            current = mirror.promote()
            service._manifest["captures"]["fois--desktop"]["status"] = "stale"
            with self.assertRaisesRegex(RuntimeError, "complete, current"):
                mirror.promote()
            self.assertEqual(mirror.manifest()["current_generation"], current["current_generation"])

            service._manifest["captures"]["fois--desktop"]["status"] = "current"
            self.publish(service, "two")
            service.screenshot("fois", "desktop").write_bytes(b"not-a-valid-png")
            with self.assertRaisesRegex(RuntimeError, "hash"):
                mirror.promote()
            self.assertEqual(mirror.manifest()["current_generation"], current["current_generation"])
            self.assertFalse(any(root.glob("rolling/.candidate-*")))

    def test_private_or_unknown_generation_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service, "https://dtos.example")
            self.publish(service, "one")
            current = mirror.promote()
            row = current["captures"][0]
            name = row["image_url"].rsplit("/", 1)[-1]
            path = mirror.image(current["current_generation"], name)
            self.assertIsNotNone(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
            self.assertIsNone(mirror.image("old-generation", name))
            self.assertNotIn("league-b", str(current).casefold())

    def test_routes_expose_stable_manifest_and_direct_decodable_png(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service, "https://dtos.example")
            self.publish(service, "one")
            manifest = mirror.promote()
            app = FastAPI()
            app.include_router(create_inspection_router(
                state={"data": {}}, route_provider=lambda: app.routes,
                live_visual_service=service, current_visual_mirror=mirror,
            ))
            client = TestClient(app)
            response = client.get("/api/inspect/current-visual/manifest")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["application_version"], VERSION)
            self.assertEqual(response.json()["application_build"], BUILD_NUMBER)
            row = manifest["captures"][0]
            image = client.get(row["image_url"].removeprefix("https://dtos.example"))
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers["content-type"], "image/png")
            self.assertEqual(hashlib.sha256(image.content).hexdigest(), row["sha256"])

    def test_external_consumer_discovers_and_decodes_actual_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service, "https://dtos.example")
            service.schedule([
                capture_request(surface, viewport, "one")
                for surface in ("fois-page", "market-page", "front-offices-page", "league-history-page")
                for viewport in ("desktop", "mobile")
            ])
            service.wait()
            manifest = mirror.promote()
            payloads = {"manifest": json.dumps(manifest).encode()}
            for row in manifest["captures"]:
                name = row["image_url"].rsplit("/", 1)[-1]
                payloads[row["image_url"]] = mirror.image(manifest["current_generation"], name).read_bytes()
            result = verify_current("manifest", fetch=lambda url: payloads[url])
            self.assertEqual(result["images_decoded"], 8)
            self.assertEqual(result["decode_failures"], 0)


if __name__ == "__main__":
    unittest.main()
