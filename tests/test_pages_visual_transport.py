from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from tools.inspection.pages_visual import PublicResponse, build_pages_visual, verify_pages_visual


def png(color: str = "navy") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (20, 10), color).save(output, "PNG")
    return output.getvalue()


class PagesVisualTransportTests(unittest.TestCase):
    def fixture(self) -> dict[str, bytes]:
        captures = []
        payloads: dict[str, bytes] = {}
        required = [
            "fois-page-desktop", "fois-page-mobile", "market-page-desktop",
            "front-offices-page-desktop", "teams-page-desktop", "matchups-page-desktop",
            "league-history-page-desktop",
        ]
        for index in range(38):
            capture_id = required[index] if index < len(required) else f"surface-{index}-desktop"
            content = png("navy" if index % 2 else "green")
            url = f"https://dtos.example/current-visual/images/{capture_id}.png"
            payloads[url] = content
            captures.append({
                "capture_id": capture_id, "surface_id": capture_id.rsplit("-", 1)[0],
                "title": capture_id, "viewport": "mobile" if capture_id.endswith("mobile") else "desktop",
                "public_url": url, "sha256": hashlib.sha256(content).hexdigest(),
                "width": 20, "height": 10, "captured_at": "now",
            })
        manifest = {
            "status": "complete", "application_version": VERSION,
            "application_build": BUILD_NUMBER, "commit": "abc", "current_generation": "generation",
            "captured_at": "now", "image_count": 38, "stale_count": 0, "failed_count": 0,
            "captures": captures,
        }
        payloads["/current-visual/manifest.json"] = json.dumps(manifest).encode()
        return payloads

    def test_static_site_is_current_only_discoverable_and_not_git_backed(self):
        values = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "current-visual"
            result = build_pages_visual(
                source_base="https://dtos.example", public_base="https://owner.github.io/dtos",
                output=output, fetch=lambda url: values[url],
            )
            self.assertEqual(result["capture_count"], 38)
            self.assertEqual(result["transport"]["actions_artifact_retention_days"], 1)
            page = (output / "index.html").read_text()
            self.assertIn("DTOS Current Visual Mirror", page)
            self.assertIn('href="manifest.json"', page)
            self.assertIn("fois-page-desktop.png", page)
            self.assertFalse(any(path.name == ".git" for path in output.rglob("*")))
            self.assertEqual(len(list((output / "images").glob("*.png"))), 38)

    def test_verifier_starts_from_html_and_checks_every_png(self):
        values = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "current-visual"
            build_pages_visual(
                source_base="https://dtos.example", public_base="https://owner.github.io/dtos",
                output=output, fetch=lambda url: values[url],
            )
            root = "https://owner.github.io/dtos/current-visual/"
            def fetch(url: str) -> PublicResponse:
                relative = url.removeprefix(root)
                path = output / (relative or "index.html")
                media = "text/html" if path.suffix == ".html" else "application/json" if path.suffix == ".json" else "image/png"
                return PublicResponse(200, media, path.read_bytes(), url)
            result = verify_pages_visual(root, fetch=fetch)
            self.assertEqual(result["captures"], 38)
            self.assertEqual(result["failures"], 0)

    def test_missing_private_malformed_or_failed_candidate_cannot_publish(self):
        for mutation, message in (
            (lambda value: value["captures"].__setitem__(0, {**value["captures"][0], "capture_id": "../private"}), "unsafe"),
            (lambda value: value.__setitem__("image_count", 37), "38"),
            (lambda value: value.__setitem__("private", "League B"), "private"),
        ):
            values = self.fixture()
            manifest = json.loads(values["/current-visual/manifest.json"])
            mutation(manifest)
            values["/current-visual/manifest.json"] = json.dumps(manifest).encode()
            with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(RuntimeError, message):
                build_pages_visual(
                    source_base="https://dtos.example", public_base="https://owner.github.io/dtos",
                    output=Path(folder) / "current-visual", fetch=lambda url: values[url],
                )

    def test_failed_replacement_preserves_existing_current(self):
        values = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "current-visual"
            build_pages_visual(source_base="https://dtos.example", public_base="https://owner.github.io/dtos", output=output, fetch=lambda url: values[url])
            before = (output / "manifest.json").read_bytes()
            first_image = next(key for key in values if key.startswith("https://"))
            values[first_image] = b"not png"
            with self.assertRaisesRegex(RuntimeError, "PNG"):
                build_pages_visual(source_base="https://dtos.example", public_base="https://owner.github.io/dtos", output=output, fetch=lambda url: values[url])
            self.assertEqual((output / "manifest.json").read_bytes(), before)
            self.assertFalse((Path(folder) / "current-visual.candidate").exists())


if __name__ == "__main__":
    unittest.main()
