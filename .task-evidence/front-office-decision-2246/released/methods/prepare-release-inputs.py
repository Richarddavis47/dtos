"""Record exact final committed metadata and patch; no release or source mutation."""
import ast
import subprocess

from common import BASE, SOURCE_REPOSITORY, command, digest, load_source, write_json

source = load_source()
assert command("git", "rev-parse", source["candidate"] + "^{tree}", cwd=SOURCE_REPOSITORY) == source["tree"]
subprocess.run(["git", "merge-base", "--is-ancestor", source["baseline"], source["candidate"]], cwd=SOURCE_REPOSITORY, check=True)
metadata_text = command("git", "show", source["candidate"] + ":app_metadata.py", cwd=SOURCE_REPOSITORY)
parsed = ast.parse(metadata_text)
metadata = {node.targets[0].id: ast.literal_eval(node.value) for node in parsed.body
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    and node.targets[0].id in {"VERSION", "BUILD_NUMBER"}}
assert metadata == {"VERSION": source["version"], "BUILD_NUMBER": source["build"]}
patch = BASE / "candidate.patch"
expected_patch = subprocess.check_output(["git", "diff", "--binary", source["baseline"], source["candidate"]], cwd=SOURCE_REPOSITORY)
if patch.exists():
    assert patch.read_bytes() == expected_patch, "Existing patch differs; preserve and inspect it"
else:
    with patch.open("xb") as stream:
        stream.write(expected_patch)
write_json(BASE / "release-inputs.json", dict(candidate=source["candidate"], tree=source["tree"], baseline=source["baseline"],
    baseline_tree=command("git", "rev-parse", source["baseline"] + "^{tree}", cwd=SOURCE_REPOSITORY), metadata=metadata,
    patch_sha256=digest(patch), patch_bytes=patch.stat().st_size,
    scope="Exact committed patch/centralized metadata only; no validation or live acceptance claim."))
print("Recorded final committed metadata and exact patch.")
