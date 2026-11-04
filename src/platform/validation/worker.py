"""Structured contracts for isolated HTTP validation workers."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class HttpValidationResult:
    run_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    completed: bool = False
    startup: str = "NOT_RUN"
    http_smoke: str = "NOT_RUN"
    cleanup: str = "NOT_RUN"
    process_cleanup: str = "NOT_RUN"
    pid: int | None = None
    port: int | None = None
    shutdown_method: str | None = None
    timings: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(value == "PASS" for value in (self.startup, self.http_smoke, self.cleanup, self.process_cleanup)) and not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "passed": self.passed}


REQUIRED_RESULT_FIELDS = {
    "run_id", "started_at", "completed_at", "completed", "startup", "http_smoke", "cleanup",
    "process_cleanup", "timings", "errors", "passed",
}


def validate_worker_result(payload: dict[str, Any], expected_run_id: str | None = None) -> tuple[str, ...]:
    errors = []
    missing = sorted(REQUIRED_RESULT_FIELDS - set(payload))
    if missing:
        errors.append(f"Missing result fields: {missing}")
    if payload.get("completed") is not True:
        errors.append("Worker result is incomplete.")
    if not payload.get("run_id"):
        errors.append("Worker result has no validation run ID.")
    if expected_run_id is not None and payload.get("run_id") != expected_run_id:
        errors.append(f"Worker result run ID mismatch: expected {expected_run_id}, got {payload.get('run_id')}.")
    for key in ("started_at", "completed_at"):
        try:
            datetime.fromisoformat(str(payload.get(key)).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{key} is not a valid timestamp.")
    if not isinstance(payload.get("timings"), dict):
        errors.append("timings must be an object.")
    if not isinstance(payload.get("errors"), list):
        errors.append("errors must be an array.")
    return tuple(errors)
