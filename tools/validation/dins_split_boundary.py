"""Focused fixture proof: independent2GiB server and capture cgroups, shared loopback.

No production entry point. No full DINS acceptance. The server retains the same
production-shaped baseline; only the browser's execution/resource boundary moves.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import psutil

from tools.inspection.loopback_relay import RelayPolicy, RelayServer, valid_target
from tools.validation import linux_dins_memory_gate as gate
from tools.validation import linux_market_cgroup_gate as lifecycle

CONTROL = Path("/output")
ORIGIN = "http://dtos.fixture:8768"
REQUIRED = ["/api/market/health", "/api/inspect/site-map", "/api/status",
            "/api/inspect/valuation", "/api/inspect/health", "/health/ready"]


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for key in ("href", "src"):
            value = attributes.get(key, "")
            parsed = urlsplit(value)
            if parsed.netloc and parsed.netloc != "dtos.fixture:8768":
                continue
            target = urlunsplit(("", "", parsed.path, parsed.query, ""))
            if valid_target(target):
                self.targets.add(target)


def inventory(token: str, *, full: bool = False) -> list[str]:
    policy = RelayPolicy(REQUIRED, token, 8767)
    status, _, body = policy.read("GET", "/api/inspect/site-map")
    if status != 200:
        raise AssertionError("Fixture inventory unavailable")
    pages = json.loads(body)["pages"]
    targets = set(REQUIRED)
    for page in pages:
        if not page.get("excluded"):
            targets.add(page["route"])
            targets.add("/api/inspect/pages/" + page["page_id"])
    # Only CSS/JS repository assets, not archived inspection or arbitrary disk.
    for folder in (Path("static/css"), Path("static/js")):
        targets.update("/" + path.as_posix() for path in folder.rglob("*") if path.is_file())
    # Focused Teams workload only. Full inventory is still exposed unchanged;
    # the established focused harness selects the one page and mobile viewport.
    html_targets = [page["route"] for page in pages if not page.get("excluded")] if full else ["/teams", "/teams/4"]
    for target in html_targets:
        policy = RelayPolicy(sorted(targets), token, 8767)
        status, _, body = policy.read("GET", target)
        if status != 200:
            raise AssertionError("Fixture Teams warm read failed")
        parser = Resources()
        parser.feed(body.decode("utf-8"))
        targets.update(parser.targets)
    return sorted(targets)


def server() -> int:
    output = CONTROL / "server"
    output.mkdir(exist_ok=True)
    full = os.environ.get("DTOS_DINS_SPLIT_SCOPE") == "full"
    summary = {"passed": False, "release_acceptance_eligible": full}
    process = relay = thread = None
    padding: list[bytearray] = []
    peak = 0
    try:
        if lifecycle._cgroup("memory.max") != lifecycle.MEMORY_MAX:
            raise AssertionError("Server hard limit changed")
        lifecycle._retire_validation_archive(warm=False)
        with (output / "server.private.log").open("w+") as log:
            process = lifecycle._start_server(log, popen_factory=gate.production_server)
            lifecycle._cold_build()
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                ready = json.loads(lifecycle._request("/health/ready")[1])
                if gate.startup_settled((ready.get("runtime") or {}).get("background_tasks") or {}):
                    break
                time.sleep(1)
            else:
                raise AssertionError("Fixture startup did not settle")
            from tools.validation.dins_fixture_images import prepare

            prepare(lifecycle.FIXTURE / "dins-images")
            token = lifecycle._fixture_inspection_environment(os.environ.copy())["DTOS_INSPECTION_AUTH_TOKEN"]
            targets = inventory(token, full=full)
            relay = RelayServer(8768, RelayPolicy(targets, token, 8767))
            thread = threading.Thread(target=relay.serve_forever, daemon=True)
            thread.start()
            while True:
                remaining = gate.PRODUCTION_BASELINE - gate.memory_sample()["effective_working_set_bytes"]
                if remaining <= 0:
                    break
                padding.append(bytearray(min(16 * gate.MIB, remaining)))
            summary["before_capture"] = gate.memory_sample()
            summary["padding_bytes"] = sum(map(len, padding))
            summary["relay_targets"] = len(targets)
            full_map = json.loads(relay.policy.read("GET", "/api/inspect/site-map")[2])
            for page in gate.baseline_routes(full_map):
                status, _, _ = relay.policy.read("GET", page["route"])
                if status != 200:
                    raise AssertionError("Prior fixture route warmup failed")
            summary["after_prior_route_warmup"] = gate.memory_sample()
            (output / "pre-capture.json").write_text(json.dumps(summary))
            gate.enforce_memory(summary["after_prior_route_warmup"])
            summary["market_before"] = json.loads(lifecycle._request("/api/market/health")[1])["cache"]
            # Persist only bounded counters, never the full health payload.
            keys = ("build_count", "attempted_constructions", "artifact_loads", "market_generation")
            summary["market_before"] = {key: summary["market_before"].get(key) for key in keys}
            (CONTROL / "server-ready.json").write_text('{"ready":true}')
            deadline = time.monotonic() + (1800 if full else 480)
            with (output / "memory-curve.jsonl").open("w") as curve:
                while not (CONTROL / "capture-done.json").exists():
                    sample = gate.memory_sample()
                    sample["processes"] = gate.process_sample(process.pid, -1)
                    curve.write(json.dumps(sample) + "\n")
                    curve.flush()
                    peak = max(peak, sample["effective_working_set_bytes"])
                    gate.enforce_memory(sample)
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError("Server exited or focused proof deadline expired")
                    time.sleep(.1)
            after = json.loads(lifecycle._request("/api/market/health")[1])["cache"]
            summary["market_after"] = {key: after.get(key) for key in keys}
            if summary["market_after"] != summary["market_before"]:
                raise AssertionError("Capture changed fixture Market generation/work counters")
            if relay.counts["denied"] or relay.counts["failed"]:
                raise AssertionError("Focused relay requests failed")
            summary["passed"] = True
    except Exception as exc:
        summary["error"] = lifecycle._public_error(exc)
    finally:
        if relay is not None:
            relay.shutdown()
            relay.server_close()
            thread.join(2)
            summary["relay_counts"] = relay.counts
            summary["relay_thread_alive"] = thread.is_alive()
        if process is not None:
            gate.stop_group(process)
        padding.clear()
        summary.update(effective_peak_bytes=peak, minimum_headroom_bytes=lifecycle.MEMORY_MAX - peak,
                       after_cleanup=gate.memory_sample(), remaining_children=len(psutil.Process().children(recursive=True)))
        if summary["remaining_children"] or any(summary["after_cleanup"]["memory_events"].values()):
            summary["passed"] = False
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        raw_log = output / "server.private.log"
        if raw_log.exists():
            (output / "server.log").write_text(lifecycle._sanitize_server_log(raw_log.read_text(errors="replace"), limit=100))
            raw_log.unlink()
    return 0 if summary["passed"] else 1


def capture() -> int:
    if os.environ.get("DTOS_INSPECTION_AUTH_TOKEN"):
        raise AssertionError("Capture container must not receive the inspection token")
    full = os.environ.get("DTOS_DINS_SPLIT_SCOPE") == "full"
    summary = {"passed": False, "runs": [], "release_acceptance_eligible": full}
    try:
        if lifecycle._cgroup("memory.max") != lifecycle.MEMORY_MAX:
            raise AssertionError("Capture hard limit changed")
        for number in range(1, 2 if full else 4):
            folder = CONTROL / f"capture-{number}"
            folder.mkdir(exist_ok=True)
            environment = dict(os.environ, DTOS_DINS_OUTPUT=str(folder), DTOS_DINS_DIAGNOSTIC_PAGE="" if full else "teams")
            process = None
            peak = 0
            try:
                with (folder / "capture.private.log").open("w") as log, (folder / "memory-curve.jsonl").open("w") as curve:
                    process = subprocess.Popen([sys.executable, "-m", "tools.validation.dins_split_boundary", "worker"],
                                               env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    deadline = time.monotonic() + (1500 if full else 150)
                    while process.poll() is None:
                        sample = gate.memory_sample()
                        sample["processes"] = gate.process_sample(-1, process.pid)
                        curve.write(json.dumps(sample) + "\n")
                        curve.flush()
                        peak = max(peak, sample["effective_working_set_bytes"])
                        gate.enforce_memory(sample)
                        if time.monotonic() > deadline:
                            raise AssertionError("Focused isolated capture timed out")
                        time.sleep(.1)
                    if process.returncode:
                        raise AssertionError("Focused isolated capture failed")
                # Include stage samples, not just the periodic observer.
                for line in (folder / "page-boundaries.jsonl").read_text().splitlines():
                    peak = max(peak, json.loads(line)["effective_working_set_bytes"])
                headroom = lifecycle.MEMORY_MAX - peak
                if headroom < (500 if full else 550) * gate.MIB:
                    raise AssertionError("Focused isolation proof lacks comfortable550MiB margin")
                summary["runs"].append({"effective_peak_bytes": peak, "headroom_bytes": headroom,
                                        "capture": json.loads((folder / "capture-result.json").read_text())})
            finally:
                if process is not None:
                    gate.stop_group(process)
                raw_log = folder / "capture.private.log"
                if raw_log.exists():
                    (folder / "capture.log").write_text(lifecycle._sanitize_server_log(raw_log.read_text(errors="replace"), limit=100))
                    raw_log.unlink()
        summary["passed"] = True
    except Exception as exc:
        summary["error"] = lifecycle._public_error(exc)
    finally:
        summary["after_cleanup"] = gate.memory_sample()
        summary["remaining_children"] = len(psutil.Process().children(recursive=True))
        if summary["remaining_children"] or any(summary["after_cleanup"]["memory_events"].values()):
            summary["passed"] = False
        (CONTROL / "capture-summary.json").write_text(json.dumps(summary, indent=2))
        (CONTROL / "capture-done.json").write_text('{"done":true}')
    return 0 if summary["passed"] else 1


def main() -> int:
    if sys.platform != "linux" or os.environ.get("RENDER") or os.environ.get("DTOS_PRODUCTION_SHAPED_FIXTURE") != "1":
        raise RuntimeError("Isolated fixture-only proof")
    role = sys.argv[1]
    if role == "worker":
        gate.PUBLIC_ORIGIN = ORIGIN
        return gate.capture_worker()
    return server() if role == "server" else capture() if role == "capture" else 1


if __name__ == "__main__":
    raise SystemExit(main())
