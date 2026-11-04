"""Decision Engine recommendation contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RecommendationPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RecommendationCategory(str, Enum):
    BUY = "Buy"
    SELL = "Sell"
    HOLD = "Hold"
    TRADE = "Trade"
    COMPETE = "Compete"
    REBUILD = "Rebuild"
    WAIVER = "Waiver"
    MONITOR = "Monitor"


@dataclass(frozen=True)
class ConfidenceScore:
    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", max(0, min(100, int(self.value))))


@dataclass(frozen=True)
class Recommendation:
    title: str
    summary: str
    priority: RecommendationPriority
    confidence: ConfidenceScore
    category: RecommendationCategory
    reasoning: str
    supporting_metrics: tuple[str, ...]
    future_explanation_hook: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        """Compatibility alias for existing presentation components."""
        return self.summary
