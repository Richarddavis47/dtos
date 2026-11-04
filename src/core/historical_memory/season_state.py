"""Deterministic NFL season-state classification for provider eligibility."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class SeasonState(str, Enum):
    COMPLETED = "completed"
    ACTIVE = "active"
    PRE_REGULAR = "pre_regular"
    FUTURE = "future"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class SeasonClassification:
    season: int
    state: SeasonState
    regular_season_start: date
    regular_season_end: date
    next_eligible_at: date | None


def regular_season_start(season: int) -> date:
    """Return the NFL opener: the Thursday following Labor Day."""
    september_first = date(season, 9, 1)
    labor_day = september_first + timedelta(
        days=(7 - september_first.weekday()) % 7,
    )
    return labor_day + timedelta(days=3)


def classify_season(
    season: int, *, today: date, minimum_supported: int = 1999,
) -> SeasonClassification:
    """Classify an NFL season without relying on calendar-year comparison."""
    start = regular_season_start(season)
    end = start + timedelta(weeks=18, days=4)
    current_season = today.year if today.month >= 3 else today.year - 1
    if season < minimum_supported:
        state = SeasonState.UNSUPPORTED
    elif season > current_season:
        state = SeasonState.FUTURE
    elif season < current_season or today > end:
        state = SeasonState.COMPLETED
    elif today < start:
        state = SeasonState.PRE_REGULAR
    else:
        state = SeasonState.ACTIVE
    next_eligible = start if state in {SeasonState.PRE_REGULAR, SeasonState.FUTURE} else None
    return SeasonClassification(season, state, start, end, next_eligible)
