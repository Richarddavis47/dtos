"""Explainable evaluation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvaluationHorizon(str, Enum):
    CURRENT = "Current Championship Outlook"
    FUTURE = "Future Outlook"
    DEPTH = "Depth Analysis"
    ASSET_HEALTH = "Asset Health"


@dataclass(frozen=True)
class EvaluationFactor:
    name: str
    value: str
    contribution: float
    explanation: str
    source: str


@dataclass(frozen=True)
class Evaluation:
    horizon: EvaluationHorizon
    score: int
    grade: str
    confidence: int
    summary: str
    factors: tuple[EvaluationFactor, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", max(0, min(100, int(self.score))))
        object.__setattr__(self, "confidence", max(0, min(100, int(self.confidence))))
