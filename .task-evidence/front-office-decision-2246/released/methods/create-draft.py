"""Create only the guarded unused-version draft after complete final-source acceptance."""
import json
import subprocess

from common import BASE, SOURCE_REPOSITORY, command, load_source, write_json
from release_common import passing_inputs, publisher

source, local, host, native, focused = passing_inputs()
guard = publisher()
runs = json.loads((BASE / "validation-runs.json").read_text())
assert runs["candidate"] == source["candidate"] and runs["tree"] == source["tree"]
product = json.loads((BASE / "product-test-counts.json").read_text())
assert product["candidate"] == source["candidate"] and product["tree"] == source["tree"] and product["total"] > 0
plan = dict(source, repository=source.get("repository", "Richarddavis47/dtos"), runs=runs["runs"], canonical_tests=source["expected_test_count"], product_tests=product["total"])
guard.verify_runs(plan)
repo = "repos/" + plan["repository"]


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", repo + "/" + path], text=True))


assert api("git/ref/heads/main")["object"]["sha"] == source["baseline"]
pr = api("pulls/335")
assert pr["state"] == "open" and not pr["merged"] and pr["head"]["sha"] == source["candidate"] and pr["base"]["ref"] == "main"
tag = "v" + source["version"]
lookup = subprocess.run(["gh", "api", repo + "/git/ref/tags/" + tag], capture_output=True, text=True)
assert lookup.returncode and "HTTP 404" in lookup.stderr, "Immutable target already used; hold"
existing = [row for row in api("releases?per_page=100") if row["tag_name"] == tag]
if existing:
    assert len(existing) == 1 and existing[0]["draft"] and not existing[0]["immutable"] and existing[0]["target_commitish"] == source["candidate"]
    draft = existing[0]
else:
    notes = command("git", "show", source["candidate"] + ":RELEASE_NOTES.md", cwd=SOURCE_REPOSITORY).split("\n# ", 1)[0]
    payload = dict(tag_name=tag, target_commitish=source["candidate"], name="DTOS " + tag + " / build " + str(source["build"]),
        body=notes, draft=True, prerelease=False)
    write_json(BASE / "draft-create-input.json", payload)
    draft = json.loads(subprocess.check_output(["gh", "api", repo + "/releases", "--method", "POST", "--input", str(BASE / "draft-create-input.json")], text=True))
assert draft["draft"] and draft["tag_name"] == tag and draft["target_commitish"] == source["candidate"]
write_json(BASE / "draft-created.json", draft)
print("Created/reused only exact validated draft", draft["id"], "without tag/merge/publication")

