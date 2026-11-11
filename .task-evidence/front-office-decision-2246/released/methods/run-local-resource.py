"""Prepare fresh final-source native resource proof; never overwrite old attempts."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from common import (
    BASE,
    IMAGE,
    SOURCE_CHECKOUT,
    assert_checkout,
    digest,
    docker_base,
    image_record,
    load_source,
    write_json,
)


OLD_ROOT = Path("/workspace/2246-granite-activation")
PUBLISHER = Path("/workspace/dtos-publisher-2246/tools/release/publish.py")
FROZEN_FIXTURES = {
    "oneqb.json": "98d76b8452431ff3e6f961b6bddd9a654f7b6d23129d96cce60e52cbf79cb11b",
    "superflex.json": "49915270f727cd3eb6a3a792b8531a487d7da96a06c031ee0e5a176887f69c81",
    "projections.sqlite3": "43541f6a3c738d0ebeac0794cdfd7c009bd27f450816919315b824b512a7b708",
}
STUDY_SHA256 = "df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439"
STUDY_BYTES = 9_072_793
CASE_NAMES = ("local-preflight", "local-restoration-unused", "local-resident-refresh")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def checked_copy(original, destination, expected_sha256):
    """Verify the frozen original before and after copying it into this attempt."""
    if not original.is_file() or digest(original) != expected_sha256:
        raise RuntimeError("Missing or changed frozen input: " + str(original))
    with original.open("rb") as reader, destination.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
    if digest(destination) != expected_sha256 or digest(original) != expected_sha256:
        raise RuntimeError("Frozen input copy changed: " + str(original))
    destination.chmod(0o444)
    return {
        "original": str(original),
        "copy": str(destination),
        "bytes": destination.stat().st_size,
        "sha256": expected_sha256,
        "copied_without_modification": True,
    }


def publisher_guards():
    # Loading this host-only guard module creates no publisher source changes.
    # Suppress .pyc writes as the publisher is an immutable input to this runner.
    sys.dont_write_bytecode = True
    specification = importlib.util.spec_from_file_location("final_resource_publisher", PUBLISHER)
    if specification is None or specification.loader is None:
        raise RuntimeError("Current publisher native guards are unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main():
    source = load_source()
    assert_checkout(source)
    source_before = digest(BASE / "source.json")
    runner_sha256 = digest(Path(__file__))
    common_sha256 = digest(BASE / "common.py")
    guard_sha256 = digest(PUBLISHER)
    targets = [
        BASE / "local-resource-inputs",
        BASE / "local-resource-native-archives",
        BASE / "resource-inputs.json",
        BASE / "resource-invocation.json",
        BASE / "resource-native-guards.json",
        BASE / "resource-preservation-verified.json",
        *(BASE / name for name in CASE_NAMES),
    ]
    existing = [str(path) for path in targets if path.exists() or path.is_symlink()]
    if existing:
        raise RuntimeError("Preserve the existing attempt before any fresh run: " + ", ".join(existing))

    originals = OLD_ROOT / "local-resident-refresh-candidate588" / "inputs"
    archive_original = OLD_ROOT / "local-restoration-unused" / "prior-study.zip"
    # Check every retained input before creating any final-attempt destination.
    for name, expected in FROZEN_FIXTURES.items():
        if not (originals / name).is_file() or digest(originals / name) != expected:
            raise RuntimeError("Missing or changed retained native fixture: " + name)
    if not archive_original.is_file() or archive_original.stat().st_size != STUDY_BYTES \
            or digest(archive_original) != STUDY_SHA256:
        raise RuntimeError("Retained sealed study input is missing or changed")

    base = list(docker_base(source, readonly=True))
    if base[:2] != ["docker", "run"] or base[-2:] != ["--workdir", "/app"]:
        raise RuntimeError("Unexpected common Docker command contract")
    image_reference = IMAGE
    image_inspect_command = ["docker", "image", "inspect", image_reference]
    image = image_record()
    invocation = {
        "source": source,
        "source_checkout": str(SOURCE_CHECKOUT),
        "source_json_sha256": source_before,
        "started_at": utc_now(),
        "passed": False,
        "commands": [],
        "runner": {"path": str(Path(__file__)), "sha256": runner_sha256},
        "common": {"path": str(BASE / "common.py"), "sha256": common_sha256},
        "publisher_guard": {"path": str(PUBLISHER), "sha256": guard_sha256},
        "image": {
            "reference": image_reference,
            "id": image["Id"],
            "repo_digests": image.get("RepoDigests", []),
            "created": image.get("Created"),
            "os": image.get("Os"),
            "architecture": image.get("Architecture"),
        },
        "image_inspect_command": image_inspect_command,
        "docker_base": base,
        "resource_contract": {
            "memory_bytes": 2_147_483_648,
            "additional_swap_bytes": 0,
            "cpus": 2,
            "network": "none",
            "uid": 1000,
            "gid": 1000,
            "source_mount": "read-only",
        },
        "scope": "Fresh final-source native fixture acceptance; no old profiling study rerun or live Granite claim",
    }
    write_json(BASE / "resource-invocation.json", invocation)

    try:
        guards = publisher_guards()
        fixture_destination = BASE / "local-resource-inputs"
        fixture_destination.mkdir()
        inputs = {
            name: checked_copy(originals / name, fixture_destination / name, sha)
            for name, sha in FROZEN_FIXTURES.items()
        }
        fixture_destination.chmod(0o555)
        for name in CASE_NAMES:
            (BASE / name).mkdir()
        archives = BASE / "local-resource-native-archives"
        archives.mkdir()
        inputs["prior-study.zip"] = checked_copy(
            archive_original,
            BASE / "local-restoration-unused" / "prior-study.zip",
            STUDY_SHA256,
        )
        write_json(BASE / "resource-inputs.json", {
            "source": source,
            "inputs": inputs,
            "scope": "Retained immutable native fixture bytes reused only as tool inputs; not a new Granite memory profile",
        })

        # Use the immutable inspected ID rather than a mutable image tag.
        runtime_command = base + [image["Id"], "python", "-c", (
            "import json,platform,sys; "
            "print(json.dumps(dict(version=platform.python_version(), "
            "full_version=sys.version, executable=sys.executable, "
            "implementation=platform.python_implementation())))"
        )]
        invocation["runtime_command"] = runtime_command
        write_json(BASE / "resource-invocation.json", invocation)
        runtime_bytes = subprocess.check_output(runtime_command)
        invocation["runtime"] = json.loads(runtime_bytes)
        write_json(BASE / "resource-invocation.json", invocation)

        cases = [
            (
                "local-preflight",
                ["-m", "tools.validation.restoration_preflight_gate", "--output", "/evidence/local-preflight"],
                ["result.json", "raw.log"],
                guards.verify_preflight,
            ),
            (
                "local-restoration-unused",
                ["-m", "tools.validation.restoration_unused_memory", "--archive",
                 "/evidence/local-restoration-unused/prior-study.zip", "--output",
                 "/evidence/local-restoration-unused/evidence", "--native-actuals"],
                ["evidence/result.json", "raw.log", "prior-study.zip"],
                guards.verify_actuals_restoration,
            ),
            (
                "local-resident-refresh",
                ["-m", "tools.validation.resident_refresh_ownership", "--fixtures",
                 "/evidence/local-resource-inputs", "--output", "/evidence/local-resident-refresh/evidence"],
                ["evidence/result.json", "raw.log"],
                guards.verify_resident_refresh,
            ),
        ]
        native_results = {}
        receipts = []
        for name, arguments, members, verify in cases:
            assert_checkout(source)
            folder = BASE / name
            command = base + [image["Id"], "python", *arguments]
            began = time.monotonic()
            record = {"name": name, "command": command, "started_at": utc_now(), "finished": False}
            invocation["commands"].append(record)
            write_json(BASE / "resource-invocation.json", invocation)
            with (folder / "raw.log").open("xb") as sink:
                completed = subprocess.run(command, stdout=sink, stderr=subprocess.STDOUT)
            record.update(exit_code=completed.returncode, elapsed_seconds=time.monotonic() - began,
                          completed_at=utc_now(), finished=True)
            write_json(folder / "invocation.json", {"source": source, "runtime": invocation["runtime"],
                       "image": invocation["image"], **record})
            write_json(BASE / "resource-invocation.json", invocation)
            if completed.returncode:
                raise RuntimeError(name + " failed with exit " + str(completed.returncode))
            assert_checkout(source)
            sums = "".join(digest(folder / member) + "  " + member + "\n" for member in members)
            (folder / "SHA256SUMS").write_text(sums)
            original_zip = archives / (name + ".zip")
            guards.make_zip(original_zip, {
                member: (folder / member).read_bytes() for member in [*members, "SHA256SUMS"]
            })
            result = verify(original_zip, source)
            if result.get("passed") is not True:
                raise RuntimeError(name + " native publisher guard did not pass")
            native_results[name] = result
            receipts.append({"name": name, "guard": verify.__name__, "passed": True,
                             "archive": str(original_zip), "archive_sha256": digest(original_zip),
                             "archive_bytes": original_zip.stat().st_size,
                             "members": {member: digest(folder / member) for member in [*members, "SHA256SUMS"]}})
            write_json(BASE / "resource-native-guards.json", {
                "source": source,
                "publisher_guard": invocation["publisher_guard"],
                "all_native_guards_passed": len(receipts) == len(cases),
                "receipts": receipts,
            })

        assert_checkout(source)
        if load_source() != source or digest(BASE / "source.json") != source_before:
            raise RuntimeError("Final source specification changed during resource validation")
        if digest(PUBLISHER) != guard_sha256 or digest(Path(__file__)) != runner_sha256 \
                or digest(BASE / "common.py") != common_sha256:
            raise RuntimeError("Resource runner or native guard changed during execution")
        for name, expected in FROZEN_FIXTURES.items():
            if digest(originals / name) != expected or digest(fixture_destination / name) != expected:
                raise RuntimeError("Frozen fixture changed during resource validation: " + name)
        if digest(archive_original) != STUDY_SHA256 \
                or digest(BASE / "local-restoration-unused" / "prior-study.zip") != STUDY_SHA256:
            raise RuntimeError("Frozen study input changed during resource validation")
        write_json(BASE / "resource-preservation-verified.json", {
            "source": source,
            "all_native_guards_passed": True,
            "native_results": native_results,
            "native_guard_receipts": receipts,
            "runtime": invocation["runtime"],
            "image": invocation["image"],
            "inputs_manifest_sha256": digest(BASE / "resource-inputs.json"),
            "publisher_guard": invocation["publisher_guard"],
            "runner": invocation["runner"],
            "common": invocation["common"],
            "method": "Fresh final-source native preflight, --native-actuals unused-memory restoration and resident-refresh ownership under enforced2GiB; retained archives are fixture inputs only, not old-study reruns or live Granite acceptance",
        })
        invocation["passed"] = True
    except Exception as exc:
        invocation["failure"] = {"type": type(exc).__name__, "reason": str(exc)}
        raise
    finally:
        invocation["completed_at"] = utc_now()
        write_json(BASE / "resource-invocation.json", invocation)


if __name__ == "__main__":
    main()
