"""Market source clocks: retrieval is knowledge, never source freshness."""
from __future__ import annotations

from typing import Any


def market_times(row: dict[str, Any], observed_at: str | None = None) -> dict[str, Any]:
    """Legacy updated_at is an observation clock; only explicit source clocks qualify.

    Do not synthesize a new timestamp when reading a cached row. Historical
    publication, when supplied, remains separate from both retrieval and effect.
    """
    return {
        'retrieved_at': row.get('retrieved_at') or row.get('updated_at') or observed_at,
        'source_updated_at': row.get('source_updated_at'),
        'published_at': row.get('published_at'),
    }
