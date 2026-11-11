"""Final-only publication helpers; imports never mutate controller or remote state."""
import importlib.util
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from common import BASE, SOURCE_REPOSITORY, command, digest, load_source, write_json

CONTROLLER = Path("/workspace/dtos-publisher-2246")
PLAN_PATH = CONTROLLER / ".github/release-plans/2246.json"


def verify_release_inputs(patch_bytes=None, receipt=None):
    """Bind the handoff patch to the actual committed source, never a stale file."""
    source = load_source()
    if patch_bytes is None:
        patch_bytes = (BASE / "candidate.patch").read_bytes()
    if receipt is None:
        receipt = json.loads((BASE / "release-inputs.json").read_text())
    expected = subprocess.check_output(
        ["git", "diff", "--binary", source["baseline"], source["candidate"]], cwd=SOURCE_REPOSITORY)
    assert patch_bytes == expected, "Handoff patch is not the exact final committed patch"
    assert command("git", "rev-parse", source["candidate"] + "^{tree}", cwd=SOURCE_REPOSITORY) == source["tree"]
    parsed = ast.parse(command("git", "show", source["candidate"] + ":app_metadata.py", cwd=SOURCE_REPOSITORY))
    metadata = {node.targets[0].id: ast.literal_eval(node.value) for node in parsed.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {"VERSION", "BUILD_NUMBER"}}
    assert metadata == {"VERSION": source["version"], "BUILD_NUMBER": source["build"]}
    for key in ("candidate", "tree", "baseline"):
        assert receipt[key] == source[key], "Patch receipt identity mismatch: " + key
    assert receipt["metadata"] == metadata
    assert receipt["baseline_tree"] == command("git", "rev-parse", source["baseline"] + "^{tree}", cwd=SOURCE_REPOSITORY)
    assert receipt["patch_bytes"] == len(patch_bytes)
    assert receipt["patch_sha256"] == hashlib.sha256(patch_bytes).hexdigest()
    return {"passed": True, "candidate": source["candidate"], "tree": source["tree"],
            "patch_bytes": len(patch_bytes), "patch_sha256": receipt["patch_sha256"]}


def publisher():
    sys.dont_write_bytecode = True
    path = CONTROLLER / "tools/release/publish.py"
    spec = importlib.util.spec_from_file_location("final_publication_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def final_plan():
    source = load_source()
    plan = json.loads(PLAN_PATH.read_text())
    assert plan["candidate"] == source["candidate"] and plan["tree"] == source["tree"] and plan["baseline"] == source["baseline"]
    assert plan["canonical_tests"] == source["expected_test_count"]
    assert plan["version"] == source["version"] and plan["build"] == source["build"] and plan["pr"] == 335
    return source, plan


def passing_inputs():
    source = load_source()
    local = json.loads((BASE / "local-verified.json").read_text())
    host = json.loads((BASE / "host-canonical-verified.json").read_text())
    native = json.loads((BASE / "hosted-artifacts-verified.json").read_text())
    focused = json.loads((BASE / "focused-resource-verified.json").read_text())
    assert local["all_local_gates_passed"] and host["all_gates_passed"] and native["passed"] and focused["all_native_guards_passed"]
    for proof in (local, host, native, focused):
        assert proof["candidate"] == source["candidate"] and proof["tree"] == source["tree"]
    assert local["tests"] == host["tests"] == source["expected_test_count"]
    return source, local, host, native, focused


def native_plan():
    source = load_source()
    host = json.loads((BASE / "host-canonical-verified.json").read_text())
    return dict(source, canonical_tests=source["expected_test_count"], canonical_entries=host["entries"], python_version="3.14.3")


def canonical_steps(text):
    start = text.index("  canonical-release:\n")
    body = text[start:]
    import re
    next_job = re.search(r"\n  [A-Za-z][A-Za-z0-9_-]*:\n", body[1:])
    if next_job:
        body = body[:next_job.start() + 1]
    return body[body.index("    steps:\n"):]


def controller_review():
    source = load_source()
    guard = publisher()
    changed = set(command("git", "diff", "--name-only", source["baseline"], cwd=CONTROLLER).splitlines())
    changed |= set(command("git", "ls-files", "--others", "--exclude-standard", cwd=CONTROLLER).splitlines())
    assert changed <= guard.ALLOWED_PATHS, "Controller includes unexpected paths: " + repr(changed - guard.ALLOWED_PATHS)
    candidate_workflow = command("git", "show", source["candidate"] + ":.github/workflows/canonical-release-recovery.yml", cwd=SOURCE_REPOSITORY)
    controller_workflow = (CONTROLLER / ".github/workflows/canonical-release-recovery.yml").read_text()
    assert canonical_steps(candidate_workflow) == canonical_steps(controller_workflow), "Final candidate/controller canonical steps differ"
    assert command("git", "merge-base", "HEAD", source["baseline"], cwd=CONTROLLER) == source["baseline"], "Controller is not baseline-derived"
    files = {name: digest(CONTROLLER / name) for name in sorted(guard.ALLOWED_PATHS)}
    return dict(candidate=source["candidate"], tree=source["tree"], baseline=source["baseline"], allowed_paths=sorted(guard.ALLOWED_PATHS),
        changed_paths=sorted(changed), source=files, canonical_steps_byte_identical=True, baseline_derived=True)

