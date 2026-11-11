"""Prepare a new writable exact-source checkout and copied harness; never start tests."""
from pathlib import Path
import shutil
import subprocess

from common import BASE, SOURCE_CHECKOUT, SOURCE_REPOSITORY, CONTAINER_NAME, assert_checkout, command, image_record, load_source, now, write_json

source = load_source()
assert not (BASE / "canonical-invocation.json").exists(), "Existing attempt must remain intact"
assert not SOURCE_CHECKOUT.exists(), "Existing checkout must be inspected, never replaced"
assert not command("docker", "ps", "-a", "--filter", "name=^/" + CONTAINER_NAME + "$", "--format", "{{.ID}}"), "Existing container must be preserved"
assert not (BASE / "local-canonical").exists(), "Existing output must be preserved"
assert not (BASE / "fixture").exists(), "Existing fixture must be preserved"
assert command("git", "rev-parse", source["candidate"] + "^{tree}", cwd=SOURCE_REPOSITORY) == source["tree"]
image = image_record()
subprocess.run(["git", "worktree", "add", "--detach", str(SOURCE_CHECKOUT), source["candidate"]], cwd=SOURCE_REPOSITORY, check=True)
assert_checkout(source)
shutil.copytree(BASE / "harness", BASE / "local-canonical")
(BASE / "fixture").mkdir()
# Only this fresh owned checkout/output/scratch are made writable by UID1000.
# The official compileall gate writes bytecode, so a root-owned checkout is invalid.
subprocess.run(["chown", "-R", "1000:1000", str(SOURCE_CHECKOUT), str(BASE / "local-canonical"), str(BASE / "fixture")], check=True)
write_json(BASE / "setup.json", dict(candidate=source["candidate"], tree=source["tree"], prepared_at=now(),
    checkout=str(SOURCE_CHECKOUT), container_name=CONTAINER_NAME, image=image["Id"],
    expected_test_count=source["expected_test_count"], tests_started=False,
    method="Fresh detached writable validation checkout; copied final-only harness. Prior attempts untouched."))
print("Prepared exact-source checkout and harness; no tests started.")

