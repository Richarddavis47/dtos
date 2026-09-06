"""Full unchanged DINS workload under the measured production baseline."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import weakref

import psutil

from tools.validation import linux_market_cgroup_gate as lifecycle

MIB = 1024**2
RESERVE = 500 * MIB
# Retained production working set immediately before the bounded browser probe.
PRODUCTION_BASELINE = 1_241_243_648
PUBLIC_ORIGIN = "http://dtos.fixture:8767"
OUTPUT = Path(os.environ.get("DTOS_DINS_OUTPUT", "/output"))


def production_server_command(command: list[str]) -> list[str]:
    """Use the actual production route inventory, not diagnostic control routes."""
    return ["dtos_app:app" if item == "tools.validation.market_profile_app:app" else item for item in command]


def production_server(command, **kwargs):
    return subprocess.Popen(production_server_command(command), **kwargs)


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

    refs: list[weakref.ReferenceType] = []
    original_capture = dins._capture_page
    original_write = dins._write_artifact_json
    boundaries = OUTPUT / "page-boundaries.jsonl"

    def boundary(phase, page_id=None, viewport=None):
        row = {"phase": phase, "page_id": page_id, "viewport": viewport,
               "completed_payloads_alive": sum(ref() is not None for ref in refs),
               "capture_rss_bytes": psutil.Process().memory_info().rss,
               **memory_sample()}
        with boundaries.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        temporary = OUTPUT / "active-page.tmp"
        temporary.write_text(json.dumps(row), encoding="utf-8")
        temporary.replace(OUTPUT / "active-page.json")
        enforce_memory(row)
        if phase in {"before_capture", "capture_complete"} and row["completed_payloads_alive"]:
            raise AssertionError("Completed full page payload remained reachable")

    def capture_page(browser, store, base, spec, viewport, league):
        boundary("before_capture", spec["page_id"], viewport.name)
        return original_capture(browser, store, base, spec, viewport, league)

    def write(path, value, **kwargs):
        result = original_write(path, value, **kwargs)
        if path.name in {"desktop.json", "tablet.json", "mobile.json"}:
            result = TrackedPage(result)
            refs.append(weakref.ref(result))
            boundary("page_persisted", path.parent.name, path.stem)
        return result

    dins._capture_page = capture_page
    dins._write_artifact_json = write
    boundary("capture_start")
    inventory = dins._json(PUBLIC_ORIGIN + "/api/inspect/site-map")
    if any(str(row.get("route", "")).startswith("/__validation__/") for row in inventory["pages"]):
        raise AssertionError("Diagnostic control routes contaminated the DINS workload")
    manifest = dins.capture(PUBLIC_ORIGIN, Path("/fixture/dins-capture"), public_url=PUBLIC_ORIGIN)
    boundary("capture_complete")
    expected = manifest["total_pages_expected"]
    if expected < 61 or manifest["total_pages_completed"] != expected:
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
    boundary("packaging")
    package_bundle(root, Path("/fixture/dins-package"))
    boundary("packaging_complete")
    (OUTPUT / "capture-result.json").write_text(json.dumps({
        "pages": expected, "viewports": viewports, "page_json": len(page_files),
        "png": len(png_files), "artifacts": manifest["total_visual_artifacts"],
        "sanitization": "pass", "completed_payloads_alive": sum(ref() is not None for ref in refs),
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
                if tasks.get("fois_generation") == "complete":
                    summary["settled_background_tasks"] = tasks
                    break
                time.sleep(1)
            else:
                raise AssertionError("FOIS startup did not settle before full DINS")
            while True:
                sample = memory_sample()
                remaining = PRODUCTION_BASELINE - sample["effective_working_set_bytes"]
                if remaining <= 0:
                    break
                padding.append(bytearray(min(16 * MIB, remaining)))
            summary["before_capture"] = memory_sample()
            enforce_memory(summary["before_capture"])
            with worker_log.open("w+") as capture_log, (OUTPUT / "memory-curve.jsonl").open("w") as curve:
                worker = subprocess.Popen([sys.executable, "-m", __name__.replace("__main__", "tools.validation.linux_dins_memory_gate"), "--worker"],
                    stdout=capture_log, stderr=subprocess.STDOUT, start_new_session=True,
                    env=lifecycle._fixture_inspection_environment(os.environ.copy()))
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
        if remaining:
            summary["passed"] = False
        (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
