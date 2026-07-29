"""The single authoritative competitive-window computation."""
from __future__ import annotations

from src.core.competitive_window.models import (
    CompetitiveWindowClassification,
    CompetitiveWindowContract,
)


def build_competitive_window(
    *,
    current_strength: int,
    overall_strength: int,
    future_strength: int,
    depth: int,
    youth: int,
    draft_capital: int,
    risk: int,
    confidence: int,
    elite_assets: int = 0,
    starter_strength: int | None = None,
) -> CompetitiveWindowContract:
    """Classify calibrated league-relative inputs exactly once."""
    starter = current_strength if starter_strength is None else starter_strength
    championship = round(
        current_strength * .45 + overall_strength * .25 + starter * .20 + depth * .10
    )
    playoff = round(current_strength * .60 + overall_strength * .25 + depth * .15)
    rebuild = round(
        (100 - current_strength) * .35
        + future_strength * .25
        + youth * .15
        + draft_capital * .20
        + (100 - risk) * .05
    )
    if current_strength >= 85 and overall_strength >= 80:
        classification = CompetitiveWindowClassification.ELITE_CONTENDER
    elif current_strength >= 70 and overall_strength >= 65:
        classification = CompetitiveWindowClassification.CONTENDER
    elif current_strength >= 52:
        classification = CompetitiveWindowClassification.PLAYOFF_TEAM
    elif current_strength < 25 and future_strength < 35:
        classification = CompetitiveWindowClassification.FULL_REBUILD
    elif current_strength < 40:
        classification = CompetitiveWindowClassification.REBUILDING
    else:
        classification = CompetitiveWindowClassification.RETOOLING
    metrics = {
        "starter strength": starter,
        "depth": depth,
        "future draft capital": draft_capital,
        "youth": youth,
        "age-curve/future outlook": future_strength,
    }
    strengths = tuple(
        f"{name.title()} is league-relative {value}/100."
        for name, value in metrics.items()
        if value >= 65
    ) or ("No input is above the league-relative strength threshold.",)
    weaknesses = tuple(
        f"{name.title()} is league-relative {value}/100."
        for name, value in metrics.items()
        if value < 40
    ) or ("No input is below the league-relative weakness threshold.",)
    reasons = (
        f"Calibrated current strength is {current_strength}/100 and overall strength is {overall_strength}/100.",
        f"Future strength is {future_strength}/100, draft capital is {draft_capital}/100, and risk is {risk}/100.",
        f"Elite/cornerstone asset count is {elite_assets}; championship, playoff, and rebuild scores are {championship}, {playoff}, and {rebuild}.",
    )
    return CompetitiveWindowContract.generated(
        classification,
        max(0, min(100, confidence)),
        max(0, min(100, championship)),
        max(0, min(100, playoff)),
        max(0, min(100, rebuild)),
        reasons,
        strengths,
        weaknesses,
    )
