"""Deterministic conversion of cached news facts into structured intelligence."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsIntelligence:
    headline: str
    category: str
    severity: str
    expected_availability: str
    projection_impact: int
    risk_adjustment: int
    confidence: int
    reasoning: tuple[str, ...]


def interpret_news(headline: str, *, source_confidence: int, verified: bool) -> NewsIntelligence:
    normalized = headline.casefold()
    if any(token in normalized for token in ("injured reserve", "out for season", "torn")):
        category, severity, availability, impact, risk = "Injury", "High", "Extended absence expected", -20, 25
    elif any(token in normalized for token in ("questionable", "limited", "day-to-day")):
        category, severity, availability, impact, risk = "Injury", "Medium", "Uncertain", -7, 12
    elif any(token in normalized for token in ("starter", "promoted", "depth chart")):
        category, severity, availability, impact, risk = "Role Change", "Medium", "Available", 8, -5
    else:
        category, severity, availability, impact, risk = "League Event", "Low", "Unknown", 0, 0
    confidence = max(0, min(100, source_confidence - (0 if verified else 25)))
    reasoning = (f"Classification uses observable headline terms from a source with {source_confidence}% confidence.", "No medical timeline or projection change is fabricated beyond the supplied facts.")
    return NewsIntelligence(headline, category, severity, availability, impact, risk, confidence, reasoning)
