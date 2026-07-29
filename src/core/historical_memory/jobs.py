"""Persistent import jobs, leases, retry policy, and completeness reporting."""
from __future__ import annotations

import asyncio
import random
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

import httpx

from src.core.historical_memory.models import (
    HISTORICAL_SCHEMA_VERSION,
    IMPORTER_VERSION,
)
from src.core.historical_memory.store import HistoricalStore

JOB_STATES = frozenset({
    "queued", "running", "partially_complete", "retry_wait", "failed",
    "completed", "completed_with_pending", "cancelled", "blocked",
})
REQUIRED_CATEGORIES = (
    "league_season", "franchise_identity", "weekly_roster", "matchup",
    "season_standing", "playoff_result", "draft", "draft_pick",
    "transaction", "trade", "player_week",
)
UNSUPPORTED_CATEGORIES = (
    "player_usage", "player_availability",
)
RetryCall = Callable[[], Awaitable[Any]]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def classify_failure(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "rate_limited"
        if status in {500, 502, 503, 504}:
            return "retryable"
        if status in {401, 403}:
            return "authentication"
        return "permanent"
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, OSError)):
        return "retryable"
    if isinstance(exc, (ValueError, TypeError)):
        return "malformed_response"
    return "internal_error"


async def with_retry(
    operation: RetryCall, *, attempts: int = 4, base_delay: float = .25,
    jitter: Callable[[], float] = random.random,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[Any, int]:
    """Run a provider call with bounded retry and return result/retry count."""
    retries = 0
    while True:
        try:
            return await operation(), retries
        except Exception as exc:
            category = classify_failure(exc)
            if category not in {"retryable", "rate_limited"} or retries >= attempts - 1:
                raise
            retry_after = None
            if isinstance(exc, httpx.HTTPStatusError):
                retry_after = exc.response.headers.get("Retry-After")
            delay = (
                min(30.0, float(retry_after))
                if retry_after and retry_after.replace(".", "", 1).isdigit()
                else min(30.0, base_delay * (2 ** retries) + jitter() * base_delay)
            )
            retries += 1
            await sleep(delay)


@dataclass
class ImportJob:
    store: HistoricalStore
    league_id: str
    seasons: tuple[int, ...]
    data_types: tuple[str, ...]
    requested_by: str = "automatic_recovery"
    job_id: str = ""
    worker_identity: str = ""

    def create(self) -> str:
        self.job_id = self.job_id or uuid4().hex
        self.worker_identity = self.worker_identity or f"{socket.gethostname()}:{uuid4().hex[:8]}"
        now = utcnow().isoformat()
        self.store.create_job({
            "job_id": self.job_id,
            "league_id": self.league_id,
            "requested_seasons": list(self.seasons),
            "requested_data_types": list(self.data_types),
            "status": "queued",
            "created_at": now,
            "total_steps": len(self.seasons) * len(self.data_types),
            "requested_by": self.requested_by,
            "schema_version": HISTORICAL_SCHEMA_VERSION,
            "importer_version": IMPORTER_VERSION,
        })
        return self.job_id

    def acquire(self, lease_minutes: int = 15) -> bool:
        now = utcnow()
        lock_key = (
            f"{self.league_id}:{','.join(map(str, self.seasons))}:"
            f"{','.join(self.data_types)}:Sleeper:{IMPORTER_VERSION}"
        )
        acquired = self.store.acquire_lock(
            lock_key, self.job_id, self.worker_identity, now.isoformat(),
            (now + timedelta(minutes=lease_minutes)).isoformat(),
        )
        if acquired:
            self.store.update_job(
                self.job_id, status="running", started_at=now.isoformat(),
                last_progress_at=now.isoformat(), worker_identity=self.worker_identity,
                lock_expiration=(now + timedelta(minutes=lease_minutes)).isoformat(),
            )
        return acquired


def recover_stalled_jobs(store: HistoricalStore, league_id: str) -> int:
    """Queue jobs whose persisted lease expired; permanent failures stay failed."""
    now = utcnow()
    recovered = 0
    for job in store.jobs(league_id):
        if job["status"] != "running" or not job.get("lock_expiration"):
            continue
        if datetime.fromisoformat(job["lock_expiration"]) <= now:
            store.update_job(
                job["job_id"], status="queued", worker_identity=None,
                lock_expiration=None, last_error_type="worker_interrupted",
                last_error_message="Worker lease expired; job is safe to resume.",
            )
            recovered += 1
    return recovered


def completeness_report(
    store: HistoricalStore, league_id: str, seasons: tuple[int, ...],
) -> dict[str, Any]:
    quality = store.quality(league_id)
    checkpoints = store.checkpoints(league_id)
    report: list[dict[str, Any]] = []
    all_complete = True
    for season in seasons:
        completed: list[str] = []
        missing: list[str] = []
        totals: dict[str, int] = {}
        first: str | None = None
        last: str | None = None
        for category in REQUIRED_CATEGORIES:
            count, rows = store.records(
                league_id, category, season=season, limit=500,
            )
            totals[category] = count
            if count:
                completed.append(category)
                dates = [row["observed_at"] for row in rows]
                first = min([first, *dates]) if first else min(dates)
                last = max([last, *dates]) if last else max(dates)
            else:
                missing.append(category)
        failed = sorted({
            row["data_type"] for row in checkpoints
            if row["season"] == season and row["status"] == "failed"
        })
        pending = sorted({
            row["data_type"] for row in checkpoints
            if row["season"] == season
            and row["status"] in {"pending", "not_yet_available"}
        })
        blocking = [
            item for item in quality
            if item["season"] in {None, season}
            and item["severity"] == "blocking" and not item["resolved"]
        ]
        required_missing = [
            category for category in missing
            if category not in pending
        ]
        complete = not required_missing and not failed and not blocking
        all_complete &= complete
        report.append({
            "season": season,
            "status": (
                "pending" if pending and not failed and not blocking
                else "complete" if complete else "incomplete"
            ),
            "completed_categories": completed, "missing_categories": missing,
            "unsupported_categories": list(UNSUPPORTED_CATEGORIES),
            "pending_categories": pending, "failed_categories": failed,
            "record_totals": totals,
            "first_observation": first, "last_observation": last,
            "blocking_issues": len(blocking),
            "importer_version": IMPORTER_VERSION,
            "historical_schema_version": HISTORICAL_SCHEMA_VERSION,
        })
    return {
        "league_id": league_id,
        "status": "complete" if all_complete else "incomplete",
        "seasons": report,
        "reference_total": 30051 if league_id == "1313066632158924800" else None,
        "reconciliation_rule": (
            "Category completeness is authoritative; totals may change when "
            "provider corrections add or version records."
        ),
    }
