"""Durable, bounded Live Visual Inspection read model and capture queue."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.inspection.live import LiveInspection, external_mirror_policy, matchup_semantic
from src.platform.lifecycle import lifecycle_coordinator

LIVE_VISUAL_SCHEMA_VERSION = "1.0"
LIVE_VIEWPORTS = {
    "mobile": {"width": 390, "height": 844},
    "desktop": {"width": 1440, "height": 1000},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "-" for char in value)


@dataclass(frozen=True)
class CaptureRequest:
    surface_id: str
    title: str
    human_url: str
    semantic_url: str
    viewport: str
    fingerprint: str
    canonical: dict[str, Any]


class LiveVisualService:
    """Single-flight durable screenshot service; HTTP reads never launch browsers."""

    def __init__(
        self, root: Path, capture: Callable[[CaptureRequest, Path], dict[str, Any]] | None = None,
        *, start_grace_seconds: float = 0.0,
    ) -> None:
        self.root = root
        self._capture = capture
        self._start_grace_seconds = max(0.0, float(start_grace_seconds))
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._queue: list[CaptureRequest] = []
        self._active: str | None = None
        self._browser_processes = 0
        self._last_error: str | None = None
        self._deferred_captures = 0
        self._required_keys: set[str] = set()
        self._requests: dict[str, CaptureRequest] = {}
        self._refresh_keys: set[str] = set()
        self._refresh_counts = {
            "refresh_requested": 0, "refresh_started": 0,
            "refresh_succeeded": 0, "refresh_failed": 0,
            "refresh_deduped": 0,
        }
        self._last_refresh: dict[str, Any] | None = None
        self._completed_callback: Callable[[], None] | None = None
        self._attempts: dict[tuple[str, str], int] = {}
        self._capture_started_at: float | None = None
        self._capture_finished_at: float | None = None
        self._telemetry = {
            "captures_started": 0, "captures_completed": 0,
            "captures_failed": 0, "capture_attempt_failures": 0,
            "captures_retried": 0,
            "capture_worker_count": 0, "capture_worker_peak": 0,
            "browser_process_peak": 0, "capture_worker_rss_peak_bytes": 0,
            "browser_rss_peak_bytes": 0,
            "last_capture_worker_pid": None,
            "capture_process_nice": None,
            "capture_tree_nice_min": None,
            "available_cpu_count": None, "capture_cpu_count": None,
        }
        self._manifest = self._load_manifest()

    def on_complete(self, callback: Callable[[], None]) -> None:
        """Publish a derived read model only after a complete capture flight."""
        with self._lock:
            self._completed_callback = callback

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def _load_manifest(self) -> dict[str, Any]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": LIVE_VISUAL_SCHEMA_VERSION, "captures": {}}
        return value if isinstance(value, dict) else {"schema_version": LIVE_VISUAL_SCHEMA_VERSION, "captures": {}}

    def _write_manifest(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._manifest, sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)

    @staticmethod
    def capture_key(surface_id: str, viewport: str) -> str:
        return f"{_safe_id(surface_id)}--{viewport}"

    def schedule(self, requests: Iterable[CaptureRequest]) -> int:
        """Deduplicate by surface, viewport, and semantic presentation fingerprint."""
        if self._capture is None:
            return 0
        with self._lock:
            pending = {(row.surface_id, row.viewport, row.fingerprint) for row in self._queue}
            added = 0
            for request in requests:
                key = self.capture_key(request.surface_id, request.viewport)
                self._required_keys.add(key)
                self._requests[key] = request
                current = (self._manifest.get("captures") or {}).get(key) or {}
                identity = (request.surface_id, request.viewport, request.fingerprint)
                if (
                    current.get("status") == "current"
                    and current.get("fingerprint") == request.fingerprint
                ) or identity in pending or self._active == key:
                    continue
                self._queue.append(request)
                pending.add(identity)
                added += 1
            if self._queue and not (self._worker and self._worker.is_alive()):
                self._capture_started_at = time.monotonic()
                self._capture_finished_at = None
                self._worker = threading.Thread(target=self._run, name="dtos-live-visual", daemon=True)
                self._telemetry["capture_worker_count"] = 1
                self._telemetry["capture_worker_peak"] = max(
                    self._telemetry["capture_worker_peak"], 1,
                )
                self._worker.start()
            return added

    def refresh(self, surface_id: str, viewport: str) -> dict[str, Any] | None:
        """Request one registered stale/missing capture without duplicating current work."""
        key = self.capture_key(surface_id, viewport)
        with self._lock:
            request = self._requests.get(key)
            current = (self._manifest.get("captures") or {}).get(key)
            if request is None:
                return dict(current) if current else None
            self._refresh_counts["refresh_requested"] += 1
            prior_state = (current or {}).get("status", "missing")
            self._last_refresh = {
                "target_capture_id": key, "prior_state": prior_state,
                "queue_result": "pending", "requested_at": _now(),
            }
            if (
                current
                and current.get("status") == "current"
                and current.get("fingerprint") == request.fingerprint
            ):
                self._refresh_counts["refresh_deduped"] += 1
                self._last_refresh["queue_result"] = "deduped_current"
                return dict(current)
            self._refresh_keys.add(key)
        added = self.schedule((request,))
        with self._lock:
            if self._last_refresh and self._last_refresh.get("target_capture_id") == key:
                self._last_refresh["queue_result"] = "queued" if added else "deduped_pending"
                if not added:
                    self._refresh_counts["refresh_deduped"] += 1
            row = (self._manifest.get("captures") or {}).get(key)
            return dict(row) if row else None

    def _run(self) -> None:
        if self._start_grace_seconds:
            time.sleep(self._start_grace_seconds)
        while True:
            if not lifecycle_coordinator.visual_capture_allowed():
                with self._lock:
                    self._deferred_captures += 1
                lifecycle_coordinator.defer_visual_capture()
                lifecycle_coordinator.wait_for_visual_capture()
                continue
            with self._lock:
                if not self._queue:
                    self._active = None
                    self._browser_processes = 0
                    self._telemetry["capture_worker_count"] = 0
                    self._capture_finished_at = time.monotonic()
                    callback = self._completed_callback
                    completed = True
                else:
                    callback = None
                    completed = False
                    request = self._queue.pop(0)
                    self._active = self.capture_key(request.surface_id, request.viewport)
                    refresh = self._active in self._refresh_keys
                    if refresh:
                        self._refresh_counts["refresh_started"] += 1
                        if self._last_refresh and self._last_refresh.get("target_capture_id") == self._active:
                            self._last_refresh["worker_started_at"] = _now()
                    self._browser_processes = 0
            if completed:
                if callback is not None:
                    try:
                        callback()
                    except Exception as exc:
                        with self._lock:
                            self._last_error = f"{type(exc).__name__}: visual publication failed"
                return
            folder = self.root / "captures" / _safe_id(request.surface_id)
            folder.mkdir(parents=True, exist_ok=True)
            final = folder / f"{request.viewport}.png"
            temporary = folder / f".{request.viewport}.partial.png"
            backup = folder / f".{request.viewport}.previous.png"
            capture_completed = False
            try:
                with lifecycle_coordinator.phase("live_visual_capture") as phase:
                    with self._lock:
                        self._browser_processes = 1
                        self._telemetry["captures_started"] += 1
                        self._telemetry["browser_process_peak"] = max(
                            self._telemetry["browser_process_peak"], 1,
                        )
                    try:
                        result = self._capture(request, temporary) if self._capture else {}
                        capture_completed = True
                    finally:
                        with self._lock:
                            self._browser_processes = 0
                    phase.update({
                        "surface_id": request.surface_id,
                        "viewport": request.viewport,
                        "browser_processes": 1,
                    })
                if not temporary.is_file() or temporary.stat().st_size <= 0:
                    raise RuntimeError("capture artifact is missing or empty")
                artifact_hash = hashlib.sha256(temporary.read_bytes()).hexdigest()
                deployment = deployment_metadata()
                row = {
                    "surface_id": request.surface_id, "title": request.title,
                    "human_url": request.human_url, "semantic_url": request.semantic_url,
                    "viewport": request.viewport, "status": "current",
                    "captured_at": _now(), "data_as_of": request.canonical.get("data_as_of"),
                    "fingerprint": request.fingerprint,
                    "screenshot_url": f"/api/inspect/live/visual/captures/{_safe_id(request.surface_id)}/{request.viewport}.png",
                    "metadata_url": f"/api/inspect/live/visual/metadata/{_safe_id(request.surface_id)}/{request.viewport}",
                    "application_version": VERSION, "application_build": BUILD_NUMBER,
                    "commit": deployment.get("commit"), "canonical": request.canonical,
                    "presentation": {
                        key: value for key, value in result.items()
                        if key != "capture_process"
                    },
                    "artifact_hash": artifact_hash,
                }
                with self._lock:
                    key = self.capture_key(request.surface_id, request.viewport)
                    process_metrics = result.get("capture_process") or {}
                    self._telemetry["capture_worker_rss_peak_bytes"] = max(
                        self._telemetry["capture_worker_rss_peak_bytes"],
                        int(process_metrics.get("worker_rss_peak_bytes") or 0),
                    )
                    self._telemetry["browser_rss_peak_bytes"] = max(
                        self._telemetry["browser_rss_peak_bytes"],
                        int(process_metrics.get("browser_rss_peak_bytes") or 0),
                    )
                    self._telemetry["browser_process_peak"] = max(
                        self._telemetry["browser_process_peak"],
                        int(process_metrics.get("browser_process_peak") or 1),
                    )
                    self._telemetry["last_capture_worker_pid"] = (
                        int(process_metrics.get("worker_pid"))
                        if process_metrics.get("worker_pid") is not None else None
                    )
                    self._telemetry["capture_process_nice"] = process_metrics.get(
                        "process_nice"
                    )
                    self._telemetry["capture_tree_nice_min"] = process_metrics.get(
                        "capture_tree_nice_min"
                    )
                    self._telemetry["available_cpu_count"] = process_metrics.get(
                        "available_cpu_count"
                    )
                    self._telemetry["capture_cpu_count"] = process_metrics.get(
                        "capture_cpu_count"
                    )
                    self._telemetry["captures_completed"] += 1
                    self._attempts.pop((key, request.fingerprint), None)
                    previous = (self._manifest.get("captures") or {}).get(key)
                    if final.exists():
                        final.replace(backup)
                    temporary.replace(final)
                    self._manifest.setdefault("captures", {})[key] = row
                    self._manifest.update({"schema_version": LIVE_VISUAL_SCHEMA_VERSION, "updated_at": _now()})
                    self._last_error = None
                    try:
                        self._write_manifest()
                    except Exception:
                        if previous is None:
                            self._manifest.get("captures", {}).pop(key, None)
                        else:
                            self._manifest.setdefault("captures", {})[key] = previous
                        final.unlink(missing_ok=True)
                        if backup.exists():
                            backup.replace(final)
                        raise
                    backup.unlink(missing_ok=True)
                    if refresh:
                        self._refresh_counts["refresh_succeeded"] += 1
                        self._refresh_keys.discard(key)
                        if self._last_refresh and self._last_refresh.get("target_capture_id") == key:
                            self._last_refresh.update({
                                "worker_completed_at": _now(), "final_state": "current",
                                "artifact_hash": artifact_hash,
                            })
            except Exception as exc:  # last valid capture must survive
                temporary.unlink(missing_ok=True)
                backup.unlink(missing_ok=True)
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: capture failed"
                    key = self.capture_key(request.surface_id, request.viewport)
                    attempt_key = (key, request.fingerprint)
                    attempts = self._attempts.get(attempt_key, 0)
                    self._telemetry["capture_attempt_failures"] += 1
                    if not capture_completed and attempts < 1:
                        self._attempts[attempt_key] = attempts + 1
                        self._queue.append(request)
                        self._telemetry["captures_retried"] += 1
                    else:
                        self._telemetry["captures_failed"] += 1
                    current = (self._manifest.get("captures") or {}).get(key)
                    if current:
                        current["status"] = "stale"
                        current["failure_reason"] = self._last_error
                        current["stale_reason"] = "other"
                    if refresh:
                        self._refresh_counts["refresh_failed"] += 1
                        self._refresh_keys.discard(key)
                        if self._last_refresh and self._last_refresh.get("target_capture_id") == key:
                            self._last_refresh.update({
                                "worker_completed_at": _now(), "final_state": "stale",
                            })
                    self._write_manifest()

    def capture(self, surface_id: str, viewport: str) -> dict[str, Any] | None:
        with self._lock:
            row = (self._manifest.get("captures") or {}).get(self.capture_key(surface_id, viewport))
            return dict(row) if row else None

    def screenshot(self, surface_id: str, viewport: str) -> Path | None:
        row = self.capture(surface_id, viewport)
        if not row:
            return None
        path = self.root / "captures" / _safe_id(surface_id) / f"{viewport}.png"
        return path if path.is_file() else None

    def manifest(self) -> dict[str, Any]:
        with self._lock:
            rows = list((self._manifest.get("captures") or {}).values())
            return {
                "status": "complete" if rows and not self._queue and not self._active else "pending",
                "schema_version": LIVE_VISUAL_SCHEMA_VERSION,
                "captures": rows, "capture_count": len(rows),
                "current": sum(row.get("status") == "current" for row in rows),
                "stale": sum(row.get("status") == "stale" for row in rows),
                "pending": len(self._queue) + int(self._active is not None),
                "failures": int(self._last_error is not None),
                "last_capture": self._manifest.get("updated_at"),
            }

    def health(self, required: int = 0) -> dict[str, Any]:
        manifest = self.manifest()
        required = max(required, len(self._required_keys))
        completed = manifest["capture_count"]
        current = manifest["current"]
        return {
            "status": "complete" if completed >= required and manifest["pending"] == 0 else "pending",
            "eligible_surfaces": required // len(LIVE_VIEWPORTS) if required else 0,
            "required_captures": required, "completed": completed,
            "current": current, "missing": max(0, required - completed),
            "stale": manifest["stale"], "pending": manifest["pending"],
            "failures": manifest["failures"], "browser_processes": self._browser_processes,
            "last_capture": manifest["last_capture"], "last_error": self._last_error,
            "deferred_captures": self._deferred_captures,
            "defer_reason": (
                "market_critical" if not lifecycle_coordinator.visual_capture_allowed()
                else None
            ),
            "read_only_requests": True, "single_browser_worker": True,
            **self._refresh_counts,
            "last_refresh": dict(self._last_refresh) if self._last_refresh else None,
            "stale_reasons": {
                key: row.get("stale_reason", "other")
                for key, row in (self._manifest.get("captures") or {}).items()
                if row.get("status") == "stale"
            },
            "capture_generation": VERSION,
            "candidate_state": "capturing" if manifest["pending"] else (
                "failed" if manifest["failures"] or manifest["stale"] else "complete"
            ),
            "capture_elapsed_ms": round(
                ((self._capture_finished_at or time.monotonic()) - self._capture_started_at) * 1000,
                3,
            ) if self._capture_started_at is not None else 0.0,
            **self._telemetry,
        }

    def wait(self, timeout: float = 10) -> bool:
        """Testing and shutdown boundary; HTTP routes never call this."""
        worker = self._worker
        if worker:
            worker.join(timeout)
        return not bool(worker and worker.is_alive())


def matchup_capture_requests(data: dict[str, Any], semantic: Callable[[str], dict[str, Any] | None], identity: dict[str, Any]) -> tuple[CaptureRequest, ...]:
    """Build mandatory current-matchup requests from canonical semantic output."""
    requests = []
    for matchup_id in sorted((data.get("matchups") or {}), key=lambda value: int(value)):
        contract = semantic(str(matchup_id))
        if contract is None:
            continue
        relevant = {"teams": contract.get("teams"), "status": contract.get("status")}
        canonical = {
            "data_as_of": identity.get("inspection_generated_at"),
            "projection_snapshot_id": identity.get("projection_snapshot_id"),
            "brain_snapshot_id": identity.get("brain_snapshot_id"),
            "market_generation": identity.get("asset_market_generation"),
        }
        for viewport in LIVE_VIEWPORTS:
            requests.append(CaptureRequest(
                surface_id=f"matchups-{matchup_id}", title=f"Matchup {matchup_id}",
                human_url=f"/matchups/{matchup_id}",
                semantic_url=f"/api/inspect/live/matchups/{matchup_id}",
                viewport=viewport, fingerprint=_digest({"contract": relevant, "viewport": viewport, "version": VERSION}),
                canonical=canonical,
            ))
    return tuple(requests)


def live_visual_capture_requests(inspector: LiveInspection) -> tuple[CaptureRequest, ...]:
    """Derive core and current-matchup captures from canonical registration."""
    identity = inspector.identity()
    requests = list(matchup_capture_requests(
        inspector.data,
        lambda matchup_id: matchup_semantic(
            inspector.data, matchup_id, inspector.projection_snapshot,
        ),
        identity,
    ))
    seen = {request.surface_id for request in requests}
    for surface in inspector.surfaces:
        if external_mirror_policy(surface) != "always" or not surface.human_url:
            continue
        if surface.surface_id in seen:
            continue
        seen.add(surface.surface_id)
        canonical = {
            "data_as_of": identity.get("inspection_generated_at"),
            "projection_snapshot_id": identity.get("projection_snapshot_id"),
            "brain_snapshot_id": identity.get("brain_snapshot_id"),
            "market_generation": identity.get("asset_market_generation"),
        }
        relevant = {
            "surface_id": surface.surface_id, "route": surface.route,
            "semantic_url": surface.semantic_url, "version": VERSION,
            "projection_snapshot_id": identity.get("projection_snapshot_id"),
            "brain_snapshot_id": identity.get("brain_snapshot_id"),
            "market_generation": identity.get("asset_market_generation"),
        }
        for viewport in LIVE_VIEWPORTS:
            requests.append(CaptureRequest(
                surface_id=surface.surface_id, title=surface.title,
                human_url=surface.human_url, semantic_url=surface.semantic_url,
                viewport=viewport,
                fingerprint=_digest({**relevant, "viewport": viewport}),
                canonical=canonical,
            ))
    return tuple(requests)
