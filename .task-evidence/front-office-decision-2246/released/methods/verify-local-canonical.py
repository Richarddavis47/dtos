"""Verify complete final-source local canonical originals; never convert failed attempts."""
from collections import Counter
import hashlib
import json
from pathlib import PurePosixPath
import re

from common import BASE, digest, load_source, write_json

source = load_source()
expected = source["expected_test_count"]
root = BASE / "local-canonical"
result = json.loads((root / "result.json").read_text())
assert result["head"] == source["candidate"] and result["tree"] == source["tree"]
assert result["passed"] and result["exit_code"] == 0
assert result["expected_test_count"] == expected
assert result["cgroup_limit"] == 2147483648 and result["cpus"] == 2 and result["network"] == "none"
assert result["python"].startswith("3.14.3")
assert result["process_cleanup"].get("validator_reaped") and not result["process_cleanup"].get("timeout_triggered")
assert not any(result["final_memory"]["cgroup_memory_events"].get(key, 0) for key in ("oom_kill", "oom"))
console = (root / "unittest-console.log").read_bytes()
match = re.search(rb"Ran (\d+) tests in [0-9.]+s\s+OK\s*$", console)
assert match and int(match[1]) == expected
counts = Counter(json.loads(row)["event"] for row in (root / "tests.jsonl").read_text().splitlines())
assert counts["start"] == counts["stop"] == expected
assert not any(counts[key] for key in ("error", "failure", "skip"))
trace = [json.loads(row) for row in (root / "canonical-trace.jsonl").read_text().splitlines()]
gates = [row for row in trace if row.get("event") == "validation_child_completed"]
assert len(gates) == 10 and all(row["return_code"] == 0 for row in gates)
assert any(row.get("event") == "validator_final_summary" and row.get("gates") == 10 for row in trace)
assert any(row.get("event") == "validator_exit" and row.get("exit_code") == 0 for row in trace)
manifest = json.loads((root / "manifest.json").read_text())
sums = dict(row.split("  ", 1)[::-1] for row in (root / "SHA256SUMS").read_text().splitlines())
assert len(sums) == len(manifest)
names = set()
for row in manifest:
    name = PurePosixPath(row["name"])
    assert not name.is_absolute() and ".." not in name.parts and row["name"] not in names
    names.add(row["name"])
    path = root / row["name"]
    assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"] == sums[row["name"]]
actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}}
assert actual == names, "Unmanifested or missing canonical original"
summary = dict(candidate=source["candidate"], tree=source["tree"], tests=expected, all_local_gates_passed=True,
    local_manifest_entries=len(manifest), console_sha256=hashlib.sha256(console).hexdigest(),
    kernel_peak=result["kernel_peak"], elapsed_seconds=result["elapsed_seconds"], cgroup_limit=result["cgroup_limit"])
write_json(BASE / "local-verified.json", summary)
parts = BASE / "readable-console"
parts.mkdir(exist_ok=False)
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
    (parts / f"unittest-console-{index:03d}.log").write_bytes(data)
assert b"".join(chunks) == console
(parts / "SHA256SUMS").write_text("".join(hashlib.sha256(data).hexdigest() + f"  unittest-console-{index:03d}.log\n" for index, data in enumerate(chunks, 1)))
print(json.dumps(summary))

