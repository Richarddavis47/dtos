"""Seal prior core originals and immutable links without rebuilding old archives."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote
import zipfile

from common import BASE, digest, load_source, write_json


OLD_ROOT = Path("/workspace/2246-granite-activation")
PUBLISHER = Path("/workspace/dtos-publisher-2246/tools/release/publish.py")
PUBLIC_COMMIT = "ba102d1eb9f9bc90679d7b4f1fafc30cb76c1efd"
PUBLIC_PREFIX = ".task-evidence/activation-deferral-2246/validation-held"
PUBLIC_ROOT = Path("/workspace/cache-sharing-handoff") / PUBLIC_PREFIX
PUBLIC_MANIFEST_SHA256 = "0e51270d0c7509ead541b3ebde1251a6e194e720c5dca062b497879aa10d5049"
READBACK_SHA256 = "18d4fc9a8f52c7d555651ff07aa6a32b41b0e1ccc85a5c0ce46c1d7bc017c0ad"
OLD_CANDIDATE = "836d036464bfb1e13cf350e44635620b0978f05d"
OLD_TREE = "d35a21d697d603d4eb4b4f46cf88e8a514c50d77"
CORE = {
    "unittest-console.log", "canonical.log", "result.json", "manifest.json",
    "SHA256SUMS", "tests.jsonl", "canonical-trace.jsonl", "memory.jsonl",
}
ARCHIVES = (
    {
        "name": "prior-attempts-original.zip",
        "bytes": 81_491_689,
        "sha256": "39f794f9f825c3d26766239c6d3906e6f4f3d3a24c2e3f2101c31b3b6b39cb78",
        "attempt": "first-failed-local-plus-earlier-originals",
        "canonical_prefix": "prior-local-retained-deferral/local-canonical/",
        "canonical_manifest_entries": 665,
        "expected_errors": 1,
        "expected_failures": 0,
    },
    {
        "name": "local-isolated-failed-original.zip",
        "bytes": 81_042_922,
        "sha256": "cca0b7f4d239fc1338618458594b60da747e8ca3aa4988b28413c8b0a07e7da6",
        "attempt": "second-failed-local",
        "canonical_prefix": "local-canonical/",
        "canonical_manifest_entries": 667,
        "expected_errors": 0,
        "expected_failures": 1,
    },
)
SECRET = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def encoded_json(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def checked_name(name):
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or ".." in parsed.parts or "\\" in name or "private" in parsed.parts:
        raise RuntimeError("Unsafe evidence member: " + name)


def native_guards():
    sys.dont_write_bytecode = True
    specification = importlib.util.spec_from_file_location("final_prior_publisher", PUBLISHER)
    if specification is None or specification.loader is None:
        raise RuntimeError("Current publisher native guards are unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def verify_failed_canonical(archive, descriptor):
    prefix = descriptor["canonical_prefix"]
    manifest = json.loads(archive.read(prefix + "manifest.json"))
    names = [entry["name"] for entry in manifest]
    if len(names) != len(set(names)) or len(names) != descriptor["canonical_manifest_entries"]:
        raise RuntimeError("Original failed canonical manifest population changed")
    sums = [line.split("  ", 1) for line in archive.read(prefix + "SHA256SUMS").decode().splitlines()]
    if any(len(row) != 2 for row in sums) or len(sums) != len(manifest):
        raise RuntimeError("Original failed canonical checksums are incomplete")
    if {name: sha for sha, name in sums} != {entry["name"]: entry["sha256"] for entry in manifest}:
        raise RuntimeError("Original failed canonical manifest/checksum mismatch")
    for entry in manifest:
        checked_name(entry["name"])
        raw = archive.read(prefix + entry["name"])
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise RuntimeError("Original failed canonical payload changed: " + entry["name"])
    result = json.loads(archive.read(prefix + "result.json"))
    if result["head"] != OLD_CANDIDATE or result["tree"] != OLD_TREE \
            or result["passed"] is not False or result["exit_code"] != 1:
        raise RuntimeError("Original failed canonical source/outcome changed")
    events = Counter(json.loads(line)["event"] for line in archive.read(prefix + "tests.jsonl").splitlines())
    if events["start"] != 4358 or events["stop"] != 4358 \
            or events["error"] != descriptor["expected_errors"] \
            or events["failure"] != descriptor["expected_failures"] or events["skip"]:
        raise RuntimeError("Original failed canonical event population changed")
    return {
        "candidate": OLD_CANDIDATE, "tree": OLD_TREE, "passed": False,
        "canonical_manifest_entries": len(manifest), "original_manifest_bytes_verified": True,
        "events": dict(events), "scope": "Historical failed run; never final-source validation",
    }


def main():
    source = load_source()
    target = BASE / "prior-package.zip"
    receipt_path = BASE / "prior-package.json"
    if any(path.exists() or path.is_symlink() for path in (target, receipt_path)):
        raise RuntimeError("Prior package already exists; preserve it before any new attempt")
    source_sha256 = digest(BASE / "source.json")
    runner_sha256 = digest(Path(__file__))
    guard_sha256 = digest(PUBLISHER)
    supplement_path = BASE / "prior-r2-additions.py"
    supplement_sha256 = digest(supplement_path)
    b602_supplement_path = BASE / "prior-b602-additions.py"
    b602_supplement_sha256 = digest(b602_supplement_path)
    historical_r2 = Path('/workspace/2246-granite-activation/expansion/final-r2')
    historical_r2_source = json.loads((historical_r2 / 'source.json').read_bytes())
    if historical_r2_source['candidate'] != 'b602d6acd03cc1c95d85ee734d2d7f28658885cf' \
            or historical_r2_source['tree'] != '8a687ea0256d6e0031b57e08e2a1a38a90a1a535' \
            or historical_r2_source['supersedes'] != '3a19eec0a00def82418d9658414f13e090d11b14' \
            or digest(historical_r2 / 'prior-r2-additions.py') != supplement_sha256:
        raise RuntimeError('Historical R2 source/helper must remain unchanged; never relabel it as R3')
    historical_r2_source_sha256 = digest(historical_r2 / 'source.json')
    guards = native_guards()
    payloads = {}
    origins = {}

    def add(name, raw, origin):
        checked_name(name)
        if name in payloads:
            raise RuntimeError("Duplicate embedded member: " + name)
        if SECRET.search(raw):
            raise RuntimeError("Credential-shaped bytes require manual evidence review: " + name)
        payloads[name] = raw
        origins[name] = origin

    manifest_raw = (PUBLIC_ROOT / "publication-manifest.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != PUBLIC_MANIFEST_SHA256:
        raise RuntimeError("Original public held manifest changed")
    public_manifest = json.loads(manifest_raw)
    public_rows = public_manifest["files"]
    public_files = {row["name"]: row for row in public_rows}
    if len(public_files) != len(public_rows) or len(public_rows) != 622 \
            or sum(row["bytes"] for row in public_rows) != 273_973_316 \
            or public_manifest["status"] != "HELD" \
            or public_manifest["candidate"] != OLD_CANDIDATE or public_manifest["tree"] != OLD_TREE:
        raise RuntimeError("Original public held manifest association/population changed")
    sums_raw = (PUBLIC_ROOT / "PUBLIC_SHA256SUMS").read_bytes()
    sums = [line.split("  ", 1) for line in sums_raw.decode().splitlines()]
    expected_sums = {name: row["sha256"] for name, row in public_files.items()}
    expected_sums["publication-manifest.json"] = PUBLIC_MANIFEST_SHA256
    if any(len(row) != 2 for row in sums) or len(sums) != len(expected_sums) \
            or {name: sha for sha, name in sums} != expected_sums:
        raise RuntimeError("Original public held checksum list changed")
    readback_raw = (OLD_ROOT / "held-evidence-public-readback.json").read_bytes()
    if hashlib.sha256(readback_raw).hexdigest() != READBACK_SHA256:
        raise RuntimeError("Original public readback receipt changed")
    readback = json.loads(readback_raw)
    publication_raw = (OLD_ROOT / "held-evidence-publication.json").read_bytes()
    publication = json.loads(publication_raw)
    for record in (readback, publication):
        if record["commit"] != PUBLIC_COMMIT or record["prefix"] != PUBLIC_PREFIX \
                or record["manifest_sha256"] != PUBLIC_MANIFEST_SHA256 \
                or record["candidate"] != OLD_CANDIDATE or record["tree"] != OLD_TREE:
            raise RuntimeError("Original public publication/readback association changed")
    if readback["all_public_bytes_read_back"] is not True or readback["verified_files"] != 622 \
            or readback["verified_bytes"] != 273_973_316:
        raise RuntimeError("Original full public-byte readback is not established")
    add("public-held-originals/publication-manifest.json", manifest_raw, "Exact original immutable held-publication manifest")
    add("public-held-originals/PUBLIC_SHA256SUMS", sums_raw, "Exact original held-publication checksum list")
    add("public-held-originals/held-evidence-publication.json", publication_raw, "Exact original publication receipt")
    add("public-held-originals/held-evidence-public-readback.json", readback_raw, "Exact original complete remote-byte readback receipt; historical, not a new network check")

    def public_original(name):
        checked_name(name)
        row = public_files[name]
        original = PUBLIC_ROOT / name
        if original.is_symlink() or not original.is_file():
            raise RuntimeError("Original public mirror member missing: " + name)
        raw = original.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise RuntimeError("Original public mirror bytes changed: " + name)
        return raw

    linked = []
    for index, descriptor in enumerate(ARCHIVES, 1):
        name = descriptor["name"]
        if public_files[name]["bytes"] != descriptor["bytes"] \
                or public_files[name]["sha256"] != descriptor["sha256"]:
            raise RuntimeError("Original linked archive identity changed: " + name)
        original_path = PUBLIC_ROOT / name
        if original_path.is_symlink() or original_path.stat().st_size != descriptor["bytes"] \
                or digest(original_path) != descriptor["sha256"]:
            raise RuntimeError("Original linked archive bytes changed: " + name)
        guards.verify_zip(original_path)
        with zipfile.ZipFile(original_path) as archive:
            outcome = verify_failed_canonical(archive, descriptor)
            original_names = set(archive.namelist())
            if index == 1:
                old_prior_raw = archive.read("prior-manifest.json")
                old_prior = json.loads(old_prior_raw)
                if old_prior["candidate"] != OLD_CANDIDATE or old_prior["tree"] != OLD_TREE \
                        or old_prior["scope"] != "prior-attempts-only":
                    raise RuntimeError("First original prior archive source association changed")
                old_rows = old_prior["files"]
                if len(old_rows) != len({row["name"] for row in old_rows}) \
                        or {row["name"] for row in old_rows} | {"prior-manifest.json"} != original_names:
                    raise RuntimeError("First original prior archive manifest population changed")
                for row in old_rows:
                    raw = archive.read(row["name"])
                    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
                        raise RuntimeError("First original prior archive payload changed: " + row["name"])
                add("first-failed-originals/original-prior-manifest.json", old_prior_raw,
                    "Exact manifest from linked first failed/earlier-originals archive")
            prefix = descriptor["canonical_prefix"]
            for member in sorted(original_names):
                if member.endswith("/") or member == "prior-manifest.json":
                    continue
                checked_name(member)
                relative = member.removeprefix(prefix)
                is_core = member.startswith(prefix) and (relative in CORE or relative.startswith("observer/"))
                earlier_original = index == 1 and not member.startswith(prefix) \
                    and PurePosixPath(member).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".zip"}
                if is_core or earlier_original:
                    add(("first-failed-originals/" if index == 1 else "second-failed-originals/") + member,
                        archive.read(member), "Exact original member from immutable linked archive " + name)
            for core_name in CORE:
                if prefix + core_name not in original_names:
                    raise RuntimeError("Original canonical core missing: " + core_name)
        linked.append({
            "attempt": descriptor["attempt"], "file": name,
            "bytes": descriptor["bytes"], "sha256": descriptor["sha256"],
            "commit": PUBLIC_COMMIT, "prefix": PUBLIC_PREFIX,
            "raw_url": "https://raw.githubusercontent.com/Richarddavis47/dtos/" + PUBLIC_COMMIT + "/" + PUBLIC_PREFIX + "/" + quote(name),
            "browser_url": "https://github.com/Richarddavis47/dtos/blob/" + PUBLIC_COMMIT + "/" + PUBLIC_PREFIX + "/" + quote(name),
            "original_archive_rebuilt": False, "complete_original_archive_embedded": False,
            "original_archive_verified_locally": True,
            "original_remote_readback_receipt": "public-held-originals/held-evidence-public-readback.json",
            "historical_source": {"candidate": OLD_CANDIDATE, "tree": OLD_TREE},
            "canonical_outcome": outcome,
        })

    # These public-held originals preserve the second failure, focused controls,
    # skipped-command reconciliation and earlier passing hosted outcome separately.
    for name in sorted(public_files):
        if name.startswith("host-canonical-readable/"):
            selected = name.removeprefix("host-canonical-readable/") in CORE
        elif "/" not in name:
            selected = not name.endswith(".zip")
        else:
            selected = name.split("/", 1)[0] in {
                "liveness-focused", "local-remaining-gates", "fixture-cleanup-control",
                "healthy-workflow-control", "focused-module-isolation", "focused-final",
            } and PurePosixPath(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".zip"}
        if selected:
            add("old-held-checkpoint/" + name, public_original(name),
                "Exact original member from immutable held public manifest; old candidate only")

    add("PRIOR_PACKAGE_README.md", (
        "# Prior attempts only\n\n"
        "Both old complete local runs FAILED on candidate `" + OLD_CANDIDATE + "`, tree `" + OLD_TREE + "`. "
        "The first recorded one browser error after real safe Trade deferral; the second recorded one unchanged157.6226ms versus100ms latency failure. "
        "Focused passes and separately completed remaining gates do not erase either full failure.\n\n"
        "This package embeds byte-original core consoles, traces, event streams, manifests, checksums, setup failures and reconciliation controls. "
        "The two full original archives, including every original PNG and manifest payload, remain at the immutable commit-pinned URLs and SHA256 identities in LINKED_ORIGINALS.json. "
        "They are linked originals, not rebuilt archives and not embedded duplicates. The original all-byte remote readback receipt and public manifest are included verbatim. "
        "Packaging rechecks retained original archive bytes locally; it does not assert a fresh network readback.\n\n"
        "Association with final candidate `" + source["candidate"] + "`, tree `" + source["tree"] + "` records release history only. "
        "No old failed or successful check in this package certifies the expanded final source. Private Render reports, private cache data and credentials are excluded.\n\n"
        "PRIOR_SUPPLEMENT_INDEX.json separately indexes the superseded3a19 failed Product original, canceled incomplete local/hosted originals, modeled GC/viewport controls and sanitized reader/transport failures. "
        "The original failed Product ZIP is preserved byte-for-byte; no successful native Product guard is applied to it. Full Docker configurations and private signed-URL stderr remain excluded.\n"
        "B602_PRIOR_SUPPLEMENT_INDEX.json separately preserves the actual4364-test/one-failure hosted b602 canonical and intentionally canceled local2555-start/2554-stop attempt. "
        "The original failed native ZIP remains an immutable linked original. Complete canceled-local ZIP containers are newly authored containers of original member bytes, not original runtime archives. "
        "The held-worker2.0s setup assertion failed before the unchanged100ms assertion was reached; exact historical GC duration is unproven. None of this history is R3 validation.\n"
    ).encode(), "New packaging explanation; historical original files remain unedited")
    supplement_spec = importlib.util.spec_from_file_location("prior_r2_additions", supplement_path)
    if supplement_spec is None or supplement_spec.loader is None:
        raise RuntimeError("Reviewed R2 prior supplement method is unavailable")
    supplement = importlib.util.module_from_spec(supplement_spec)
    supplement_spec.loader.exec_module(supplement)
    # The reviewed R2 helper has an intentionally fixed historical source.
    # Feed it retained R2 BASE/source, never globally replace its b602/3a19 IDs.
    superseded_history = supplement.append_prior_history(historical_r2, historical_r2_source, add, guards)
    b602_spec = importlib.util.spec_from_file_location('prior_b602_additions', b602_supplement_path)
    if b602_spec is None or b602_spec.loader is None:
        raise RuntimeError('Reviewed b602 prior supplement method is unavailable')
    b602_supplement = importlib.util.module_from_spec(b602_spec)
    b602_spec.loader.exec_module(b602_supplement)
    b602_history = b602_supplement.append_b602_history(BASE, source, add, guards)
    if b602_history['b602_publication_readback_verified'] is not True:
        raise RuntimeError('Actual immutable failed-b602 publication/readback is required')
    linked.extend(b602_history['linked_originals'])
    add("LINKED_ORIGINALS.json", encoded_json({
        "scope": "prior-attempts-only", "full_original_archives_linked_not_rebuilt": True,
        "historical_public_readback": readback,
        "b602_publication_readback_verified": True,
        "fresh_remote_readback_performed_by_packager": False,
        "archives": linked,
    }), "New index of existing original archive identities; not reconstructed archive bytes")
    rows = [
        {"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "origin": origins[name]}
        for name, raw in sorted(payloads.items())
    ]
    meta = {
        "candidate": source["candidate"], "tree": source["tree"], "scope": "prior-attempts-only",
        "historical_source": {"candidate": OLD_CANDIDATE, "tree": OLD_TREE},
        "additional_historical_sources": [superseded_history, b602_history],
        "files": rows, "full_original_archives_linked_not_rebuilt": True,
        "source_boundary": "Final-source association is historical only. Every old original retains its old source and failed/passing outcome; no prior artifact substitutes for final-source gates.",
    }
    payloads["prior-manifest.json"] = encoded_json(meta)
    if sum(len(raw) for raw in payloads.values()) >= 512 * 1024**2:
        raise RuntimeError("Prior evidence exceeds the unchanged native uncompressed archive limit")
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_LZMA) as archive:
        for name, raw in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_LZMA
            info.external_attr = 0o100600 << 16
            archive.writestr(info, raw)
    if target.stat().st_size >= 100 * 1024**2:
        raise RuntimeError("Prior package must remain strictly below100MiB; original output retained for review")
    package_sha256 = digest(target)
    guards.verify_prior_evidence(target, {**source, "prior_evidence_sha256": package_sha256})
    if load_source() != source or digest(BASE / "source.json") != source_sha256 \
            or digest(PUBLISHER) != guard_sha256 or digest(Path(__file__)) != runner_sha256 \
            or digest(supplement_path) != supplement_sha256 \
            or digest(b602_supplement_path) != b602_supplement_sha256 \
            or digest(historical_r2 / 'source.json') != historical_r2_source_sha256:
        raise RuntimeError("Prior packaging source, method or native guard changed during packaging")
    write_json(receipt_path, {
        "source": source, "file": str(target), "files": len(rows),
        "bytes": target.stat().st_size, "sha256": package_sha256,
        "native_prior_guard_passed": True, "embedded_original_bytes_verified": True,
        "embedded_original_bytes_verified_scope": "Byte-original entries checked against original manifests/receipts. Derived indexes and sanitized Docker metadata are explicitly labeled and are not byte-identical full Docker originals.",
        "both_complete_original_archives_linked_not_rebuilt": True,
        "linked_originals": linked, "historical_public_readback_verified": True,
        "b602_publication_readback_verified": True,
        "fresh_remote_readback_performed": False, "private_production_reports_excluded": True,
        "publisher_guard": {"path": str(PUBLISHER), "sha256": guard_sha256},
        "runner": {"path": str(Path(__file__)), "sha256": runner_sha256},
        "supplement_runner": {"path": str(supplement_path), "sha256": supplement_sha256},
        "b602_supplement_runner": {"path": str(b602_supplement_path), "sha256": b602_supplement_sha256},
        "historical_r2_source": {"path": str(historical_r2 / 'source.json'), "sha256": historical_r2_source_sha256},
        "additional_historical_sources": [superseded_history, b602_history],
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Prior attempts integrity only; not final validation or application release",
    })


if __name__ == "__main__":
    main()
