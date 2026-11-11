"""Verify locally sealed Recovery/Prior with the current native publisher guards."""
import json
import hashlib
from pathlib import Path
import tempfile
import zipfile

from common import BASE, digest, load_source, verify_worker_setup_controls, write_json
from release_common import publisher, verify_release_inputs
from worker_evidence import verify_worker_setup_evidence

source = load_source()
plan = json.loads((BASE / "2246-finalized-plan.json").read_text())
guard = publisher()
guard.verify_plan(plan)
assert plan["candidate"] == source["candidate"] and plan["tree"] == source["tree"] and plan["canonical_tests"] == source["expected_test_count"]
recovery = BASE / "recovery-package.zip"
prior = BASE / "prior-package.zip"
assert digest(recovery) == plan["recovery_sha256"] and digest(prior) == plan["prior_evidence_sha256"]
results = {"local_canonical": guard.verify_local_recovery(recovery, plan)}
for name, verify, prefix in [
    ("partner_history", guard.verify_partner_history_links, "partner-history/"),
    ("team_need", guard.verify_team_need_handoff, "team-need/"),
    ("offer_comparison", guard.verify_offer_comparison, "offer-comparison/"),
    ("protections", guard.verify_recommended_protections, "protections/"),
    ("activation", guard.verify_activation_deferral, "local-canonical/activation/"),
    ("front_office_workflow", guard.verify_front_office_workflow, "local-canonical/front-office-workflow/"),
    ("history", guard.verify_completed_trade_browser, "feature/"),
]:
    results[name] = verify(recovery, plan, prefix=prefix)
    assert results[name]["passed"]
results["history_cases"] = guard.verify_completed_trade_cases(recovery, plan)
assert results["history_cases"]["passed"]
with tempfile.TemporaryDirectory() as temporary, zipfile.ZipFile(recovery) as archive:
    manifest = json.loads(archive.read("recovery-manifest.json"))
    assert manifest["candidate"] == source["candidate"] and manifest["tree"] == source["tree"]
    rows = manifest["files"]
    names = {row["name"] for row in rows}
    assert len(names) == len(rows)
    assert set(archive.namelist()) == names | {"recovery-manifest.json"}
    for row in rows:
        raw = archive.read(row["name"])
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], row["name"]
    results["exact_patch"] = verify_release_inputs(archive.read("candidate.patch"), json.loads(archive.read("release-inputs.json")))
    worker_setup_controls = verify_worker_setup_controls(source)
    assert json.loads(archive.read('worker-setup-verified.json')) == worker_setup_controls
    assert json.loads(archive.read('focused-ready.json'))['worker_setup_controls'] == worker_setup_controls
    worker_prefix = 'worker-setup-controls/'
    worker_names = {name.removeprefix(worker_prefix) for name in archive.namelist() if name.startswith(worker_prefix)}
    results['worker_setup_evidence'] = verify_worker_setup_evidence(
        lambda name: archive.read(worker_prefix + name), worker_setup_controls, worker_names,
        archive.read('methods/worker_evidence.py'))
    results['worker_setup_controls'] = worker_setup_controls
    guard.verify_handoff(archive.read("SCOUT_HANDOFF.md"), plan)
    for name, verify, members in [
        ("local-preflight", guard.verify_preflight, ["result.json", "raw.log", "SHA256SUMS"]),
        ("local-restoration-unused", guard.verify_actuals_restoration, ["evidence/result.json", "raw.log", "prior-study.zip", "SHA256SUMS"]),
        ("local-resident-refresh", guard.verify_resident_refresh, ["evidence/result.json", "raw.log", "SHA256SUMS"]),
    ]:
        path = Path(temporary) / (name + ".zip")
        guard.make_zip(path, {member: archive.read(name + "/" + member) for member in members})
        results[name] = verify(path, plan)
        assert results[name]["passed"]
guard.verify_prior_evidence(prior, plan)
write_json(BASE / "recovery-offline-verified.json", dict(candidate=source["candidate"], tree=source["tree"],
    all_native_recovery_guards_passed=True, recovery_sha256=digest(recovery), prior_sha256=digest(prior),
    local_canonical_tests=source["expected_test_count"],
    guards={name: {key: value for key, value in row.items() if key in ("passed", "head", "tree", "commit", "cgroup_limit", "matched_cases")} for name, row in results.items()},
    method="Current publisher native guards applied to sealed original final-source Recovery and Prior ZIPs; not Actions preparation or production acceptance."))
print("Offline final-source Recovery/Prior native guards passed.")

