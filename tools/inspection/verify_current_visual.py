"""Verify stable current visual discovery and actual externally consumable images."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit

from PIL import Image

from tools.inspection.mirror import _fetcher


def verify_current(
    manifest_url: str, fetch: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    fetch = fetch or _fetcher("https://dtos.onrender.com", retries=3, timeout=60)
    manifest = json.loads(fetch(manifest_url))
    if manifest.get("status") != "complete" or not manifest.get("current_generation"):
        raise RuntimeError("Current visual mirror is not complete.")
    if manifest.get("stale_count") or manifest.get("failed_count"):
        raise RuntimeError("Current visual mirror contains stale or failed captures.")
    captures = manifest.get("captures") or []
    if len(captures) != manifest.get("image_count"):
        raise RuntimeError("Current visual mirror image inventory is inconsistent.")
    decoded = []
    manifest_origin = urlsplit(manifest_url)
    for row in captures:
        relative = str(row.get("relative_path") or "")
        public_url = str(row.get("public_url") or row.get("image_url") or "")
        if not relative.startswith((
            "/api/inspect/current-visual/images/", "/current-visual/images/",
        )):
            raise RuntimeError("Current visual image has an invalid relative identity.")
        if not public_url:
            public_url = urljoin(manifest_url, relative)
        parsed = urlsplit(public_url)
        if (
            parsed.scheme != "https" or parsed.netloc != manifest_origin.netloc
            or (parsed.hostname or "").casefold() in {
                "localhost", "127.0.0.1", "0.0.0.0", "::1",
            }
        ):
            raise RuntimeError("Current visual image does not use a safe public HTTPS origin.")
        image_bytes = fetch(public_url)
        if hashlib.sha256(image_bytes).hexdigest() != row.get("sha256"):
            raise RuntimeError("Current visual image hash mismatch.")
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                width, height = image.size
                content_type = Image.MIME.get(image.format)
        except (OSError, ValueError) as exc:
            raise RuntimeError("Current visual image cannot be decoded.") from exc
        if content_type != "image/png" or width <= 0 or height <= 0:
            raise RuntimeError("Current visual image has an invalid native image contract.")
        if (width, height) != (row.get("width"), row.get("height")):
            raise RuntimeError("Current visual image dimensions differ from the manifest.")
        decoded.append({
            "surface_id": row.get("surface_id"), "viewport": row.get("viewport"),
            "bytes": len(image_bytes), "width": width, "height": height,
        })
    surfaces = {str(row.get("surface_id")) for row in captures}
    required = {"fois-page", "market-page", "front-offices-page", "league-history-page"}
    missing = sorted(required - surfaces)
    if missing:
        raise RuntimeError("Current visual mirror is missing required review surfaces: " + ", ".join(missing))
    return {
        "status": "complete", "current_generation": manifest["current_generation"],
        "version": manifest.get("application_version"), "build": manifest.get("application_build"),
        "images_decoded": len(decoded), "decoded": decoded,
        "failed_downloads": 0, "hash_mismatches": 0, "decode_failures": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DTOS current visual images from stable discovery.")
    parser.add_argument(
        "--manifest-url", default="https://dtos.onrender.com/current-visual/manifest.json",
    )
    args = parser.parse_args()
    print(json.dumps(verify_current(args.manifest_url), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
