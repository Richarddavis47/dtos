from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from routes.inspect import create_inspection_router
from routes.current_visual import create_current_visual_router
from src.core.inspection.current_visual import (
    CurrentVisualMirror, public_manifest, public_visual_origin,
)
from src.core.inspection.discovery import unsupported_dynamic_patterns
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
            mirror = CurrentVisualMirror(root / "rolling", service)
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
            self.assertTrue(mirror.health()["current_visual_matches_deployment"])
            self.assertTrue(all(row["relative_path"].startswith("/api/inspect/current-visual/images/") for row in first["captures"]))
            self.assertNotIn("image_url", first["captures"][0])
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
            mirror = CurrentVisualMirror(root / "rolling", service)
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
            mirror = CurrentVisualMirror(root / "rolling", service)
            self.publish(service, "one")
            current = mirror.promote()
            row = current["captures"][0]
            name = row["relative_path"].rsplit("/", 1)[-1]
            path = mirror.image(current["current_generation"], name)
            self.assertIsNotNone(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
            self.assertIsNone(mirror.image("old-generation", name))
            self.assertNotIn("league-b", str(current).casefold())

    def test_routes_expose_stable_manifest_and_direct_decodable_png(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service)
            self.publish(service, "one")
            mirror.promote()
            with patch.dict("os.environ", {"DTOS_PUBLIC_URL": "https://dtos.example"}):
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
            row = response.json()["captures"][0]
            self.assertEqual(row["public_url"], "https://dtos.example" + row["relative_path"])
            self.assertEqual(row["image_url"], row["public_url"])
            image = client.get(row["relative_path"])
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers["content-type"], "image/png")
            self.assertEqual(hashlib.sha256(image.content).hexdigest(), row["sha256"])

    def test_native_consumer_routes_are_stable_allowlisted_and_head_compatible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service)
            service.schedule([
                capture_request("fois-page", viewport, "one")
                for viewport in ("desktop", "mobile")
            ])
            self.assertTrue(service.wait())
            durable = mirror.promote()
            app = FastAPI()
            app.include_router(create_current_visual_router(
                mirror=mirror, public_base="https://dtos.example",
            ))
            client = TestClient(app)
            self.assertEqual(unsupported_dynamic_patterns(app.routes), ())

            discovery = client.get("/current-visual")
            self.assertEqual(discovery.status_code, 200)
            self.assertEqual(discovery.headers["content-type"], "application/json")
            self.assertEqual(
                discovery.json()["manifest_url"],
                "https://dtos.example/current-visual/manifest.json",
            )
            self.assertEqual(discovery.json()["current_generation"], durable["current_generation"])
            self.assertEqual(client.head("/current-visual").status_code, 200)

            response = client.get("/current-visual/manifest.json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "application/json")
            self.assertEqual(response.headers["cache-control"], "public, max-age=0, must-revalidate")
            self.assertIn("etag", response.headers)
            head = client.head("/current-visual/manifest.json")
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.headers["content-type"], "application/json")
            self.assertEqual(head.content, b"")

            manifest = response.json()
            self.assertEqual(manifest["capture_count"], 2)
            self.assertFalse(manifest["transport"]["authentication_required"])
            row = next(row for row in manifest["captures"] if row["capture_id"] == "fois-page-desktop")
            self.assertEqual(row["relative_path"], "/current-visual/images/fois-page-desktop.png")
            self.assertEqual(row["generation"], durable["current_generation"])
            image = client.get(row["relative_path"])
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers["content-type"], "image/png")
            self.assertTrue(image.headers["content-disposition"].startswith("inline;"))
            self.assertEqual(hashlib.sha256(image.content).hexdigest(), row["sha256"])
            self.assertEqual(client.head(row["relative_path"]).status_code, 200)

            for path in (
                "/current-visual/images/not-registered.png",
                "/current-visual/images/%2e%2e%2fcurrent.json",
                "/current-visual/images/current.json",
            ):
                with self.subTest(path=path):
                    self.assertEqual(client.get(path).status_code, 404)

    def test_consumer_reads_do_not_capture_or_promote(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service)
            self.publish(service, "one")
            mirror.promote()
            app = FastAPI()
            app.include_router(create_current_visual_router(
                mirror=mirror, public_base="https://dtos.example",
            ))
            client = TestClient(app)
            before = mirror.manifest()
            with patch.object(service, "schedule", wraps=service.schedule) as schedule, \
                 patch.object(mirror, "promote", wraps=mirror.promote) as promote:
                manifest = client.get("/current-visual/manifest.json").json()
                client.get(manifest["captures"][0]["relative_path"])
            schedule.assert_not_called()
            promote.assert_not_called()
            self.assertEqual(mirror.manifest(), before)

    def test_external_consumer_discovers_and_decodes_actual_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root, ["navy"])
            mirror = CurrentVisualMirror(root / "rolling", service)
            service.schedule([
                capture_request(surface, viewport, "one")
                for surface in ("fois-page", "market-page", "front-offices-page", "league-history-page")
                for viewport in ("desktop", "mobile")
            ])
            service.wait()
            durable = mirror.promote()
            manifest = public_manifest(durable, "https://dtos.example")
            manifest_url = "https://dtos.example/api/inspect/current-visual/manifest"
            payloads = {manifest_url: json.dumps(manifest).encode()}
            for row in manifest["captures"]:
                name = row["relative_path"].rsplit("/", 1)[-1]
                payloads[row["public_url"]] = mirror.image(manifest["current_generation"], name).read_bytes()
            result = verify_current(manifest_url, fetch=lambda url: payloads[url])
            self.assertEqual(result["images_decoded"], 8)
            self.assertEqual(result["decode_failures"], 0)

    def test_public_origin_contract_rejects_internal_production_hosts(self):
        self.assertEqual(
            public_visual_origin("https://dtos.example/", production=True),
            "https://dtos.example",
        )
        self.assertEqual(
            public_visual_origin("http://127.0.0.1:8000", production=False),
            "http://127.0.0.1:8000",
        )
        for value in (
            "http://dtos.example", "https://127.0.0.1:10000",
            "https://localhost", "https://0.0.0.0", "https://192.168.1.4",
            "https://trusted.example/evil", "https://user@trusted.example",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                public_visual_origin(value, production=True)

    def test_legacy_loopback_manifest_is_presented_with_configured_public_origin(self):
        legacy = {
            "status": "complete", "current_generation": "abc123",
            "captures": [{
                "surface_id": "fois-page", "viewport": "desktop",
                "image_url": "http://127.0.0.1:10000/api/inspect/current-visual/images/abc123/fois-page-desktop.png",
            }],
        }
        result = public_manifest(legacy, "https://dtos.example")
        row = result["captures"][0]
        self.assertEqual(
            row["relative_path"],
            "/api/inspect/current-visual/images/abc123/fois-page-desktop.png",
        )
        self.assertEqual(row["public_url"], "https://dtos.example" + row["relative_path"])
        self.assertNotIn("127.0.0.1", json.dumps(result))

    def test_invalid_persisted_relative_identity_fails_closed(self):
        value = {
            "status": "complete", "current_generation": "abc123",
            "captures": [{"relative_path": "/api/inspect/current-visual/images/other/private.png"}],
        }
        with self.assertRaisesRegex(ValueError, "invalid relative image identity"):
            public_manifest(value, "https://dtos.example")


if __name__ == "__main__":
    unittest.main()
