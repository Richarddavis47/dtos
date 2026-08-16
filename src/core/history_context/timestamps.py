"""Canonical provider-event timestamp normalization."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_iso(value: Any) -> str | None:
    """Normalize a provider epoch/ISO timestamp without inventing missing time."""
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().replace(".", "", 1).isdigit():
            numeric = float(value)
            # Sleeper transaction timestamps are milliseconds; tolerate seconds
            # for schema-compatible historical fixtures and provider corrections.
            seconds = numeric / 1000 if abs(numeric) >= 100_000_000_000 else numeric
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        else:
            text = str(value).strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return None
            parsed = parsed.astimezone(timezone.utc)
    except (OverflowError, OSError, TypeError, ValueError):
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def canonical_utc_timestamp(value: Any) -> str | None:
    """Normalize provider event time without inventing an observation time."""
    return _utc_iso(value)


def canonical_transaction_timestamp(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Return occurrence time and bounded provenance from Sleeper evidence.

    ``created`` is Sleeper's transaction occurrence timestamp. ``status_updated``
    is a legitimate fallback for older completed records lacking ``created``.
    Cache/import/retrieval time is deliberately never considered.
    """
    for field in ("created", "status_updated"):
        raw = payload.get(field)
        normalized = _utc_iso(raw)
        if normalized is not None:
            return normalized, {
                "provider": "Sleeper", "field": field,
                "raw_value": raw, "normalized_utc": normalized,
            }
    return None, {
        "provider": "Sleeper", "field": None,
        "raw_value": None, "normalized_utc": None,
        "reason": "provider_timestamp_unavailable_or_invalid",
    }
