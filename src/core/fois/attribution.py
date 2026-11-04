"""FOIS attribution: never transfer unattributed franchise evidence to a GM."""
from __future__ import annotations

from typing import Any, Mapping


def belongs_to_manager(
    record: Mapping[str, Any], owner_id: str | None,
    owner_by_season: Mapping[str, Any],
) -> bool:
    """Require an identified owner; explicit event ownership takes precedence.

    Season ownership is a season-level attribution, not proof of the precise
    time of an intra-season handover. Conflicting/unknown season owners must be
    represented as unavailable by the canonical adapter.
    """
    if not owner_id:
        return False
    observed = record.get("owner_id")
    if observed is None:
        observed = owner_by_season.get(str(record.get("season")))
    return observed is not None and str(observed) == str(owner_id)
