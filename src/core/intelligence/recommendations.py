"""Unified recommendation and conflict-resolution contracts."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.intelligence.confidence import UnifiedConfidence
from src.core.intelligence.evidence import UnifiedEvidence


@dataclass(frozen=True)
class UnifiedRecommendation:
    title: str
    recommendation: str
    priority: str
    confidence: UnifiedConfidence
    current_outlook: str
    future_outlook: str
    why: tuple[str, ...]
    why_not: tuple[str, ...]
    assumptions: tuple[str, ...]
    change_conditions: tuple[str, ...]
    evidence: tuple[UnifiedEvidence, ...]
    sources: tuple[str, ...]


def resolve_recommendation(*, decision, trade, front_office, market, evidence: tuple[UnifiedEvidence, ...], confidence: UnifiedConfidence) -> UnifiedRecommendation:
    trade_rec = trade.recommendation if trade is not None else None
    low_acceptance = trade_rec is not None and trade_rec.acceptance_likelihood is not None and trade_rec.acceptance_likelihood < 45
    negative_value = trade_rec is not None and trade_rec.expected_value < 0
    if trade_rec is None:
        action, title, priority = "Monitor the market.", "Preserve optionality", "Low"
    elif low_acceptance or negative_value:
        action, title, priority = "Wait and monitor an alternative structure.", "Patience is the best current action", "Medium"
    else:
        action, title, priority = trade_rec.summary, trade_rec.title, trade_rec.priority.value
    supporting = tuple(item.explanation for item in evidence if item.supports)[:5] or ("No supporting factor crossed the unified evidence boundary.",)
    risks = tuple(item.explanation for item in evidence if not item.supports)[:5] or ("No measured counterargument crossed the unified evidence boundary.",)
    return UnifiedRecommendation(
        title, action, priority, confidence,
        f"{decision.current_outlook.grade} ({decision.current_outlook.score}/100): {decision.current_outlook.summary}",
        f"{decision.future_outlook.grade} ({decision.future_outlook.score}/100): {decision.future_outlook.summary}",
        supporting, risks,
        ("Sleeper cached data reflects the latest successful synchronization.", "Market consensus is used only where traceable provider data exists."),
        ("A new successful synchronization changes the evidence snapshot.", "Material roster, injury, market, or trade-history changes require reevaluation.", "A meaningful market value or trend change may open or close a timing window."),
        evidence, ("Decision Engine", "Asset Intelligence", "Trade Intelligence", "Front Office Intelligence", "Market Intelligence"),
    )
