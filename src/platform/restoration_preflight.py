"""Read-only, bounded cache-restoration resource observations.

The caller supplies the already-running application's providers and enforces
operator authorization and league scope before calling this module.  A positive
answer is not a lease, a payload validation, or permission to skip admission.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any, Callable, Iterator

from src.platform.cache_budget import JSON_BUDGET
from src.platform.cache_restoration_admission import restoration_admission

MAX_PARENT_COMPONENTS = 32
_HEAVY_FLAGS = ("fois_generation", "trade_search", "historical_response",
                "market_critical", "market_build_active")
_MEMORY_FIELDS = ("cgroup_current_bytes", "cgroup_limit_bytes",
                  "cgroup_inactive_file_bytes", "cgroup_anonymous_bytes",
                  "rss_bytes", "vms_bytes")
_EVENT_FIELDS = ("low", "high", "max", "oom", "oom_kill", "oom_group_kill")


class _MetadataProblem(Exception):
    def __init__(self, reason: str, *, applicable: bool | None, exists: bool | None = None):
        self.reason = reason
        self.applicable = applicable
        self.exists = exists


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _boolean(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _finite_nonnegative(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _supports_pinning() -> bool:
    return (sys.platform.startswith("linux")
            and all(hasattr(os, name) for name in ("O_PATH", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"))
            and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and os.stat in os.supports_follow_symlinks)


def _open_parent(path: Path, check: Callable[[], None]) -> int:
    """Pin one bounded no-follow directory chain; caller owns the returned fd."""
    components = path.parent.parts
    if (not path.is_absolute() or len(components) - 1 > MAX_PARENT_COMPONENTS
            or any(part in {".", ".."} for part in components)):
        raise _MetadataProblem("cache_parent_unverified", applicable=None)
    parent = None
    try:
        check()
        parent = os.open(path.anchor, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        for component in components[1:]:
            check()
            following = os.open(component, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=parent)
            previous, parent = parent, following
            os.close(previous)
        result, parent = parent, None
        return result
    finally:
        if parent is not None:
            os.close(parent)


@contextmanager
def _pinned_cache(path: Path, check: Callable[[], None]) -> Iterator[tuple[int, int, str, os.stat_result]]:
    """Never read-open a leaf which may race into a FIFO or device."""
    if not _supports_pinning():
        raise _MetadataProblem("safe_metadata_handle_unsupported", applicable=None)
    path = path.absolute()  # Lexical only; never resolve/follow a symlink.
    if not path.name or path.name in {".", ".."}:
        raise _MetadataProblem("cache_path_unavailable", applicable=None)
    parent = leaf = None
    try:
        try:
            parent = _open_parent(path, check)
            check()
            leaf = os.open(path.name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            observed = os.fstat(leaf)
            if stat.S_ISLNK(observed.st_mode):
                raise _MetadataProblem("cache_symlink", applicable=False, exists=True)
            if not stat.S_ISREG(observed.st_mode):
                raise _MetadataProblem("cache_not_regular", applicable=False, exists=True)
        except FileNotFoundError:
            raise _MetadataProblem("cache_missing", applicable=False, exists=False) from None
        except (NotADirectoryError, PermissionError, OSError):
            raise _MetadataProblem("cache_metadata_unavailable", applicable=None) from None
        yield parent, leaf, path.name, observed
    finally:
        if leaf is not None:
            os.close(leaf)
        if parent is not None:
            os.close(parent)


def _revalidate(path: Path, parent: int, leaf: int, name: str, original: os.stat_result,
                check: Callable[[], None]) -> bool:
    check()
    current_parent = None
    try:
        current_parent = _open_parent(path.absolute(), check)
        parent_before, parent_after = os.fstat(parent), os.fstat(current_parent)
        if (parent_before.st_dev, parent_before.st_ino) != (parent_after.st_dev, parent_after.st_ino):
            return False
        descriptor = os.fstat(leaf)
        entry = os.stat(name, dir_fd=current_parent, follow_symlinks=False)
    except (OSError, _MetadataProblem):
        return False
    finally:
        if current_parent is not None:
            os.close(current_parent)
    return (_signature(original) == _signature(descriptor) == _signature(entry)
            and stat.S_ISREG(entry.st_mode))


def _cache_metadata(observed: os.stat_result) -> dict[str, Any]:
    age = time.time() - observed.st_mtime
    valid_age = math.isfinite(age)
    eligible = (valid_age and 0 <= age <= JSON_BUDGET.maximum_age_seconds
                and 0 <= observed.st_size <= JSON_BUDGET.maximum_entry_bytes)
    return {"exists": True, "regular_file": True, "size_bytes": observed.st_size,
            "modified_at_unix_ns": observed.st_mtime_ns,
            "age_seconds": round(age, 6) if valid_age else None,
            "age_scope": "file_modification_time_only",
            "retention_eligible": bool(eligible), "generation_pinned": True,
            "path_matches_pinned_generation_at_end": None,
            "payload_readability": "not_checked", "content_compatibility": "not_evaluated"}


def _identity(provider: Callable[[], Any]) -> dict[str, Any]:
    value = provider()
    value = value if isinstance(value, dict) else {}
    version, commit = value.get("version"), value.get("commit")
    return {"application": "DTOS" if value.get("application") == "DTOS" else None,
            "version": version if isinstance(version, str) and len(version) <= 32
            and re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", version) else None,
            "build": _integer(value.get("build")),
            "commit": commit if isinstance(commit, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", commit) else None,
            "ready": _boolean(value.get("ready"))}


def _resident(provider: Callable[[str], Any], league_id: str) -> dict[str, Any]:
    value = provider(league_id)
    value = value if isinstance(value, dict) else {}
    state = value.get("status")
    cooldown = _finite_nonnegative(value.get("cooldown_remaining_seconds"))
    valid = value.get("cooldown_valid") is True and cooldown is not None
    return {"resident": _boolean(value.get("resident")),
            "status": state if state in {"cold", "hydrating", "warm", "failed", "deferred", "evicting", "closed"} else None,
            "cooldown_remaining_seconds": cooldown if valid else None, "cooldown_valid": valid}


def restoration_preflight(
    league_id: str, *, cache_path: Callable[[str], Path],
    lifecycle_snapshot: Callable[[], Any], resident_metadata: Callable[[str], Any],
    deployment_identity: Callable[[], Any], fois_working_bytes: int, fois_safety_bytes: int,
    check_budget: Callable[[], None] = lambda: None,
) -> dict[str, Any]:
    """Observe one authorized cache. The router owns authorization and scope."""
    check_budget()
    report: dict[str, Any] = {
        "schema_version": "restoration-preflight-v1", "observation_started_at": _utcnow(),
        "observation_completed_at": None, "league_id": league_id,
        "advisory_only": True, "non_atomic": True, "recheck_required": True,
        "assessment_scope": "saved_cache_resource_and_coordination_admission_only",
        "process": {"pid": os.getpid(), "lifecycle_scope": "serving_process_only",
                    "other_worker_idleness": "not_established"},
        "deployment": _identity(deployment_identity),
        "runtime": _resident(resident_metadata, league_id),
        "cache": {"exists": None, "regular_file": None, "size_bytes": None,
                  "modified_at_unix_ns": None, "age_seconds": None,
                  "retention_eligible": None, "generation_pinned": False,
                  "path_matches_pinned_generation_at_end": None,
                  "payload_readability": "not_checked", "content_compatibility": "not_evaluated"},
        "lifecycle": {}, "memory": {}, "capacity": {}, "unknown_fields": [],
        "verdict": "unknown", "reason": "observation_unavailable",
    }
    problem = None

    def observe() -> None:
        check_budget()
        observed = lifecycle_snapshot()
        observed = observed if isinstance(observed, dict) else {}
        available = observed.get("available") is True
        work = observed.get("heavy_work")
        work = work if isinstance(work, dict) else {}
        flags = {key: _boolean(work.get(key)) for key in _HEAVY_FLAGS}
        phase = observed.get("phase")
        report["lifecycle"] = {
            "available": available,
            "phase": phase if isinstance(phase, str) and re.fullmatch(r"[a-z_]{1,64}", phase) else None,
            "heavy_work": flags,
            "cache_lease_conflict": _boolean(observed.get("cache_lease_conflict")) if available else None,
        }
        memory = observed.get("memory")
        memory = memory if isinstance(memory, dict) else {}
        safe = {key: _integer(memory.get(key)) for key in _MEMORY_FIELDS}
        scope = memory.get("memory_accounting_scope")
        safe["memory_accounting_scope"] = scope if scope in {"cgroup", "windows_job_commit"} else None
        safe["scope"] = "shared_container" if scope == "cgroup" else "shared_job" if scope == "windows_job_commit" else "unknown"
        events = memory.get("cgroup_memory_events")
        safe["memory_events"] = {key: _integer(events.get(key)) for key in _EVENT_FIELDS} if isinstance(events, dict) else None
        report["memory"] = safe
        raw = dict(memory)  # Admission validates the actual types, not sanitized substitutes.
        report["capacity"] = restoration_admission(
            report["cache"]["size_bytes"], raw, flags["fois_generation"] if available else None,
            fois_working_bytes=fois_working_bytes, fois_safety_bytes=fois_safety_bytes,
        )

    try:
        check_budget()
        selected_path = Path(cache_path(league_id))
        with _pinned_cache(selected_path, check_budget) as pinned:
            parent, leaf, name, before = pinned
            report["cache"] = _cache_metadata(before)
            observe()
            stable = _revalidate(selected_path, parent, leaf, name, before, check_budget)
            report["cache"]["path_matches_pinned_generation_at_end"] = stable
            if not stable:
                problem = _MetadataProblem("cache_changed_during_observation", applicable=None, exists=True)
            elif not report["cache"]["retention_eligible"]:
                problem = _MetadataProblem("cache_retention_ineligible", applicable=False, exists=True)
    except _MetadataProblem as exc:
        problem = exc
        report["cache"]["exists"] = exc.exists
        observe()

    life, capacity, runtime = report["lifecycle"], report["capacity"], report["runtime"]
    unknown = report["unknown_fields"]
    for key in _MEMORY_FIELDS:
        if report["memory"].get(key) is None:
            unknown.append("memory." + key)
    if not life.get("available"):
        unknown.append("lifecycle")
    if life.get("cache_lease_conflict") is None:
        unknown.append("lifecycle.cache_lease_conflict")
    if not capacity["reservation_valid"]:
        unknown.append("lifecycle.heavy_work.fois_generation")
    if not runtime["cooldown_valid"]:
        unknown.append("runtime.cooldown")
    if report["cache"]["size_bytes"] is None:
        unknown.append("cache.metadata")
    if problem is not None:
        report["verdict"] = "restoration_not_applicable" if problem.applicable is False else "unknown"
        report["reason"] = problem.reason
    elif runtime["cooldown_valid"] and runtime["cooldown_remaining_seconds"] > 0:
        report.update(verdict="would_defer", reason="retry_cooldown_active")
    elif life.get("cache_lease_conflict") is True:
        report.update(verdict="would_defer", reason="heavyweight_lease_conflict")
    elif not life.get("available") or life.get("cache_lease_conflict") is None:
        report.update(verdict="unknown", reason="lifecycle_unavailable")
    elif not runtime["cooldown_valid"]:
        report.update(verdict="unknown", reason="runtime_metadata_unavailable")
    elif capacity["would_admit"] is None:
        report.update(verdict="unknown", reason=capacity["reason"])
    elif capacity["would_admit"]:
        report.update(verdict="would_admit", reason=capacity["reason"])
    else:
        report.update(verdict="would_defer", reason=capacity["reason"])
    check_budget()
    report["observation_completed_at"] = _utcnow()
    return report
