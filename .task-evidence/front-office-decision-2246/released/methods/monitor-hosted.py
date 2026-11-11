"""Bounded read-only final-head monitor: at most one API request per sixty seconds."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from common import load_source

BASE = Path(__file__).resolve().parent
SOURCE = load_source()
REQUIRED = {"canonical-release", "product-browser", "my-team-browser", "beginner-navigation", "public-welcome-browser",
            "historical-trade-timeline", "projection-display-cross-version", "resident-refresh-memory",
            "tooling (ubuntu-24.04)", "tooling (windows-latest)", "cgroup-lifecycle (ordinary)",
            "cgroup-lifecycle (archive-warmed)", "cgroup-lifecycle (combined-read)"}
folder = BASE / "hosted-monitor"
folder.mkdir(exist_ok=False)
started = time.monotonic()
first = BASE / "hosted-checks-first.json"
next_request = max(time.time(), first.stat().st_mtime + 60)
previous = None
for index in range(95):
    if time.monotonic() - started >= 95 * 60:
        break
    delay = next_request - time.time()
    if delay > 0:
        time.sleep(min(delay, 60))
        while time.time() < next_request:
            time.sleep(min(next_request - time.time(), 1))
    assert json.loads((BASE / "source.json").read_text()) == SOURCE, "Source changed: stop old monitor"
    request_at = time.time()
    command = ["gh", "api", "repos/Richarddavis47/dtos/commits/" + SOURCE["candidate"] + "/check-runs?filter=latest&per_page=100"]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    next_request = request_at + 60
    path = folder / f"checks-{index + 1:03d}.json"
    path.write_bytes(result.stdout)
    if result.returncode:
        (folder / f"checks-{index + 1:03d}.stderr").write_bytes(result.stderr)
        raise RuntimeError("Read-only check API failed; preserve transport output and stop, no retry")
    data = json.loads(result.stdout)
    rows = [row for row in data["check_runs"] if row["name"] in REQUIRED]
    assert len(rows) == len({row["name"] for row in rows}) and all(row["head_sha"] == SOURCE["candidate"] for row in rows)
    failed = [row for row in rows if row["status"] == "completed" and row["conclusion"] != "success"]
    status = dict(observed_at=datetime.now(timezone.utc).isoformat(), candidate=SOURCE["candidate"], tree=SOURCE["tree"],
                  expected=len(REQUIRED), seen=len(rows), passed=sum(row["conclusion"] == "success" for row in rows),
                  in_progress=sum(row["status"] == "in_progress" for row in rows), failed=len(failed),
                  jobs=[{key: row[key] for key in ("id", "name", "status", "conclusion", "details_url")} for row in rows],
                  original=dict(file=str(path.relative_to(BASE)), bytes=len(result.stdout), sha256=hashlib.sha256(result.stdout).hexdigest()),
                  scope="Read-only hosted status only; native artifact/source/console validation remains separate.")
    (BASE / "hosted-monitor-status.json").write_text(json.dumps(status, indent=2) + "\n")
    signature = [(row["name"], row["status"], row["conclusion"]) for row in rows]
    if signature != previous:
        print(json.dumps({key: status[key] for key in ("observed_at", "seen", "passed", "in_progress", "failed")}), flush=True)
        previous = signature
    if failed:
        status["status"] = "STOPPED_REQUIRED_HOSTED_FAILURE"
        (BASE / "hosted-reconciliation-stopped.json").write_text(json.dumps(status, indent=2) + "\n")
        print(json.dumps(dict(stopped=True, failures=[(row["name"], row["id"], row["conclusion"]) for row in failed])), flush=True)
        raise SystemExit(2)
    if len(rows) == len(REQUIRED) and all(row["status"] == "completed" and row["conclusion"] == "success" for row in rows):
        status["status"] = "ALL_13_REQUIRED_HOSTED_JOBS_PASSED"
        (BASE / "hosted-monitor-complete.json").write_text(json.dumps(status, indent=2) + "\n")
        print("ALL_13_REQUIRED_HOSTED_JOBS_PASSED", flush=True)
        raise SystemExit(0)
raise RuntimeError("Bounded95minute observation ended; no rerun, dispatch or acceptance claim")
