"""Typed contracts for Commissioner Desk context and intelligence."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class ActiveLeague:
    league_id: str
    name: str
    season: str
    is_active: bool = True


@dataclass(frozen=True)
class ActiveFrontOffice:
    roster_id: int
    owner_id: str
    owner_name: str
    team_name: str


class LeagueEventType(str, Enum):
    TRADE = "Trade"
    WAIVER = "Waiver Claim"
    ADD = "Add"
    DROP = "Drop"
    MATCHUP = "Matchup Result"
    INJURY = "Injury"
    DRAFT_PICK = "Draft Pick Movement"
    LEAGUE = "League Event"


@dataclass(frozen=True)
class LeagueEvent:
    event_type: LeagueEventType
    occurred_at: str
    occurred_ms: int
    title: str
    detail: str
    roster_ids: tuple[int, ...] = ()
    source_id: str | None = None


@dataclass(frozen=True)
class LeagueHeadline:
    title: str
    detail: str
    evidence: str
    category: str


@dataclass(frozen=True)
class DailyBriefing:
    since_label: str
    events: tuple[LeagueEvent, ...]
    counts: dict[str, int]
    unavailable: tuple[str, ...] = ()


class RecommendationPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True)
class ConfidenceScore:
    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", max(0, min(100, int(self.value))))


@dataclass(frozen=True)
class Recommendation:
    title: str
    priority: RecommendationPriority
    confidence: ConfidenceScore
    action: str
    reasoning: str
    supporting_metrics: tuple[str, ...]
    future_explanation_hook: dict[str, Any] = field(default_factory=dict)
