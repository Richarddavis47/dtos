"""Run the unchanged canonical validator in an enforced disposable cgroup."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

import psutil

ROOT = Path("/app")
OUTPUT = Path("/output")
FIXTURE = Path("/fixture")
OUTPUT.mkdir(exist_ok=True)
FIXTURE.mkdir(exist_ok=True)
os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=256")
for key, name in {"CACHE":"cache.json", "PROJECTION_DB":"projections.sqlite3",
                  "METADATA_DB":"metadata.sqlite3", "INTELLIGENCE_CHECKPOINT":"intelligence.sqlite3",
                  "FOIS_DB":"fois.sqlite3", "HISTORY_DB":"retired.sqlite3",
                  "ACCOUNT_DB":"accounts.sqlite3"}.items():
    os.environ["DTOS_" + key + "_FILE"] = str(FIXTURE / name)
os.environ.update(
    DTOS_DURABLE_HISTORY_REQUIRED="0", SLEEPER_BASE_URL="http://127.0.0.1:9/v1",
    SLEEPER_LEAGUE_ID="1804000000000000000", DTOS_FIXTURE_ROOT="/fixture",
    DTOS_SLEEPER_SEASON_CACHE_ROOT="/fixture/sleeper-season-cache",
    DTOS_HISTORY_STORAGE_ROOT="/fixture", DTOS_ATTRIBUTION_TEST_LOG="/output/tests.jsonl",
    DTOS_PLAIN_ENGLISH_EVIDENCE="/output/plain-browser",
    DTOS_PREMIUM_EVIDENCE="/output/premium-browser",
    DTOS_OUTLOOK_EVIDENCE="/output/outlook-browser",
    DTOS_BRIEF_EVIDENCE="/output/home-browser",
    DTOS_TREND_BROWSER_EVIDENCE="/output/market-browser.json",
    DTOS_MANAGER_EVIDENCE="/output/manager-browser",
    DTOS_PERSONAL_AVAILABILITY_EVIDENCE="/output/personal-browser",
    DTOS_PERSONAL_RECOVERY_EVIDENCE="/output/personal-recovery",
    DTOS_PHASE2_EVIDENCE="/output/source-screen",
    DTOS_PERSONAL_PARTIAL_EVIDENCE="/output/custom-partial",
    DTOS_RELATIVE_EVIDENCE="/output/relative-custom",
    DTOS_DECISION_HISTORY_EVIDENCE="/output/decision-history",
    DTOS_PROJECTION_COVERAGE_EVIDENCE="/output/projection-coverage",
    DTOS_LINEUP_REVIEW_EVIDENCE="/output/lineup-review",
    DTOS_TRADE_WORKFLOW_EVIDENCE="/output/trade-workflow",
    DTOS_TRADE_PICKER_EVIDENCE="/output/trade-picker",
    DTOS_MARKET_PREPARATION_EVIDENCE="/output/market-preparation",
    DTOS_CUSTOMER_CLARITY_EVIDENCE="/output/customer-clarity",
    DTOS_CUSTOM_READINESS_EVIDENCE="/output/custom-readiness",
    DTOS_REBUILD_DISCOVERY_EVIDENCE="/output/rebuild-discovery",
    DTOS_REBUILD_SPACE_EVIDENCE="/output/rebuild-space",
    DTOS_TRADE_RESPONSE_EVIDENCE="/output/trade-response",
    DTOS_CONDITIONAL_EVIDENCE="/output/conditional-trades",
    DTOS_STRATEGY_STATE_EVIDENCE="/output/strategy-state",
    DTOS_CONTEXTUAL_BACK_EVIDENCE="/output/contextual-back",
    DTOS_FOIS_BROWSER_EVIDENCE="/output/fois-browser.json",
    DTOS_PREPARATION_BROWSER_EVIDENCE="/output/preparation-browser.json",
    PYTHONPATH="/output/observer:/app")
git_n = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
os.environ["GIT_CONFIG_COUNT"] = str(git_n + 1)
os.environ["GIT_CONFIG_KEY_" + str(git_n)] = "safe.directory"
os.environ["GIT_CONFIG_VALUE_" + str(git_n)] = "/app"
sys.path.insert(0, str(ROOT))
from src.platform.lifecycle import memory_snapshot

head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert head == os.environ["DTOS_EXPECTED_HEAD"], "Checkout is not the exact requested candidate."
assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
assert memory_snapshot()["cgroup_limit_bytes"] == 2147483648
assert shutil.disk_usage(FIXTURE).free > 8 * 1024**3, "Need 8 GiB diagnostic scratch space."
started = time.time()
stop = threading.Event()
parent = psutil.Process()

def watch():
    with (OUTPUT / "memory.jsonl").open("a", buffering=1) as sink:
        for _ in range(10000):
            if stop.wait(.5):
                break
            sample_start = time.monotonic()
            row = dict(time=time.time(), monotonic=sample_start,
                       memory=memory_snapshot(), processes=[],
                       fixture_free_bytes=shutil.disk_usage(FIXTURE).free)
            try:
                stat = dict(line.split() for line in Path("/sys/fs/cgroup/memory.stat").read_text().splitlines())
                row.update({k:int(stat[k]) for k in ("anon", "file", "shmem", "inactive_file", "active_file", "kernel") if k in stat})
                row["kernel_peak"] = int(Path("/sys/fs/cgroup/memory.peak").read_text())
                processes = [parent, *parent.children(recursive=True)]
                row["process_samples_truncated"] = len(processes) > 24
                row["zombies"] = 0
                for process in processes[:24]:
                    try:
                        if process.status() == psutil.STATUS_ZOMBIE:
                            row["zombies"] += 1
                            continue
                        info = process.memory_full_info()
                        row["processes"].append(dict(pid=process.pid, ppid=process.ppid(),
                            name=process.name(), rss=info.rss, pss=getattr(info, "pss", None),
                            uss=getattr(info, "uss", None)))
                    except psutil.Error:
                        pass
            except (psutil.Error, OSError, ValueError):
                row["sampling_incomplete"] = True
            row["sampling_window_ms"] = (time.monotonic() - sample_start) * 1000
            sink.write(json.dumps(row, separators=(",", ":")) + "\n")

def run_canonical_process(command, stream, timeout, cleanup):
    """Reap the timed-out validator tree before hashing its evidence."""
    child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                             start_new_session=os.name == "posix")
    cleanup.update(timeout_triggered=False, validator_pid=child.pid)
    try:
        result = child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        cleanup["timeout_triggered"] = True
        discovery_ok = True
        try:
            descendants = psutil.Process(child.pid).children(recursive=True)
        except psutil.Error:
            descendants = []
            discovery_ok = False
        if os.name == "posix":
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            child.terminate()
        # Detached descendants may not belong to the validator group.
        for process in descendants:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)
        _, alive = psutil.wait_procs(descendants, timeout=3)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(alive, timeout=3)
        active = [p.pid for p in alive if p.is_running()]
        cleanup.update(descendant_count=len(descendants), active_after_count=len(active),
                       active_after=active[:16], discovery_complete=discovery_ok,
                       timeout_cleanup_complete=discovery_ok and not active and child.poll() is not None)
        raise
    cleanup["validator_reaped"] = True
    return subprocess.CompletedProcess(command, result)

watcher = threading.Thread(target=watch, daemon=True)
watcher.start()
code = 1
error = None
process_cleanup = {}
try:
    from tools.validation import generate_sanitized_market_fixture as seed
    seed.ASSET_COUNT = 250
    data = seed._cache(FIXTURE / "cache.json")
    seed.seed_fixture_projection(data, FIXTURE / "projections.sqlite3")
    seed._canonical_history_fixture(FIXTURE)
    with (OUTPUT / "canonical.log").open("w") as stream:
        # Matched CI evidence completed4188/4326tests at75min, with
        # no assertion failures; remaining local work was38seconds.
        # Keep every test/cap/performance assertion, within the85min job.
        result = run_canonical_process(
            [sys.executable, "-m", "tools.validation.validate_release"],
            stream, timeout=4800, cleanup=process_cleanup)
    code = result.returncode
except BaseException as exc:
    error = type(exc).__name__ + ": " + str(exc)
    raise
finally:
    stop.set()
    watcher.join(3)
    trace = ROOT / ".validation" / "validator_trace.jsonl"
    if trace.exists():
        shutil.copy2(trace, OUTPUT / "canonical-trace.jsonl")
    report = dict(head=head, tree=subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
        python=sys.version, started_at=started, finished_at=time.time(),
        elapsed_seconds=time.time()-started, exit_code=code, passed=code == 0,
        error=error, process_cleanup=process_cleanup,
        cgroup_limit=2147483648, cpus=2, network="none",
        final_memory=memory_snapshot(), kernel_peak=int(Path("/sys/fs/cgroup/memory.peak").read_text()),
        fixture="250 asset prepared sanitized foundation; disposable authenticated test transports")
    (OUTPUT / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    manifest = []
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}:
            manifest.append(dict(name=str(path.relative_to(OUTPUT)), bytes=path.stat().st_size,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (OUTPUT / "SHA256SUMS").write_text("".join(item["sha256"] + "  " + item["name"] + "\n" for item in manifest))
    tail = (OUTPUT / "canonical.log")
    if tail.exists():
        print(tail.read_text(errors="replace")[-12000:], flush=True)
raise SystemExit(code)
