"""Retain stopped container evidence first; verify success before ordinary removal."""
import json
import subprocess
import sys

from common import BASE, SOURCE_CHECKOUT, assert_checkout, command, load_source, now, write_json

source = load_source()
invocation = json.loads((BASE / "canonical-invocation.json").read_text())
assert invocation["candidate"] == source["candidate"] and invocation["tree"] == source["tree"]
container = invocation["container"]
record = json.loads(command("docker", "inspect", container))[0]
state = record["State"]
assert record["Id"] == container and not state["Running"] and state["Pid"] == 0, "Still running: inspect without stopping it"
write_json(BASE / "local-container-state-original.json", dict(
    Id=record["Id"], Image=record["Image"], State=state,
    HostConfig={key: record["HostConfig"][key] for key in ("Memory", "MemorySwap", "NanoCpus", "NetworkMode")},
    User=record["Config"]["User"],
    scope="Whitelisted original Docker identity/state/limits only; configuration environment and credentials deliberately not exported."))
stdout = BASE / "local-container-stdout-original.log"
with stdout.open("xb") as stream:
    subprocess.run(["docker", "logs", container], stdout=stream, stderr=subprocess.STDOUT, check=True)
assert state["ExitCode"] == 0 and not state["OOMKilled"], "Failed original preserved; no success/cleanup claim"
config = record["HostConfig"]
assert config["Memory"] == config["MemorySwap"] == 2147483648
assert config["NanoCpus"] == 2000000000 and config["NetworkMode"] == "none" and record["Config"]["User"] == "1000:1000"
with (BASE / "local-canonical-integrity-original.log").open("x") as stream:
    subprocess.run([sys.executable, str(BASE / "verify-local-canonical.py")], stdout=stream, stderr=subprocess.STDOUT, check=True)
proof = json.loads((BASE / "local-verified.json").read_text())
assert proof["all_local_gates_passed"] and proof["tests"] == source["expected_test_count"]
assert_checkout(source, SOURCE_CHECKOUT)
subprocess.run(["docker", "rm", container], check=True, stdout=subprocess.DEVNULL)
assert not command("docker", "ps", "-a", "--filter", "id=" + container, "--format", "{{.ID}}")
write_json(BASE / "local-container-cleanup.json", dict(observed_at=now(), candidate=source["candidate"], tree=source["tree"],
    container=container, started_at=state["StartedAt"], finished_at=state["FinishedAt"], exit_code=state["ExitCode"],
    oom_killed=False, pid_after=0, stopped_container_removed=True, container_absent_after_removal=True,
    all_original_manifest_bytes_verified=True, all_local_tests_and_ten_gates_passed=True, working_tree_clean=True,
    scope="Actual exit0/source/limits/ten gates/original manifest verified before removing only this stopped owned container. Failed prior containers are untouched."))
print("Collected complete successful original; verified and removed only the stopped final container.")

