"""Record an already committed/pushed clean sealed controller; never commit or push."""
import json
import subprocess

from common import BASE, command, digest, load_source, now, write_json
from release_common import CONTROLLER, PLAN_PATH, controller_review, final_plan

source, plan = final_plan()
sealed = json.loads((BASE / "publisher-scoped-sealed.json").read_text())
assert sealed["candidate"] == source["candidate"] and sealed["tree"] == source["tree"]
assert all(value == 0 for value in sealed["results"].values()) and sealed["tests"] > 0
assert not command("git", "status", "--porcelain", cwd=CONTROLLER), "Controller must already be committed and clean"
review = controller_review()
assert review["source"] == sealed["source"]
head = command("git", "rev-parse", "HEAD", cwd=CONTROLLER)
tree = command("git", "rev-parse", "HEAD^{tree}", cwd=CONTROLLER)
repo = "repos/" + plan["repository"]
remote = json.loads(subprocess.check_output(["gh", "api", repo + "/git/ref/heads/" + plan["publisher_ref"].removeprefix("refs/heads/")], text=True))
assert remote["object"]["sha"] == head, "Reviewed frozen controller must already be pushed"
record = dict(publisher=head, tree=tree, candidate=source["candidate"], candidate_tree=source["tree"],
    publisher_ref=plan["publisher_ref"], recorded_at=now(), sealed_receipt_sha256=digest(BASE / "publisher-scoped-sealed.json"),
    source=sealed["source"], scope="Existing clean committed/pushed sealed publisher identity; no commit/push/dispatch performed.")
target = BASE / "publisher-source.json"
if target.exists():
    existing = json.loads(target.read_text())
    assert existing["publisher"] == head and existing["tree"] == tree and existing["source"] == sealed["source"]
    print("Existing exact frozen publisher receipt retained:", head)
else:
    write_json(target, record)
    print("Recorded existing frozen publisher:", head)

