"""Dispatch one reviewed frozen publisher stage; never retry an ambiguous request."""
from datetime import datetime
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote

from common import BASE, command, digest, load_source, now, write_json

CONTROLLER = Path("/workspace/dtos-publisher-2246")
PLAN = CONTROLLER / ".github/release-plans/2246.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preparation", "publication"))
    args = parser.parse_args()
    stage = args.stage
    operation = "prepare" if stage == "preparation" else "publish"
    source = load_source()
    plan = json.loads(PLAN.read_text())
    frozen = json.loads((BASE / "publisher-source.json").read_text())
    publisher = frozen["publisher"]
    assert re.fullmatch("[a-f0-9]{40}", publisher)
    assert plan["finalized"] is True
    assert all(plan[key] == source[key] for key in ("candidate", "tree", "baseline", "version", "build"))
    assert plan["pr"] == source.get("pr", 335) == 335 and plan["canonical_tests"] == source["expected_test_count"]
    assert plan["product_tests"] == json.loads((BASE / "product-test-counts.json").read_text())["total"]
    assert len(plan["artifacts"]) == 15 and sum(len(row["jobs"]) for row in plan["runs"]) == 13
    assert plan["publisher_ref"] == "refs/heads/release/2246-actions-publisher"
    assert command("git", "rev-parse", "HEAD", cwd=CONTROLLER) == publisher
    assert command("git", "rev-parse", "HEAD^{tree}", cwd=CONTROLLER) == frozen["tree"]
    assert not command("git", "status", "--porcelain", cwd=CONTROLLER), "Frozen controller must be clean"
    allowed = {".github/workflows/canonical-release-recovery.yml", ".github/release-plans/2246.json",
               ".github/release-plans/2246-recovery.zip", ".github/release-plans/2246-prior.zip",
               ".github/release-plans/README.md", "tools/release/__init__.py",
               "tools/release/publish.py", "tests/test_release_publisher.py"}
    changed = set(command("git", "diff", "--name-only", plan["baseline"], publisher, cwd=CONTROLLER).splitlines())
    assert changed <= allowed, "Controller contains application changes"
    sealed = json.loads((BASE / "publisher-scoped-sealed.json").read_text())
    assert sealed["candidate"] == source["candidate"] and sealed["tree"] == source["tree"]
    assert sealed["tests"] > 0 and set(sealed["results"]) == {"tests", "lint", "compile"}
    assert all(value == 0 for value in sealed["results"].values())
    required = {"tools/release/publish.py", "tests/test_release_publisher.py", ".github/workflows/canonical-release-recovery.yml",
                ".github/release-plans/2246.json", ".github/release-plans/2246-recovery.zip", ".github/release-plans/2246-prior.zip"}
    assert required <= set(sealed["source"])
    for name, expected in sealed["source"].items():
        assert digest(CONTROLLER / name) == expected, "Sealed controller changed: " + name
    assert digest(CONTROLLER / plan["recovery_file"]) == plan["recovery_sha256"]
    assert digest(CONTROLLER / plan["prior_evidence_file"]) == plan["prior_evidence_sha256"]
    repo = "repos/" + plan["repository"]

    def api(path):
        return json.loads(subprocess.check_output(["gh", "api", repo + "/" + path], text=True))

    assert api("git/ref/heads/" + plan["publisher_ref"].removeprefix("refs/heads/"))["object"]["sha"] == publisher
    retained = BASE / (stage + "-run.json")
    request_path = BASE / (stage + "-dispatch-request.json")
    if retained.exists():
        previous = json.loads(retained.read_text())
        actual = api("actions/runs/" + str(previous["id"]))
        assert actual["head_sha"] == publisher and actual["event"] == "workflow_dispatch"
        assert actual["path"] == ".github/workflows/canonical-release-recovery.yml"
        print("Existing stage retained; no dispatch:", actual["id"], actual["status"], actual["conclusion"])
        return
    assert not request_path.exists(), "An earlier request has no reconciled run receipt; inspect it instead of dispatching again"
    offline = json.loads((BASE / "recovery-offline-verified.json").read_text())
    assert offline["candidate"] == source["candidate"] and offline["tree"] == source["tree"]
    assert offline["all_native_recovery_guards_passed"] is True
    assert offline["recovery_sha256"] == plan["recovery_sha256"] and offline["prior_sha256"] == plan["prior_evidence_sha256"]
    if stage == "preparation":
        assert api("git/ref/heads/main")["object"]["sha"] == plan["baseline"]
        pr = api("pulls/" + str(plan["pr"]))
        assert not pr["merged"] and pr["state"] == "open" and pr["head"]["sha"] == source["candidate"]
    else:
        merge = json.loads((BASE / "merged-source.json").read_text())
        verified = json.loads((BASE / "prepared-attachment-verification.json").read_text())
        assert merge["candidate"] == source["candidate"] and merge["tree"] == plan["tree"] and merge["validated_tree_unchanged"]
        assert merge["publisher"] == publisher and api("git/ref/heads/main")["object"]["sha"] == merge["merge_commit"]
        assert verified["candidate"] == source["candidate"] and verified["tree"] == source["tree"] and verified["publisher"] == publisher
        assert verified["native_all_attachment_bytes_read_back"] and verified["cloud_api_digests_match_certificate"]
        assert len(verified["attachments"]) == 23
        preparation = api("actions/runs/" + str(json.loads((BASE / "preparation-run.json").read_text())["id"]))
        assert preparation["head_sha"] == publisher and preparation["status"] == "completed" and preparation["conclusion"] == "success"
    started = now()
    invocation = ["gh", "workflow", "run", "canonical-release-recovery.yml", "--repo", plan["repository"],
                  "--ref", plan["publisher_ref"].removeprefix("refs/heads/"), "-f", "release_operation=" + operation]
    if stage == "publication":
        invocation += ["-f", "preparation_run_id=" + str(preparation["id"])]
    write_json(request_path, dict(stage=stage, publisher=publisher, candidate=source["candidate"], tree=source["tree"],
        requested_at=started, command=invocation, plan_sha256=digest(PLAN),
        mechanism="Reviewed frozen Actions workflow_dispatch; no Cloud release-asset upload. A request without run receipt is never retried automatically."))
    subprocess.run(invocation, check=True)
    branch = quote(plan["publisher_ref"].removeprefix("refs/heads/"), safe="")
    for _ in range(10):
        runs = api("actions/workflows/canonical-release-recovery.yml/runs?event=workflow_dispatch&branch=" + branch + "&per_page=20")["workflow_runs"]
        matches = [row for row in runs if row["head_sha"] == publisher and row["event"] == "workflow_dispatch"
                   and datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).timestamp()
                   >= datetime.fromisoformat(started).timestamp() - 2]
        if matches:
            assert len(matches) == 1, "Ambiguous dispatch: preserve request and inspect"
            write_json(retained, matches[0])
            print(stage, matches[0]["id"], matches[0]["html_url"], matches[0]["status"])
            return
        time.sleep(3)
    raise RuntimeError("Dispatch accepted but exact run not visible; reconcile retained request, never dispatch again blindly")


if __name__ == "__main__":
    main()

