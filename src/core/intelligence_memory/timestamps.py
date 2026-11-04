"""Typed checkpoint clocks; milestone labels are identities, never dates."""
from datetime import datetime

from src.core.history_context.timestamps import canonical_utc_timestamp


class CheckpointTimestampError(ValueError):
    """Unsupported observation time, safe for the producer to skip individually."""


def observation_time(value) -> datetime | None:
    normalized = canonical_utc_timestamp(value)
    return datetime.fromisoformat(normalized.replace('Z', '+00:00')) if normalized else None


def checkpoint_timestamp(value) -> str:
    parsed = observation_time(value)
    if parsed is None:
        raise CheckpointTimestampError('Checkpoint timestamp requires a supported timezone-aware observation time.')
    return parsed.isoformat()
