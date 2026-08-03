"""Build deterministic, sanitized GitHub Release assets from a DINS capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from app_metadata import BUILD_NUMBER, VERSION


def asset_names(version: str = VERSION) -> dict[str, str]:
    prefix = f"dtos-v{version}-dins"
    return {"bundle": f"{prefix}-full.zip", "manifest": f"{prefix}-manifest.json", "checksums": f"{prefix}-checksums.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _validate_public_content(path: Path, content: bytes) -> None:
    if path.suffix.casefold() not in {".json", ".txt", ".html", ".xml"}:
        return
    text = content.decode("utf-8", errors="replace").casefold()
    forbidden = ("localhost", "127.0.0.1", "c:\\users\\", "authorization:", "cookie:")
    local_home_path = re.search(r"(?<![a-z0-9._~:/-])/home/", text)
    if any(item in text for item in forbidden) or local_home_path:
        raise ValueError(f"Capture contains a forbidden local or sensitive reference in {path.name}.")


def package_bundle(capture_root: Path, output: Path, *, repository: str = "Richarddavis47/dtos") -> dict[str, Path]:
    """Create deterministic release assets without writing inside the repository."""
    manifest_path = capture_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != VERSION or manifest.get("build") != BUILD_NUMBER:
        raise ValueError("Capture version/build does not match the running packager.")
    names = asset_names()
    tag = f"v{VERSION}"
    download = f"https://github.com/{repository}/releases/download/{tag}"
    manifest.update({
        "release_tag": tag,
        "github_release_url": f"https://github.com/{repository}/releases/tag/{tag}",
        "full_bundle_url": f"{download}/{names['bundle']}",
        "published_manifest_url": f"{download}/{names['manifest']}",
        "checksums_url": f"{download}/{names['checksums']}",
        "checksum_algorithm": "sha256",
        "artifact_access": {"mode": "zip", "bundle_url": f"{download}/{names['bundle']}", "internal_root": "dins/"},
    })
    _validate_public_content(Path("manifest.json"), _json_bytes(manifest))
    output.mkdir(parents=True, exist_ok=True)
    manifest_asset = output / names["manifest"]
    manifest_asset.write_bytes(_json_bytes(manifest))
    bundle = output / names["bundle"]
    files = sorted(path for path in capture_root.rglob("*") if path.is_file() and path != manifest_path)
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in [(Path("manifest.json"), manifest_asset.read_bytes()), *[(path.relative_to(capture_root), path.read_bytes()) for path in files]]:
            _validate_public_content(path, content)
            info = zipfile.ZipInfo(f"dins/{path.as_posix()}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    checksums = output / names["checksums"]
    checksums.write_bytes(_json_bytes({"algorithm": "sha256", "release_tag": tag, "files": {names["bundle"]: sha256(bundle), names["manifest"]: sha256(manifest_asset)}}))
    return {"bundle": bundle, "manifest": manifest_asset, "checksums": checksums}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", default="Richarddavis47/dtos")
    args = parser.parse_args()
    assets = package_bundle(args.capture_root, args.output, repository=args.repository)
    print(json.dumps({key: str(path) for key, path in assets.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
