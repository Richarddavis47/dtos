"""Deterministic temporal confidence for historical intelligence evidence."""
from __future__ import annotations

from datetime import datetime


def temporal_confidence(
    observation_at: str | None,
    event_at: str,
    *,
    intervening_material_event: bool = False,
    observation_is_after_event: bool = False,
) -> tuple[int, str]:
    """Return a bounded confidence score without treating later evidence as prior knowledge."""
    if not observation_at:
        return 0, "observation_unavailable"
    observation = datetime.fromisoformat(observation_at)
    event = datetime.fromisoformat(event_at)
    seconds = int((event - observation).total_seconds())
    if observation_is_after_event or seconds < 0:
        return 0, "later_snapshot_not_execution_time_evidence"
    days = seconds / 86_400
    if days <= 1:
        score, reason = 95, "same_day_or_24h"
    elif days <= 3:
        score, reason = 82, "one_to_three_days"
    elif days <= 7:
        score, reason = 65, "three_to_seven_days"
    else:
        score, reason = 35, "older_than_seven_days"
    if intervening_material_event:
        return min(score, 40), f"{reason}_material_event_downgrade"
    return score, reason
