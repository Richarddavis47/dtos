"""Shared competitive-window contracts consumed by every intelligence module."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

COMPETITIVE_WINDOW_CONTRACT_VERSION = "1.0"


class CompetitiveWindowClassification(str, Enum):
    ELITE_CONTENDER = "Elite Contender"
    CONTENDER = "Contender"
    PLAYOFF_TEAM = "Playoff Team"
    RETOOLING = "Re-tooling"
    REBUILDING = "Rebuilding"
    FULL_REBUILD = "Full Rebuild"


@dataclass(frozen=True)
class CompetitiveWindowContract:
    """One explainable, versioned competitive-window result."""

    classification: CompetitiveWindowClassification
    confidence: int
    championship_score: int
    playoff_score: int
    rebuild_score: int
    reasons: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    generated_at: str = field(compare=False)
    version: str = COMPETITIVE_WINDOW_CONTRACT_VERSION

    @classmethod
    def generated(
        cls,
        classification: CompetitiveWindowClassification,
        confidence: int,
        championship_score: int,
        playoff_score: int,
        rebuild_score: int,
        reasons: tuple[str, ...],
        strengths: tuple[str, ...],
        weaknesses: tuple[str, ...],
    ) -> CompetitiveWindowContract:
        return cls(
            classification,
            confidence,
            championship_score,
            playoff_score,
            rebuild_score,
            reasons,
            strengths,
            weaknesses,
            datetime.now(timezone.utc).isoformat(),
        )
