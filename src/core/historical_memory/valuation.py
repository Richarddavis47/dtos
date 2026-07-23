"""Confidence-capped historical contribution to the existing valuation model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HistoricalValuationContribution:
    adjusted_value: int
    weight: float
    confidence: int
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]


def apply_historical_evidence(
    base_value: int, position: str, evidence: dict[str, Any] | None,
) -> HistoricalValuationContribution:
    if not evidence or int(evidence.get("games_played") or 0) < 6:
        return HistoricalValuationContribution(
            base_value, 0.0, 20,
            ("Historical evidence did not change the intrinsic value.",),
            ("At least six observed games are required before history contributes.",),
        )
    games = int(evidence["games_played"])
    ppg = evidence.get("points_per_game")
    if ppg is None:
        return HistoricalValuationContribution(
            base_value, 0.0, 20, ("Historical points per game are unavailable.",),
            ("Missing production is not treated as zero.",),
        )
    baseline = {"QB": 18.0, "RB": 10.0, "WR": 11.0, "TE": 8.5}.get(position, 10.0)
    production_delta = max(-20.0, min(20.0, (float(ppg) - baseline) * 2))
    weight = min(.10, games / 160)
    adjusted = round(base_value + production_delta * 10 * weight)
    confidence = min(80, 35 + games * 2)
    return HistoricalValuationContribution(
        max(0, min(1000, adjusted)), weight, confidence,
        (
            f"{games} observed historical games contribute {weight:.1%}.",
            f"{float(ppg):.2f} PPG is compared with a transparent {position} reference of {baseline:.1f}.",
        ),
        ("Historical evidence is capped at 10% and cannot dominate Asset Intelligence.",),
    )
