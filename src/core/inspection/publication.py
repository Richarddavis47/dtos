"""Public GitHub Release discovery for immutable DINS bundles."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.inspection.models import INSPECTION_SCHEMA_VERSION

REQUIRED_ASSET_SUFFIXES = ("dins-full.zip", "dins-manifest.json", "dins-checksums.json")


@dataclass(frozen=True)
class PublicationResult:
    payload: dict[str, Any]
    expires_at: float


class GitHubPublicationResolver:
    """Resolve and validate the running release's public DINS assets."""

    def __init__(self, repository: str | None = None, *, ttl_seconds: int = 300, timeout: float = 5.0) -> None:
        self.repository = repository or os.getenv("DTOS_GITHUB_REPOSITORY", "Richarddavis47/dtos")
        self.ttl_seconds = ttl_seconds
        self.timeout = timeout
        self._cached: PublicationResult | None = None
        self._lock = threading.Lock()

    @property
    def tag(self) -> str:
        return f"v{VERSION}"

    def _request(self, url: str) -> bytes:
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "DTOS-DINS/1.0"})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def _pending(self, status: str, reason: str) -> dict[str, Any]:
        deployment = deployment_metadata()
        return {
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "production_commit": deployment["commit"], "expected_release_tag": self.tag,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "publication_status": status, "status": status, "reason": reason,
            "identities_match": False, "published_manifest_url": None,
            "full_bundle_url": None, "checksums_url": None,
        }

    def _resolve(self) -> dict[str, Any]:
        release_url = f"https://api.github.com/repos/{self.repository}/releases/tags/{self.tag}"
        try:
            release = json.loads(self._request(release_url))
        except HTTPError as exc:
            return self._pending("pending" if exc.code == 404 else "failed", f"GitHub release lookup returned HTTP {exc.code}.")
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._pending("failed", f"GitHub release lookup failed: {type(exc).__name__}.")
        assets = {str(row.get("name")): row for row in release.get("assets") or []}
        names = {suffix: f"dtos-{self.tag}-{suffix}" for suffix in REQUIRED_ASSET_SUFFIXES}
        missing = [name for name in names.values() if name not in assets]
        if missing:
            result = self._pending("partial" if assets else "pending", "Required GitHub Release assets are not yet published.")
            result["missing_assets"] = missing
            return result
        urls = {suffix: str(assets[name].get("browser_download_url") or "") for suffix, name in names.items()}
        try:
            manifest_bytes = self._request(urls["dins-manifest.json"])
            checksum_bytes = self._request(urls["dins-checksums.json"])
            manifest = json.loads(manifest_bytes)
            checksums = json.loads(checksum_bytes)
        except (OSError, URLError, TimeoutError, json.JSONDecodeError, HTTPError) as exc:
            return self._pending("failed", f"Published DINS metadata could not be read: {type(exc).__name__}.")
        expected_manifest_hash = (checksums.get("files") or {}).get(names["dins-manifest.json"])
        expected_bundle_hash = (checksums.get("files") or {}).get(names["dins-full.zip"])
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        bundle_size = int(assets[names["dins-full.zip"]].get("size") or 0)
        checksum_valid = (
            expected_manifest_hash == manifest_hash
            and isinstance(expected_bundle_hash, str)
            and len(expected_bundle_hash) == 64
            and all(character in "0123456789abcdef" for character in expected_bundle_hash.casefold())
            and bundle_size > 0
        )
        deployment = deployment_metadata()
        identity = {
            "version": manifest.get("version") == VERSION,
            "build": manifest.get("build") == BUILD_NUMBER,
            "commit": manifest.get("commit_sha") == deployment["commit"],
            "tag": manifest.get("release_tag") == self.tag,
            "schema": manifest.get("inspection_schema_version") == INSPECTION_SCHEMA_VERSION,
            "checksums": checksum_valid,
            "bundle_asset": bundle_size > 0,
            "capture": manifest.get("validation_outcome") == "pass" and manifest.get("status") == "complete",
        }
        complete = all(identity.values())
        return {
            **manifest,
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "production_commit": deployment["commit"], "expected_release_tag": self.tag,
            "publication_status": "complete" if complete else "stale",
            "status": "complete" if complete else "stale", "identities_match": complete,
            "identity_checks": identity, "published_manifest_url": urls["dins-manifest.json"],
            "full_bundle_url": urls["dins-full.zip"], "checksums_url": urls["dins-checksums.json"],
            "release_url": str(release.get("html_url") or ""),
        }

    def current(self, *, refresh: bool = False) -> dict[str, Any]:
        now = monotonic()
        with self._lock:
            if not refresh and self._cached is not None and self._cached.expires_at > now:
                return self._cached.payload
            payload = self._resolve()
            self._cached = PublicationResult(payload, now + self.ttl_seconds)
            return payload
