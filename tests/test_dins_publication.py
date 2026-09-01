"""GitHub DINS publication, identity, checksum, and archive regressions."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from app_metadata import BUILD_NUMBER, VERSION
from src.core.inspection.models import INSPECTION_SCHEMA_VERSION
from src.core.inspection.publication import GitHubPublicationResolver
from tools.inspection.capture import (
    DOM_SCRIPT,
    _interaction_path,
    _interaction_target,
    _public_origin,
    _rebase_application_urls,
    _write_artifact_json,
    capture,
)
from tools.inspection.package import asset_names, package_bundle, sha256


class DinsPublicationTests(unittest.TestCase):
    commit = "abc123def456"

    def manifest(self, **changes) -> dict:
        payload = {
            "version": VERSION, "build": BUILD_NUMBER, "commit_sha": self.commit,
            "release_tag": f"v{VERSION}", "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "status": "complete", "validation_outcome": "pass", "total_pages_completed": 2,
            "total_visual_artifacts": 24, "generated_at": "2026-08-03T00:00:00+00:00",
        }
        payload.update(changes)
        return payload

    def resolver_payloads(self, manifest: dict | None = None, *, missing: tuple[str, ...] = ()) -> tuple[GitHubPublicationResolver, dict[str, bytes]]:
        manifest = manifest or self.manifest()
        names = asset_names()
        base = f"https://github.com/Richarddavis47/dtos/releases/download/v{VERSION}"
        assets = [
            {"name": name, "browser_download_url": f"{base}/{name}", "size": 10}
            for name in names.values() if name not in missing
        ]
        manifest_bytes = (json.dumps(manifest) + "\n").encode()
        checksums = {"files": {names["manifest"]: hashlib.sha256(manifest_bytes).hexdigest(), names["bundle"]: "a" * 64}}
        responses = {
            f"https://api.github.com/repos/Richarddavis47/dtos/releases/tags/v{VERSION}": json.dumps({"assets": assets, "html_url": f"https://github.com/Richarddavis47/dtos/releases/tag/v{VERSION}"}).encode(),
            f"{base}/{names['manifest']}": manifest_bytes,
            f"{base}/{names['checksums']}": json.dumps(checksums).encode(),
        }
        return GitHubPublicationResolver(ttl_seconds=60), responses

    def test_successful_complete_state_and_cache(self) -> None:
        resolver, responses = self.resolver_payloads()
        with patch("src.core.inspection.publication.deployment_metadata", return_value={"commit": self.commit, "branch": "main", "deployed_at": "now"}), patch.object(resolver, "_request", side_effect=lambda url: responses[url]) as request:
            first = resolver.current()
            second = resolver.current()
        self.assertEqual(first["publication_status"], "complete")
        self.assertTrue(first["identities_match"])
        self.assertIs(first, second)
        self.assertEqual(request.call_count, 3)

    def test_missing_release_and_api_timeout_are_explicit(self) -> None:
        resolver = GitHubPublicationResolver()
        with patch.object(resolver, "_request", side_effect=HTTPError("url", 404, "missing", {}, None)):
            self.assertEqual(resolver.current(refresh=True)["publication_status"], "pending")
        with patch.object(resolver, "_request", side_effect=TimeoutError):
            self.assertEqual(resolver.current(refresh=True)["publication_status"], "failed")

    def test_missing_and_partial_assets_are_not_complete(self) -> None:
        for missing, expected in ((tuple(asset_names().values()), "pending"), ((asset_names()["bundle"],), "partial")):
            resolver, responses = self.resolver_payloads(missing=missing)
            with patch.object(resolver, "_request", side_effect=lambda url: responses[url]):
                self.assertEqual(resolver.current()["publication_status"], expected)

    def test_stale_identity_and_corrupted_checksum_are_rejected(self) -> None:
        for manifest in (self.manifest(version="0.0.0"), self.manifest(build=0), self.manifest(commit_sha="stale"), self.manifest(release_tag="v0.0.0"), self.manifest(inspection_schema_version="0")):
            resolver, responses = self.resolver_payloads(manifest)
            with patch("src.core.inspection.publication.deployment_metadata", return_value={"commit": self.commit, "branch": "main", "deployed_at": "now"}), patch.object(resolver, "_request", side_effect=lambda url: responses[url]):
                self.assertEqual(resolver.current()["publication_status"], "stale")
        resolver, responses = self.resolver_payloads()
        checksum_url = next(url for url in responses if url.endswith("checksums.json"))
        responses[checksum_url] = json.dumps({"files": {asset_names()["manifest"]: "bad", asset_names()["bundle"]: "a" * 64}}).encode()
        with patch("src.core.inspection.publication.deployment_metadata", return_value={"commit": self.commit, "branch": "main", "deployed_at": "now"}), patch.object(resolver, "_request", side_effect=lambda url: responses[url]):
            self.assertEqual(resolver.current()["publication_status"], "stale")

    def test_deterministic_archive_checksums_and_no_repository_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "capture"
            capture.mkdir()
            (capture / "manifest.json").write_text(json.dumps(self.manifest()), encoding="utf-8")
            (capture / "site-map.json").write_text('{"pages": []}', encoding="utf-8")
            (capture / "pages").mkdir()
            (capture / "pages" / "home.json").write_text('{"page": "home"}', encoding="utf-8")
            first = package_bundle(capture, root / "first")
            second = package_bundle(capture, root / "second")
            self.assertEqual(sha256(first["bundle"]), sha256(second["bundle"]))
            checksums = json.loads(first["checksums"].read_text(encoding="utf-8"))
            self.assertEqual(checksums["files"][first["manifest"].name], sha256(first["manifest"]))
            self.assertEqual(set(path.parent for path in first.values()), {root / "first"})

    def test_republishing_same_capture_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "capture"
            capture.mkdir()
            (capture / "manifest.json").write_text(json.dumps(self.manifest()), encoding="utf-8")
            first = package_bundle(capture, root / "assets")
            hashes = {key: sha256(path) for key, path in first.items()}
            second = package_bundle(capture, root / "assets")
            self.assertEqual(hashes, {key: sha256(path) for key, path in second.items()})

    def test_public_home_page_urls_do_not_match_local_home_paths(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "capture"
            capture.mkdir()
            manifest = self.manifest(screenshot_artifact_urls=[
                "https://dtos.onrender.com/inspection-artifacts/v1.7.0/pages/home/desktop.png",
            ])
            (capture / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            assets = package_bundle(capture, root / "assets")
            self.assertTrue(assets["bundle"].is_file())

    def test_local_home_path_remains_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "capture"
            capture.mkdir()
            (capture / "manifest.json").write_text(
                json.dumps(self.manifest(build_path="/home/render/project")),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "forbidden local or sensitive reference"):
                package_bundle(capture, root / "assets")

    def test_external_attribution_origin_is_preserved_for_interaction(self) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(
                '<main><a href="https://github.com/dynastyprocess/data" '
                'target="_blank" rel="noopener">DynastyProcess</a></main>'
            )
            link = next(
                row for row in page.evaluate(DOM_SCRIPT)["nodes"]
                if row.get("role") == "link"
                and row.get("text") == "DynastyProcess"
            )
            browser.close()

        self.assertEqual(
            link["href"], "https://github.com/dynastyprocess/data",
        )
        self.assertEqual(_interaction_path(link["href"]), "/dynastyprocess/data")
        self.assertEqual(
            _interaction_target("https://dtos.onrender.com", link["href"]),
            "https://github.com/dynastyprocess/data",
        )

    def test_loopback_capture_serializes_internal_links_with_public_origin(self) -> None:
        from playwright.sync_api import sync_playwright

        html = (
            '<main><a href="/market?position=QB#asset">Market</a>'
            '<a href="https://github.com/dynastyprocess/data">External</a></main>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for capture_origin in (
                "http://127.0.0.1:10000",
                "http://localhost:10000",
                "http://[::1]:10000",
            ):
                with self.subTest(capture_origin=capture_origin):
                    page = browser.new_page()
                    page.route("**/*", lambda route: route.fulfill(
                        status=200, content_type="text/html", body=html,
                    ))
                    page.goto(f"{capture_origin}/history/2025")
                    links = {
                        row["text"]: row["href"]
                        for row in page.evaluate(DOM_SCRIPT, {
                            "captureOrigin": capture_origin,
                            "publicOrigin": "https://dtos.onrender.com",
                        })["nodes"]
                        if row.get("role") == "link"
                    }
                    page.close()
                    self.assertEqual(
                        links["Market"],
                        "https://dtos.onrender.com/market?position=QB#asset",
                    )
                    self.assertEqual(
                        links["External"], "https://github.com/dynastyprocess/data",
                    )
            browser.close()

    def test_packaging_still_rejects_surviving_loopback_dom_reference(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "capture"
            capture.mkdir()
            (capture / "manifest.json").write_text(
                json.dumps(self.manifest()), encoding="utf-8",
            )
            (capture / "desktop-dom.json").write_text(
                json.dumps({"href": "http://127.0.0.1:10000/market"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "forbidden local or sensitive reference",
            ):
                package_bundle(capture, root / "assets")

    def test_internal_interaction_target_remains_on_dtos_origin(self) -> None:
        self.assertEqual(
            _interaction_target(
                "https://dtos.onrender.com", "/players/10866",
            ),
            "https://dtos.onrender.com/players/10866",
        )

    def test_structured_artifact_origin_rebases_every_discovered_url_class(self) -> None:
        capture_origin = "http://127.0.0.1:10000"
        public_origin = "https://dtos.example"
        payload = {
            "document_url": f"{capture_origin}/market?position=WR#asset",
            "base_uri": f"{capture_origin}/market/",
            "metadata": {"canonical_url": f"{capture_origin}/market"},
            "dom": {"href": f"{capture_origin}/players/1"},
            "resource": {"src": f"{capture_origin}/static/app.css"},
            "form": {"action": f"{capture_origin}/trades?mode=build#offer"},
            "interaction": {"resulting_url": f"{capture_origin}/league"},
            "external": "https://api.sleeper.app/v1/league/1",
        }
        result = _rebase_application_urls(
            payload, capture_origin=capture_origin, public_origin=public_origin,
        )
        self.assertEqual(
            result["document_url"],
            "https://dtos.example/market?position=WR#asset",
        )
        self.assertEqual(result["base_uri"], "https://dtos.example/market/")
        self.assertEqual(result["metadata"]["canonical_url"], "https://dtos.example/market")
        self.assertEqual(result["dom"]["href"], "https://dtos.example/players/1")
        self.assertEqual(result["resource"]["src"], "https://dtos.example/static/app.css")
        self.assertEqual(
            result["form"]["action"],
            "https://dtos.example/trades?mode=build#offer",
        )
        self.assertEqual(result["interaction"]["resulting_url"], "https://dtos.example/league")
        self.assertEqual(result["external"], payload["external"])

    def test_loopback_capture_requires_explicit_public_origin(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "explicit configured public origin"):
                _public_origin("http://127.0.0.1:10000")
        self.assertEqual(
            _public_origin(
                "http://127.0.0.1:10000",
                "https://dtos.example/deployment-path",
            ),
            "https://dtos.example",
        )

    def test_production_shaped_capture_rebases_metadata_semantic_page_and_manifest(self) -> None:
        capture_origin = "http://127.0.0.1:10000"
        public_origin = "https://dtos.example"
        spec = {"page_id": "market", "page_name": "Market", "route": "/market"}

        def response(url: str) -> dict:
            if url.endswith("api/market/health"):
                return {"status": "ready"}
            if url.endswith("api/inspect/site-map"):
                return {"pages": [spec], "document_url": f"{capture_origin}/market"}
            if url.endswith("api/status"):
                return {"version": VERSION, "league_id": "league", "deployment": {"commit": self.commit, "branch": "main"}}
            if url.endswith("api/inspect/valuation"):
                return {"route": f"{capture_origin}/api/valuation", "status": "ready"}
            if url.endswith("api/inspect/health"):
                return {"historical_progress": {"url": f"{capture_origin}/history"}}
            return {"canonical_url": f"{capture_origin}/market?position=QB#asset"}

        page_result = {
            "page_id": "market", "viewport": {"name": "desktop"},
            "metrics": {"product_contract_failures": 0, "critical_accessibility_count": 0},
            "artifact_urls": {
                "viewport_screenshot": f"{capture_origin}/inspection/market.png",
                "full_page_screenshot": f"{capture_origin}/inspection/market-full.png",
            },
            "interactions": (), "accessibility": {"violations": ()},
            "network": {"console_errors": (), "failed_requests": ()},
            "canonical_url": f"{capture_origin}/market?position=QB#asset",
        }
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch("tools.inspection.capture._json", side_effect=response),
                patch("tools.inspection.capture.VIEWPORTS", (type("Viewport", (), {"name": "desktop"})(),)),
                patch("tools.inspection.capture._capture_page", return_value=page_result),
                patch("tools.inspection.capture.sync_playwright"),
            ):
                root = Path(folder)
                result = capture(capture_origin, root, public_url=public_origin)
                capture_root = next(root.iterdir())
                text = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in capture_root.rglob("*.json")
                )
                self.assertNotIn("127.0.0.1", text)
                self.assertIn("https://dtos.example/market?position=QB#asset", text)
                self.assertEqual(result["commit_sha"], self.commit)
                package_bundle(capture_root, root / "package")

    def test_non_url_text_is_not_scrubbed_and_fail_closed_packaging_rejects_it(self) -> None:
        marker = "diagnostic mentions 127.0.0.1 but is not a structured URL"
        normalized = _rebase_application_urls(
            {"diagnostic": marker}, capture_origin="http://127.0.0.1:10000",
            public_origin="https://dtos.example",
        )
        self.assertEqual(normalized["diagnostic"], marker)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture_root = root / "capture"
            capture_root.mkdir()
            (capture_root / "manifest.json").write_text(
                json.dumps(self.manifest()), encoding="utf-8",
            )
            _write_artifact_json(
                capture_root / "diagnostic.json", normalized,
                capture_origin="http://127.0.0.1:10000",
                public_origin="https://dtos.example",
            )
            with self.assertRaisesRegex(ValueError, "forbidden local or sensitive reference"):
                package_bundle(capture_root, root / "package")


if __name__ == "__main__":
    unittest.main()
