"""Shared contextual asset-evaluation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.asset_intelligence.models.evidence import Evidence


@dataclass(frozen=True)
class AssetContext:
    league_id: str
    active_front_office_id: int
    league_settings: dict[str, Any]
    team_window: str = "Transition Window"
    team_strategy: str = "Unspecified"
    team_needs: tuple[str, ...] = ()
    position_depth: dict[str, int] | None = None
    league_position_counts: dict[str, int] | None = None


@dataclass(frozen=True)
class AssetEvaluation:
    name: str
    score: int
    confidence: int
    summary: str
    evidence: tuple[Evidence, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", max(0, min(100, int(self.score))))
        object.__setattr__(self, "confidence", max(0, min(100, int(self.confidence))))


@dataclass(frozen=True)
class CoreValues:
    dynasty: AssetEvaluation
    redraft: AssetEvaluation
    market: AssetEvaluation
    team_fit: AssetEvaluation
