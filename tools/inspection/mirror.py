"""Build the small, public External Visual Inspection Mirror from live artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from tools.inspection.package import _validate_public_content

Fetch = Callable[[str], bytes]
_MATCHUP_DETAIL_SURFACE = re.compile(r"matchups-([1-9][0-9]*)\Z")


def matchup_detail_id(surface_id: str) -> str | None:
    """Return the numeric matchup ID only for canonical detail surfaces."""
    match = _MATCHUP_DETAIL_SURFACE.fullmatch(surface_id)
    return match.group(1) if match else None


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_json_values(value: Any) -> None:
    """Reject sensitive values before JSON escaping can obscure path markers."""
    if isinstance(value, dict):
        for item in value.values():
            _validate_json_values(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json_values(item)
    elif isinstance(value, str):
        lowered = value.casefold()
        forbidden = ("localhost", "127.0.0.1", "c:\\users\\", "authorization:", "cookie:")
        if any(marker in lowered for marker in forbidden) or lowered.startswith("/home/"):
            raise ValueError("Mirror JSON contains a forbidden local or sensitive reference.")


def _name(surface_id: str) -> str:
    matchup_id = matchup_detail_id(surface_id)
    if matchup_id is not None:
        return "matchup-" + matchup_id
    return surface_id


def _fetcher(base_url: str, retries: int = 3, timeout: float = 60) -> Fetch:
    base = base_url.rstrip("/")

    def fetch(path: str) -> bytes:
        url = path if path.startswith("https://") else base + path
        error: Exception | None = None
        for attempt in range(retries):
            try:
                request = Request(url, headers={
                    "Accept": "application/json,image/png,*/*",
                    "User-Agent": "DTOS-External-Visual-Mirror/1.0",
                    "X-DTOS-Inspection": "deterministic",
                })
                with urlopen(request, timeout=timeout) as response:
                    return response.read()
            except (OSError, HTTPError, URLError, TimeoutError) as exc:
                error = exc
                if attempt + 1 < retries:
                    time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"Mirror source request failed after {retries} attempts: {type(error).__name__}")

    return fetch


def _write(output: Path, name: str, content: bytes) -> dict[str, Any]:
    _validate_public_content(Path(name), content)
    path = output / name
    path.write_bytes(content)
    return {"name": name, "bytes": len(content), "sha256": _sha256(content)}


def build_mirror(
    *, base_url: str, output: Path, repository: str = "Richarddavis47/dtos",
    fetch: Fetch | None = None, require_dins: bool = False,
) -> dict[str, Any]:
    """Copy exact verified live artifacts into a bounded release mirror."""
    fetch = fetch or _fetcher(base_url)
    output.mkdir(parents=True, exist_ok=True)
    live = json.loads(fetch("/api/inspect/live"))
    visual = json.loads(fetch("/api/inspect/live/visual/manifest"))
    audit = json.loads(fetch("/api/audit/projections/current"))
    catalog = json.loads(fetch("/api/inspect/live/visual"))
    for payload in (live, visual, audit, catalog):
        _validate_json_values(payload)
    if require_dins:
        dins = json.loads(fetch("/api/inspect/health?refresh=true"))
        if dins.get("inspection_status") != "complete" or not dins.get("production_inspection_matches_deployment"):
            raise RuntimeError("DINS publication is not complete for the running deployment.")
    if visual.get("status") != "complete" or not visual.get("captures"):
        raise RuntimeError("Live Visual Inspection is not complete.")
    identity = live.get("identity") or {}
    expected = {
        "application_version": VERSION, "application_build": BUILD_NUMBER,
    }
    if any(identity.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Production identity does not match the mirror packager.")

    tag = f"v{VERSION}"
    download = f"https://github.com/{repository}/releases/download/{tag}"
    artifacts: list[dict[str, Any]] = []
    artifacts.append(_write(output, "dtos-live-inspection-root.json", _json_bytes(live)))
    artifacts.append(_write(output, "dtos-live-visual-manifest.json", _json_bytes(visual)))
    artifacts.append(_write(output, "dtos-live-surface-catalog.json", _json_bytes(catalog)))
    artifacts.append(_write(output, "dtos-projection-audit-current.json", _json_bytes(audit)))

    audit_rows = {
        (str(row.get("matchup_id")), str(row.get("roster_id")), str(row.get("player_id"))): row
        for row in audit.get("players") or []
    }
    semantic_by_surface: dict[str, dict[str, Any]] = {}
    entries = []
    for row in sorted(visual.get("captures") or [], key=lambda item: (item["surface_id"], item["viewport"])):
        if row.get("status") != "current":
            raise RuntimeError("The mirror refuses stale or partial visual captures.")
        surface_id = str(row["surface_id"])
        public_name = _name(surface_id)
        screenshot_name = f"{public_name}-{row['viewport']}.png"
        screenshot = fetch(str(row["screenshot_url"]))
        if not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"{screenshot_name} is not a PNG.")
        temporary = output / f".{screenshot_name}.verify"
        temporary.write_bytes(screenshot)
        try:
            with Image.open(temporary) as image:
                width, height = image.size
        finally:
            temporary.unlink(missing_ok=True)
        if width <= 0 or height <= 0:
            raise RuntimeError(f"{screenshot_name} has invalid dimensions.")
        screenshot_artifact = _write(output, screenshot_name, screenshot)
        artifacts.append(screenshot_artifact)

        semantic = semantic_by_surface.get(surface_id)
        semantic_name = f"{public_name}-semantic.json"
        if semantic is None:
            semantic = json.loads(fetch(str(row["semantic_url"])))
            _validate_json_values(semantic)
            semantic_by_surface[surface_id] = semantic
            artifacts.append(_write(output, semantic_name, _json_bytes(semantic)))

        presentation = (row.get("presentation") or {}).get("presentation_contract") or {}
        starter_count = sum(
            len(team.get("starters") or []) for team in semantic.get("teams") or []
        )
        matchup_id = matchup_detail_id(surface_id)
        if matchup_id is not None:
            if starter_count != presentation.get("starter_count") or starter_count != 22:
                raise RuntimeError(f"{surface_id} starter counts do not reconcile.")
            for team in semantic.get("teams") or []:
                for starter in team.get("starters") or []:
                    audit_row = audit_rows.get((matchup_id, str(team.get("roster_id")), str(starter.get("player_id"))))
                    if audit_row is None:
                        raise RuntimeError(f"{surface_id} starter is absent from the projection audit.")
                    displayed = starter.get("displayed") or {}
                    for field in ("sleeper_projection", "dtos_projection"):
                        if displayed.get(field) != audit_row.get(field):
                            raise RuntimeError(f"{surface_id} {field} does not match the projection audit.")
            if not presentation.get("sleeper_projection_visible") or not presentation.get("dtos_projection_visible"):
                raise RuntimeError(f"{surface_id} does not visibly expose both projection sources.")
        entries.append({
            "surface_id": surface_id, "title": row.get("title"),
            "human_url": row.get("human_url"), "semantic_url": row.get("semantic_url"),
            "live_visual_url": row.get("screenshot_url"),
            "mirror_url": f"{download}/{screenshot_name}",
            "semantic_mirror_url": f"{download}/{semantic_name}",
            "viewport": row.get("viewport"), "sha256": screenshot_artifact["sha256"],
            "bytes": screenshot_artifact["bytes"], "width": width, "height": height,
            "captured_at": row.get("captured_at"), "starter_count": starter_count,
            "projection_visibility": {
                "sleeper": bool(presentation.get("sleeper_projection_visible")),
                "dtos": bool(presentation.get("dtos_projection_visible")),
            },
        })

    manifest_name = f"dtos-v{VERSION}-visual-mirror-manifest.json"
    manifest = {
        "status": "complete", "schema_version": "1.0", "version": VERSION,
        "build": BUILD_NUMBER, "commit": identity.get("commit"),
        "league": {"id": identity.get("league_id"), "name": identity.get("league_name")},
        "captured_at": visual.get("last_capture"),
        "projection_snapshot_id": identity.get("projection_snapshot_id"),
        "brain_snapshot_id": identity.get("brain_snapshot_id"),
        "asset_market_generation": identity.get("asset_market_generation"),
        "canonical_source": base_url.rstrip("/"), "release_tag": tag,
        "current_manifest_url": "https://github.com/Richarddavis47/dtos/releases/latest/download/dtos-live-inspection-current.json",
        "release_manifest_url": f"{download}/{manifest_name}",
        "projection_audit_url": f"{download}/dtos-projection-audit-current.json",
        "surface_catalog_url": f"{download}/dtos-live-surface-catalog.json",
        "entries": entries,
        "matchup_directory": {
            "surface_id": "matchups-page",
            "entries": sorted({
                row["surface_id"] for row in entries
                if matchup_detail_id(str(row["surface_id"])) is not None
            }),
        },
        "catalog": catalog.get("eligible_surfaces") or [],
        "artifact_count": len(artifacts),
        "total_bytes": sum(row["bytes"] for row in artifacts),
        "side_effect_contract": {
            "provider_calls": 0, "projection_refreshes": 0, "brain_regenerations": 0,
            "asset_market_constructions": 0, "fois_writes": 0, "history_writes": 0,
        },
    }
    release_manifest = _write(output, manifest_name, _json_bytes(manifest))
    current_manifest = _write(output, "dtos-live-inspection-current.json", _json_bytes(manifest))
    artifacts.extend((release_manifest, current_manifest))
    checksums = {
        "algorithm": "sha256", "release_tag": tag,
        "files": {row["name"]: row["sha256"] for row in artifacts},
    }
    checksum_artifact = _write(output, f"dtos-v{VERSION}-visual-mirror-checksums.json", _json_bytes(checksums))
    artifacts.append(checksum_artifact)
    return {**manifest, "artifacts": artifacts, "artifact_count": len(artifacts),
            "total_bytes": sum(row["bytes"] for row in artifacts)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public DTOS visual mirror.")
    parser.add_argument("--base-url", default="https://dtos.onrender.com")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", default="Richarddavis47/dtos")
    parser.add_argument("--require-dins", action="store_true")
    args = parser.parse_args()
    result = build_mirror(
        base_url=args.base_url, output=args.output,
        repository=args.repository, require_dins=args.require_dins,
    )
    print(json.dumps({
        "status": result["status"], "version": result["version"],
        "artifacts": result["artifact_count"], "bytes": result["total_bytes"],
        "matchup_captures": sum(
            matchup_detail_id(str(row["surface_id"])) is not None
            for row in result["entries"]
        ),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
