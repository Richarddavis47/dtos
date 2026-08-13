"""Verify the public mirror using GitHub only; never contact the DTOS origin."""
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any, Callable

from app_metadata import BUILD_NUMBER, VERSION
from tools.inspection.mirror import _fetcher, matchup_detail_id


def verify(url: str, fetch: Callable[[str], bytes] | None = None) -> dict[str, Any]:
    fetch = fetch or _fetcher("https://github.com", retries=5, timeout=120)
    manifest = json.loads(fetch(url))
    if manifest.get("status") != "complete":
        raise RuntimeError("External Visual Mirror is not complete.")
    if manifest.get("version") != VERSION or manifest.get("build") != BUILD_NUMBER:
        raise RuntimeError("External Visual Mirror identity is stale.")
    audit = json.loads(fetch(str(manifest["projection_audit_url"])))
    audit_rows = {
        (str(row.get("matchup_id")), str(row.get("roster_id")), str(row.get("player_id"))): row
        for row in audit.get("players") or []
    }
    if (audit.get("identity") or {}).get("projection_snapshot_id") != manifest.get("projection_snapshot_id"):
        raise RuntimeError("Projection audit identity does not match the mirror.")
    semantic_cache: dict[str, Any] = {}
    matchup_images = 0
    for entry in manifest.get("entries") or []:
        image = fetch(str(entry["mirror_url"]))
        if hashlib.sha256(image).hexdigest() != entry.get("sha256"):
            raise RuntimeError("Mirrored PNG hash mismatch.")
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Mirrored visual is not a PNG.")
        matchup_id = matchup_detail_id(str(entry.get("surface_id")))
        if matchup_id is None:
            continue
        matchup_images += 1
        semantic_url = str(entry["semantic_mirror_url"])
        if semantic_url not in semantic_cache:
            semantic_cache[semantic_url] = json.loads(fetch(semantic_url))
        semantic = semantic_cache[semantic_url]
        starters = [(team, starter) for team in semantic.get("teams") or []
                    for starter in team.get("starters") or []]
        if len(starters) != entry.get("starter_count") or len(starters) != 22:
            raise RuntimeError("Mirrored matchup starter count mismatch.")
        if not all((entry.get("projection_visibility") or {}).values()):
            raise RuntimeError("Mirrored matchup projection labels are incomplete.")
        for team, starter in starters:
            expected = audit_rows.get((matchup_id, str(team.get("roster_id")), str(starter.get("player_id"))))
            if expected is None:
                raise RuntimeError("Mirrored starter is absent from projection audit.")
            displayed = starter.get("displayed") or {}
            for field in ("sleeper_projection", "dtos_projection"):
                if displayed.get(field) != expected.get(field):
                    raise RuntimeError("Mirrored projection differs from projection audit.")
    if matchup_images == 0 or matchup_images % 2:
        raise RuntimeError("Mirrored matchup viewport inventory is incomplete.")
    directory = manifest.get("matchup_directory") or {}
    directory_entries = set(directory.get("entries") or [])
    expected_entries = {
        str(entry["surface_id"]) for entry in manifest.get("entries") or []
        if matchup_detail_id(str(entry.get("surface_id"))) is not None
    }
    if directory.get("surface_id") != "matchups-page" or directory_entries != expected_entries:
        raise RuntimeError("Mirrored matchup directory discovery is inconsistent.")
    return {
        "status": "complete", "version": VERSION,
        "artifacts_verified": len(manifest.get("entries") or []),
        "matchup_images": matchup_images,
        "matchups": matchup_images // 2,
        "failed_downloads": 0, "hash_mismatches": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the anonymous GitHub-only visual mirror.")
    parser.add_argument(
        "--manifest-url",
        default="https://github.com/Richarddavis47/dtos/releases/latest/download/dtos-live-inspection-current.json",
    )
    args = parser.parse_args()
    result = verify(args.manifest_url)
    print("External Visual Mirror: complete")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
