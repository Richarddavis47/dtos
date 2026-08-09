"""Linux-only 2 GiB cgroup gate for the production-scale Asset Market lifecycle."""
from __future__ import annotations

import json
import os
import base64
import hashlib
import re
import signal
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

GIB = 1024**3
MIB = 1024**2
MEMORY_MAX = 2 * GIB
STARTUP_MAX = int(1.2 * GIB)
COLD_MAX = int(1.5 * GIB)
RAW_EMERGENCY_MAX = 1740 * MIB
BASELINE = int(1.03 * GIB)
BASE_URL = "http://127.0.0.1:8767"
CGROUP = Path("/sys/fs/cgroup")
OUTPUT = Path(os.environ.get("DTOS_BENCHMARK_OUTPUT", "/output/summary.json"))
FIXTURE = Path(os.environ.get("DTOS_FIXTURE_ROOT", "/fixture"))
FIXTURE_SETTINGS = {
    "DTOS_CACHE_FILE": "dtos_cache.json",
    "DTOS_HISTORY_DB_FILE": "dtos_history.sqlite3",
    "DTOS_HISTORY_STORAGE_ROOT": ".",
}


class ExpansionLatencyFailure(AssertionError):
    def __init__(self, message: str, result: dict[str, object]) -> None:
        super().__init__(message)
        self.result = result


class StartupFailure(RuntimeError):
    """Preserve the original startup failure and its bounded evidence."""

    def __init__(
        self, message: str, evidence: dict[str, object],
        process: subprocess.Popen | None = None,
    ) -> None:
        super().__init__(message)
        self.evidence = evidence
        self.process = process


def _sanitize_server_log(value: str, *, limit: int = 200) -> str:
    """Return a bounded diagnostic tail without paths, identities, or secrets."""
    lines = value.splitlines()[-limit:]
    sanitized = "\n".join(lines)
    sanitized = re.sub(
        r'(?i)(authorization|cookie|token|password|secret)([=: ]+)\S+',
        r'\1\2<redacted>', sanitized,
    )
    sanitized = re.sub(
        r'(?i)(file\s+["\'])(?:[A-Za-z]:\\|/)[^"\']*[\\/]([^\\/"\']+)(["\'])',
        r'\1<path>/\2\3', sanitized,
    )
    sanitized = re.sub(
        r'(?<![\w.-])(?:[A-Za-z]:\\[^\s"\']+|/(?:app|fixture|home|tmp|var)/[^\s"\']+)',
        '<path>', sanitized,
    )
    sanitized = re.sub(
        r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
        '<database-id>', sanitized,
    )
    return sanitized[-32_768:]


def _bounded_log_tail(log) -> str:
    try:
        log.flush()
        if log.readable():
            log.seek(0)
            value = log.read()
            log.seek(0, os.SEEK_END)
            return _sanitize_server_log(value)
        return _sanitize_server_log(Path(log.name).read_text(
            encoding="utf-8", errors="replace",
        ))
    except (AttributeError, OSError):
        return ""


def _normalized_headers(items) -> dict[str, str]:
    """Normalize HTTP names while rejecting ambiguous retry instructions."""
    normalized: dict[str, str] = {}
    retry_values: list[str] = []
    for raw_name, raw_value in items:
        name, value = str(raw_name).casefold(), str(raw_value)
        if name == "retry-after":
            retry_values.append(value)
        elif name not in normalized:
            normalized[name] = value
    if len(retry_values) > 1:
        raise AssertionError(
            f"warming response contains duplicate Retry-After headers: {retry_values}"
        )
    if retry_values:
        normalized["retry-after"] = retry_values[0]
    return normalized


def _cgroup(name: str) -> int:
    path = CGROUP / name
    if not path.is_file():
        raise RuntimeError(f"required cgroup metric unavailable: {name}")
    value = path.read_text(encoding="ascii").strip()
    if value == "max":
        raise RuntimeError(f"cgroup metric is unlimited: {name}")
    return int(value)


def _cgroup_cpu() -> dict[str, int | bool]:
    path = CGROUP / "cpu.stat"
    if not path.is_file():
        raise RuntimeError("required cgroup metric unavailable: cpu.stat")
    values: dict[str, int | bool] = {"available": True}
    for line in path.read_text(encoding="ascii").splitlines():
        name, value = line.split()
        values[name] = int(value)
    return values


def _rss_high_water(pid: int) -> int:
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    return 0


def _cgroup_values(name: str) -> dict[str, int]:
    path = CGROUP / name
    if not path.is_file():
        raise RuntimeError(f"required cgroup metric unavailable: {name}")
    values: dict[str, int] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        key, raw = line.split()
        value = int(raw)
        if value < 0:
            raise RuntimeError(f"invalid cgroup metric: {name}/{key}")
        values[key] = value
    return values


def _memory_state() -> dict[str, object]:
    current = _cgroup("memory.current")
    stats = _cgroup_values("memory.stat")
    events = _cgroup_values("memory.events")
    inactive = int(stats.get("inactive_file", 0))
    if inactive > current:
        raise RuntimeError("inactive_file exceeds memory.current")
    return {
        "raw_cgroup_bytes": current,
        "inactive_file_bytes": inactive,
        "active_file_bytes": int(stats.get("active_file", 0)),
        "file_bytes": int(stats.get("file", 0)),
        "effective_working_set_bytes": current - inactive,
        "anonymous_bytes": int(stats.get("anon", 0)),
        "memory_events": {
            key: int(events.get(key, 0))
            for key in ("oom", "oom_kill", "oom_group_kill")
        },
    }


def _archive_size() -> int:
    configured = Path(os.environ.get(
        "DTOS_HISTORY_DB_FILE", str(FIXTURE / "dtos_history.sqlite3"),
    ))
    return configured.stat().st_size if configured.is_file() else 0


def _warm_historical_archive() -> dict[str, object]:
    """Read real historical payload pages without retaining decoded records."""
    configured = Path(os.environ.get(
        "DTOS_HISTORY_DB_FILE", str(FIXTURE / "dtos_history.sqlite3"),
    ))
    started = time.perf_counter()
    with closing(sqlite3.connect(
        f"file:{configured.as_posix()}?mode=ro", uri=True,
    )) as connection:
        row = connection.execute(
            "SELECT count(*), coalesce(sum(length(payload)), 0) "
            "FROM historical_records"
        ).fetchone()
        hotset = connection.execute(
            "SELECT count(*), coalesce(sum(length(payload)), 0) FROM ("
            "SELECT payload FROM historical_records ORDER BY rowid DESC LIMIT 8192)"
        ).fetchone()
        pages = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
    return {
        "record_count": int(row[0]),
        "payload_bytes_scanned": int(row[1]),
        "hotset_records": int(hotset[0]),
        "hotset_payload_bytes": int(hotset[1]),
        "database_pages": pages,
        "page_size_bytes": page_size,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _memory_evidence(phase: str) -> dict[str, object]:
    """Return a sanitized snapshot even when strict cgroup parsing fails."""
    try:
        state = _memory_state()
        return {
            **state,
            "archive_size_bytes": _archive_size(),
            "accounting_mode": "cgroup_working_set",
            "timestamp": time.time(),
            "lifecycle_phase": phase,
        }
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return {
            "raw_cgroup_bytes": None,
            "inactive_file_bytes": None,
            "active_file_bytes": None,
            "file_bytes": None,
            "anonymous_bytes": None,
            "effective_working_set_bytes": None,
            "memory_events": None,
            "archive_size_bytes": _archive_size(),
            "accounting_mode": "conservative",
            "metric_error": type(exc).__name__,
            "timestamp": time.time(),
            "lifecycle_phase": phase,
        }


def _archive_material_threshold(archive_size: int) -> int:
    """Use five percent of the archive, bounded from 64 KiB to 8 MiB."""
    return max(64 * 1024, min(8 * MIB, max(0, archive_size) // 20))


def _archive_cache_assessment(
    before: dict[str, object], after: dict[str, object], *,
    coverage_status: int, coverage: dict[str, object],
    expected_records: int = 30_726,
) -> dict[str, object]:
    """Classify a verified archive read as newly warmed or already resident."""
    archive_size = int(before.get("archive_size_bytes") or 0)
    threshold = _archive_material_threshold(archive_size)
    before_inactive = before.get("inactive_file_bytes")
    after_inactive = after.get("inactive_file_bytes")
    progress = coverage.get("canonical_progress") or {}
    counts_by_season = coverage.get("counts_by_season") or {}
    canonical_record_count = sum(
        int((counts or {}).get("player_week") or 0)
        for counts in counts_by_season.values()
        if isinstance(counts, dict)
    ) if isinstance(counts_by_season, dict) else 0
    canonical_event_count = int(coverage.get("asset_event_count") or 0)
    verified_evidence_count = canonical_event_count or canonical_record_count
    coverage_valid = (
        coverage_status == 200
        and verified_evidence_count == expected_records
        and int(progress.get("completed_steps") or 0) == 5
        and int(progress.get("total_steps") or 0) == 6
        and progress.get("status") == "completed_with_pending"
    )
    metrics_valid = (
        before.get("accounting_mode") == "cgroup_working_set"
        and after.get("accounting_mode") == "cgroup_working_set"
        and isinstance(before_inactive, int)
        and isinstance(after_inactive, int)
    )
    growth = (
        after_inactive - before_inactive if metrics_valid else None
    )
    mode = None
    if coverage_valid and metrics_valid and growth is not None and growth >= threshold:
        mode = "newly_warmed"
    elif (
        coverage_valid and metrics_valid
        and before_inactive >= threshold and after_inactive >= threshold
    ):
        mode = "already_resident"
    reason = (
        f"archive cache established via {mode}"
        if mode else
        "coverage contract invalid" if not coverage_valid else
        "cgroup metrics unavailable or malformed" if not metrics_valid else
        "inactive_file did not meet the fixture-derived threshold"
    )
    return {
        "passed": mode is not None,
        "establishment_mode": mode,
        "reason": reason,
        "archive_size_bytes": archive_size,
        "material_threshold_bytes": threshold,
        "inactive_file_before_bytes": before_inactive,
        "inactive_file_after_bytes": after_inactive,
        "inactive_file_growth_bytes": growth,
        "coverage_valid": coverage_valid,
        "canonical_historical_record_count": canonical_record_count,
        "canonical_asset_event_count": canonical_event_count,
        "verified_evidence_count": verified_evidence_count,
    }


def _record_archive_assessment(
    phases: dict[str, object], before: dict[str, object],
    after: dict[str, object], *, coverage_status: int,
    coverage: dict[str, object], duration_ms: float,
    archive_scan: dict[str, object] | None = None,
) -> dict[str, object]:
    """Persist bounded evidence before enforcing the archive-cache gate."""
    assessment = _archive_cache_assessment(
        before, after, coverage_status=coverage_status, coverage=coverage,
    )
    phases["archive_warming"] = {
        "timestamp": time.time(),
        "duration_ms": round(duration_ms, 3),
        "before": before,
        "after": after,
        "assessment": assessment,
        "archive_scan": archive_scan,
        "coverage": {
            "status": coverage_status,
            "asset_event_count": coverage.get("asset_event_count"),
            "canonical_historical_record_count": assessment[
                "canonical_historical_record_count"
            ],
            "canonical_progress": coverage.get("canonical_progress"),
            "query_scope": coverage.get("read_model"),
            "provider_synchronization": False,
            "historical_mutation": False,
        },
    }
    if not assessment["passed"]:
        raise AssertionError(str(assessment["reason"]))
    return assessment


def _archive_cache_retained(snapshot: dict[str, object], threshold: int) -> bool:
    return (
        snapshot.get("accounting_mode") == "cgroup_working_set"
        and isinstance(snapshot.get("inactive_file_bytes"), int)
        and int(snapshot["inactive_file_bytes"]) >= threshold
    )


def _startup_memory_within_limit(snapshot: dict[str, object]) -> bool:
    """Apply the startup ceiling to the verified effective working set."""
    return (
        snapshot.get("accounting_mode") == "cgroup_working_set"
        and isinstance(snapshot.get("effective_working_set_bytes"), int)
        and int(snapshot["effective_working_set_bytes"]) < STARTUP_MAX
    )


def _combined_read_audit() -> dict[str, object]:
    """Run the observed production audit plus supported overlapping reads."""
    sequential_paths = (
        "/health/ready", "/api/history/coverage", "/api/market/health",
        "/api/market/assets?limit=1", "/api/market/search?q=QB&limit=1",
    )
    overlapping_paths = (
        "/api/history/coverage", "/api/market/health",
        "/api/market/assets?limit=50",
        "/api/market/assets/player:10213",
        "/api/market/search?q=QB&limit=50",
    )

    def observed(path: str, phase: str) -> dict[str, object]:
        before = _memory_evidence(f"{phase}_before")
        status, body, duration_ms = _request(path)
        after = _memory_evidence(f"{phase}_after")
        return {
            "path": path, "status": status, "duration_ms": round(duration_ms, 3),
            "response_bytes": len(
                body if isinstance(body, bytes) else body.encode("utf-8")
            ),
            "memory_before": before, "memory_after": after,
        }

    cycles = []
    for cycle_index in range(2):
        sequential = []
        for index, path in enumerate(sequential_paths):
            sample = observed(path, f"combined_{cycle_index}_sequential_{index}")
            sequential.append(sample)
            if sample["status"] != 200:
                raise AssertionError(f"combined audit failed: {path}={sample['status']}")
        overlapping = []
        with ThreadPoolExecutor(max_workers=len(overlapping_paths)) as executor:
            futures = {
                executor.submit(
                    observed, path, f"combined_{cycle_index}_overlap_{index}",
                ): path
                for index, path in enumerate(overlapping_paths)
            }
            for future in as_completed(futures):
                sample = future.result()
                overlapping.append(sample)
                if sample["status"] != 200:
                    raise AssertionError(
                        f"combined overlap failed: {sample['path']}={sample['status']}"
                    )
        overlapping.sort(key=lambda sample: overlapping_paths.index(sample["path"]))
        cycles.append({"sequential": sequential, "overlapping": overlapping})
    events = _cgroup_values("memory.events")
    if any(int(events.get(name) or 0) for name in ("oom", "oom_kill", "oom_group_kill")):
        raise AssertionError(f"combined audit recorded OOM events: {events}")
    return {"cycles": cycles, "memory_events": events}


class Monitor:
    def __init__(self) -> None:
        self.peak = _cgroup("memory.current")
        self.effective_peak = int(_memory_state()["effective_working_set_bytes"])
        self.samples = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(0.01):
            self.peak = max(self.peak, _cgroup("memory.current"))
            self.effective_peak = max(
                self.effective_peak,
                int(_memory_state()["effective_working_set_bytes"]),
            )
            self.samples += 1

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args) -> None:
        self.stop.set()
        self.thread.join(timeout=2)
        self.peak = max(self.peak, _cgroup("memory.current"))
        self.effective_peak = max(
            self.effective_peak,
            int(_memory_state()["effective_working_set_bytes"]),
        )


def _diagnostic_request(
    path: str, expected: tuple[int, ...] = (200,),
) -> tuple[int, bytes, float, float]:
    started = time.perf_counter()
    request = Request(BASE_URL + path, headers={"X-DTOS-Diagnostics": "1"})
    try:
        with urlopen(request, timeout=60) as response:
            status, body = response.status, response.read()
            server_ms = float(response.headers.get("X-DTOS-Request-Duration", 0))
    except HTTPError as exc:
        status, body = exc.code, exc.read()
        server_ms = float(exc.headers.get("X-DTOS-Request-Duration", 0))
    elapsed = (time.perf_counter() - started) * 1000
    if status not in expected:
        raise AssertionError(f"{path}: HTTP {status}, expected {expected}")
    return status, body, elapsed, server_ms


def _request(path: str, expected: tuple[int, ...] = (200,)) -> tuple[int, bytes, float]:
    status, body, elapsed, _server_ms = _diagnostic_request(path, expected)
    return status, body, elapsed


def _start_server(
    log, mode: str = "normal", *, evidence: dict[str, object] | None = None,
    popen_factory=subprocess.Popen, request_observer=_request,
    clock=time.monotonic, sleeper=time.sleep, memory_observer=None,
) -> subprocess.Popen:
    evidence = evidence if evidence is not None else {}
    memory_observer = memory_observer or (lambda: _cgroup("memory.current"))
    environment = os.environ.copy()
    environment["DTOS_MARKET_PROFILE_MODE"] = mode
    command = [
        sys.executable, "-m", "uvicorn",
        "tools.validation.market_profile_app:app", "--host", "127.0.0.1",
        "--port", "8767", "--workers", "1",
    ]
    evidence.update({
        "command": [Path(command[0]).name, *command[1:]],
        "mode": mode,
        "fixture": {
            "cache_file": Path(environment.get("DTOS_CACHE_FILE", "")).name,
            "history_database": Path(
                environment.get("DTOS_HISTORY_DB_FILE", "")
            ).name,
            "storage_root": ".",
        },
        "observations": [],
        "memory_at_launch": memory_observer(),
        "termination": "launching",
    })
    try:
        process = popen_factory(
            command, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, env=environment,
        )
    except OSError as exc:
        evidence.update({
            "exit_code": None, "termination": "launch_failure",
            "exception_type": type(exc).__name__,
            "message": _sanitize_server_log(str(exc)),
            "server_log_tail": _bounded_log_tail(log),
        })
        raise StartupFailure("application executable could not start", evidence) from exc
    evidence["pid_recorded"] = True
    deadline = clock() + 60
    while clock() < deadline:
        if process.poll() is not None:
            returncode = process.returncode
            evidence.update({
                "exit_code": returncode,
                "termination": "signal" if returncode < 0 else "natural_exit",
                "memory_at_exit": memory_observer(),
                "server_log_tail": _bounded_log_tail(log),
            })
            raise StartupFailure(
                f"application exited during startup: {returncode}", evidence, process,
            )
        try:
            status, _body, elapsed = request_observer("/health/live")
            evidence["observations"].append({
                "endpoint": "/health/live", "status": status,
                "client_ms": round(elapsed, 3),
            })
            if status == 200:
                evidence.update({"exit_code": None, "termination": "running"})
                return process
        except OSError as exc:
            evidence["observations"].append({
                "endpoint": "/health/live", "status": "connection_error",
                "error": type(exc).__name__,
            })
        sleeper(0.25)
    evidence.update({
        "exit_code": process.poll(), "termination": "startup_timeout",
        "memory_at_exit": memory_observer(),
        "server_log_tail": _bounded_log_tail(log),
    })
    raise StartupFailure(
        "application did not become live within 60 seconds", evidence, process,
    )


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


def _configured_fixture_contract() -> dict[str, object]:
    root = FIXTURE.resolve()
    resolved: dict[str, Path] = {}
    for name in FIXTURE_SETTINGS:
        raw = os.environ.get(name)
        if not raw:
            raise AssertionError(f"required fixture setting is missing: {name}")
        path = Path(raw).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise AssertionError(f"fixture setting escapes configured root: {name}") from exc
        resolved[name] = path
    if resolved["DTOS_HISTORY_STORAGE_ROOT"] != root:
        raise AssertionError("history storage root does not resolve to fixture root")
    for name in ("DTOS_CACHE_FILE", "DTOS_HISTORY_DB_FILE"):
        if not resolved[name].is_file():
            raise AssertionError(f"configured fixture file is unavailable: {name}")
    league_id = os.environ.get("SLEEPER_LEAGUE_ID")
    if league_id != "validation-league-1804":
        raise AssertionError("configured fixture league identity is unavailable")
    history_stat = resolved["DTOS_HISTORY_DB_FILE"].stat()
    connection = sqlite3.connect(resolved["DTOS_HISTORY_DB_FILE"])
    try:
        database_uuid = str(connection.execute(
            "SELECT value FROM database_metadata WHERE key='database_uuid'",
        ).fetchone()[0])
    finally:
        connection.close()
    return {
        "storage_root": ".",
        "cache_file": resolved["DTOS_CACHE_FILE"].relative_to(root).as_posix(),
        "history_database": resolved["DTOS_HISTORY_DB_FILE"].relative_to(root).as_posix(),
        "contained": True,
        "league_id": league_id,
        "file_identity_digest": hashlib.sha256(
            f"{history_stat.st_dev}:{history_stat.st_ino}".encode()
        ).hexdigest(),
        "database_identity_digest": hashlib.sha256(
            json.dumps(database_uuid).encode()
        ).hexdigest(),
        "history_database_size": history_stat.st_size,
    }


def _application_fixture_contract(expected: dict[str, object]) -> dict[str, object]:
    actual = json.loads(_request("/__validation__/fixture-contract")[1])
    for name in ("storage_root", "cache_file", "history_database", "league_id"):
        if actual.get(name) != expected.get(name):
            raise AssertionError(f"application fixture setting mismatch: {name}")
    if actual.get("active_store_database") != expected.get("history_database"):
        raise AssertionError("application HistoricalStore does not use fixture database")
    if actual.get("cache_league_id") != expected.get("league_id"):
        raise AssertionError("application cache uses a different fixture league")
    for name in (
        "database_identity_digest", "file_identity_digest", "history_database_size",
    ):
        if actual.get(name) != expected.get(name):
            raise AssertionError(f"application fixture identity mismatch: {name}")
    for name in (
        "cache_exists", "history_database_exists", "active_store_matches", "contained",
    ):
        if actual.get(name) is not True:
            raise AssertionError(f"application fixture contract failed: {name}")
    return actual


def _artifact_state() -> dict[str, object]:
    state = json.loads(_request("/__validation__/market-artifact")[1])
    if not state.get("active") or not state.get("exists"):
        raise AssertionError("active market artifact is unavailable")
    if int(state.get("final_artifacts") or 0) != 1:
        raise AssertionError(
            "expected one active market generation, found "
            f"{state.get('final_artifacts')}"
        )
    if int(state.get("temporary_artifacts") or 0):
        raise AssertionError("temporary market artifacts remain after publication")
    if state.get("complete") is not True or not state.get("generation"):
        raise AssertionError("active market artifact metadata is incomplete")
    if int(state.get("size_bytes") or 0) <= 0:
        raise AssertionError("active market artifact is empty")
    return state


def _cold_build() -> tuple[dict, float, int, dict[str, object]]:
    started = time.perf_counter()
    attempts = 0
    warming_client: list[float] = []
    warming_server: list[float] = []
    health_latency: list[float] = []
    liveness_latency: list[float] = []
    phases: set[str] = set()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        attempts += 1
        status, _body, elapsed, server_ms = _diagnostic_request(
            "/api/market/assets?limit=50", (200, 503),
        )
        if status == 200:
            return (
                _market_health(),
                (time.perf_counter() - started) * 1000,
                attempts,
                {
                    "warming_client_max_ms": round(max(warming_client, default=0), 3),
                    "warming_server_max_ms": round(max(warming_server, default=0), 3),
                    "health_max_ms": round(max(health_latency, default=0), 3),
                    "liveness_max_ms": round(max(liveness_latency, default=0), 3),
                    "background_phases": sorted(phases),
                },
            )
        warming_client.append(elapsed)
        warming_server.append(server_ms)
        if elapsed >= 500:
            raise AssertionError(f"warming response exceeded 500ms: {elapsed:.3f}ms")
        if server_ms >= 50:
            raise AssertionError(
                f"warming server time exceeded 50ms: {server_ms:.3f}ms"
            )
        _health_status, health_body, health_ms, _ = _diagnostic_request(
            "/api/market/health",
        )
        health_latency.append(health_ms)
        health = json.loads(health_body)
        phases.add(str((health.get("cache") or {}).get("build_phase")))
        _live_status, _live_body, live_ms, _ = _diagnostic_request("/health/live")
        liveness_latency.append(live_ms)
        if health_ms >= 500 or live_ms >= 500:
            raise AssertionError(
                f"background responsiveness failed: health={health_ms:.3f}ms "
                f"liveness={live_ms:.3f}ms"
            )
        error = (health.get("cache") or {}).get("last_error")
        if error:
            raise AssertionError(f"market build failed: {error}")
        time.sleep(0.5)
    raise AssertionError("cold market build exceeded 60 seconds")


def _history_metrics() -> dict[str, object]:
    payload = json.loads(_request("/api/history/coverage")[1])
    return dict(payload.get("read_model") or {})


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int(len(ordered) * percentile + 0.999) - 1),
    )
    return ordered[index]


def _public_error(exc: BaseException) -> dict[str, str]:
    message = str(exc).replace(str(FIXTURE), "<fixture>").replace(BASE_URL, "<server>")
    return {"type": type(exc).__name__, "message": message}


def _profile_expansion(path: str) -> dict[str, object]:
    # The first request intentionally hydrates the selected player's bounded
    # historical summary. Only subsequent stable-cache reads are gated.
    _diagnostic_request(path)
    baseline = _history_metrics()
    baseline_health = _market_health()
    samples: list[dict[str, object]] = []
    identities: list[tuple[object, object, object]] = []
    previous = baseline
    for sequence in range(1, 11):
        status, body, client_ms, server_ms = _diagnostic_request(path)
        current = _history_metrics()
        payload = json.loads(body)
        cache = (_market_health().get("cache") or {})
        query_count = int(current.get("query_count") or 0) - int(
            previous.get("query_count") or 0
        )
        sqlite_ms = (
            float(current.get("query_duration_ms") or 0)
            if query_count else 0.0
        )
        identity = (
            payload.get("market_generation"),
            payload.get("brain_snapshot_id"),
            payload.get("historical_dataset_version"),
        )
        identities.append(identity)
        samples.append({
            "sequence": sequence,
            "status": status,
            "client_ms": round(client_ms, 3),
            "server_ms": round(server_ms, 3),
            "network_and_client_ms": round(max(0.0, client_ms - server_ms), 3),
            "sqlite_query_count": query_count,
            "sqlite_ms": round(sqlite_ms, 3),
            "response_bytes": len(body),
            "market_cache_status": cache.get("status"),
            "market_build_count": cache.get("build_count"),
            "player_summary_build_count": current.get("player_summary_build_count"),
            "player_summary_cache_hits": current.get("player_summary_cache_hits"),
            "runner_load": [round(value, 3) for value in os.getloadavg()],
        })
        previous = current
    client_values = [float(sample["client_ms"]) for sample in samples]
    server_values = [float(sample["server_ms"]) for sample in samples]
    result = {
        "warmup_completed": True,
        "samples": samples,
        "median_ms": round(statistics.median(client_values), 3),
        "p95_ms": round(_percentile(client_values, 0.95), 3),
        "maximum_ms": round(max(client_values), 3),
        "server_median_ms": round(statistics.median(server_values), 3),
        "server_maximum_ms": round(max(server_values), 3),
        "dataset_generation_stable": len({identity[0] for identity in identities}) == 1,
        "brain_snapshot_stable": len({identity[1] for identity in identities}) == 1,
        "historical_dataset_stable": len({identity[2] for identity in identities}) == 1,
        "market_build_count_stable": all(
            sample["market_build_count"]
            == (baseline_health.get("cache") or {}).get("build_count")
            for sample in samples
        ),
        "player_summary_build_count_stable": all(
            sample["player_summary_build_count"] == baseline.get("player_summary_build_count")
            for sample in samples
        ),
        "player_summary_cache_hits_increased": int(
            samples[-1]["player_summary_cache_hits"] or 0
        ) >= int(baseline.get("player_summary_cache_hits") or 0) + len(samples),
    }
    if result["median_ms"] >= 1000 or result["maximum_ms"] >= 1000:
        slow = [sample for sample in samples if float(sample["client_ms"]) >= 1000]
        result["failed_samples"] = slow
        raise ExpansionLatencyFailure(
            "expansion latency gate failed: "
            f"median={result['median_ms']:.3f}ms maximum={result['maximum_ms']:.3f}ms "
            f"failed_samples={json.dumps(slow, sort_keys=True)}",
            result,
        )
    for field in (
        "dataset_generation_stable", "brain_snapshot_stable",
        "historical_dataset_stable", "market_build_count_stable",
        "player_summary_build_count_stable", "player_summary_cache_hits_increased",
    ):
        if not result[field]:
            raise AssertionError(f"expansion identity/cache invariant failed: {field}")
    return result


def _latencies() -> dict[str, object]:
    endpoints = {
        "directory": "/api/market/assets?limit=50",
        "search": "/api/market/search?q=Validation%20Player%2010213",
        "trending": "/api/market/trending",
        "health": "/api/market/health",
    }
    values = {}
    for name, path in endpoints.items():
        values[name] = round(_request(path)[2], 3)
    limits = {"directory": 1000, "search": 500, "trending": 1000, "health": 500}
    for name, value in values.items():
        if value >= limits[name]:
            raise AssertionError(f"{name} latency {value:.3f}ms exceeds {limits[name]}ms")
    values["expansion"] = _profile_expansion(
        f"/api/market/assets/{quote('player:10213', safe=':')}"
    )
    return values


def _pad_to_production_baseline() -> list[bytearray]:
    padding = []
    while _cgroup("memory.current") < BASELINE:
        padding.append(bytearray(min(16 * MIB, BASELINE - _cgroup("memory.current"))))
    return padding


def _semantic_contract() -> dict[str, object]:
    return json.loads(_request("/__validation__/semantic-market-contract")[1])


_NONSEMANTIC_VOLATILE_PATHS = {
    "$.historical_progress.canonical_history_progress.semantic_generations."
    "historical_records",
    "$.valuation_generation",
}
_MATERIAL_PUBLICATION_ENVELOPE_PATHS = {
    "$.brain_generation",
    "$.generated_at",
    "$.historical_progress.canonical_history_progress.semantic_generations."
    "historical_records",
    "$.historical_dataset_version",
    "$.market_generation",
    "$.valuation_generation",
}


def _json_differences(
    before: object, after: object, path: str = "$",
) -> list[dict[str, object]]:
    differences: list[dict[str, object]] = []
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                differences.append({"path": child, "before": "<missing>", "after": after[key]})
            elif key not in after:
                differences.append({"path": child, "before": before[key], "after": "<missing>"})
            else:
                differences.extend(_json_differences(before[key], after[key], child))
        return differences
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            differences.append({
                "path": f"{path}.length", "before": len(before), "after": len(after),
            })
        for index, (left, right) in enumerate(zip(before, after)):
            differences.extend(_json_differences(left, right, f"{path}[{index}]"))
        return differences
    if before != after:
        differences.append({"path": path, "before": before, "after": after})
    return differences


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _nonsemantic_payload_comparison(before_body: bytes, after_body: bytes) -> dict[str, object]:
    """Compare product content while explicitly auditing two volatile fields."""
    before = json.loads(before_body)
    after = json.loads(after_body)
    differences = _json_differences(before, after)
    unexpected = [
        difference for difference in differences
        if difference["path"] not in _NONSEMANTIC_VOLATILE_PATHS
    ]
    if unexpected:
        raise AssertionError(
            "non-semantic refresh changed unapproved response paths: "
            + json.dumps(unexpected, sort_keys=True)
        )
    for difference in differences:
        path = str(difference["path"])
        before_value, after_value = difference["before"], difference["after"]
        if path.endswith(".historical_records") and not all(
            isinstance(value, int) and value >= 0 for value in (before_value, after_value)
        ):
            raise AssertionError("historical record generation is not a nonnegative integer")
        if path == "$.valuation_generation" and not all(
            value is None or isinstance(value, str) for value in (before_value, after_value)
        ):
            raise AssertionError("valuation generation is not nullable text")
    before_stable = json.loads(before_body)
    after_stable = json.loads(after_body)
    before_stable.pop("valuation_generation", None)
    after_stable.pop("valuation_generation", None)
    for payload in (before_stable, after_stable):
        generations = (
            payload.get("historical_progress", {})
            .get("canonical_history_progress", {})
            .get("semantic_generations", {})
        )
        generations.pop("historical_records", None)
    before_rows = before.get("assets") or []
    after_rows = after.get("assets") or []
    before_ids = [row.get("asset_id") for row in before_rows]
    after_ids = [row.get("asset_id") for row in after_rows]
    row_digest_before = _canonical_digest(before_rows)
    row_digest_after = _canonical_digest(after_rows)
    stable_digest_before = _canonical_digest(before_stable)
    stable_digest_after = _canonical_digest(after_stable)
    if before_ids != after_ids or row_digest_before != row_digest_after:
        raise AssertionError("non-semantic refresh changed market rows or ordering")
    if stable_digest_before != stable_digest_after:
        raise AssertionError("non-semantic refresh changed stable response contract")
    return {
        "changed_path_count": len(differences),
        "changed_paths": differences,
        "asset_row_ids_changed": [],
        "row_order_changed": False,
        "row_digest_before": row_digest_before,
        "row_digest_after": row_digest_after,
        "stable_digest_before": stable_digest_before,
        "stable_digest_after": stable_digest_after,
        "raw_digest_before": _canonical_digest(before),
        "raw_digest_after": _canonical_digest(after),
    }


def _material_target_comparison(
    before_body: bytes, after_body: bytes,
) -> list[dict[str, object]]:
    before_rows = json.loads(before_body).get("results") or []
    after_rows = json.loads(after_body).get("results") or []
    expected_ids = ["player:10213"]
    if [row.get("asset_id") for row in before_rows] != expected_ids:
        raise AssertionError("material target is unavailable in compact market search")
    if [row.get("asset_id") for row in after_rows] != expected_ids:
        raise AssertionError("published material target is unavailable in compact search")
    differences = _json_differences(
        before_rows[0], after_rows[0], "$.assets[player:10213]",
    )
    expected_paths = {
        "$.assets[player:10213].values.intrinsic_dtos_value",
        "$.assets[player:10213].values.league_adjusted_value",
    }
    if {difference["path"] for difference in differences} != expected_paths:
        raise AssertionError(
            "material replacement changed unexpected target fields: "
            + json.dumps(differences, sort_keys=True)
        )
    return differences


def _material_target_search_path(asset_id: str = "player:10213") -> str:
    """Use the public canonical-ID search contract for an unambiguous target."""
    if not asset_id.startswith("player:") or not asset_id.removeprefix("player:"):
        raise AssertionError("material target must be a canonical player asset ID")
    return f"/api/market/search?q={quote(asset_id, safe='')}&limit=50"


def _material_first_page_comparison(
    before_body: bytes, after_body: bytes, *,
    old_market_generation: object, new_market_generation: object,
) -> dict[str, object]:
    """Require identical ordered rows and audit exact publication metadata changes."""
    before = json.loads(before_body)
    after = json.loads(after_body)
    before_assets = before.get("assets") or []
    after_assets = after.get("assets") or []
    before_asset_bytes = json.dumps(
        before_assets, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()
    after_asset_bytes = json.dumps(
        after_assets, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()
    if before_asset_bytes != after_asset_bytes:
        raise AssertionError(
            "material replacement changed unrelated first-page assets: "
            + json.dumps(
                _json_differences(before_assets, after_assets, "$.assets"),
                sort_keys=True,
            )
        )
    before_envelope = dict(before)
    after_envelope = dict(after)
    before_envelope.pop("assets", None)
    after_envelope.pop("assets", None)
    envelope_differences = _json_differences(before_envelope, after_envelope)
    unexpected = [
        difference for difference in envelope_differences
        if difference["path"] not in _MATERIAL_PUBLICATION_ENVELOPE_PATHS
    ]
    if unexpected:
        raise AssertionError(
            "material publication changed unexpected envelope paths: "
            + json.dumps(unexpected, sort_keys=True)
        )
    if before.get("market_generation") != old_market_generation:
        raise AssertionError("pre-publication response used an unexpected generation")
    if after.get("market_generation") != new_market_generation:
        raise AssertionError("post-publication response used a stale generation")
    if old_market_generation == new_market_generation:
        raise AssertionError("material publication did not change market generation")
    if after.get("generated_at") != new_market_generation:
        raise AssertionError("post-publication generated_at conflicts with generation")
    if before.get("historical_dataset_version_scope") != "artifact_build" or (
        after.get("historical_dataset_version_scope") != "artifact_build"
    ):
        raise AssertionError("directory historical identity is not artifact provenance")
    return {
        "asset_count": len(before_assets),
        "asset_digest_before": hashlib.sha256(before_asset_bytes).hexdigest(),
        "asset_digest_after": hashlib.sha256(after_asset_bytes).hexdigest(),
        "asset_order": [row.get("asset_id") for row in before_assets],
        "envelope_changed_paths": envelope_differences,
        "old_market_generation": old_market_generation,
        "new_market_generation": new_market_generation,
    }


def _nonsemantic_reuse(
    first_generation: object, first_build_count: int, expected_body: bytes,
) -> dict[str, object]:
    before = _semantic_contract()
    marker = f"validation-nonsemantic-{time.time_ns()}"
    _profiled_request(
        f"/__validation__/nonsemantic-refresh?marker={quote(marker)}", method="POST",
    )
    bodies = [_request("/api/market/assets?limit=50")[1] for _ in range(3)]
    after = _semantic_contract()
    health = _market_health()
    cache = health.get("cache") or {}
    if before.get("semantic_generation") != after.get("semantic_generation"):
        raise AssertionError("non-semantic refresh changed semantic generation")
    if after.get("artifact_compatibility") != "compatible":
        raise AssertionError("non-semantic refresh rejected retained artifact")
    comparisons = [
        _nonsemantic_payload_comparison(expected_body, body) for body in bodies
    ]
    if int(cache.get("build_count") or 0) != first_build_count:
        raise AssertionError("non-semantic refresh published a replacement")
    if cache.get("build_active") or cache.get("market_generation") != first_generation:
        raise AssertionError("non-semantic refresh started a replacement worker")
    before_raw = before.get("raw_identities") or {}
    after_raw = after.get("raw_identities") or {}
    for field in (
        "last_sync", "brain_generated_at", "historical_record_generation",
    ):
        if before_raw.get(field) == after_raw.get(field):
            raise AssertionError(
                f"non-semantic fixture mutation did not change raw identity: {field}"
            )
    return {
        "classification": "non_semantic_reuse",
        "semantic_generation_stable": True,
        "serialized_output_unchanged": True,
        "artifact_compatibility": "compatible",
        "replacement_workers": 0,
        "replacement_builds": 0,
        "raw_before": before_raw,
        "raw_after": after_raw,
        "semantic_before": before.get("semantic_identities"),
        "semantic_after": after.get("semantic_identities"),
        "payload_comparison": comparisons[0],
    }


def _profiled_request(
    path: str, *, method: str = "GET",
) -> tuple[int, bytes, dict[str, str], float, float, dict[str, object]]:
    started = time.perf_counter()
    trace_id = uuid4().hex
    request = Request(
        BASE_URL + path,
        headers={"X-DTOS-Diagnostics": "1", "X-DTOS-Trace-ID": trace_id},
        method=method,
    )
    try:
        response = urlopen(request, timeout=60)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read()
        server_ms = float(response.headers.get("X-DTOS-Request-Duration", 0))
        encoded = response.headers.get("X-DTOS-Validation-Profile", "")
        profile = json.loads(base64.urlsafe_b64decode(encoded).decode())
        status = response.status
        headers = _normalized_headers(response.headers.items())
    client_ms = (time.perf_counter() - started) * 1000
    try:
        trace_request = Request(BASE_URL + f"/__validation__/trace/{trace_id}")
        with urlopen(trace_request, timeout=10) as trace_response:
            profile["response_trace"] = json.loads(trace_response.read())
    except OSError as exc:
        profile["response_trace_error"] = type(exc).__name__
    return (
        status, body, headers,
        client_ms, server_ms, profile,
    )


def _replacement_profile(
    first_generation: object, first_build_count: int, expected_body: bytes,
) -> tuple[dict[str, object], dict[str, object]]:
    before_semantic = _semantic_contract()
    _target_status, target_before_body, _target_elapsed = _request(
        _material_target_search_path(),
    )
    marker = f"validation-material-{time.time_ns()}"
    mutation_status, mutation_body, _headers, _client, _server, _profile = _profiled_request(
        f"/__validation__/material-market-change?marker={quote(marker)}", method="POST",
    )
    mutation = json.loads(mutation_body)
    if mutation_status != 200:
        raise AssertionError("material fixture mutation was rejected")
    if mutation.get("asset_id") != "player:10213" or mutation.get("attached") is not True:
        raise AssertionError("material fixture target is missing or detached")
    if mutation.get("field") != "normalized_players.10213.dtos_value":
        raise AssertionError("material fixture changed an unexpected canonical field")
    if int(mutation.get("changed_canonical_fields") or 0) != 1:
        raise AssertionError("material fixture did not change exactly one canonical input")
    if not isinstance(mutation.get("before"), (int, float)) or not isinstance(
        mutation.get("after"), (int, float),
    ):
        raise AssertionError("material fixture scalar evidence is unavailable")
    if mutation["before"] == mutation["after"]:
        raise AssertionError("material fixture scalar did not change")
    changed_semantic = _semantic_contract()
    if (
        before_semantic.get("semantic_generation")
        == changed_semantic.get("semantic_generation")
    ):
        raise AssertionError("material fixture mutation did not change semantic digest")
    if changed_semantic.get("artifact_compatibility") != "brain_semantic_output_changed":
        raise AssertionError(
            "material artifact mismatch reason was not brain_semantic_output_changed"
        )
    before_digests = before_semantic.get("semantic_identities") or {}
    after_digests = changed_semantic.get("semantic_identities") or {}
    for stable in ("asset_universe_digest", "ownership_dependency_digest"):
        if before_digests.get(stable) != after_digests.get(stable):
            raise AssertionError(f"material fixture changed unrelated digest: {stable}")
    if (
        before_digests.get("brain_semantic_output_digest")
        == after_digests.get("brain_semantic_output_digest")
    ):
        raise AssertionError("material fixture did not change Brain/valuation digest")
    before_history = _history_metrics()
    samples: list[dict[str, object]] = []
    for sequence in range(1, 11):
        status, body, headers, client_ms, server_ms, profile = _profiled_request(
            "/api/market/assets?limit=50",
        )
        payload = json.loads(body)
        if status != 503 or payload != {
            "detail": "Asset Market generation is building safely in the "
            "background; retry shortly.",
        }:
            raise AssertionError(
                f"replacement request did not use bounded warming contract: {status}"
            )
        if headers.get("retry-after") != "5":
            raise AssertionError("replacement warming omitted Retry-After: 5")
        health = _market_health()
        cache = health.get("cache") or {}
        _live_status, _live_body, live_client_ms, live_server_ms = (
            _diagnostic_request("/health/live")
        )
        samples.append({
            "sequence": sequence,
            "status": status,
            "client_ms": round(client_ms, 3),
            "server_ms": round(server_ms, 3),
            "event_loop_client_ms": round(live_client_ms, 3),
            "event_loop_server_ms": round(live_server_ms, 3),
            "lifecycle_lock_ms": profile.get("lifecycle_lock_ms", 0.0),
            "cache_lookup_ms": profile.get("cache_lookup_ms", 0.0),
            "request_marker_ms": profile.get("request_marker_ms", 0.0),
            "response_processing_ms": round(
                max(0.0, server_ms - float(profile.get("market_get_ms", 0.0))), 3,
            ),
            "request_thread_calls": {
                name: profile.get(f"{name}_calls", 0)
                for name in (
                    "cache_key", "durable_generation", "dataset_version",
                    "database_uuid", "market_construction",
                )
            },
            "active_threads": profile.get("active_threads"),
            "thread_pool_threads": profile.get("thread_pool_threads"),
            "worker_alive": profile.get("worker_alive"),
            "sleeper_syncing": profile.get("sleeper_syncing"),
            "transactions_syncing": profile.get("transactions_syncing"),
            "runner_load": [round(value, 3) for value in os.getloadavg()],
            "cgroup_memory_current": _cgroup("memory.current"),
            "memory_evidence": _memory_evidence(
                f"replacement_warming_{sequence}"
            ),
            "response_bytes": len(body),
            "served_generation": cache.get("market_generation"),
            "build_count": cache.get("build_count"),
            "build_phase": cache.get("build_phase"),
            "build_active": cache.get("build_active"),
        })
    after_history = _history_metrics()
    deadline = time.monotonic() + 60
    final_health: dict[str, object] = {}
    while time.monotonic() < deadline:
        final_health = _market_health()
        final_cache = final_health.get("cache") or {}
        if not final_cache.get("build_active"):
            break
        time.sleep(0.05)
    final_cache = final_health.get("cache") or {}
    client_values = [float(sample["client_ms"]) for sample in samples]
    server_values = [float(sample["server_ms"]) for sample in samples]
    result = {
        "samples": samples,
        "median_client_ms": round(statistics.median(client_values), 3),
        "p95_client_ms": round(_percentile(client_values, 0.95), 3),
        "maximum_client_ms": round(max(client_values), 3),
        "median_server_ms": round(statistics.median(server_values), 3),
        "p95_server_ms": round(_percentile(server_values, 0.95), 3),
        "maximum_server_ms": round(max(server_values), 3),
        "sqlite_query_count": int(after_history.get("query_count") or 0)
        - int(before_history.get("query_count") or 0),
        "last_valid_generation_stable": all(
            sample["served_generation"] == first_generation for sample in samples
        ),
        "replacement_builds": int(final_cache.get("build_count") or 0)
        - first_build_count,
        "new_generation_published": final_cache.get("market_generation")
        != first_generation,
        "request_thread_generation_work": any(
            any(int(count or 0) for count in sample["request_thread_calls"].values())
            for sample in samples
        ),
    }
    failures = [sample for sample in samples if float(sample["server_ms"]) >= 50]
    if failures:
        result["failed_samples"] = failures
        raise ExpansionLatencyFailure(
            "replacement warming server gate failed: "
            f"maximum={result['maximum_server_ms']:.3f}ms "
            f"failed_samples={json.dumps(failures, sort_keys=True)}",
            result,
        )
    if result["replacement_builds"] != 1:
        raise AssertionError(
            f"expected exactly one replacement build, got {result['replacement_builds']}"
        )
    if not result["last_valid_generation_stable"]:
        raise AssertionError("last-valid generation changed during replacement warming")
    if not result["new_generation_published"]:
        raise AssertionError("replacement generation was not published")
    if result["request_thread_generation_work"] or result["sqlite_query_count"]:
        raise AssertionError("replacement warming performed request-thread generation work")
    published_artifact = _artifact_state()
    if published_artifact.get("generation") != changed_semantic.get("semantic_generation"):
        raise AssertionError("validator sampled before the new semantic generation published")
    _status, final_body, _elapsed = _request("/api/market/assets?limit=50")
    first_page_comparison = _material_first_page_comparison(
        expected_body, final_body,
        old_market_generation=first_generation,
        new_market_generation=final_cache.get("market_generation"),
    )
    if (
        published_artifact.get("historical_dataset_version")
        != json.loads(final_body).get("historical_dataset_version")
    ):
        raise AssertionError("directory historical provenance conflicts with artifact manifest")
    _target_status, target_after_body, _target_elapsed = _request(
        _material_target_search_path(),
    )
    target_differences = _material_target_comparison(
        target_before_body, target_after_body,
    )
    changed_assets = ["player:10213"]
    repeat_bodies = [_request("/api/market/assets?limit=50")[1] for _ in range(3)]
    repeated_health = _market_health()
    repeated_cache = repeated_health.get("cache") or {}
    if any(body != final_body for body in repeat_bodies):
        raise AssertionError("repeated material state changed serialized output")
    if int(repeated_cache.get("build_count") or 0) != first_build_count + 1:
        raise AssertionError("repeated material state started another construction")
    if repeated_cache.get("build_active"):
        raise AssertionError("repeated material state started another worker")
    result.update({
        "semantic_before": before_semantic.get("semantic_identities"),
        "semantic_after": changed_semantic.get("semantic_identities"),
        "incompatibility_reason": changed_semantic.get("artifact_compatibility"),
        "changed_assets": changed_assets,
        "controlled_output_difference": True,
        "mutation": mutation,
        "target_row_differences": target_differences,
        "published_semantic_generation": published_artifact.get("generation"),
        "first_page_comparison": first_page_comparison,
    })
    return final_health, result


def _identity(payload: dict[str, object]) -> dict[str, object]:
    return {
        name: payload.get(name)
        for name in (
            "application_version", "application_build", "market_schema_version",
            "league_id", "historical_dataset_version", "market_generation",
            "historical_dataset_version_scope", "brain_generation",
            "valuation_generation",
        )
    }


def _restart_reuse(
    expected_identity: dict[str, object], expected_body: bytes,
    *, request=_profiled_request, clock=time.monotonic, sleeper=time.sleep,
    event_probe=None, load_observer=None, memory_observer=None,
    cpu_observer=None,
) -> dict[str, object]:
    event_probe = event_probe or (lambda: _diagnostic_request("/health/live"))
    load_observer = load_observer or os.getloadavg
    memory_observer = memory_observer or (lambda: _cgroup("memory.current"))
    cpu_observer = cpu_observer or (
        _cgroup_cpu if sys.platform == "linux"
        else lambda: {"available": False}
    )
    started = clock()
    samples: list[dict[str, object]] = []
    while clock() - started < 60:
        status, body, headers, client_ms, server_ms, profile = request(
            "/api/market/assets?limit=50",
        )
        if status == 200:
            payload = json.loads(body)
            actual_identity = _identity(payload)
            if actual_identity != expected_identity:
                raise AssertionError(
                    "restart artifact identity mismatch: "
                    f"expected={expected_identity} actual={actual_identity}"
                )
            if body != expected_body:
                raise AssertionError("restart artifact output differs from published output")
            if int(profile.get("market_construction_total") or 0) != 0:
                raise AssertionError("restart accidentally rebuilt the market")
            if int(profile.get("artifact_load_total") or 0) != 1:
                raise AssertionError("restart did not load exactly one durable artifact")
            return {
                "duration_ms": round((clock() - started) * 1000, 3),
                "warming_attempts": len(samples), "warming_samples": samples,
                "identity_match": True, "output_equivalent": True,
                "artifact_loads": profile.get("artifact_load_total"),
                "market_constructions": profile.get("market_construction_total"),
                "hydration_stages": profile.get("hydration_stages") or {},
            }
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AssertionError("malformed restart warming response") from exc
        if status != 503 or payload != {
            "detail": "Asset Market generation is building safely in the "
            "background; retry shortly.",
        }:
            raise AssertionError(
                f"restart returned unrelated response: HTTP {status} body={body[:200]!r}"
            )
        if headers.get("retry-after") != "5":
            raise AssertionError("restart warming omitted Retry-After: 5")
        if int(profile.get("market_construction_total") or 0):
            raise AssertionError("restart began market reconstruction")
        if int(profile.get("market_object_build_total") or 0):
            raise AssertionError("restart constructed a new market object")
        if profile.get("market_last_error"):
            raise AssertionError(
                f"restart artifact load failed: {profile['market_last_error']}"
            )
        if profile.get("market_build_phase") == "building":
            raise AssertionError("restart artifact was incompatible and triggered a rebuild")
        _live_status, _live_body, live_client_ms, live_server_ms = event_probe()
        samples.append({
            "client_ms": round(client_ms, 3), "server_ms": round(server_ms, 3),
            "response_bytes": len(body),
            "artifact_loads": profile.get("artifact_load_total"),
            "market_constructions": profile.get("market_construction_total"),
            "build_phase": profile.get("market_build_phase"),
            "event_loop_client_ms": round(live_client_ms, 3),
            "event_loop_server_ms": round(live_server_ms, 3),
            "lifecycle_lock_ms": profile.get("lifecycle_lock_ms", 0.0),
            "cache_lookup_ms": profile.get("cache_lookup_ms", 0.0),
            "active_threads": profile.get("active_threads"),
            "thread_pool_threads": profile.get("thread_pool_threads"),
            "runner_load": [round(value, 3) for value in load_observer()],
            "cgroup_memory_current": memory_observer(),
            "cgroup_cpu": cpu_observer(),
            "preparation_active": profile.get("preparation_active") or {},
            "preparation_events": profile.get("preparation_events") or [],
            "hydration_stages": profile.get("hydration_stages") or {},
            "response_trace": profile.get("response_trace") or {},
        })
        sleeper(0.05)
    raise AssertionError("durable market artifact reuse exceeded 60 seconds")


def _response_stack_experiments(
    log, expected_identity: dict[str, object], expected_body: bytes,
) -> dict[str, object]:
    """Run validation-only first-response variants against one durable artifact."""
    results: dict[str, object] = {}
    for mode in (
        "normal", "prestarted_idle_thread", "direct_response",
        "post_body_worker",
    ):
        cycles: list[dict[str, object]] = []
        for _sequence in range(3):
            process = _start_server(log, mode)
            try:
                _wait_ready()
                cycles.append(_restart_reuse(expected_identity, expected_body))
            finally:
                _stop_server(process)
        samples = [
            sample for cycle in cycles for sample in cycle["warming_samples"]
        ]
        results[mode] = {"cycles": cycles, "warming_samples": samples}
    return results


def main() -> int:
    if sys.platform != "linux":
        raise RuntimeError("Linux cgroup validation must run on Linux")
    memory_max = _cgroup("memory.max")
    if memory_max != MEMORY_MAX:
        raise RuntimeError(f"Docker did not enforce 2 GiB: memory.max={memory_max}")
    if not (CGROUP / "memory.peak").is_file():
        raise RuntimeError("memory.peak is required for this validation")

    fixture_contract = _configured_fixture_contract()
    archive_warmed = os.environ.get("DTOS_ARCHIVE_WARMED") == "1"
    combined_read = os.environ.get("DTOS_COMBINED_READ") == "1"
    summary: dict[str, object] = {
        "schema": "dtos-linux-market-memory-v1",
        "memory_max": memory_max,
        "fixture": {
            "assets": 12_322, "canonical_asset_events": 30_726,
            "database_records": 461_166 if combined_read else 30_726,
            "progress": "5/6",
            "configuration": fixture_contract,
        },
        "scenario": (
            "combined_read" if combined_read else
            "archive_warmed" if archive_warmed else "ordinary"
        ),
        "phases": {},
        "passed": False,
        "completed": False,
        "exit_code": 1,
        "errors": [],
        "memory_evidence": [],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT.parent / "server.log"
    padding: list[bytearray] = []
    process = None
    failure: BaseException | None = None
    startup_evidence: dict[str, object] = {}
    memory_evidence = summary["memory_evidence"]
    assert isinstance(memory_evidence, list)
    memory_evidence.append(_memory_evidence("container_startup"))
    try:
        with log_path.open("w", encoding="utf-8") as log, Monitor() as monitor:
            process = _start_server(log, evidence=startup_evidence)
            ready_ms = _wait_ready()
            _application_fixture_contract(fixture_contract)
            memory_evidence.append(_memory_evidence("fixture_ready"))
            startup_snapshot = _memory_evidence("application_startup")
            memory_evidence.append(startup_snapshot)
            startup_current = int(startup_snapshot["raw_cgroup_bytes"] or 0)
            summary["phases"]["startup"] = {
                "timestamp": time.time(), "duration_ms": round(ready_ms, 3),
                "memory_current": startup_current,
                "effective_working_set_bytes": startup_snapshot.get(
                    "effective_working_set_bytes"
                ),
                "process_rss_high_water": _rss_high_water(process.pid),
            }
            if not _startup_memory_within_limit(startup_snapshot):
                raise AssertionError(
                    "startup effective working set exceeds 1.2 GiB"
                )
            cold_health = _market_health()
            if int((cold_health.get("cache") or {}).get("build_count") or 0) != 0:
                raise AssertionError("metadata-only health constructed the market")
            padding = _pad_to_production_baseline()
            if archive_warmed:
                archive_before = _memory_evidence("before_coverage")
                memory_evidence.append(archive_before)
                archive_scan = _warm_historical_archive()
                coverage_status, coverage_body, coverage_ms = _request(
                    "/api/history/coverage",
                )
                archive_after = _memory_evidence("after_coverage")
                memory_evidence.append(archive_after)
                try:
                    coverage = json.loads(coverage_body)
                except (TypeError, ValueError, json.JSONDecodeError):
                    coverage = {}
                phases = summary["phases"]
                assert isinstance(phases, dict)
                _record_archive_assessment(
                    phases, archive_before, archive_after,
                    coverage_status=coverage_status, coverage=coverage,
                    duration_ms=coverage_ms, archive_scan=archive_scan,
                )
            before_cold = _cgroup("memory.current")
            health, build_ms, attempts, responsiveness = _cold_build()
            cold_peak = monitor.peak
            summary["phases"]["cold_market"] = {
                "timestamp": time.time(), "duration_ms": round(build_ms, 3), "attempts": attempts,
                "memory_before": before_cold, "memory_current": _cgroup("memory.current"),
                "memory_peak": cold_peak, "build_count": (health.get("cache") or {}).get("build_count"),
                "effective_memory_peak": monitor.effective_peak,
                "generation": (health.get("cache") or {}).get("market_generation"),
                "responsiveness": responsiveness,
            }
            raw_ceiling = RAW_EMERGENCY_MAX if archive_warmed else COLD_MAX
            if cold_peak >= raw_ceiling:
                raise AssertionError(
                    f"cold-build cgroup peak {cold_peak} exceeds {raw_ceiling}"
                )
            if monitor.effective_peak >= COLD_MAX:
                raise AssertionError(
                    f"effective working-set peak {monitor.effective_peak} exceeds 1.5 GiB"
                )
            try:
                latency_result = _latencies()
            except ExpansionLatencyFailure as exc:
                summary["phases"]["warm_requests"] = {
                    "timestamp": time.time(), "latency_ms": {"expansion": exc.result},
                    "memory_current": _cgroup("memory.current"),
                }
                raise
            summary["phases"]["warm_requests"] = {
                "timestamp": time.time(), "latency_ms": latency_result,
                "memory_current": _cgroup("memory.current"),
            }
            if combined_read:
                combined_before = _memory_evidence("combined_read_before")
                memory_evidence.append(combined_before)
                combined_result = _combined_read_audit()
                combined_after = _memory_evidence("combined_read_after")
                memory_evidence.append(combined_after)
                summary["phases"]["combined_read"] = {
                    "timestamp": time.time(), "before": combined_before,
                    "after": combined_after, **combined_result,
                }
                if monitor.effective_peak >= COLD_MAX:
                    raise AssertionError(
                        "combined-read effective working set exceeded the 1.5 GiB ceiling"
                    )
            first_generation = (health.get("cache") or {}).get("market_generation")
            first_build_count = int((health.get("cache") or {}).get("build_count") or 0)
            _baseline_status, baseline_body, _baseline_ms = _request(
                "/api/market/assets?limit=50",
            )
            nonsemantic = _nonsemantic_reuse(
                first_generation, first_build_count, baseline_body,
            )
            summary["phases"]["nonsemantic_reuse"] = {
                "timestamp": time.time(), **nonsemantic,
                "memory_current": _cgroup("memory.current"),
            }
            replacement_started = time.perf_counter()
            before_replacement = _memory_evidence("before_replacement")
            memory_evidence.append(before_replacement)
            if archive_warmed and not _archive_cache_retained(
                before_replacement,
                int((summary["phases"]["archive_warming"])["assessment"][
                    "material_threshold_bytes"
                ]),
            ):
                raise AssertionError(
                    "archive cache was not retained immediately before replacement"
                )
            try:
                replacement, replacement_profile = _replacement_profile(
                    first_generation, first_build_count, baseline_body,
                )
            except ExpansionLatencyFailure as exc:
                summary["phases"]["generation_replacement"] = {
                    "timestamp": time.time(), "profile": exc.result,
                    "memory_current": _cgroup("memory.current"),
                }
                raise
            replacement_ms = (time.perf_counter() - replacement_started) * 1000
            second_generation = (replacement.get("cache") or {}).get("market_generation")
            if second_generation == first_generation:
                raise AssertionError("generation replacement did not publish a new identity")
            artifact = _artifact_state()
            summary["phases"]["generation_replacement"] = {
                "timestamp": time.time(), "duration_ms": round(replacement_ms, 3),
                "attempts": 10, "generation_changed": True,
                "active_generations": artifact["final_artifacts"],
                "artifact": {
                    name: artifact.get(name) for name in (
                        "artifact_name", "size_bytes", "complete", "generation",
                        "generated_at", "schema_version", "asset_count",
                        "temporary_artifacts",
                    )
                },
                "memory_current": _cgroup("memory.current"),
                "profile": replacement_profile,
            }
            memory_evidence.append(_memory_evidence("post_publication"))
            _pre_status, pre_restart_body, _pre_ms = _request(
                "/api/market/assets?limit=50",
            )
            expected_identity = _identity(json.loads(pre_restart_body))
            _stop_server(process)
            process = None
            restart_cycles: list[dict[str, object]] = []
            restart_samples: list[dict[str, object]] = []
            reuse_health: dict[str, object] = {}
            while len(restart_samples) < 10 and len(restart_cycles) < 12:
                process = _start_server(log)
                _wait_ready()
                cycle = _restart_reuse(expected_identity, pre_restart_body)
                restart_cycles.append(cycle)
                restart_samples.extend(cycle["warming_samples"])
                reuse_health = _market_health()
                if (reuse_health.get("cache") or {}).get("market_generation") != second_generation:
                    raise AssertionError("restart reused a different market generation")
                reused_artifact = _artifact_state()
                if reused_artifact.get("artifact_name") != artifact.get("artifact_name"):
                    raise AssertionError("restart reused a different artifact file")
                if reused_artifact.get("generation") != artifact.get("generation"):
                    raise AssertionError("restart reused a different artifact generation")
                if len(restart_samples) < 10:
                    _stop_server(process)
                    process = None
            if len(restart_samples) < 10:
                raise AssertionError(
                    f"only {len(restart_samples)} restart warming samples were captured"
                )
            failed_restart_samples = [
                sample for sample in restart_samples
                if float(sample["server_ms"]) >= 50
                or float(sample["client_ms"]) >= 500
            ]
            if failed_restart_samples:
                summary["phases"]["restart_reuse"] = {
                    "timestamp": time.time(), "cycles": restart_cycles,
                    "warming_samples": restart_samples,
                    "failed_samples": failed_restart_samples,
                    "memory_current": _cgroup("memory.current"),
                }
                if process is not None:
                    _stop_server(process)
                    process = None
                summary["phases"]["response_stack_experiments"] = (
                    _response_stack_experiments(
                        log, expected_identity, pre_restart_body,
                    )
                )
                raise ExpansionLatencyFailure(
                    "restart warming latency gate failed: "
                    f"failed_samples={json.dumps(failed_restart_samples, sort_keys=True)}",
                    {
                        "cycles": restart_cycles,
                        "samples": restart_samples,
                        "failed_samples": failed_restart_samples,
                    },
                )
            restart_server_values = [
                float(sample["server_ms"]) for sample in restart_samples
            ]
            summary["phases"]["restart_reuse"] = {
                "timestamp": time.time(), "cycles": restart_cycles,
                "warming_samples": restart_samples,
                "server_median_ms": round(statistics.median(restart_server_values), 3),
                "server_p95_ms": round(_percentile(restart_server_values, 0.95), 3),
                "server_maximum_ms": round(max(restart_server_values), 3),
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
            summary["completed"] = True
    except BaseException as exc:
        failure = exc
        if isinstance(exc, StartupFailure):
            process = exc.process
            startup_evidence = exc.evidence
        summary["startup_evidence"] = startup_evidence
        summary["errors"] = [{
            **_public_error(exc),
            "phase": next(reversed(summary["phases"]), "initialization"),
        }]
    finally:
        if process is not None:
            try:
                _stop_server(process)
            except BaseException as exc:
                summary["errors"] = [
                    *list(summary.get("errors") or []),
                    {**_public_error(exc), "phase": "cleanup"},
                ]
                summary["passed"] = False
                summary["exit_code"] = 1
                failure = failure or exc
        padding.clear()
        memory_evidence.append(_memory_evidence("post_cleanup"))
        if log_path.is_file():
            sanitized_log = _sanitize_server_log(log_path.read_text(
                encoding="utf-8", errors="replace",
            ))
            log_path.write_text(sanitized_log + ("\n" if sanitized_log else ""), encoding="utf-8")
            summary["server_log"] = {
                "artifact": "server.log", "line_count": len(sanitized_log.splitlines()),
                "bounded": True, "sanitized": True,
            }
        OUTPUT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if failure is not None:
        print(f"{type(failure).__name__}: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
