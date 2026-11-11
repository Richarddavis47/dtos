"""Run scoped final publisher checks on sealed reviewed bytes; no commit/push/dispatch."""
import json
import re
import subprocess

from common import BASE, digest, image_record, load_source, write_json
from release_common import CONTROLLER, PLAN_PATH, controller_review, final_plan, publisher

source, plan = final_plan()
guard = publisher()
guard.verify_plan(plan)
offline = json.loads((BASE / "recovery-offline-verified.json").read_text())
assert offline["all_native_recovery_guards_passed"] and offline["candidate"] == source["candidate"] and offline["tree"] == source["tree"]
assert digest(CONTROLLER / plan["recovery_file"]) == offline["recovery_sha256"] == plan["recovery_sha256"]
assert digest(CONTROLLER / plan["prior_evidence_file"]) == offline["prior_sha256"] == plan["prior_evidence_sha256"]
review = controller_review()
write_json(BASE / "publisher-workflow-review.json", review)
image = image_record()
prefix = ["docker", "run", "--rm", "--init", "--user", "1000:1000", "--memory=2g", "--memory-swap=2g", "--cpus=2", "--network=none",
    "--env", "HOME=/tmp", "--env", "PYTHONPYCACHEPREFIX=/tmp/pycache", "--volume", str(CONTROLLER) + ":/app:ro", "--workdir", "/app", image["Id"], "python"]
commands = {
    "tests": ["-m", "unittest", "discover", "-s", "tests", "-p", "test_release_publisher.py", "-v"],
    "lint": ["-m", "ruff", "check", "--no-cache", "tools/release", "tests/test_release_publisher.py"],
    "compile": ["-m", "compileall", "-q", "tools/release", "tests/test_release_publisher.py"],
}
assert not (BASE / "publisher-scoped-sealed.json").exists()
results = {}
for name, arguments in commands.items():
    with (BASE / ("publisher-" + name + "-sealed-original.log")).open("xb") as stream:
        result = subprocess.run(prefix + arguments, stdout=stream, stderr=subprocess.STDOUT)
    results[name] = result.returncode
    assert result.returncode == 0, name
console = (BASE / "publisher-tests-sealed-original.log").read_bytes()
match = re.search(rb"Ran (\d+) tests in [0-9.]+s\s+OK\s*$", console)
assert match and int(match[1]) > 0
actual_tests = int(match[1])
if "expected_publisher_test_count" in source:
    assert actual_tests == source["expected_publisher_test_count"]
after = controller_review()
assert after["source"] == review["source"], "Controller changed during sealed checks"
write_json(BASE / "publisher-scoped-sealed.json", dict(candidate=source["candidate"], tree=source["tree"],
    results=results, tests=actual_tests, source=after["source"], commands={name: prefix + arguments for name, arguments in commands.items()},
    runtime_image=image["Id"], canonical_steps_byte_identical=True, allowed_paths=after["allowed_paths"],
    scope="Actual final sealed publisher tests/Ruff/compile under nonroot Python3.14 immutable runtime/2GiB/noextraSwap/2CPU/networknone. No commit/push/dispatch."))
print("Final sealed publisher checks passed; actual unittest executions:", actual_tests)

