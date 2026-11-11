"""Start one exact-source canonical attempt after source-bound focused success."""
import argparse
import json
import subprocess

from common import BASE, SOURCE_CHECKOUT, CONTAINER_NAME, IMAGE, assert_checkout, command, digest, git_common_dir, image_record, load_source, now, verify_worker_setup_controls, write_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--focused-proof", type=str, default=str(BASE / "focused-ready.json"))
args = parser.parse_args()
source = load_source()
assert_checkout(source)
proof = json.loads(open(args.focused_proof).read())
proof_source = proof.get("source", proof)
assert proof_source.get("candidate", proof_source.get("head")) == source["candidate"]
assert proof_source["tree"] == source["tree"]
assert proof.get("passed") is True or proof.get("all_native_guards_passed") is True, "Focused passing proof required"
worker_setup_controls = verify_worker_setup_controls(source)
if proof.get('worker_setup_controls') != worker_setup_controls:
    raise RuntimeError('Focused proof must contain the exact independently re-read worker setup controls receipt')
assert (BASE / "setup.json").exists()
assert not (BASE / "canonical-invocation.json").exists(), "Existing invocation must remain intact"
assert not command("docker", "ps", "-a", "--filter", "name=^/" + CONTAINER_NAME + "$", "--format", "{{.ID}}")
output = BASE / "local-canonical"
allowed = {"runner.py", "observer"}
assert {p.name for p in output.iterdir()} == allowed, "Output already contains an attempt"
for path in (BASE / "harness").rglob("*"):
    if path.is_file():
        assert digest(path) == digest(output / path.relative_to(BASE / "harness"))
assert not any((BASE / "fixture").iterdir()), "Fixture already used"
image = image_record()
common = git_common_dir(SOURCE_CHECKOUT)
command_line = [
    "docker", "run", "--detach", "--name", CONTAINER_NAME, "--init", "--user", "1000:1000",
    "--memory=2g", "--memory-swap=2g", "--cpus=2", "--network=none",
    "--env", "HOME=/tmp", "--env", "NODE_OPTIONS=--max-old-space-size=256",
    "--env", "DTOS_EXPECTED_HEAD=" + source["candidate"],
    "--env", "DTOS_EXPECTED_TREE=" + source["tree"],
    "--env", "DTOS_EXPECTED_TEST_COUNT=" + str(source["expected_test_count"]),
    "--volume", str(SOURCE_CHECKOUT) + ":/app",
    "--volume", str(common) + ":" + str(common) + ":ro",
    "--volume", str(output) + ":/output", "--volume", str(BASE / "fixture") + ":/fixture",
    "--workdir", "/app", IMAGE, "python", "-c",
    "import os,runpy; assert os.geteuid()==1000; print('Validation UID',os.geteuid(),flush=True); runpy.run_path('/output/runner.py',run_name='__main__')",
]
record = dict(candidate=source["candidate"], tree=source["tree"], expected_test_count=source["expected_test_count"],
    command=command_line, runtime_image=image["Id"], started_at=now(), checkout=str(SOURCE_CHECKOUT),
    harness_sha256=digest(output / "runner.py"), observer_sha256=digest(output / "observer/sitecustomize.py"),
    fixture_cleanup_sha256=digest(output / "observer/fixture_cleanup.py"),
    focused_proof_path=args.focused_proof, focused_proof_sha256=digest(args.focused_proof),
    worker_setup_controls=worker_setup_controls,
    state="STARTING; not validation success",
    method="Official ten-gate CLI unchanged; 120min outer budget, bounded 0.5s observer, 2GiB/noextraSwap/2CPU/networknone/nonroot. Existing validation-only GC/allocator cleanup between completed modules. No100ms-threshold/application/admission change by the orchestration. The committed benchmark setup correction is part of the pinned source.")
write_json(BASE / "canonical-invocation.json", record)
# Preserve an ambiguous or failed start; never blindly dispatch another container.
container = command(*command_line)
record.update(container=container, state="RUNNING; await actual exit, expected test count, ten gates, complete manifest and cleanup.")
write_json(BASE / "canonical-invocation.json", record)
print(json.dumps(record))

