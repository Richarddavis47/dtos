"""Complete Decision Engine output contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.core.decision_engine.models.evaluation import Evaluation
from src.core.decision_engine.models.recommendation import Recommendation
from src.core.decision_engine.models.team_profile import TeamProfile


class TeamWindow(str, Enum):
    CHAMPIONSHIP = "Championship Window"
    PLAYOFF = "Playoff Window"
    TRANSITION = "Transition Window"
    REBUILD = "Rebuild Window"
    ASCENSION = "Ascension Window"


@dataclass(frozen=True)
class DecisionContext:
    active_front_office_id: int
    league_id: str
    league_settings: dict[str, Any]
    team_strategy: str = "Unspecified"
    market_conditions: dict[str, Any] | None = None


@dataclass(frozen=True)
class TeamDecision:
    profile: TeamProfile
    current_outlook: Evaluation
    future_outlook: Evaluation
    depth: Evaluation
    asset_health: Evaluation
    position_evaluations: dict[str, Evaluation]
    window: TeamWindow
    window_explanation: str
    recommendations: tuple[Recommendation, ...]
