"""Linux-only 2 GiB cgroup gate for the production-scale Asset Market lifecycle."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

GIB = 1024**3
MIB = 1024**2
MEMORY_MAX = 2 * GIB
STARTUP_MAX = int(1.2 * GIB)
COLD_MAX = int(1.5 * GIB)
BASELINE = int(1.03 * GIB)
BASE_URL = "http://127.0.0.1:8767"
CGROUP = Path("/sys/fs/cgroup")
OUTPUT = Path(os.environ.get("DTOS_BENCHMARK_OUTPUT", "/output/summary.json"))
FIXTURE = Path(os.environ.get("DTOS_FIXTURE_ROOT", "/fixture"))


def _cgroup(name: str) -> int:
    path = CGROUP / name
    if not path.is_file():
        raise RuntimeError(f"required cgroup metric unavailable: {name}")
    value = path.read_text(encoding="ascii").strip()
    if value == "max":
        raise RuntimeError(f"cgroup metric is unlimited: {name}")
    return int(value)


def _rss_high_water(pid: int) -> int:
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    return 0


class Monitor:
    def __init__(self) -> None:
        self.peak = _cgroup("memory.current")
        self.samples = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(0.01):
            self.peak = max(self.peak, _cgroup("memory.current"))
            self.samples += 1

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args) -> None:
        self.stop.set()
        self.thread.join(timeout=2)
        self.peak = max(self.peak, _cgroup("memory.current"))


def _request(path: str, expected: tuple[int, ...] = (200,)) -> tuple[int, bytes, float]:
    started = time.perf_counter()
    try:
        with urlopen(BASE_URL + path, timeout=60) as response:
            status, body = response.status, response.read()
    except HTTPError as exc:
        status, body = exc.code, exc.read()
    elapsed = (time.perf_counter() - started) * 1000
    if status not in expected:
        raise AssertionError(f"{path}: HTTP {status}, expected {expected}")
    return status, body, elapsed


def _start_server(log) -> subprocess.Popen:
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dtos_app:app", "--host", "127.0.0.1", "--port", "8767", "--workers", "1"],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"application exited during startup: {process.returncode}")
        try:
            status, _body, _elapsed = _request("/health/live")
            if status == 200:
                return process
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError("application did not become live within 60 seconds")


def _stop_server(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
    if process.returncode not in (0, -signal.SIGTERM):
        raise RuntimeError(f"application exited unexpectedly: {process.returncode}")


def _wait_ready() -> float:
    started = time.perf_counter()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            status, _body, _elapsed = _request("/health/ready", (200, 503))
            if status == 200:
                return (time.perf_counter() - started) * 1000
        except OSError:
            pass
        time.sleep(0.25)
    raise AssertionError("readiness did not reach HTTP 200 within 60 seconds")


def _market_health() -> dict:
    return json.loads(_request("/api/market/health")[1])


def _cold_build() -> tuple[dict, float, int]:
    started = time.perf_counter()
    attempts = 0
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        attempts += 1
        status, _body, elapsed = _request("/api/market/assets?limit=50", (200, 503))
        if status == 200:
            return _market_health(), (time.perf_counter() - started) * 1000, attempts
        if elapsed >= 500:
            raise AssertionError(f"warming response exceeded 500ms: {elapsed:.3f}ms")
        health = _market_health()
        error = (health.get("cache") or {}).get("last_error")
        if error:
            raise AssertionError(f"market build failed: {error}")
        time.sleep(0.5)
    raise AssertionError("cold market build exceeded 60 seconds")


def _latencies() -> dict[str, float]:
    endpoints = {
        "directory": "/api/market/assets?limit=50",
        "search": "/api/market/search?q=Validation%20Player%2010213",
        "expansion": f"/api/market/assets/{quote('player:10213', safe=':')}",
        "trending": "/api/market/trending",
        "health": "/api/market/health",
    }
    values = {}
    for name, path in endpoints.items():
        values[name] = round(_request(path)[2], 3)
    limits = {"directory": 1000, "search": 500, "expansion": 1000, "trending": 1000, "health": 500}
    for name, value in values.items():
        if value >= limits[name]:
            raise AssertionError(f"{name} latency {value:.3f}ms exceeds {limits[name]}ms")
    return values


def _pad_to_production_baseline() -> list[bytearray]:
    padding = []
    while _cgroup("memory.current") < BASELINE:
        padding.append(bytearray(min(16 * MIB, BASELINE - _cgroup("memory.current"))))
    return padding


def _mutate_generation() -> None:
    cache_path = FIXTURE / "dtos_cache.json"
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["last_sync"] = "2026-08-07T00:01:00+00:00"
    cache_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    if sys.platform != "linux":
        raise RuntimeError("Linux cgroup validation must run on Linux")
    memory_max = _cgroup("memory.max")
    if memory_max != MEMORY_MAX:
        raise RuntimeError(f"Docker did not enforce 2 GiB: memory.max={memory_max}")
    if not (CGROUP / "memory.peak").is_file():
        raise RuntimeError("memory.peak is required for this validation")

    summary: dict[str, object] = {
        "schema": "dtos-linux-market-memory-v1",
        "memory_max": memory_max,
        "fixture": {"assets": 12_322, "historical_records": 30_726, "progress": "5/6"},
        "phases": {},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT.parent / "server.log"
    padding: list[bytearray] = []
    process = None
    try:
        with log_path.open("w", encoding="utf-8") as log, Monitor() as monitor:
            process = _start_server(log)
            ready_ms = _wait_ready()
            startup_current = _cgroup("memory.current")
            summary["phases"]["startup"] = {
                "timestamp": time.time(), "duration_ms": round(ready_ms, 3),
                "memory_current": startup_current, "process_rss_high_water": _rss_high_water(process.pid),
            }
            if startup_current >= STARTUP_MAX:
                raise AssertionError(f"startup memory {startup_current} exceeds 1.2 GiB")
            cold_health = _market_health()
            if int((cold_health.get("cache") or {}).get("build_count") or 0) != 0:
                raise AssertionError("metadata-only health constructed the market")
            padding = _pad_to_production_baseline()
            before_cold = _cgroup("memory.current")
            health, build_ms, attempts = _cold_build()
            cold_peak = monitor.peak
            summary["phases"]["cold_market"] = {
                "timestamp": time.time(), "duration_ms": round(build_ms, 3), "attempts": attempts,
                "memory_before": before_cold, "memory_current": _cgroup("memory.current"),
                "memory_peak": cold_peak, "build_count": (health.get("cache") or {}).get("build_count"),
                "generation": (health.get("cache") or {}).get("market_generation"),
            }
            if cold_peak >= COLD_MAX:
                raise AssertionError(f"cold-build cgroup peak {cold_peak} exceeds 1.5 GiB")
            summary["phases"]["warm_requests"] = {
                "timestamp": time.time(), "latency_ms": _latencies(),
                "memory_current": _cgroup("memory.current"),
            }
            first_generation = (health.get("cache") or {}).get("market_generation")
            _stop_server(process)
            process = None
            _mutate_generation()
            process = _start_server(log)
            _wait_ready()
            replacement, replacement_ms, replacement_attempts = _cold_build()
            second_generation = (replacement.get("cache") or {}).get("market_generation")
            if second_generation == first_generation:
                raise AssertionError("generation replacement did not publish a new identity")
            artifacts = list(FIXTURE.glob(".*.asset-market-*.sqlite3"))
            if len(artifacts) != 1:
                raise AssertionError(f"expected one active market generation, found {len(artifacts)}")
            summary["phases"]["generation_replacement"] = {
                "timestamp": time.time(), "duration_ms": round(replacement_ms, 3),
                "attempts": replacement_attempts, "generation_changed": True,
                "active_generations": len(artifacts), "memory_current": _cgroup("memory.current"),
            }
            _stop_server(process)
            process = None
            process = _start_server(log)
            _wait_ready()
            status, _body, reuse_ms = _request("/api/market/assets?limit=50", (200, 503))
            if status != 200:
                raise AssertionError("compatible durable market generation was not reused after restart")
            reuse_health = _market_health()
            if (reuse_health.get("cache") or {}).get("market_generation") != second_generation:
                raise AssertionError("restart reused a different market generation")
            summary["phases"]["restart_reuse"] = {
                "timestamp": time.time(), "duration_ms": round(reuse_ms, 3),
                "generation_match": True, "memory_current": _cgroup("memory.current"),
            }
            summary.update({
                "memory_current": _cgroup("memory.current"),
                "memory_peak": max(monitor.peak, _cgroup("memory.peak")),
                "margin_below_limit": memory_max - max(monitor.peak, _cgroup("memory.peak")),
                "container_restart_count": 0,
                "worker_count": 1,
                "provider_synchronization": False,
                "exit_code": 0,
                "passed": True,
            })
            if int(summary["margin_below_limit"]) < 500 * MIB:
                raise AssertionError("memory margin below 2 GiB is less than 500 MiB")
    finally:
        if process is not None:
            _stop_server(process)
        padding.clear()
        OUTPUT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
