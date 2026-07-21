"""Trade-specific evidence helpers built on Asset Intelligence evidence."""
from __future__ import annotations

from src.core.asset_intelligence import Evidence


def trade_evidence(factor: str, value: str, impact: float, explanation: str, source: str) -> Evidence:
    return Evidence(factor, value, impact, explanation, source)
