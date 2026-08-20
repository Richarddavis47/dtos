"""Build and verify the rolling GitHub Pages Current Visual transport."""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen

from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from tools.inspection.mirror import _fetcher, _validate_json_values

Fetch = Callable[[str], bytes]
_PNG = b"\x89PNG\r\n\x1a\n"
_REPRESENTATIVE = (
    "fois-page-desktop", "fois-page-mobile", "market-page-desktop",
    "front-offices-page-desktop", "teams-page-desktop", "matchups-page-desktop",
    "league-history-page-desktop",
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_name(row: dict[str, Any]) -> str:
    capture_id = str(row.get("capture_id") or "")
    if not capture_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in capture_id):
        raise RuntimeError("Current Visual contains an unsafe capture identity.")
    return capture_id + ".png"


def _validate_identity(manifest: dict[str, Any]) -> None:
    if manifest.get("status") != "complete":
        raise RuntimeError("Current Visual is not complete.")
    if manifest.get("application_version") != VERSION or manifest.get("application_build") != BUILD_NUMBER:
        raise RuntimeError("Current Visual deployment identity is not the requested release.")
    captures = manifest.get("captures") or []
    if len(captures) != 38 or manifest.get("image_count") != 38:
        raise RuntimeError("Current Visual does not contain the required 38 captures.")
    if manifest.get("stale_count") or manifest.get("failed_count"):
        raise RuntimeError("Current Visual contains stale or failed captures.")
    _validate_json_values(manifest)
    lowered = json.dumps(manifest, sort_keys=True).casefold()
    if "league b" in lowered or "private_secondary" in lowered:
        raise RuntimeError("Current Visual contains private-league material.")


def _index(manifest: dict[str, Any]) -> bytes:
    captures = {str(row["capture_id"]): row for row in manifest["captures"]}
    missing = [capture for capture in _REPRESENTATIVE if capture not in captures]
    if missing:
        raise RuntimeError("Current Visual lacks required discovery links: " + ", ".join(missing))
    links = []
    for capture_id in _REPRESENTATIVE:
        row = captures[capture_id]
        name = _safe_name(row)
        title = html.escape(str(row.get("title") or row.get("surface_id") or capture_id))
        viewport = html.escape(str(row.get("viewport") or ""))
        links.append(
            f'<li><a href="images/{name}">{title} — {viewport}</a>'
            f'<br><img src="images/{name}" alt="{title} {viewport}" loading="lazy"></li>'
        )
    version = html.escape(str(manifest["application_version"]))
    build = html.escape(str(manifest["application_build"]))
    generation = html.escape(str(manifest["current_generation"]))
    captured = html.escape(str(manifest.get("captured_at") or ""))
    commit = html.escape(str(manifest.get("commit") or ""))
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow"><title>DTOS Current Visual Mirror</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:auto;padding:2rem}}img{{max-width:100%;height:auto;border:1px solid #ccc}}li{{margin:2rem 0}}code{{overflow-wrap:anywhere}}</style></head>
<body><h1>DTOS Current Visual Mirror</h1><p>This is the current verified public DTOS visual mirror.</p>
<dl><dt>Version</dt><dd>{version}</dd><dt>Build</dt><dd>{build}</dd><dt>Generation</dt><dd><code>{generation}</code></dd>
<dt>Deployment commit</dt><dd><code>{commit}</code></dd><dt>Captured</dt><dd>{captured}</dd></dl>
<p><a href="manifest.json">Current machine-readable manifest</a></p><h2>Current major surfaces</h2><ul>{''.join(links)}</ul></body></html>"""
    return page.encode()


def build_pages_visual(
    *, source_base: str, public_base: str, output: Path, fetch: Fetch | None = None,
) -> dict[str, Any]:
    """Build one current-only static site without placing image bytes in Git."""
    fetch = fetch or _fetcher(source_base, retries=5, timeout=120)
    source = json.loads(fetch("/current-visual/manifest.json"))
    _validate_identity(source)
    public = public_base.rstrip("/") + "/current-visual"
    candidate = output.parent / (output.name + ".candidate")
    shutil.rmtree(candidate, ignore_errors=True)
    (candidate / "images").mkdir(parents=True)
    captures = []
    total = 0
    try:
        for row in sorted(source["captures"], key=lambda value: str(value["capture_id"])):
            name = _safe_name(row)
            content = fetch(str(row.get("public_url") or row.get("image_url")))
            if not content.startswith(_PNG) or hashlib.sha256(content).hexdigest() != row.get("sha256"):
                raise RuntimeError("Current Visual PNG verification failed.")
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                size = image.size
            if size != (row.get("width"), row.get("height")):
                raise RuntimeError("Current Visual PNG dimensions changed.")
            (candidate / "images" / name).write_bytes(content)
            total += len(content)
            captures.append({
                "capture_id": row["capture_id"], "surface_id": row.get("surface_id"),
                "title": row.get("title"), "viewport": row.get("viewport"),
                "bytes": len(content), "width": size[0], "height": size[1],
                "sha256": row["sha256"], "captured_at": row.get("captured_at"),
                "image_url": f"{public}/images/{quote(name)}",
            })
        manifest = {
            "status": "complete", "schema_version": "1.0",
            "kind": "dtos_static_current_visual", "application_version": VERSION,
            "application_build": BUILD_NUMBER, "commit": source.get("commit"),
            "current_generation": source["current_generation"],
            "captured_at": source.get("captured_at"), "capture_count": len(captures),
            "image_count": len(captures), "stale_count": 0, "failed_count": 0,
            "current_visual_bytes": total, "index_url": public + "/",
            "manifest_url": public + "/manifest.json", "captures": captures,
            "transport": {
                "host": "github_pages", "authentication_required": False,
                "cookies_required": False, "javascript_required": False,
                "release_number_required": False, "rolling_current_only": True,
                "actions_artifact_retention_days": 1,
            },
        }
        (candidate / "manifest.json").write_bytes(_json_bytes(manifest))
        (candidate / "index.html").write_bytes(_index(source))
        (candidate / ".nojekyll").write_bytes(b"")
        shutil.rmtree(output, ignore_errors=True)
        candidate.replace(output)
        return manifest
    except Exception:
        shutil.rmtree(candidate, ignore_errors=True)
        raise


@dataclass(frozen=True)
class PublicResponse:
    status: int
    content_type: str
    body: bytes
    final_url: str


def _public_fetch(url: str) -> PublicResponse:
    request = Request(url, headers={"Accept": "text/html,application/json,image/png,*/*", "User-Agent": "ChatGPT-User/1.0"})
    with urlopen(request, timeout=120) as response:
        return PublicResponse(response.status, response.headers.get_content_type(), response.read(), response.url)


def verify_pages_visual(index_url: str, fetch: Callable[[str], PublicResponse] | None = None) -> dict[str, Any]:
    """Verify public static transport starting from only its stable HTML index."""
    fetch = fetch or _public_fetch
    index = fetch(index_url)
    if index.status != 200 or index.content_type != "text/html" or b"DTOS Current Visual Mirror" not in index.body:
        raise RuntimeError("Static Current Visual index contract failed.")
    manifest_url = urljoin(index_url, "manifest.json")
    response = fetch(manifest_url)
    if response.status != 200 or response.content_type != "application/json":
        raise RuntimeError("Static Current Visual manifest contract failed.")
    manifest = json.loads(response.body)
    _validate_identity(manifest)
    failures = 0
    for row in manifest["captures"]:
        image = fetch(str(row["image_url"]))
        if image.status != 200 or image.content_type != "image/png":
            failures += 1
            continue
        if hashlib.sha256(image.body).hexdigest() != row["sha256"]:
            failures += 1
            continue
        with Image.open(io.BytesIO(image.body)) as decoded:
            decoded.load()
            if decoded.size != (row["width"], row["height"]):
                failures += 1
    if failures:
        raise RuntimeError(f"Static Current Visual image verification failed: {failures}")
    if urlsplit(manifest_url).hostname != urlsplit(index_url).hostname:
        raise RuntimeError("Static Current Visual discovery crossed origins.")
    return {
        "status": "complete", "index_url": index_url, "manifest_url": manifest_url,
        "generation": manifest["current_generation"], "captures": len(manifest["captures"]),
        "bytes": manifest["current_visual_bytes"], "failures": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the rolling GitHub Pages Current Visual site.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--source-base", default="https://dtos.onrender.com")
    build.add_argument("--public-base", default="https://richarddavis47.github.io/dtos")
    build.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--index-url", default="https://richarddavis47.github.io/dtos/current-visual/")
    args = parser.parse_args()
    if args.command == "build":
        result = build_pages_visual(source_base=args.source_base, public_base=args.public_base, output=args.output)
    else:
        result = verify_pages_visual(args.index_url)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
