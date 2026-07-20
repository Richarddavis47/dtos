"""Reusable evidence and confidence calculations."""
from __future__ import annotations

from src.core.asset_intelligence.models.evidence import Evidence


class EvidenceEngine:
    def confidence(self, evidence: tuple[Evidence, ...], base: int = 45) -> int:
        available = sum(item.available for item in evidence)
        return max(0, min(100, base + available * 8))

    def summarize(self, evidence: tuple[Evidence, ...], limit: int = 3) -> str:
        observable = sorted(
            (item for item in evidence if item.available),
            key=lambda item: (-abs(item.impact), item.factor),
        )
        if not observable:
            return "Insufficient observable evidence; a neutral evaluation is retained."
        return " ".join(item.explanation for item in observable[:limit])


evidence_engine = EvidenceEngine()
