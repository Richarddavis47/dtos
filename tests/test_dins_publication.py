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


if __name__ == "__main__":
    unittest.main()
