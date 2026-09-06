"""Full unchanged DINS workload under the measured production baseline."""
from __future__ import annotations

import json
import inspect
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import weakref
from urllib.parse import urlsplit
from contextlib import contextmanager

import psutil

from tools.validation import linux_market_cgroup_gate as lifecycle

MIB = 1024**2
RESERVE = 500 * MIB
# Retained production working set immediately before the bounded browser probe.
PRODUCTION_BASELINE = 1_241_243_648
PUBLIC_ORIGIN = "http://dtos.fixture:8767"
OUTPUT = Path(os.environ.get("DTOS_DINS_OUTPUT", "/output"))


def capture_object_counts() -> dict:
    """Lengths only: never copy, stringify, or retain capture payloads."""
    result = {}
    frame = inspect.currentframe()
    try:
        while frame is not None:
            if frame.f_code.co_name in {"_capture_page", "full_page_screenshot"}:
                for key in ("original_content", "encoded", "chunks", "dom", "accessibility"):
                    value = frame.f_locals.get(key)
                    if isinstance(value, (bytes, str, list, tuple, dict)):
                        result[frame.f_code.co_name + "." + key] = {
                            "length": len(value), "shallow_bytes": sys.getsizeof(value)}
            frame = frame.f_back
    finally:
        del frame
    return result


def baseline_routes(inventory: dict) -> list[dict]:
    result = []
    for spec in inventory["pages"]:
        if spec["page_id"] == "teams":
            return result
        if spec.get("excluded"):
            continue
        if not spec["route"].startswith("/") or spec["route"].startswith("//"):
            raise ValueError("Baseline route must remain on fixture origin")
        result.append(spec)
    raise ValueError("Teams boundary absent from fixture inventory")


def startup_settled(tasks: dict) -> bool:
    # Historical resolution publishes another FOIS generation after cold Market.
    return all(tasks.get(name) == "complete" for name in (
        "fois_generation", "historical_market_resolution", "live_visual_capture",
    ))


def production_server_command(command: list[str]) -> list[str]:
    """Use the actual production route inventory, not diagnostic control routes."""
    return ["dtos_app:app" if item == "tools.validation.market_profile_app:app" else item for item in command]


def production_server(command, **kwargs):
    # A nonempty "0" enables this existing opt-in. DINS is the sole capture
    # flight in this isolated gate, as it is after production Current Visual.
    environment = kwargs["env"].copy()
    environment.pop("DTOS_LIVE_VISUAL_CAPTURE", None)
    kwargs["env"] = environment
    command = production_server_command(command)
    return subprocess.Popen(command, **kwargs)


def memory_sample() -> dict:
    stats = lifecycle._cgroup_values("memory.stat")
    if not {"inactive_file", "anon", "file"} <= stats.keys():
        raise RuntimeError("Required cgroup accounting fields unavailable")
    return {"timestamp": time.time(), **lifecycle._memory_state()}


def enforce_memory(sample: dict) -> None:
    if lifecycle.MEMORY_MAX - sample["effective_working_set_bytes"] < RESERVE:
        raise AssertionError("DINS effective memory reserve fell below 500 MiB")
    if any(sample["memory_events"].values()):
        raise AssertionError("DINS recorded OOM or cgroup kill")


def require_full_inventory(inventory: dict) -> None:
    """Reject missing fixture surfaces before spending a full capture flight."""
    pages = inventory["pages"]
    if any(str(row.get("route", "")).startswith("/__validation__/") for row in pages):
        raise AssertionError("Diagnostic control routes contaminated the DINS workload")
    if sum(not row.get("excluded") for row in pages) < 61:
        raise AssertionError("Production-shaped DINS inventory has fewer than 61 pages")


def persist_contract_evidence(manifest: dict, output: Path) -> None:
    """Persist bounded fixture-only failure facts before any acceptance assertion."""
    failures = manifest.get("interaction_failures", [])
    rows = []
    for item in failures[:100]:
        target = urlsplit(str(item.get("target", "")))
        start = urlsplit(str(item.get("starting_page", "")))
        rows.append({"starting_path": start.path[:200], "target_host": target.hostname,
                     "target_path": target.path[:200], "http_status": item.get("http_status")})
    result = {"pages_expected": manifest.get("total_pages_expected"),
              "pages_completed": manifest.get("total_pages_completed"),
              "artifacts": manifest.get("total_visual_artifacts"),
              "status": manifest.get("status"), "validation_outcome": manifest.get("validation_outcome"),
              "failure_counts": {key: len(manifest.get(key, [])) for key in (
                  "failures", "interaction_failures", "console_errors", "failed_network_requests",
                  "product_contract_failures", "accessibility_regressions")},
              "interaction_failures": rows, "interaction_details_truncated": len(failures) > 100}
    network = {}
    for item in manifest.get("failed_network_requests", []):
        host = urlsplit(str(item.get("url", ""))).hostname
        # Only Playwright's fixed error class, never arbitrary error text/URLs.
        error = str(item.get("error", ""))
        classification = error if error.startswith("net::") and error.replace("net::", "").replace("_", "").isalnum() else "other"
        key = (host, classification)
        network[key] = network.get(key, 0) + 1
    result["network_failure_groups"] = [{"host": host, "error": error, "count": count}
                                        for (host, error), count in sorted(network.items(), key=str)][:100]
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


def process_sample(server_pid: int, capture_pid: int) -> list[dict]:
    rows = []
    for p in psutil.Process().children(recursive=True):
        try:
            command = p.cmdline()
            role = next((x.split("=", 1)[1] for x in command if x.startswith("--type=")), p.name())
            if p.pid == server_pid:
                role = "dtos_server"
            elif p.pid == capture_pid:
                role = "dins_capture"
            rows.append({"pid": p.pid, "role": role, "rss_bytes": p.memory_info().rss})
        except psutil.NoSuchProcess:
            continue
    return rows


def stop_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(10)


class TrackedPage(dict):
    """Weak-referenceable view without copying the page's nested payloads."""


def capture_worker() -> int:
    from tools.inspection import capture as dins
    from tools.inspection.package import package_bundle
    from playwright.sync_api import APIRequestContext, Browser, Page
    from tools.validation.dins_fixture_images import install

    refs: list[weakref.ReferenceType] = []
    original_capture = dins._capture_page
    original_write = dins._write_artifact_json
    original_playwright = dins.sync_playwright
    original_release = dins._release_completed_capture_resources
    boundaries = OUTPUT / "page-boundaries.jsonl"
    active = {}
    diagnostic = bool(os.environ.get("DTOS_DINS_DIAGNOSTIC_PAGE"))
    sessions = weakref.WeakKeyDictionary()
    detail = {}
    image_totals = {"responses": 0, "encoded_bytes": 0, "decoded_pixels": 0}
    original_new_page = Browser.new_page

    def new_page(browser, *args, **kwargs):
        page = original_new_page(browser, *args, **kwargs)
        install(page, fixture_origin=PUBLIC_ORIGIN, evidence=image_totals,
                directory=lifecycle.FIXTURE / "dins-images")
        if diagnostic:
            session = page.context.new_cdp_session(page)
            session.send("Performance.enable")
            sessions[page] = session
        return page

    Browser.new_page = new_page

    def boundary(phase, page_id=None, viewport=None):
        row = {"phase": phase, "page_id": page_id, "viewport": viewport,
               "completed_payloads_alive": sum(ref() is not None for ref in refs),
               "capture_child_processes": len(psutil.Process().children(recursive=True)),
               "capture_rss_bytes": psutil.Process().memory_info().rss,
               **memory_sample()}
        if diagnostic:
            row["operation"] = dict(detail)
            row["live_objects"] = capture_object_counts()
            row["child_processes"] = process_sample(-1, os.getpid())
            server_pid = os.environ.get("DTOS_DINS_SERVER_PID")
            if server_pid:
                row["server_rss_bytes"] = psutil.Process(int(server_pid)).memory_info().rss
        with boundaries.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        temporary = OUTPUT / "active-page.tmp"
        temporary.write_text(json.dumps(row), encoding="utf-8")
        temporary.replace(OUTPUT / "active-page.json")
        enforce_memory(row)
        if phase in {"before_capture", "capture_complete"} and row["completed_payloads_alive"]:
            raise AssertionError("Completed full page payload remained reachable")
        if phase == "viewport_reclaimed" and row["capture_child_processes"]:
            raise AssertionError("Completed viewport retained browser/driver processes")

    @contextmanager
    def tracked_playwright():
        try:
            with original_playwright() as playwright:
                yield playwright
        finally:
            boundary("viewport_reclaimed", **active)

    def release():
        original_release()
        boundary("viewport_heap_reclaimed", **active)

    def capture_page(browser, store, base, spec, viewport, league):
        active.update(page_id=spec["page_id"], viewport=viewport.name)
        boundary("before_capture", spec["page_id"], viewport.name)
        return original_capture(browser, store, base, spec, viewport, league)

    def trace_method(owner, name):
        original = getattr(owner, name)

        def traced(self, *args, **kwargs):
            if diagnostic:
                label = name
                if name == "evaluate" and args:
                    label = "dom_extraction" if args[0] == dins.DOM_SCRIPT else "accessibility" if args[0] == dins.A11Y_SCRIPT else "geometry_evaluation"
                detail.clear()
                detail.update(label=label)
                session = sessions.get(self)
                if session is not None and name != "close":
                    metrics = session.send("Performance.getMetrics")["metrics"]
                    detail["browser_metrics_before"] = {r["name"]: r["value"] for r in metrics if r["name"] in {"JSHeapUsedSize", "JSHeapTotalSize", "Nodes", "Documents"}}
            boundary("before_" + name, **active)
            result = original(self, *args, **kwargs)
            if diagnostic:
                if isinstance(result, (bytes, str, dict, list)):
                    detail["result_length"] = len(result)
                    detail["result_shallow_bytes"] = sys.getsizeof(result)
                if session is not None and name != "close":
                    metrics = session.send("Performance.getMetrics")["metrics"]
                    detail["browser_metrics_after"] = {r["name"]: r["value"] for r in metrics if r["name"] in {"JSHeapUsedSize", "JSHeapTotalSize", "Nodes", "Documents"}}
            boundary("after_" + name, **active)
            return result

        setattr(owner, name, traced)

    for method in ("goto", "screenshot", "evaluate", "content", "close"):
        trace_method(Page, method)
    trace_method(APIRequestContext, "get")

    def write(path, value, **kwargs):
        if diagnostic:
            detail.clear()
            detail["label"] = "artifact_serialization"
            boundary("before_artifact_write", **active)
        result = original_write(path, value, **kwargs)
        if diagnostic:
            boundary("after_artifact_write", **active)
        if path.name in {"desktop.json", "tablet.json", "mobile.json"}:
            result = TrackedPage(result)
            refs.append(weakref.ref(result))
            boundary("page_persisted", path.parent.name, path.stem)
        return result

    dins._capture_page = capture_page
    dins._write_artifact_json = write
    dins.sync_playwright = tracked_playwright
    dins._release_completed_capture_resources = release
    boundary("capture_start")
    inventory = dins._json(PUBLIC_ORIGIN + "/api/inspect/site-map")
    require_full_inventory(inventory)
    diagnostic = os.environ.get("DTOS_DINS_DIAGNOSTIC_PAGE")
    if diagnostic:
        if diagnostic not in {"teams", "teams-7", "teams-8"}:
            raise RuntimeError("Unsupported bounded diagnostic target")
        if os.environ.get("DTOS_DINS_BASELINE") == "server-warm":
            # Replay only read-only canonical routes preceding Teams, once.
            # No browser, screenshots, fabricated padding, or cache clearing.
            from urllib.request import Request, urlopen
            boundary("server_warm_start")
            for spec in baseline_routes(inventory):
                target = PUBLIC_ORIGIN + "/" + spec["route"].lstrip("/")
                with urlopen(Request(target, headers=dins._inspection_headers()), timeout=60) as response:
                    if response.status != 200:
                        raise AssertionError("Baseline canonical read failed")
                    while response.read(65536):
                        pass
                boundary("server_warm_route", spec["page_id"], "none")
            boundary("server_warm_complete")
        original_json = dins._json

        def diagnostic_json(url):
            result = original_json(url)
            if url.endswith("/api/inspect/site-map"):
                result = {**result, "pages": [row for row in result["pages"] if row["page_id"] == diagnostic]}
            return result

        dins._json = diagnostic_json
        dins.VIEWPORTS = tuple(view for view in dins.VIEWPORTS if view.name == "mobile")
    manifest = dins.capture(PUBLIC_ORIGIN, Path("/fixture/dins-capture"), public_url=PUBLIC_ORIGIN)
    persist_contract_evidence(manifest, OUTPUT / "contract-evidence.json")
    boundary("capture_complete")
    expected = manifest["total_pages_expected"]
    if expected < (1 if diagnostic else 61) or manifest["total_pages_completed"] != expected:
        raise AssertionError("Full authoritative page coverage was not captured")
    if manifest["status"] != "complete" or manifest["validation_outcome"] != "pass":
        raise AssertionError("DINS capture/product/accessibility gate failed")
    for key in ("failures", "interaction_failures", "console_errors", "failed_network_requests", "product_contract_failures", "accessibility_regressions"):
        if manifest[key]:
            raise AssertionError(f"DINS {key} was nonempty")
    root = dins.InspectionArtifactStore(Path("/fixture/dins-capture"), PUBLIC_ORIGIN).current_root
    page_files = list((root / "pages").glob("*/*.json"))
    png_files = list((root / "pages").glob("*/*.png"))
    viewports = len(dins.VIEWPORTS)
    if len(page_files) != expected * viewports * 3 or len(png_files) != expected * viewports * 2:
        raise AssertionError("Viewport artifact coverage was incomplete")
    # The existing packaging validator remains unchanged and fail closed.
    if not diagnostic:
        boundary("packaging")
        package_bundle(root, Path("/fixture/dins-package"))
        boundary("packaging_complete")
    (OUTPUT / "capture-result.json").write_text(json.dumps({
        "pages": expected, "viewports": viewports, "page_json": len(page_files),
        "png": len(png_files), "artifacts": manifest["total_visual_artifacts"],
        "sanitization": "not_run_diagnostic" if diagnostic else "pass",
        "release_acceptance_eligible": not bool(diagnostic),
        "completed_payloads_alive": sum(ref() is not None for ref in refs),
        "fixture_images": image_totals,
    }), encoding="utf-8")
    return 0


def main() -> int:
    if sys.platform != "linux" or os.environ.get("RENDER"):
        raise RuntimeError("This gate requires isolated Linux, never production")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if "--worker" in sys.argv:
        return capture_worker()
    summary = {"passed": False, "completed": False, "reserve_bytes": RESERVE,
               "production_baseline_bytes": PRODUCTION_BASELINE}
    server = worker = None
    padding = []
    peak = 0
    log_path = OUTPUT / "server.private.log"
    worker_log = OUTPUT / "capture.private.log"
    try:
        assert lifecycle._cgroup("memory.max") == lifecycle.MEMORY_MAX
        lifecycle._retire_validation_archive(warm=False)
        with log_path.open("w+") as log:
            server = lifecycle._start_server(log, popen_factory=production_server)
            summary["fixture"] = lifecycle._configured_fixture_contract()
            lifecycle._cold_build()
            # Production acceptance begins after startup/FOIS synchronization settles.
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                ready = json.loads(lifecycle._request("/health/ready")[1])
                tasks = (ready.get("runtime") or {}).get("background_tasks") or {}
                if startup_settled(tasks):
                    summary["settled_background_tasks"] = tasks
                    break
                time.sleep(1)
            else:
                raise AssertionError("FOIS startup did not settle before full DINS")
            from tools.validation.dins_fixture_images import prepare

            image_format = os.environ.get("DTOS_DINS_IMAGE_FORMAT", "png")
            if image_format != "png" and not os.environ.get("DTOS_DINS_DIAGNOSTIC_PAGE"):
                raise RuntimeError("Legacy image format is diagnostic-only")
            prepare(lifecycle.FIXTURE / "dins-images", format_name=image_format)
            summary["fixture_image_format"] = image_format
            while True:
                sample = memory_sample()
                remaining = PRODUCTION_BASELINE - sample["effective_working_set_bytes"]
                if remaining <= 0:
                    break
                padding.append(bytearray(min(16 * MIB, remaining)))
            summary["before_capture"] = memory_sample()
            summary["before_capture_processes"] = process_sample(server.pid, -1)
            enforce_memory(summary["before_capture"])
            if os.environ.get("DTOS_DINS_DIAGNOSTIC_PAGE"):
                # Reproduce the late-capture idle-worker/cache state without
                # recapturing the preceding146 viewports. Keep the same padding.
                for _ in range(65):
                    lifecycle._request("/health/ready")
                    time.sleep(1)
                # These are still within TTL at the observed Team7 boundary.
                for roster in range(2, 9):
                    lifecycle._request(f"/teams/{roster}")
                summary["diagnostic_pre_capture"] = memory_sample()
                summary["diagnostic_processes"] = process_sample(server.pid, -1)
                summary["release_acceptance_eligible"] = False
            with worker_log.open("w+") as capture_log, (OUTPUT / "memory-curve.jsonl").open("w") as curve:
                worker_environment = lifecycle._fixture_inspection_environment(os.environ.copy())
                worker_environment["DTOS_DINS_SERVER_PID"] = str(server.pid)
                worker = subprocess.Popen([sys.executable, "-m", __name__.replace("__main__", "tools.validation.linux_dins_memory_gate"), "--worker"],
                    stdout=capture_log, stderr=subprocess.STDOUT, start_new_session=True,
                    env=worker_environment)
                deadline = time.monotonic() + 1500
                while worker.poll() is None:
                    sample = memory_sample()
                    sample["processes"] = process_sample(server.pid, worker.pid)
                    stage = OUTPUT / "active-page.json"
                    if stage.exists():
                        sample["page"] = json.loads(stage.read_text())
                    curve.write(json.dumps(sample) + "\n")
                    curve.flush()  # Preserve the failing sample before asserting.
                    peak = max(peak, sample["effective_working_set_bytes"])
                    enforce_memory(sample)
                    if server.poll() is not None:
                        raise AssertionError("DTOS process exited during DINS")
                    if time.monotonic() >= deadline:
                        raise AssertionError("Full DINS bounded deadline exceeded")
                    time.sleep(.1)
                if worker.returncode != 0:
                    raise AssertionError(f"DINS worker exited {worker.returncode}")
            summary["capture"] = json.loads((OUTPUT / "capture-result.json").read_text())
            summary["passed"] = True
    except Exception as exc:
        summary["error"] = lifecycle._public_error(exc)
    finally:
        for process in (worker, server):
            if process is not None:
                stop_group(process)
        padding.clear()
        for source, target in ((log_path, OUTPUT / "server.log"), (worker_log, OUTPUT / "capture.log")):
            if source.exists():
                target.write_text(lifecycle._sanitize_server_log(source.read_text(errors="replace"), limit=1000))
                source.unlink()
        summary.update(completed=True, effective_peak_bytes=peak,
                       minimum_headroom_bytes=lifecycle.MEMORY_MAX - peak,
                       after_cleanup=memory_sample())
        remaining = psutil.Process().children(recursive=True)
        summary["remaining_children"] = len(remaining)
        if remaining or any(summary["after_cleanup"]["memory_events"].values()):
            summary["passed"] = False
        (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
