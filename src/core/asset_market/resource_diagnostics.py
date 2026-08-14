"""Bounded durable resource diagnostics for multi-league Asset Market work."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import psutil

from config import HISTORY_STORAGE_ROOT, PROJECTION_DATABASE_FILE
from src.core.asset_market.read_model import (
    HARD_CGROUP_BYTES, RESERVED_BYTES, TARGET_CGROUP_BYTES,
)

GLOBAL_LIMIT = 100
PER_LEAGUE_LIMIT = 20
DIAGNOSTIC_SCHEMA = "1.1"
REASON_CODES = {
    "admitted": "admitted",
    "memory_event_advanced": "oom_event_advanced",
    "raw_emergency_boundary": "raw_emergency_boundary",
    "hard_cgroup_pressure": "hard_cgroup_pressure",
    "observed_growth_exceeded_estimate": "stage_growth_exceeded",
    "predicted_effective_usage_exceeds_target": "predicted_effective_ceiling",
    "browser_overlap_guard": "browser_overlap_guard",
    "shutdown": "shutdown",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitized_league_id(league_id: str) -> str:
    return hashlib.sha256(str(league_id).encode()).hexdigest()[:16]


def browser_process_count() -> int:
    count = 0
    try:
        for process in psutil.process_iter(["name"]):
            name = str(process.info.get("name") or "").casefold()
            if any(token in name for token in ("chromium", "chrome", "playwright")):
                count += 1
    except (psutil.Error, OSError):
        return -1
    return count


def diagnostic_deep_size(value: Any, *, object_limit: int = 100_000) -> dict[str, Any]:
    """Bounded deterministic approximation used only by explicit diagnostics."""
    pending = [value]
    seen: set[int] = set()
    total = 0
    while pending and len(seen) < object_limit:
        item = pending.pop()
        identity = id(item)
        if identity in seen:
            continue
        seen.add(identity)
        total += sys.getsizeof(item)
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple, set, frozenset)):
            pending.extend(item)
        elif hasattr(item, "__dict__") and not callable(item):
            pending.append(vars(item))
        else:
            slots = getattr(type(item), "__slots__", ())
            for name in slots if isinstance(slots, tuple) else (slots,):
                if name and hasattr(item, name):
                    pending.append(getattr(item, name))
    return {
        "bytes": total,
        "objects": len(seen),
        "truncated": bool(pending),
        "object_limit": object_limit,
    }


class ResourceDiagnostics:
    """Atomic JSON journal with deterministic global/per-league retention."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or HISTORY_STORAGE_ROOT)
        self.path = self.root / ".asset-market-admission-history.json"
        self._lock = RLock()

    def _read(self, path: Path | None = None) -> list[dict[str, Any]]:
        source = path or self.path
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return []
        rows = payload.get("decisions") if isinstance(payload, dict) else None
        return [row for row in (rows or []) if isinstance(row, dict)]

    @staticmethod
    def _bounded(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        per_league: dict[str, int] = {}
        retained: list[dict[str, Any]] = []
        for row in reversed(rows):
            league = str(row.get("league") or "unknown")
            if per_league.get(league, 0) >= PER_LEAGUE_LIMIT:
                continue
            per_league[league] = per_league.get(league, 0) + 1
            retained.append(row)
            if len(retained) >= GLOBAL_LIMIT:
                break
        return list(reversed(retained))

    def record(
        self, league_id: str, stage: str, admission: dict[str, Any], *,
        context: dict[str, Any] | None = None, root: Path | None = None,
    ) -> dict[str, Any]:
        current = admission.get("raw_cgroup_bytes")
        source_reason = str(admission.get("reason") or "other")
        reason = REASON_CODES.get(source_reason, "other")
        safe_context = dict(context or {})
        safe_context.pop("league_id", None)
        safe_context.pop("path", None)
        record = {
            "schema_version": DIAGNOSTIC_SCHEMA,
            "timestamp": _utcnow(),
            "league": sanitized_league_id(league_id),
            "stage": stage,
            "admitted": bool(admission.get("admitted")),
            "rejection_reason": (
                None if admission.get("admitted") else reason
            ),
            "reason": reason,
            "source_reason": source_reason,
            "memory_current": current,
            "inactive_file": admission.get("inactive_file_bytes"),
            "effective_working_set": admission.get("effective_working_set_bytes"),
            "process_rss": psutil.Process().memory_info().rss,
            "cgroup_limit": (context or {}).get("cgroup_limit_bytes"),
            "raw_emergency_boundary": HARD_CGROUP_BYTES,
            "raw_boundary_margin": (
                HARD_CGROUP_BYTES - current if isinstance(current, int) else None
            ),
            "effective_safe_ceiling": admission.get("target_ceiling_bytes"),
            "required_reserve": RESERVED_BYTES,
            "target_effective_ceiling": TARGET_CGROUP_BYTES,
            "stage_estimate": admission.get("stage_estimate_bytes"),
            "predicted_effective_peak": admission.get("predicted_effective_bytes"),
            "reclaimable_allowance": admission.get("reclaimable_allowance_bytes"),
            "hard_pressure_margin": admission.get("hard_pressure_margin_bytes"),
            "hard_pressure_ceiling": admission.get("hard_pressure_ceiling_bytes"),
            "predicted_hard_pressure_peak": admission.get(
                "predicted_hard_pressure_bytes"
            ),
            "effective_headroom": admission.get("effective_headroom_bytes"),
            "memory_events": dict(safe_context.get("cgroup_memory_events") or {}),
            "memory_event_deltas": dict(admission.get("memory_event_deltas") or {}),
            "browser_process_count": browser_process_count(),
            "context": safe_context,
        }
        target_root = Path(root or self.root)
        target = target_root / self.path.name
        with self._lock:
            rows = self._bounded([*self._read(target), record])
            target_root.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            try:
                temporary.write_text(json.dumps({
                    "schema_version": DIAGNOSTIC_SCHEMA, "decisions": rows,
                }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                with temporary.open("r+b") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return record

    def health(self) -> dict[str, Any]:
        with self._lock:
            rows = self._read()
        rejected = [row for row in rows if not row.get("admitted")]
        latest_by_league: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest_by_league[str(row.get("league"))] = row
        return {
            "retention": {"global": GLOBAL_LIMIT, "per_league": PER_LEAGUE_LIMIT},
            "count": len(rows),
            "latest": rows[-1] if rows else None,
            "latest_rejection": rejected[-1] if rejected else None,
            "latest_by_league": latest_by_league,
        }


def runtime_component_sizes(runtime: Any) -> dict[str, Any]:
    """Explicit diagnostic-only retained-size attribution."""
    data = runtime.state.get("data") or {}
    components = {
        "player_catalog": data.get("players") or {},
        "normalized_players": data.get("normalized_players") or {},
        "settings": {
            "scoring": data.get("scoring_settings") or {},
            "league": data.get("league_settings") or {},
            "nfl": data.get("nfl_state") or {},
        },
        "rosters": data.get("teams") or [],
        "picks": data.get("pick_ledger") or [],
        "matchups": data.get("matchups") or {},
        "transactions": data.get("transactions") or [],
        "provider_metadata": data.get("market_data") or {},
        "projection": runtime.projection_context,
        "brain": runtime.brain_context,
        "fois": runtime.fois_context,
        "market": runtime.market_context,
        "generic_cache": runtime.cache_metadata,
    }
    sizes = {name: diagnostic_deep_size(value) for name, value in components.items()}
    classification = {
        "player_catalog": "candidate-for-sharing",
        "normalized_players": "candidate-for-sharing",
        "settings": "league-specific", "rosters": "league-specific",
        "picks": "league-specific", "matchups": "league-specific",
        "transactions": "league-specific", "provider_metadata": "candidate-for-sharing",
        "projection": "league-specific", "brain": "league-specific",
        "fois": "shared", "market": "league-specific", "generic_cache": "league-specific",
    }
    return {
        "league": sanitized_league_id(runtime.league_id),
        "components": {
            name: {**sizes[name], "classification": classification[name]}
            for name in sizes
        },
        "total_component_bytes": sum(row["bytes"] for row in sizes.values()),
        "measurement": "diagnostic_approximate_deep_size",
    }


def disk_health(history_database: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(history_database.parent)
    projection = Path(PROJECTION_DATABASE_FILE)
    artifacts = list(history_database.parent.glob(
        f".{history_database.stem}.asset-market-*.sqlite3"
    ))
    active: set[str] = set()
    per_league: dict[str, int] = {}
    for manifest in history_database.parent.glob(
        f".{history_database.stem}.asset-market-manifest*.json"
    ):
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            name = str(payload.get("artifact") or "")
            candidate = history_database.parent / name
            if (
                name == Path(name).name and candidate.is_file()
                and candidate.stat().st_size == int(payload.get("size") or -1)
            ):
                active.add(name)
                suffix = manifest.stem.rsplit("manifest", maxsplit=1)[-1].lstrip("-")
                per_league[suffix or "legacy"] = per_league.get(suffix or "legacy", 0) + 1
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    active_artifacts = [path for path in artifacts if path.name in active]
    stale_artifacts = [path for path in artifacts if path.name not in active]
    free_ratio = usage.free / usage.total if usage.total else 0.0
    status = "critical" if free_ratio < 0.10 else "warning" if free_ratio < 0.20 else "healthy"
    return {
        "status": status,
        "thresholds": {"warning_free_ratio": 0.20, "critical_free_ratio": 0.10},
        "disk": {"total": usage.total, "used": usage.used, "free": usage.free},
        "historical_database_bytes": history_database.stat().st_size if history_database.exists() else 0,
        "projection_database_bytes": projection.stat().st_size if projection.exists() else 0,
        "market_artifact_count": len(artifacts),
        "market_artifact_bytes": sum(path.stat().st_size for path in artifacts),
        "market_artifacts": {
            "active_count": len(active_artifacts),
            "active_bytes": sum(path.stat().st_size for path in active_artifacts),
            "stale_count": len(stale_artifacts),
            "stale_bytes": sum(path.stat().st_size for path in stale_artifacts),
            "per_league_manifest_count": per_league,
        },
        "artifact_storage_models": {
            str(leagues): {
                "league_count": leagues,
                "estimated_bytes": round(
                    (sum(path.stat().st_size for path in artifacts) / len(artifacts))
                    * leagues,
                ) if artifacts else 0,
                "excludes_historical_growth": True,
            }
            for leagues in (30, 100, 300)
        },
    }


resource_diagnostics = ResourceDiagnostics()
