"""Evidence-limited player archetypes."""
from __future__ import annotations

from src.core.asset_intelligence.models import PlayerProfile, RiskReport


def classify_asset_tier(dynasty_score: int, redraft_score: int) -> str:
    """Return a stable quality tier from shared present and future values."""
    score = round(dynasty_score * .65 + redraft_score * .35)
    for threshold, label in ((88, "Elite Franchise Player"), (80, "Cornerstone"), (72, "Core Starter"), (64, "Quality Starter"), (54, "Flex Asset"), (44, "Depth"), (34, "Developmental")):
        if score >= threshold:
            return label
    return "Replacement Level"


def classify_archetypes(profile: PlayerProfile, risk: RiskReport, dynasty_score: int, redraft_score: int) -> tuple[str, ...]:
    labels: list[str] = [classify_asset_tier(dynasty_score, redraft_score)]
    if profile.age is not None and profile.age <= 24:
        labels.append("Developmental Prospect")
    if profile.age is not None and profile.age >= 28 and profile.nfl_team != "Free Agent":
        labels.append("Veteran Producer Profile")
    if redraft_score >= 58 and dynasty_score < redraft_score:
        labels.append("Win Now Asset")
    if risk.level == "High":
        labels.append("Boom/Bust Risk Profile")
    return tuple(labels or ("Unclassified Asset",))
