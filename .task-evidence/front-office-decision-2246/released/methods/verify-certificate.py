"""Verify source-bound original Actions certificate and all API attachment digests; never upload."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from common import BASE, digest, load_source, write_json

CONTROLLER = Path("/workspace/dtos-publisher-2246")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preparation", "publication"))
    stage = parser.parse_args().stage
    operation = "prepare" if stage == "preparation" else "publish"
    source = load_source()
    plan = json.loads((CONTROLLER / ".github/release-plans/2246.json").read_text())
    assert plan["finalized"] and all(plan[key] == source[key] for key in ("candidate", "tree", "baseline", "version", "build"))
    assert plan["canonical_tests"] == source["expected_test_count"]
    assert plan["product_tests"] == json.loads((BASE / "product-test-counts.json").read_text())["total"]
    publisher = json.loads((BASE / "publisher-source.json").read_text())["publisher"]
    metadata = json.loads((BASE / (stage + "-certificate-metadata.json")).read_text())
    path = BASE / (stage + "-certificate.zip")
    assert path.stat().st_size == metadata["size_in_bytes"] and "sha256:" + digest(path) == metadata["digest"]
    assert metadata["workflow_run"]["head_sha"] == publisher and not metadata["expired"]
    run_id = metadata["workflow_run"]["id"]
    assert metadata["name"] == f"guarded-release-{source['build']}-{operation}-{run_id}"
    retained_run = json.loads((BASE / (stage + "-run.json")).read_text())
    assert retained_run["id"] == run_id
    repo = "repos/" + plan["repository"]

    def api(tail):
        return json.loads(subprocess.check_output(["gh", "api", repo + "/" + tail], text=True))

    run = api("actions/runs/" + str(run_id))
    assert run["head_sha"] == publisher and run["status"] == "completed" and run["conclusion"] == "success"
    assert run["event"] == "workflow_dispatch" and run["path"] == ".github/workflows/canonical-release-recovery.yml"
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == len(set(archive.namelist()))
        outcome = json.loads(archive.read("outcome.json"))
        certificate = json.loads(archive.read("publication.json"))
        validation = json.loads(archive.read("assets/VALIDATION.json"))
        manifest = json.loads(archive.read("assets/evidence-manifest.json"))
        assert outcome["passed"] and outcome["operation"] == certificate["operation"] == operation
        assert outcome["candidate"] == certificate["candidate"] == validation["candidate"] == manifest["candidate"] == source["candidate"]
        assert certificate["tree"] == validation["tree"] == manifest["tree"] == source["tree"]
        assert outcome["publisher"] == certificate["publisher"] == publisher and certificate["release_id"] == plan["draft_id"]
        assert validation["version"] == plan["version"] and validation["build"] == plan["build"]
        assert validation["canonical"]["passed"] and validation["local_canonical"]["passed"]
        assert validation["canonical"]["head"] == validation["local_canonical"]["head"] == source["candidate"]
        assert validation["canonical"]["tree"] == validation["local_canonical"]["tree"] == source["tree"]
        for name in ("local_preflight", "local_restoration_unused", "local_resident_refresh"):
            proof = validation[name]
            assert proof["passed"] and proof["head"] == source["candidate"] and proof["tree"] == source["tree"], name
        for name in ("activation_deferral", "front_office_workflow", "recommended_protections", "offer_comparison",
                     "team_need_handoff", "partner_history_links", "completed_trade_observations"):
            proof = validation[name]
            assert proof["passed"] and proof["head"] == source["candidate"] and proof["tree"] == source["tree"], name
        assert validation["completed_trade_observations"]["matched_cases"]["passed"]
        assert len(validation["required_jobs"]) == 13 and all(row["conclusion"] == "success" for row in validation["required_jobs"])
        assert validation["product_test_executions"] == plan["product_tests"]
        assert validation["original_artifacts"] == plan["artifacts"] and len(validation["original_artifacts"]) == 15
        assert validation["recovery_sha256"] == plan["recovery_sha256"] and validation["prior_evidence_sha256"] == plan["prior_evidence_sha256"]
        entries = {row["name"]: row for row in certificate["attachments"]}
        assert len(entries) == len(certificate["attachments"]) == 23
        assert len(manifest["files"]) == 21 and {row["name"] for row in manifest["files"]} == set(entries) - {"SHA256SUMS", "evidence-manifest.json"}
        for row in manifest["files"]:
            assert row == entries[row["name"]]
        sums = dict(line.split("  ", 1)[::-1] for line in archive.read("assets/SHA256SUMS").decode().splitlines())
        assert set(sums) == set(entries) - {"SHA256SUMS"}
        assert all(sums[name] == row["sha256"] for name, row in entries.items() if name != "SHA256SUMS")
        for name in ("VALIDATION.json", "evidence-manifest.json", "SHA256SUMS", "prior-attempts.json"):
            raw = archive.read("assets/" + name)
            assert len(raw) == entries[name]["bytes"] and hashlib.sha256(raw).hexdigest() == entries[name]["sha256"]
        if stage == "publication":
            ready = json.loads(archive.read("production-smoke.json"))
            merged = json.loads((BASE / "merged-source.json").read_text())["merge_commit"]
            assert ready["readiness"]["status"] == "ready" and ready["readiness"]["version"] == source["version"]
            assert ready["readiness"]["build"] == source["build"] and ready["readiness"]["deployment"]["commit"] == merged
            write_json(BASE / "publisher-production-smoke.json", ready)
    release = api("releases/" + str(plan["draft_id"]))
    assert release["tag_name"] == "v" + source["version"] and len(release["assets"]) == 23
    assert {row["name"] for row in release["assets"]} == set(entries)
    for row in release["assets"]:
        expected = entries[row["name"]]
        assert row["state"] == "uploaded" and row["size"] == expected["bytes"] and row["digest"] == "sha256:" + expected["sha256"]
    if stage == "preparation":
        assert release["draft"] and not release["immutable"] and certificate["draft"] and not certificate["immutable"]
        assert certificate["main"] == plan["baseline"]
    else:
        merged = json.loads((BASE / "merged-source.json").read_text())["merge_commit"]
        assert not release["draft"] and release["immutable"] and not certificate["draft"] and certificate["immutable"]
        assert certificate["main"] == merged and release["target_commitish"] == merged
    write_json(BASE / ("prepared-publication.json" if stage == "preparation" else "published-publication.json"), certificate)
    write_json(BASE / ("prepared-attachment-verification.json" if stage == "preparation" else "published-attachment-verification.json"),
        dict(candidate=source["candidate"], tree=source["tree"], publisher=publisher, attachments=certificate["attachments"],
             native_all_attachment_bytes_read_back=True, cloud_api_digests_match_certificate=True,
             front_office_workflow_verified=True, certificate_sha256=digest(path), validation_sha256=entries["VALIDATION.json"]["sha256"],
             scope="Frozen Actions publisher natively read every attachment byte. This reader verifies the original certificate/source and all API digests, not a second Cloud binary readback."))
    print(stage, "certificate verified;23attachment hashes, new front-office proof and final source agree.")


if __name__ == "__main__":
    main()

