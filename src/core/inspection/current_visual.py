"""Atomic, rolling current-product visual mirror over verified Live Visual bytes."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.inspection.live_visual import LIVE_VIEWPORTS, LiveVisualService

CURRENT_VISUAL_SCHEMA_VERSION = "1.1"
CURRENT_VISUAL_ROUTE = "/api/inspect/current-visual"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "-" for char in value)


def public_visual_origin(value: str, *, production: bool) -> str:
    """Validate the configured public origin without trusting request headers."""
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").casefold()
    if (
        not host or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.scheme not in ({"https"} if production else {"http", "https"})
    ):
        raise ValueError("DTOS_PUBLIC_URL must be a valid public origin.")
    prohibited = host in {"localhost", "0.0.0.0", "::1"}
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if production and (prohibited or (address is not None and not address.is_global)):
        raise ValueError("DTOS_PUBLIC_URL cannot use an internal origin in production.")
    return value.strip().rstrip("/")


def public_manifest(value: dict[str, Any], public_base: str) -> dict[str, Any]:
    """Present one durable relative manifest through a validated public origin."""
    result = json.loads(json.dumps(value))
    result["manifest_url"] = f"{public_base}{CURRENT_VISUAL_ROUTE}/manifest"
    generation = str(result.get("current_generation") or "")
    for row in result.get("captures") or []:
        relative = str(row.get("relative_path") or "")
        if not relative:
            legacy = str(row.get("image_url") or "")
            name = legacy.rsplit("/", 1)[-1]
            if generation and Path(name).name == name and name.endswith(".png"):
                relative = f"{CURRENT_VISUAL_ROUTE}/images/{generation}/{name}"
        prefix = f"{CURRENT_VISUAL_ROUTE}/images/{generation}/"
        name = relative.removeprefix(prefix)
        if (
            not relative.startswith(prefix) or Path(name).name != name
            or not name.endswith(".png") or name[:-4] != _safe(name[:-4])
        ):
            raise ValueError("Current visual manifest contains an invalid relative image identity.")
        row["relative_path"] = relative
        row["public_url"] = f"{public_base}{relative}"
        # Preserve the v1.10.37 consumer field while correcting its derivation.
        row["image_url"] = row["public_url"]
    return result


class CurrentVisualMirror:
    """Keep exactly one externally inspectable generation with safe candidate handoff."""

    def __init__(self, root: Path, live: LiveVisualService) -> None:
        self.root = root
        self.live = live
        self._lock = threading.RLock()
        self._last_error: str | None = None

    @property
    def pointer_path(self) -> Path:
        return self.root / "current.json"

    def _read(self, path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def manifest(self) -> dict[str, Any]:
        with self._lock:
            value = self._read(self.pointer_path)
            if value is None:
                return {
                    "status": "pending", "schema_version": CURRENT_VISUAL_SCHEMA_VERSION,
                    "current_generation": None, "candidate_generation": None,
                    "captures": [], "capture_count": 0, "image_count": 0,
                    "stale_count": 0, "failed_count": int(self._last_error is not None),
                    "last_error": self._last_error,
                }
            return value

    def image(self, generation: str, name: str) -> Path | None:
        current = self.manifest()
        if (
            generation != current.get("current_generation")
            or Path(name).name != name or not name.endswith(".png")
            or name[:-4] != _safe(name[:-4])
        ):
            return None
        path = (self.root / "generations" / generation / "images" / name).resolve()
        generation_root = (self.root / "generations" / generation).resolve()
        return path if generation_root in path.parents and path.is_file() else None

    @staticmethod
    def _link(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)

    @staticmethod
    def _generation(rows: list[dict[str, Any]]) -> str:
        semantic = [{
            "surface_id": row["surface_id"], "viewport": row["viewport"],
            "artifact_hash": row["artifact_hash"], "fingerprint": row["fingerprint"],
        } for row in rows]
        return hashlib.sha256(_json_bytes(semantic)).hexdigest()[:24]

    def promote(self) -> dict[str, Any]:
        """Stage, verify, and atomically publish one complete current generation."""
        with self._lock:
            source = self.live.manifest()
            rows = sorted(source.get("captures") or [], key=lambda row: (row["surface_id"], row["viewport"]))
            if (
                source.get("status") != "complete" or not rows
                or source.get("stale") or source.get("failures")
                or any(row.get("status") != "current" for row in rows)
                or any(row.get("application_version") != VERSION or row.get("application_build") != BUILD_NUMBER for row in rows)
            ):
                raise RuntimeError("Only a complete, current Live Visual generation may be promoted.")
            generation = self._generation(rows)
            previous = self._read(self.pointer_path)
            if previous and previous.get("current_generation") == generation:
                return previous

            candidate = self.root / f".candidate-{generation}"
            final = self.root / "generations" / generation
            final_created = False
            shutil.rmtree(candidate, ignore_errors=True)
            candidate.mkdir(parents=True)
            captures: list[dict[str, Any]] = []
            candidate_bytes = 0
            try:
                for row in rows:
                    surface = _safe(str(row["surface_id"]))
                    viewport = str(row["viewport"])
                    if viewport not in LIVE_VIEWPORTS:
                        raise RuntimeError("Current visual candidate contains an unknown viewport.")
                    source_path = self.live.screenshot(surface, viewport)
                    if source_path is None:
                        raise RuntimeError("Current visual candidate is missing a required image.")
                    name = f"{surface}-{viewport}.png"
                    target = candidate / "images" / name
                    self._link(source_path, target)
                    digest = hashlib.sha256(target.read_bytes()).hexdigest()
                    if digest != row.get("artifact_hash"):
                        raise RuntimeError("Current visual candidate hash does not match Live Visual.")
                    with Image.open(target) as image:
                        image.verify()
                    with Image.open(target) as image:
                        width, height = image.size
                    size = target.stat().st_size
                    if size <= 0 or width <= 0 or height <= 0:
                        raise RuntimeError("Current visual candidate image is invalid.")
                    candidate_bytes += size
                    captures.append({
                        "surface_id": row["surface_id"], "title": row.get("title"),
                        "route": row.get("human_url"), "viewport": viewport,
                        "league_context": "public_primary", "captured_at": row.get("captured_at"),
                        "purpose": f"Current {row.get('title') or row['surface_id']} {viewport} product view",
                        "content_type": "image/png", "bytes": size, "sha256": digest,
                        "width": width, "height": height,
                        "relative_path": f"{CURRENT_VISUAL_ROUTE}/images/{generation}/{name}",
                    })
                deployment = deployment_metadata()
                prior_bytes = int((previous or {}).get("current_visual_bytes") or 0)
                manifest = {
                    "status": "complete", "schema_version": CURRENT_VISUAL_SCHEMA_VERSION,
                    "current_generation": generation, "candidate_generation": None,
                    "application_version": VERSION, "application_build": BUILD_NUMBER,
                    "commit": deployment.get("commit"), "deployment_identity": deployment,
                    "captured_at": source.get("last_capture"),
                    "manifest_path": f"{CURRENT_VISUAL_ROUTE}/manifest",
                    "captures": captures, "capture_count": len(captures),
                    "image_count": len(captures),
                    "desktop_count": sum(row["viewport"] == "desktop" for row in captures),
                    "mobile_count": sum(row["viewport"] == "mobile" for row in captures),
                    "matchup_count": len({row["surface_id"] for row in captures if str(row["surface_id"]).startswith("matchups-") and str(row["surface_id"])[9:].isdigit()}),
                    "current_visual_bytes": candidate_bytes, "candidate_visual_bytes": 0,
                    "retired_generation_count": int((previous or {}).get("retired_generation_count") or 0) + int(bool(previous)),
                    "retired_bytes_deleted": prior_bytes,
                    "stale_count": 0, "failed_count": 0,
                    "retention": "rolling_current_only",
                }
                manifest["manifest_bytes"] = 0
                for _attempt in range(3):
                    manifest["manifest_bytes"] = len(_json_bytes(manifest))
                (candidate / "manifest.json").write_bytes(_json_bytes(manifest))
                if final.exists():
                    shutil.rmtree(final)
                final.parent.mkdir(parents=True, exist_ok=True)
                candidate.replace(final)
                final_created = True
                self.root.mkdir(parents=True, exist_ok=True)
                temporary = self.pointer_path.with_suffix(".tmp")
                temporary.write_bytes(_json_bytes(manifest))
                temporary.replace(self.pointer_path)
                for path in final.parent.iterdir():
                    if path.is_dir() and path != final:
                        shutil.rmtree(path)
                self._last_error = None
                return manifest
            except Exception as exc:
                shutil.rmtree(candidate, ignore_errors=True)
                if final_created and (previous or {}).get("current_generation") != generation:
                    shutil.rmtree(final, ignore_errors=True)
                self._last_error = f"{type(exc).__name__}: candidate publication failed"
                raise

    def health(self) -> dict[str, Any]:
        value = self.manifest()
        return {key: value.get(key) for key in (
            "status", "current_generation", "candidate_generation", "current_visual_bytes",
            "candidate_visual_bytes", "retired_generation_count", "retired_bytes_deleted",
            "capture_count", "image_count", "manifest_bytes", "stale_count", "failed_count",
        )}
