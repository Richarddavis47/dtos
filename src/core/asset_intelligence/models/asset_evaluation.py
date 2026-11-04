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
    canonical_production: dict[str, Any] | None = None
    canonical_projection: dict[str, Any] | None = None


@dataclass(frozen=True)
class AssetEvaluation:
    name: str
    score: int | None
    confidence: int
    summary: str
    evidence: tuple[Evidence, ...]
    limitations: tuple[str, ...] = ()
    scale_maximum: int = 100

    def __post_init__(self) -> None:
        if self.scale_maximum not in (100, 1000):
            raise ValueError("Asset evaluation requires an explicit supported value scale.")
        if self.score is not None:
            object.__setattr__(self, "score", max(0, min(self.scale_maximum, int(self.score))))
        object.__setattr__(self, "confidence", max(0, min(100, int(self.confidence))))


@dataclass(frozen=True)
class CoreValues:
    dynasty: AssetEvaluation
    redraft: AssetEvaluation
    market: AssetEvaluation
    team_fit: AssetEvaluation
