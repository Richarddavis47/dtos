"""Discover completed final-head PR workflows and list all fifteen original archives; no dispatch/download."""
import json
import re
import subprocess

from common import BASE, load_source, write_json

source = load_source()
repository = source.get("repository", "Richarddavis47/dtos")
contracts = [
    dict(name="Canonical release recovery", path=".github/workflows/canonical-release-recovery.yml", jobs=["canonical-release"]),
    dict(name="Product browser journeys", path=".github/workflows/product-browser.yml", jobs=["product-browser", "my-team-browser", "beginner-navigation", "public-welcome-browser", "historical-trade-timeline", "projection-display-cross-version", "resident-refresh-memory"]),
    dict(name="Validation tooling", path=".github/workflows/validation-tooling.yml", jobs=["tooling (ubuntu-24.04)", "tooling (windows-latest)"]),
    dict(name="Linux Asset Market lifecycle", path=".github/workflows/linux-market-lifecycle.yml", jobs=["cgroup-lifecycle (ordinary)", "cgroup-lifecycle (archive-warmed)", "cgroup-lifecycle (combined-read)"]),
]
mapping = {
    "canonical-release-2g-python314": "canonical-original.zip",
    "current-season-history-browser": "current-history-original.zip",
    "history-followthrough-browser": "history-followthrough-original.zip",
    "market-history-coverage-browser": "market-history-coverage-original.zip",
    "current-production-coverage-browser": "current-production-coverage-original.zip",
    "trade-resource-2g": "trade-resource-original.zip",
    "league-entry-2g": "league-entry-original.zip",
    "restoration-unused-2g": "restoration-unused-original.zip",
    "actuals-restoration-2g": "actuals-restoration-original.zip",
    "restoration-preflight-2g": "preflight-original.zip",
    "resident-refresh-ownership-2g": "resident-refresh-original.zip",
    "linux-market-lifecycle-ordinary-summary": "lifecycle-ordinary.zip",
    "linux-market-lifecycle-archive-warmed-summary": "lifecycle-archive-warmed.zip",
    "linux-market-lifecycle-combined-read-summary": "lifecycle-combined-read.zip",
    "public-welcome-security-browser": "public-welcome-security.zip",
}


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", "repos/" + repository + "/" + path], text=True))


known = BASE / "validation-runs.json"
if known.exists():
    payload = json.loads(known.read_text())
    assert payload["candidate"] == source["candidate"] and payload["tree"] == source["tree"]
    selected = {row["path"]: row["id"] for row in payload["runs"]}
else:
    available = api("actions/runs?event=pull_request&head_sha=" + source["candidate"] + "&per_page=100")["workflow_runs"]
    selected = {}
    for contract in contracts:
        matches = [row for row in available if row["head_sha"] == source["candidate"] and row["event"] == "pull_request" and row["path"] == contract["path"]]
        assert matches, contract["path"]
        selected[contract["path"]] = max(matches, key=lambda row: row["id"])["id"]
records = []
artifacts = []
runs = []
for contract in contracts:
    run = api("actions/runs/" + str(selected[contract["path"]]))
    assert run["head_sha"] == source["candidate"] and run["event"] == "pull_request" and run["path"] == contract["path"]
    assert run["status"] == "completed" and run["conclusion"] == "success", contract["name"]
    jobs = api("actions/runs/" + str(run["id"]) + "/jobs?per_page=100")["jobs"]
    for name in contract["jobs"]:
        rows = [row for row in jobs if row["name"] == name]
        assert len(rows) == 1 and rows[0]["status"] == "completed" and rows[0]["conclusion"] == "success", name
        assert rows[0]["head_sha"] == source["candidate"], name
    native = api("actions/runs/" + str(run["id"]) + "/artifacts?per_page=100")["artifacts"]
    artifacts.extend(native)
    records.append(dict(run=run, jobs=jobs, artifacts=native))
    runs.append(dict(contract, id=run["id"]))
queue = []
for name, filename in mapping.items():
    rows = [row for row in artifacts if row["name"] == name and not row["expired"]]
    assert len(rows) == 1, name
    row = rows[0]
    assert row["workflow_run"]["head_sha"] == source["candidate"]
    checksum = row["digest"].removeprefix("sha256:")
    assert re.fullmatch("[a-f0-9]{64}", checksum)
    queue.append(dict(id=row["id"], name=name, run=row["workflow_run"]["id"], file=filename, bytes=row["size_in_bytes"], sha256=checksum))
assert len(queue) == 15 and sum(len(row["jobs"]) for row in runs) == 13
write_json(BASE / "validation-runs.json", dict(candidate=source["candidate"], tree=source["tree"], runs=runs))
write_json(BASE / "hosted-final-records.json", records)
write_json(BASE / "artifact-download-queue.json", queue)
print(json.dumps(dict(candidate=source["candidate"], tree=source["tree"], jobs=13, original_artifacts=len(queue),
    scope="Read-only final-head PR metadata; download originals through the established connector without retaining signed URLs.")))

