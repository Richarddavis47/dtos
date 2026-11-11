"""Verify fresh hosted canonical archive and its complete actual console/manifest."""
from collections import Counter
import hashlib
import json
from pathlib import PurePosixPath
import re
import zipfile

from common import BASE, digest, load_source, write_json

source = load_source()
expected = source["expected_test_count"]
path = BASE / "hosted-originals/canonical-original.zip"
queue = json.loads((BASE / "artifact-download-queue.json").read_text())
metadata = [row for row in queue if row["file"] == path.name]
assert len(metadata) == 1 and path.stat().st_size == metadata[0]["bytes"] and digest(path) == metadata[0]["sha256"]
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    result = json.loads(archive.read("result.json"))
    assert result["head"] == source["candidate"] and result["tree"] == source["tree"] and result["passed"] and result["exit_code"] == 0
    assert result["python"].startswith("3.14.3") and result["cgroup_limit"] == 2147483648 and result["cpus"] == 2 and result["network"] == "none"
    assert not any(result["final_memory"]["cgroup_memory_events"].get(key, 0) for key in ("oom_kill", "oom"))
    manifest = json.loads(archive.read("manifest.json"))
    sums = dict(row.split("  ", 1)[::-1] for row in archive.read("SHA256SUMS").decode().splitlines())
    assert len(sums) == len(manifest)
    names = set()
    for row in manifest:
        member = PurePosixPath(row["name"])
        assert not member.is_absolute() and ".." not in member.parts and row["name"] not in names
        names.add(row["name"])
        data = archive.read(row["name"])
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"] == sums[row["name"]]
    # Container state/log files are appended by Actions after the runner seals its manifest.
    allowed_unmanifested = {"manifest.json", "SHA256SUMS", "container-state.json", "container.log"}
    assert {name for name in archive.namelist() if not name.endswith("/")} <= names | allowed_unmanifested
    console = archive.read("unittest-console.log")
    match = re.search(rb"Ran (\d+) tests in [0-9.]+s\s+OK\s*$", console)
    assert match and int(match[1]) == expected
    counts = Counter(json.loads(row)["event"] for row in archive.read("tests.jsonl").splitlines())
    assert counts["start"] == counts["stop"] == expected and not any(counts[key] for key in ("failure", "error", "skip"))
    trace = [json.loads(row) for row in archive.read("canonical-trace.jsonl").splitlines()]
    gates = [row for row in trace if row.get("event") == "validation_child_completed"]
    assert len(gates) == 10 and all(row["return_code"] == 0 for row in gates)
    assert any(row.get("event") == "validator_final_summary" and row.get("gates") == 10 for row in trace)
    output = BASE / "host-canonical-readable"
    output.mkdir(exist_ok=False)
    for name in ("result.json", "manifest.json", "SHA256SUMS", "canonical.log", "canonical-trace.jsonl", "unittest-console.log", "tests.jsonl", "memory.jsonl"):
        (output / name).write_bytes(archive.read(name))
    chunks = []
    start = 0
    while start < len(console):
        end = min(start + 60000, len(console))
        while end < len(console) and console[end] & 0xc0 == 0x80:
            end -= 1
        assert end > start
        chunks.append(console[start:end])
        start = end
    for index, data in enumerate(chunks, 1):
        (output / f"console-{index:03d}.log").write_bytes(data)
    assert b"".join(chunks) == console
    (output / "console-parts.SHA256SUMS").write_text("".join(hashlib.sha256(data).hexdigest() + f"  console-{index:03d}.log\n" for index, data in enumerate(chunks, 1)))
report = dict(candidate=source["candidate"], tree=source["tree"], tests=expected, all_gates_passed=True,
    entries=len(manifest), original_sha256=digest(path), console_sha256=hashlib.sha256(console).hexdigest(),
    kernel_peak=result["kernel_peak"], elapsed_seconds=result["elapsed_seconds"],
    scope="Fresh final-head hosted canonical original; complete checksum-verified manifest and authoritative console.")
write_json(BASE / "host-canonical-verified.json", report)
print(json.dumps(report))

