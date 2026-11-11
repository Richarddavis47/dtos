"""Expected-head squash only after successful frozen native preparation and final source gates."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from common import BASE, command, load_source, write_json

CONTROLLER = Path("/workspace/dtos-publisher-2246")


def main():
    source = load_source()
    plan = json.loads((CONTROLLER / ".github/release-plans/2246.json").read_text())
    frozen = json.loads((BASE / "publisher-source.json").read_text())
    publisher = frozen["publisher"]
    assert plan["finalized"] and all(plan[key] == source[key] for key in ("candidate", "tree", "baseline", "version", "build"))
    assert plan["pr"] == source.get("pr", 335) == 335 and plan["canonical_tests"] == source["expected_test_count"]
    assert plan["product_tests"] == json.loads((BASE / "product-test-counts.json").read_text())["total"]
    assert command("git", "rev-parse", "HEAD", cwd=CONTROLLER) == publisher
    assert command("git", "rev-parse", "HEAD^{tree}", cwd=CONTROLLER) == frozen["tree"]
    assert not command("git", "status", "--porcelain", cwd=CONTROLLER)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("final_merge_native_guard", CONTROLLER / "tools/release/publish.py")
    publish = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publish)
    publish.verify_plan(plan)
    prepared = json.loads((BASE / "prepared-publication.json").read_text())
    verified = json.loads((BASE / "prepared-attachment-verification.json").read_text())
    assert prepared["candidate"] == verified["candidate"] == source["candidate"]
    assert prepared["tree"] == verified["tree"] == source["tree"]
    assert prepared["publisher"] == verified["publisher"] == publisher
    assert prepared["draft"] and not prepared["immutable"] and prepared["release_id"] == plan["draft_id"]
    assert verified["native_all_attachment_bytes_read_back"] and verified["cloud_api_digests_match_certificate"] and len(verified["attachments"]) == 23
    assert verified["front_office_workflow_verified"] is True
    for name, flag in (("local-verified.json", "all_local_gates_passed"), ("host-canonical-verified.json", "all_gates_passed"),
                       ("focused-resource-verified.json", "all_native_guards_passed")):
        proof = json.loads((BASE / name).read_text())
        assert proof["candidate"] == source["candidate"] and proof["tree"] == source["tree"] and proof[flag]
        if "tests" in proof:
            assert proof["tests"] == source["expected_test_count"]
    repo = "repos/" + plan["repository"]

    def api(path):
        return json.loads(subprocess.check_output(["gh", "api", repo + "/" + path], text=True))

    existing = BASE / "merged-source.json"
    if existing.exists():
        merge = json.loads(existing.read_text())
        assert merge["candidate"] == source["candidate"] and merge["tree"] == source["tree"] and merge["publisher"] == publisher
        actual = api("pulls/" + str(plan["pr"]))
        assert actual["merged"] and actual["merge_commit_sha"] == merge["merge_commit"]
        assert api("git/commits/" + merge["merge_commit"])["tree"]["sha"] == source["tree"]
        print("Existing verified merge retained:", merge["merge_commit"])
        return
    run = api("actions/runs/" + str(json.loads((BASE / "preparation-run.json").read_text())["id"]))
    assert run["status"] == "completed" and run["conclusion"] == "success" and run["head_sha"] == publisher
    assert run["event"] == "workflow_dispatch" and run["path"] == ".github/workflows/canonical-release-recovery.yml"
    assert api("git/ref/heads/" + plan["publisher_ref"].removeprefix("refs/heads/"))["object"]["sha"] == publisher
    assert api("git/ref/heads/main")["object"]["sha"] == source["baseline"]
    lookup = subprocess.run(["gh", "api", repo + "/git/ref/tags/v" + plan["version"]], capture_output=True, text=True)
    assert lookup.returncode and "HTTP 404" in lookup.stderr, "Immutable release tag already used"
    pr = api("pulls/" + str(plan["pr"]))
    assert not pr["merged"] and pr["state"] == "open" and pr["head"]["sha"] == source["candidate"] and pr["base"]["sha"] == source["baseline"]
    assert pr["base"]["ref"] == "main" and pr["head"]["ref"] == plan["source_branch"]
    assert pr["mergeable"] is True and pr["mergeable_state"] not in {"dirty", "blocked", "unknown"}, "Conflict/merge state must be established"
    assert api("git/commits/" + source["candidate"])["tree"]["sha"] == source["tree"]
    records, _ = publish.verify_runs(plan)
    assert len(records) == 13
    if pr["draft"]:
        query = "mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{number isDraft}}}"
        result = json.loads(subprocess.check_output(["gh", "api", "graphql", "-f", "query=" + query, "-f", "id=" + pr["node_id"]], text=True))
        assert not result.get("errors") and result["data"]["markPullRequestReadyForReview"]["pullRequest"] == {"number": plan["pr"], "isDraft": False}
    title = "fix: preserve prepared front-office workflows and activation deferral (#335)"
    message = (
        "Preserve prepared Home need/filter context, exact temporary Recommended protections, independent Evaluate state and retained comparison navigation. "
        "Retain typed activation waiting/retry and bounded existing-plan diagnostics. No memory/admission/valuation/source-policy change or live Granite recovery claim.\n\n"
        "Validated source tree: " + source["tree"] + "\n\n"
        + f"{plan['canonical_tests']:,} tests and all ten gates passed in each final-source local/hosted canonical run; all thirteen hosted jobs and {plan['product_tests']} Product executions passed. "
        "Frozen Actions preparation verified all23attachments and the new native front-office workflow proof. Earlier failed local attempts remain separately preserved and linked. "
        "Fixture controls are separate from unverified owner live and physical Safari acceptance."
    )
    body = dict(sha=source["candidate"], merge_method="squash", commit_title=title, commit_message=message)
    path = BASE / "merge-input.json"
    assert not path.exists(), "An earlier merge request is ambiguous; inspect actual PR/main before any retry"
    write_json(path, body)
    result = json.loads(subprocess.check_output(["gh", "api", repo + "/pulls/" + str(plan["pr"]) + "/merge", "--method", "PUT", "--input", str(path)], text=True))
    assert result["merged"] is True
    sha = result["sha"]
    assert api("git/ref/heads/main")["object"]["sha"] == sha
    assert api("git/commits/" + sha)["tree"]["sha"] == source["tree"]
    report = dict(merge_commit=sha, candidate=source["candidate"], tree=source["tree"], publisher=publisher, pr=plan["pr"],
                  normal_expected_head_squash=True, validated_tree_unchanged=True)
    write_json(BASE / "merged-source.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()

