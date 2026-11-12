"""Read-only verification of the actual frozen-controller Actions certificate."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

B = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=("prepare", "publish"))
args = parser.parse_args()
phase = args.operation
plan = json.loads((B / "final-release-plan.json").read_text())
controller = json.loads((B / "publisher-controller.json").read_text())
meta = json.loads((B / (phase + "-artifact-metadata.json")).read_text())
run = json.loads((B / ("publisher-" + phase + "-final.json")).read_text())
assert run["head_sha"] == controller["commit"]
assert run["event"] == "workflow_dispatch" and run["conclusion"] == "success"
assert run["status"] == "completed" and run["head_branch"] == controller["branch"]
assert meta["workflow_run"]["head_sha"] == controller["commit"]
assert meta["workflow_run"]["id"] == run["id"] and not meta["expired"]
assert meta["name"] == f"guarded-release-2249-{phase}-{run['id']}"
path = B / (phase + "-certificate-original.zip")
raw = path.read_bytes()
assert len(raw) == meta["size_in_bytes"]
assert "sha256:" + hashlib.sha256(raw).hexdigest() == meta["digest"]
spec = importlib.util.spec_from_file_location(
    "release_certificate_guard", "/workspace/dtos-publisher-2249/tools/release/publish.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
guard.verify_zip(path)
out = B / (phase + "-certificate-native")
out.mkdir(exist_ok=False)
with zipfile.ZipFile(path) as archive:
    for name in archive.namelist():
        item = PurePosixPath(name)
        assert not item.is_absolute() and ".." not in item.parts
        if name.endswith("/"):
            continue
        target = out / str(item)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(name))
outcome = json.loads((out / "outcome.json").read_text())
pub = json.loads((out / "publication.json").read_text())
assert outcome["passed"] is True and outcome["operation"] == phase
assert outcome["publisher"] == pub["publisher"] == controller["commit"]
assert outcome["candidate"] == pub["candidate"] == plan["candidate"]
assert pub["tree"] == plan["tree"] and pub["operation"] == phase
assert pub["release_id"] == plan["draft_id"]
expected_main = plan["baseline"] if phase == "prepare" else json.loads(
    (B / "merge-verified.json").read_text()
)["merge_commit"]
assert pub["main"] == expected_main
assert pub["draft"] is (phase == "prepare")
assert pub["immutable"] is (phase == "publish")
manifest_raw = (out / "assets/evidence-manifest.json").read_bytes()
manifest = json.loads(manifest_raw)
assert manifest["candidate"] == plan["candidate"] and manifest["tree"] == plan["tree"]
expected = {r["name"]: (r["bytes"], r["sha256"]) for r in manifest["files"]}
assert len(expected) == len(manifest["files"])
expected["evidence-manifest.json"] = (len(manifest_raw), hashlib.sha256(manifest_raw).hexdigest())
sums_raw = (out / "assets/SHA256SUMS").read_bytes()
sums_rows = [line.split("  ", 1) for line in sums_raw.decode().splitlines()]
sums = {name: sha for sha, name in sums_rows}
assert len(sums) == len(sums_rows)
assert sums == {name: sha for name, (_, sha) in expected.items()}
expected["SHA256SUMS"] = (len(sums_raw), hashlib.sha256(sums_raw).hexdigest())
assert len(expected) == 23
assert {r["name"]: (r["bytes"], r["sha256"]) for r in pub["attachments"]} == expected
assert len(pub["attachments"]) == len(expected)
for row in plan["artifacts"]:
    assert expected[row["file"]] == (row["bytes"], row["sha256"])
assert expected["Market-Roster-Handoff.zip"] == (
    (B / "recovery-package.zip").stat().st_size, plan["recovery_sha256"]
)
assert expected["Prior-attempts.zip"] == (
    (B / "prior-package.zip").stat().st_size, plan["prior_evidence_sha256"]
)
validation = json.loads((out / "assets/VALIDATION.json").read_text())
assert validation["candidate"] == plan["candidate"] and validation["tree"] == plan["tree"]
assert validation["product_test_executions"] == 916
assert validation["local_draft_capital"]["evidence_origin"] == "Supplemental two-method local browser capture on the final source under enforced 2 GiB; the original full canonical manifest is unchanged."
for field in ("roster_source_scope", "local_roster_source_scope"):
    proof = validation[field]
    assert proof["passed"] and proof["candidate"] == plan["candidate"] and proof["tree"] == plan["tree"]
    assert proof["supported_roundtrips"] == 8 and proof["withheld_cases"] == 5
assert validation["recovery_sha256"] == plan["recovery_sha256"]
assert validation["prior_evidence_sha256"] == plan["prior_evidence_sha256"]
release = json.loads(subprocess.check_output([
    "gh", "api", "repos/" + plan["repository"] + "/releases/" + str(plan["draft_id"])
], text=True))
assert release["tag_name"] == "v" + plan["version"]
assert release["target_commitish"] == (plan["candidate"] if phase == "prepare" else expected_main)
assert release["draft"] is (phase == "prepare")
assert release.get("immutable") is (phase == "publish")
guard.verify_remote_assets(release, expected, complete=True)
record = dict(
    passed=True, operation=phase, run=run["id"], publisher=controller["commit"],
    candidate=plan["candidate"], tree=plan["tree"], main=expected_main,
    release_id=plan["draft_id"], assets=23,
    archive_sha256=hashlib.sha256(raw).hexdigest(),
    original_api_digest_crc_and_source_verified=True,
    internal_manifest_and_checksum_sidecar_verified=True,
    remote_asset_sizes_and_digests_verified=True,
    actions_attachment_byte_readback_completed=True,
    scope="Original successful frozen-controller certificate plus independent API/manifest verification; no new local attachment downloads or owner acceptance."
)
(B / (phase + "-certificate-verified.json")).write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
