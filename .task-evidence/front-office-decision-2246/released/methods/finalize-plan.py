"""Build a final plan locally; controller staging requires an explicit reviewed invocation."""
import argparse
import json
from pathlib import Path
import shutil

from common import BASE, digest, load_source, now, write_json
from release_common import CONTROLLER, PLAN_PATH, passing_inputs, publisher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--stage-controller", action="store_true", help="After review, back up and replace only controller plan/Recovery/Prior bytes.")
args = parser.parse_args()
source, local, host, native, focused = passing_inputs()
guard = publisher()
original_plan = json.loads(PLAN_PATH.read_text())
assert original_plan["baseline"] == source["baseline"] and original_plan["pr"] == 335
assert original_plan["version"] == source["version"] and original_plan["build"] == source["build"]
runs = json.loads((BASE / "validation-runs.json").read_text())
product = json.loads((BASE / "product-test-counts.json").read_text())
for proof in (runs, product):
    assert proof["candidate"] == source["candidate"] and proof["tree"] == source["tree"]
queue = json.loads((BASE / "artifact-download-queue.json").read_text())
assert len(queue) == 15 and sum(len(row["jobs"]) for row in runs["runs"]) == 13
draft = json.loads((BASE / "draft-created.json").read_text())
assert draft["draft"] and not draft["immutable"] and draft["target_commitish"] == source["candidate"] and draft["tag_name"] == "v" + source["version"]
plan = dict(original_plan, candidate=source["candidate"], tree=source["tree"], baseline=source["baseline"],
    source_branch=source["branch"], branch=source["branch"], runs=runs["runs"], canonical_tests=source["expected_test_count"],
    canonical_entries=host["entries"], local_canonical_entries=local["local_manifest_entries"], product_tests=product["total"],
    draft_id=draft["id"], artifacts=[], prior_runs=[], prior_jobs=[],
    # Exact prior attempts retain the superseded source's failure/cancellation;
    # they are evidence only, never substitutes for final-source required jobs.
    prior_attempts=[{"id": 42986949235, "attempt": 1}, {"id": 42986949262, "attempt": 1},
                    {"id": 42991843827, "attempt": 1}],
    recovery_sha256=digest(BASE / "recovery-package.zip"), prior_evidence_sha256=digest(BASE / "prior-package.zip"),
    python_version="3.14.3", finalized=True)
for row in queue:
    path = BASE / "hosted-originals" / row["file"]
    assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"]
    plan["artifacts"].append({key: row[key] for key in ("id", "name", "run", "file", "sha256")})
guard.verify_plan(plan)
guard.verify_prior_evidence(BASE / "prior-package.zip", plan)
write_json(BASE / "2246-finalized-plan.json", plan)
if args.stage_controller:
    offline = json.loads((BASE / "recovery-offline-verified.json").read_text())
    assert offline["all_native_recovery_guards_passed"] and offline["candidate"] == source["candidate"] and offline["tree"] == source["tree"]
    assert offline["recovery_sha256"] == plan["recovery_sha256"] and offline["prior_sha256"] == plan["prior_evidence_sha256"]
    backup = BASE / "controller-before-stage"
    backup.mkdir(exist_ok=False)
    staged = []
    for relative, original in [
        (".github/release-plans/2246.json", BASE / "2246-finalized-plan.json"),
        (plan["recovery_file"], BASE / "recovery-package.zip"),
        (plan["prior_evidence_file"], BASE / "prior-package.zip"),
    ]:
        target = CONTROLLER / relative
        if target.exists():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        assert digest(target) == digest(original)
        staged.append(dict(path=relative, sha256=digest(target), bytes=target.stat().st_size))
    write_json(BASE / "controller-staged.json", dict(candidate=source["candidate"], tree=source["tree"], staged_at=now(), files=staged,
        backup=str(backup), commit_or_push_performed=False))
    print("Staged only reviewed plan/Recovery/Prior bytes; no commit or push.")
else:
    print("Built final plan locally only. Run offline verification before explicit --stage-controller.")

