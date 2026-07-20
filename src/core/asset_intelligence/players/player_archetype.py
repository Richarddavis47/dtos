"""Evidence-limited player archetypes."""
from __future__ import annotations

from src.core.asset_intelligence.models import PlayerProfile, RiskReport


def classify_archetypes(profile: PlayerProfile, risk: RiskReport, dynasty_score: int, redraft_score: int) -> tuple[str, ...]:
    labels: list[str] = []
    if profile.age is not None and profile.age <= 24:
        labels.append("Developmental Prospect")
    if profile.age is not None and profile.age >= 28 and profile.nfl_team != "Free Agent":
        labels.append("Veteran Producer Profile")
    if redraft_score >= 58 and dynasty_score < redraft_score:
        labels.append("Win Now Asset")
    if risk.level == "High":
        labels.append("Boom/Bust Risk Profile")
    return tuple(labels or ("Unclassified Asset",))
