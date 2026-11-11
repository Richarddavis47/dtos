"""Derive actual Product/Welcome execution totals from complete original final-source consoles."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import zipfile

from common import BASE, digest, load_source, write_json

source = load_source()
records = json.loads((BASE / "hosted-final-records.json").read_text())
product_runs = [row for row in records if row["run"]["path"] == ".github/workflows/product-browser.yml"]
assert len(product_runs) == 1 and product_runs[0]["run"]["head_sha"] == source["candidate"]
jobs = [row for row in product_runs[0]["jobs"] if row["name"] == "product-browser"]
assert len(jobs) == 1 and jobs[0]["status"] == "completed" and jobs[0]["conclusion"] == "success"
assert jobs[0]["head_sha"] == source["candidate"]
# Save the complete decoded original Product job log through the existing connector first.
path = BASE / "hosted-decoded-originals/product-original.log"
raw = path.read_bytes()
source_path = BASE / "hosted-decoded-originals/product-job-source.json"
transfer_path = BASE / "hosted-decoded-originals/product-log-transfer.json"
identity = json.loads(source_path.read_text())
transfer = json.loads(transfer_path.read_text())
assert identity["candidate"] == source["candidate"] and identity["tree"] == source["tree"]
assert identity["job_id"] == transfer["job_id"] == jobs[0]["id"]
check = identity["completed_check_api_original"]
assert check["id"] == jobs[0]["id"] and check["name"] == "product-browser"
assert check["head_sha"] == source["candidate"] and check["status"] == "completed" and check["conclusion"] == "success"
assert check["app"]["slug"] == "github-actions"
link = re.search(r"/runs/(\d+)/job/(\d+)", check["details_url"])
assert link and int(link[1]) == product_runs[0]["run"]["id"] and int(link[2]) == jobs[0]["id"]
snapshot = identity["source_snapshot"]
snapshot_name = PurePosixPath(snapshot["file"])
assert not snapshot_name.is_absolute() and ".." not in snapshot_name.parts
snapshot_path = BASE / str(snapshot_name)
assert snapshot_path.stat().st_size == snapshot["bytes"] and digest(snapshot_path) == snapshot["sha256"]
original_checks = json.loads(snapshot_path.read_text())["check_runs"]
assert [row for row in original_checks if row["id"] == jobs[0]["id"]] == [check]
assert len(raw) == transfer["original_bytes"] == transfer["utf8_bytes"]
assert digest(path) == transfer["original_sha256"]
assert len(raw.decode("utf-8").encode("utf-16-le")) // 2 == transfer["utf16_length"]
parts_folder = BASE / "hosted-decoded-originals/product-original.parts"
if parts_folder.exists():
    parts = transfer["parts"]
    names = [row["name"] for row in parts]
    assert len(names) == len(set(names)) and all(re.fullmatch(r"part-\d{4}\.log", name) for name in names)
    assert {part.name for part in parts_folder.glob("part-*.log")} == set(names)
    original_parts = []
    for row in parts:
        part = parts_folder / row["name"]
        data = part.read_bytes()
        data.decode("utf-8")
        assert len(data) == row["bytes"] and digest(part) == row["sha256"]
        original_parts.append(data)
    assert b"".join(original_parts) == raw, "Retained original decoded parts differ from complete console"
totals = [int(value) for value in re.findall(rb"Ran (\d+) tests in [0-9.]+s", raw)]
assert totals and sum(totals) > 0 and b"FAILED (" not in raw
product_counts = dict(candidate=source["candidate"], tree=source["tree"], run=product_runs[0]["run"]["id"],
    job=jobs[0]["id"], counts=totals, total=sum(totals), original_bytes=len(raw), original_sha256=digest(path),
    source_proof_sha256=digest(source_path), transfer_receipt_sha256=digest(transfer_path),
    scope="Actual execution summaries from complete original final-source MCP-decoded successful Product job console. UTF8 reconstruction verified; pre-decoding wire bytes are not asserted. Canonical/native archive acceptance remains separate.")
counts_path = BASE / "product-test-counts.json"
if counts_path.exists():
    existing = json.loads(counts_path.read_text())
    assert all(existing[key] == product_counts[key] for key in product_counts if key != "scope"), "Existing count/source/transfer proof differs; preserve and inspect"
    product_counts["scope"] = existing.get("scope", product_counts["scope"])
write_json(counts_path, product_counts)
queue = json.loads((BASE / "artifact-download-queue.json").read_text())
rows = [row for row in queue if row["file"] == "public-welcome-security.zip"]
assert len(rows) == 1
archive_path = BASE / "hosted-originals" / rows[0]["file"]
assert archive_path.stat().st_size == rows[0]["bytes"] and digest(archive_path) == rows[0]["sha256"]
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    identity = json.loads(archive.read("source.json"))
    assert identity["head"] == source["candidate"] and identity["tree"] == source["tree"]
    welcome = archive.read("raw.log")
counts = [int(value) for value in re.findall(rb"Ran (\d+) tests in [0-9.]+s", welcome)]
assert counts and re.search(rb"\bOK\s*$", welcome)
write_json(BASE / "public-welcome-test-counts.json", dict(candidate=source["candidate"], tree=source["tree"], counts=counts,
    total=sum(counts), original_bytes=len(welcome), original_sha256=hashlib.sha256(welcome).hexdigest()))
print(json.dumps(dict(product=sum(totals), welcome=sum(counts), counts_are_actual=True)))

