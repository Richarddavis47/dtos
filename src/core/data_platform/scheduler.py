"""Refresh planning independent from the application event loop."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.core.data_platform.models import ProviderMetadata


@dataclass(frozen=True)
class RefreshSchedule:
    provider: str
    due: bool
    next_refresh: str
    interval_seconds: int


class RefreshScheduler:
    def schedule(self, metadata: ProviderMetadata, last_refresh: str | None, *, in_season: bool, now: datetime | None = None) -> RefreshSchedule:
        now = now or datetime.now(timezone.utc)
        interval = metadata.refresh_seconds_in_season if in_season else metadata.refresh_seconds_offseason
        last = datetime.fromisoformat(last_refresh.replace("Z", "+00:00")) if last_refresh else None
        due = metadata.enabled and metadata.supports_scheduled_refresh and (last is None or last + timedelta(seconds=interval) <= now)
        next_refresh = (last + timedelta(seconds=interval) if last else now).isoformat()
        return RefreshSchedule(metadata.name, due, next_refresh, interval)
