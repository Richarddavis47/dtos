"""Bounded parent-side contract for isolated Live Visual captures."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import psutil

from src.core.inspection.live_visual import CaptureRequest

CAPTURE_PROCESS_TIMEOUT_SECONDS = 120.0
CAPTURE_PROCESS_POLL_SECONDS = 0.05
CAPTURE_TREE_NICE = 19
CAPTURE_CPU_RUN_SECONDS = 0.005
CAPTURE_CPU_PAUSE_SECONDS = 0.045


def _lower_tree_priority(pid: int) -> int | None:
    """Keep the complete capture/browser tree below request-serving priority."""
    try:
        process = psutil.Process(pid)
        targets = [process, *process.children(recursive=True)]
    except psutil.Error:
        return None
    observed: list[int] = []
    for target in targets:
        try:
            target.nice(CAPTURE_TREE_NICE)
            observed.append(int(target.nice()))
        except (psutil.Error, OSError, ValueError):
            continue
    return min(observed) if observed else None


def _partition_request_cpu() -> tuple[list[int], list[int]] | None:
    """Confine capture to one Linux CPU while retaining request capacity."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        process = psutil.Process()
        allowed = process.cpu_affinity()
        if len(allowed) < 2:
            return None
        process.cpu_affinity(allowed[:-1])
        return allowed, [allowed[-1]]
    except (psutil.Error, AttributeError, OSError, ValueError):
        return None


def _restore_request_cpu(affinity: list[int] | None) -> None:
    if affinity is None:
        return
    try:
        psutil.Process().cpu_affinity(affinity)
    except (psutil.Error, AttributeError, OSError, ValueError):
        pass


def _isolate_capture_tree_cpu(
    pid: int, capture_affinity: list[int] | None = None,
    *, available_count: int | None = None,
) -> tuple[int, int] | None:
    """Confine capture work to one Linux CPU so request serving retains capacity."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        process = psutil.Process(pid)
        allowed = capture_affinity or process.cpu_affinity()
        if not allowed:
            return None
        selected = list(capture_affinity or [allowed[-1]])
        targets = [process, *process.children(recursive=True)]
    except (psutil.Error, AttributeError, OSError):
        return None
    for target in targets:
        try:
            target.cpu_affinity(selected)
        except (psutil.Error, AttributeError, OSError, ValueError):
            continue
    return int(available_count or len(allowed)), len(selected)


def _tree_rss(pid: int) -> tuple[int, int, int]:
    try:
        process = psutil.Process(pid)
        children = process.children(recursive=True)
        active = [child for child in children if child.is_running()]
        return int(process.memory_info().rss), sum(
            int(child.memory_info().rss) for child in active
        ), len(active)
    except (psutil.Error, OSError):
        return 0, 0, 0


def _yield_capture_cpu(process: subprocess.Popen[bytes]) -> bool:
    """Bound capture CPU bursts so request serving receives scheduling windows."""
    if not sys.platform.startswith("linux"):
        time.sleep(CAPTURE_PROCESS_POLL_SECONDS)
        return False
    time.sleep(CAPTURE_CPU_RUN_SECONDS)
    if process.poll() is not None:
        return True
    suspended: list[psutil.Process] = []
    try:
        root = psutil.Process(process.pid)
        targets = [*root.children(recursive=True), root]
        for target in targets:
            try:
                target.suspend()
                suspended.append(target)
            except psutil.Error:
                continue
        time.sleep(CAPTURE_CPU_PAUSE_SECONDS)
    except psutil.Error:
        pass
    finally:
        for target in reversed(suspended):
            try:
                target.resume()
            except psutil.Error:
                pass
    return bool(suspended)


def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate browser descendants before the orchestration process."""
    try:
        root = psutil.Process(process.pid)
        children = root.children(recursive=True)
    except psutil.Error:
        children = []
    for child in reversed(children):
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        process.kill()
    except OSError:
        pass
    process.wait(timeout=5)


def capture_page_isolated(
    capture_origin: str, request: CaptureRequest, output: Path,
    *, timeout: float = CAPTURE_PROCESS_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run one browser flight outside the request-serving interpreter."""
    token = f"{request.surface_id}-{request.viewport}"
    input_path = output.with_name(f".{token}.capture-input.json")
    result_path = output.with_name(f".{token}.capture-result.json")
    input_path.write_text(json.dumps({
        "capture_origin": capture_origin, "output_path": str(output),
        "request": asdict(request),
    }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    worker_peak = 0
    browser_peak = 0
    browser_process_peak = 0
    tree_nice_min: int | None = None
    cpu_isolation: tuple[int, int] | None = None
    cpu_throttle_cycles = 0
    cpu_partition = _partition_request_cpu()
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "src.core.inspection.live_capture_worker",
             "--input", str(input_path), "--result", str(result_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        tree_nice_min = _lower_tree_priority(process.pid)
        cpu_isolation = _isolate_capture_tree_cpu(
            process.pid,
            cpu_partition[1] if cpu_partition else None,
            available_count=len(cpu_partition[0]) if cpu_partition else None,
        )
        while process.poll() is None:
            if time.monotonic() - started >= timeout:
                _terminate_tree(process)
                raise TimeoutError("isolated visual capture exceeded its bounded timeout")
            worker_rss, browser_rss, browser_processes = _tree_rss(process.pid)
            observed_nice = _lower_tree_priority(process.pid)
            observed_isolation = _isolate_capture_tree_cpu(
                process.pid,
                cpu_partition[1] if cpu_partition else None,
                available_count=len(cpu_partition[0]) if cpu_partition else None,
            )
            if observed_isolation is not None:
                cpu_isolation = observed_isolation
            if observed_nice is not None:
                tree_nice_min = (
                    observed_nice if tree_nice_min is None
                    else min(tree_nice_min, observed_nice)
                )
            worker_peak = max(worker_peak, worker_rss)
            browser_peak = max(browser_peak, browser_rss)
            browser_process_peak = max(browser_process_peak, browser_processes)
            if _yield_capture_cpu(process):
                cpu_throttle_cycles += 1
        if process.returncode != 0 or not result_path.is_file():
            raise RuntimeError("isolated visual capture exited unsuccessfully")
        value = json.loads(result_path.read_text(encoding="utf-8"))
        if value.get("status") != "complete" or not isinstance(value.get("presentation"), dict):
            raise RuntimeError("isolated visual capture returned malformed output")
        return {**value["presentation"], "capture_process": {
            "worker_pid": process.pid,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "worker_rss_peak_bytes": worker_peak,
            "browser_rss_peak_bytes": browser_peak,
            "browser_process_peak": browser_process_peak,
            "process_nice": value.get("process_nice"),
            "capture_tree_nice_min": tree_nice_min,
            "available_cpu_count": cpu_isolation[0] if cpu_isolation else None,
            "capture_cpu_count": cpu_isolation[1] if cpu_isolation else None,
            "capture_cpu_run_ms": CAPTURE_CPU_RUN_SECONDS * 1000,
            "capture_cpu_pause_ms": CAPTURE_CPU_PAUSE_SECONDS * 1000,
            "capture_cpu_throttle_cycles": cpu_throttle_cycles,
            "exit_status": process.returncode, "cleanup_complete": True,
        }}
    finally:
        if process is not None and process.poll() is None:
            _terminate_tree(process)
        _restore_request_cpu(cpu_partition[0] if cpu_partition else None)
        input_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)
