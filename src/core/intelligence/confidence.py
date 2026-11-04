"""One explainable confidence model shared by unified recommendations."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.intelligence.evidence import UnifiedEvidence


@dataclass(frozen=True)
class UnifiedConfidence:
    score: int
    level: str
    data_completeness: int
    evidence_agreement: int
    market_certainty: int
    sample_size: int
    missing_information: tuple[str, ...]


def calculate_confidence(evidence: tuple[UnifiedEvidence, ...], *, providers: int, expected_providers: int = 4, market_available: bool = False, sample_size: int = 0, missing: tuple[str, ...] = ()) -> UnifiedConfidence:
    completeness = round(min(providers / max(expected_providers, 1), 1) * 100)
    directional = [item.supports for item in evidence if item.impact]
    agreement = round(max(directional.count(True), directional.count(False)) / len(directional) * 100) if directional else 50
    market = 75 if market_available else 40
    sample = min(100, 30 + sample_size * 7)
    penalty = min(25, len(missing) * 5)
    score = max(0, min(100, round(completeness * .30 + agreement * .30 + market * .15 + sample * .25 - penalty)))
    level = "High" if score >= 75 else "Medium" if score >= 50 else "Low"
    return UnifiedConfidence(score, level, completeness, agreement, market, sample, missing)
